#!/usr/bin/env python3
"""music-sync: keep the Navidrome library in step with the playlist CSVs.

Every SYNC_INTERVAL_HOURS:
  1. Read the library from Navidrome (Subsonic API).
  2. List the playlist songs Navidrome does not have ("missing"), and up to
     UPGRADE_BATCH songs it has only as lossy files ("upgrades").
  3. Sockseek, FLAC only: missing songs into /music, upgrades into a staging
     folder.
  4. Sockseek, FLAC or >= LOSSY_MIN_BITRATE kbps: songs still missing.
  5. Each FLAC upgrade whose length matches gets the old file's tags and is
     saved next to it with a .flac extension; the old file moves to /retired.
     Same tags + same path means Navidrome keeps plays, ratings and playlists.
  6. Ask Navidrome to scan, wait, rebuild the playlists.
  7. Report to Telegram.

SYNC_DRY_RUN=true (the default) does steps 1-2 and reports what it would do.
Run once and exit: music_sync.py --once
"""
import csv
import datetime as dt
import fcntl
import html
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

import navidrome_playlists as matcher

CONFIG = Path(os.environ.get('MUSIC_SYNC_CONFIG', '/config'))
MUSIC = Path(os.environ.get('MUSIC_SYNC_MUSIC', '/music'))
RETIRED = Path(os.environ.get('MUSIC_SYNC_RETIRED', '/retired'))
# Inside /music so moves are renames on one filesystem. Navidrome and beets
# ignore folders whose name starts with a dot.
STAGING = MUSIC / '.music-sync-staging'
SOCKSEEK = os.environ.get('SOCKSEEK_BIN', 'sockseek')
CLIENT = 'music-sync'  # Navidrome player name; turn on "Report Real Path" for it
LOSSLESS = {'flac', 'wav', 'alac', 'aiff', 'aif', 'ape', 'wv'}
LOSSY_FORMATS = 'flac,mp3,m4a,ogg,opus'
NAME_FORMAT = '{albumartist(/)album(/)title|(missing-tags/)slsk-foldername(/)slsk-filename}'
DONE, ALREADY_EXISTS = 1, 3  # Sockseek index states

_child = None
_stop = False


class Stopped(Exception):
    pass


def setting(name, default=None, cast=str):
    value = os.environ.get(name, '')
    if value == '':
        if default is None:
            raise SystemExit(f'{name} is not set')
        return default
    if cast is bool:
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return cast(value)


class Settings:
    def __init__(self):
        self.nd_url = setting('NAVIDROME_URL')
        self.nd_user = setting('NAVIDROME_USER')
        self.nd_password = setting('NAVIDROME_PASSWORD')
        self.slsk_user = setting('SLSK_USERNAME')
        self.slsk_password = setting('SLSK_PASSWORD')
        self.tg_token = setting('TELEGRAM_BOT_TOKEN', '')
        self.tg_chat = setting('TELEGRAM_CHAT_ID', '')
        self.interval_h = setting('SYNC_INTERVAL_HOURS', 6.0, float)
        self.dry_run = setting('SYNC_DRY_RUN', True, bool)
        self.upgrade_batch = setting('UPGRADE_BATCH', 50, int)
        self.upgrade_retry_days = setting('UPGRADE_RETRY_DAYS', 7, int)
        self.lossy_min_kbps = setting('LOSSY_MIN_BITRATE', 320, int)
        self.length_tol = setting('LENGTH_TOLERANCE', 3, int)
        self.sockseek_timeout_min = setting('SOCKSEEK_TIMEOUT_MINUTES', 150.0, float)
        self.concurrent_jobs = setting('SOCKSEEK_CONCURRENT_JOBS', 5, int)
        self.min_free_gb = setting('MIN_FREE_GB', 10, int)
        self.daily_summary_hour = setting('DAILY_SUMMARY_HOUR', 9, int)


def log(msg):
    print(f'{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}', flush=True)


# --- state -------------------------------------------------------------------

def load_state():
    try:
        return json.loads((CONFIG / 'state.json').read_text())
    except (OSError, ValueError):
        return {'upgrade_attempts': {}, 'last_daily_summary': '', 'since_summary': {}}


def save_state(state):
    tmp = CONFIG / 'state.json.tmp'
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
    os.replace(tmp, CONFIG / 'state.json')


# --- Telegram ----------------------------------------------------------------

def telegram(settings, text, quiet=False):
    if not (settings.tg_token and settings.tg_chat):
        log('Telegram not configured; report:\n' + text)
        return
    if len(text) > 4000:
        text = text[:3980] + '\n[cut]'
    data = urllib.parse.urlencode({'chat_id': settings.tg_chat, 'text': text, 'parse_mode': 'HTML',
                                   'disable_web_page_preview': 'true',
                                   'disable_notification': 'true' if quiet else 'false'}).encode()
    base = os.environ.get('TELEGRAM_API_URL', 'https://api.telegram.org')
    url = f'{base}/bot{settings.tg_token}/sendMessage'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as resp:
            resp.read()
    except Exception as e:  # a report must never stop the job
        log(f'Telegram send failed: {e}')


def esc(s):
    return html.escape(str(s), quote=False)


def song_list(rows, limit=10):
    lines = [f"- {esc(r.get('Artist') or '?')} - {esc(r['Title'])}" for r in rows[:limit]]
    if len(rows) > limit:
        lines.append(f'  and {len(rows) - limit} more')
    return lines


# --- Navidrome ---------------------------------------------------------------

def fetch_library(api):
    songs, offset = [], 0
    while True:
        body = api.call('search3', [('query', '""'), ('songCount', 500), ('songOffset', offset),
                                    ('artistCount', 0), ('albumCount', 0)])
        page = body.get('searchResult3', {}).get('song', []) or []
        songs += page
        if len(page) < 500:
            return songs
        offset += 500


def load_playlists():
    lists = {}
    for path in sorted((CONFIG / 'playlists').glob('*.csv')):
        lists[path.stem] = list(csv.DictReader(path.open(encoding='utf-8')))
    return lists


def row_key(row):
    return (matcher.base_title(row['Title']), matcher.norm(row.get('Artist', '')))


def check_playlists(api, playlists):
    """Returns (missing rows, ids of matched songs, {playlist: [song ids]})."""
    missing, matched_ids, per_list = {}, set(), {}
    for name, rows in playlists.items():
        ids = []
        for row in rows:
            song, _ = matcher.find(api, row, 0.8)
            if song:
                matched_ids.add(song['id'])
                if song['id'] not in ids:
                    ids.append(song['id'])
            else:
                missing.setdefault(row_key(row), row)
        per_list[name] = ids
    return list(missing.values()), matched_ids, per_list


def write_playlists(api, user, per_list):
    existing = {pl['name']: pl for pl in api.playlists() if pl.get('owner') == user}
    for name, ids in per_list.items():
        if not ids:
            continue
        if name in existing:
            api.call('createPlaylist', [('playlistId', existing[name]['id'])] + [('songId', i) for i in ids])
        else:
            api.call('createPlaylist', [('name', name)] + [('songId', i) for i in ids])


def scan_and_wait(api, timeout_s=1800):
    api.call('startScan')
    deadline = time.time() + timeout_s
    time.sleep(5)
    while time.time() < deadline:
        status = api.call('getScanStatus').get('scanStatus', {})
        if not status.get('scanning'):
            return True
        time.sleep(10)
    return False


# --- Sockseek ----------------------------------------------------------------

def write_csv(path, rows, with_length=False):
    fields = ['Artist', 'Title', 'Album'] + (['Length'] if with_length else [])
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def read_index(path):
    """{(base title, artist): (state, absolute file path)} from a Sockseek index."""
    out = {}
    if not path.exists():
        return out
    with path.open(encoding='utf-8', newline='') as f:
        for rec in csv.DictReader(f):
            if not rec.get('title'):
                continue
            fp = rec.get('filepath') or ''
            if fp.startswith('./'):
                fp = str(path.parent / fp[2:])
            try:
                state = int(rec.get('state') or 0)
            except ValueError:
                state = 0
            out[(matcher.base_title(rec['title']), matcher.norm(rec.get('artist', '')))] = (state, fp)
    return out


def run_sockseek(settings, csv_path, out_dir, index_path, extra):
    global _child
    if _stop:
        raise Stopped()
    conf = Path('/tmp/sockseek.conf')
    conf.write_text(f'username = {settings.slsk_user}\npassword = {settings.slsk_password}\n')
    conf.chmod(0o600)
    cmd = [SOCKSEEK, str(csv_path), '-c', str(conf), '-o', str(out_dir), '--index-path', str(index_path),
           '--name-format', NAME_FORMAT, '--pref-format', 'flac', '--concurrent-jobs',
           str(settings.concurrent_jobs), '--no-progress', '--log-file', str(CONFIG / 'sockseek.log')] + extra
    log('Running: ' + ' '.join(c for c in cmd if c != str(conf)))
    _child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    timed_out = threading.Event()

    def on_timeout(proc=_child):
        timed_out.set()
        log('Sockseek ran past SOCKSEEK_TIMEOUT_MINUTES; stopping it')
        proc.terminate()

    timer = threading.Timer(settings.sockseek_timeout_min * 60, on_timeout)
    timer.daemon = True
    timer.start()
    try:
        for line in _child.stdout:
            print('  sockseek: ' + line.rstrip(), flush=True)
        try:
            code = _child.wait(timeout=120)
        except subprocess.TimeoutExpired:
            _child.kill()
            code = _child.wait()
    finally:
        timer.cancel()
        _child = None
    if _stop:
        raise Stopped()
    return code, timed_out.is_set()


# --- upgrades ----------------------------------------------------------------

def audio_length(path):
    import mutagen
    f = mutagen.File(path)
    return f.info.length if f is not None and f.info else None


def copy_tags(src, dest):
    """Copy text tags and the front cover from src (mp3/m4a/ogg/opus) to dest FLAC."""
    import mutagen
    from mutagen.flac import FLAC, Picture
    old = mutagen.File(src, easy=True)
    new = FLAC(dest)
    new.delete()
    new.clear_pictures()
    if old is not None and old.tags:
        for key in old.tags.keys():
            values = old.tags[key]
            values = [str(v) for v in (values if isinstance(values, list) else [values])]
            if values:
                new[key] = values
    raw = mutagen.File(src)
    data, mime = None, 'image/jpeg'
    if raw is not None and raw.tags is not None:
        apic = [v for k, v in raw.tags.items() if str(k).startswith('APIC')]
        if apic:
            data, mime = apic[0].data, apic[0].mime or mime
        elif 'covr' in raw.tags and raw.tags['covr']:
            cover = raw.tags['covr'][0]
            data = bytes(cover)
            mime = 'image/png' if getattr(cover, 'imageformat', None) == 14 else 'image/jpeg'
        elif 'metadata_block_picture' in raw.tags:
            import base64
            pic = Picture(base64.b64decode(raw.tags['metadata_block_picture'][0]))
            data, mime = pic.data, pic.mime
    if data:
        pic = Picture()
        pic.type, pic.mime, pic.data = 3, mime, data
        new.add_picture(pic)
    new.save()


def apply_upgrade(settings, song, flac_path):
    """Put flac_path in place of the lossy song. Returns (ok, reason)."""
    old = Path(song['path'])
    flac = Path(flac_path)
    if not flac.is_file() or flac.suffix.lower() != '.flac':
        return False, 'download is not a FLAC file'
    if not old.is_file():
        return False, 'old file no longer exists'
    length = audio_length(flac)
    want = float(song.get('duration') or 0)
    if length is None:
        return False, 'cannot read the FLAC'
    if want and abs(length - want) > settings.length_tol:
        return False, f'length differs by {abs(length - want):.0f} s'
    target = old.with_suffix('.flac')
    if target.exists():
        return False, f'{target.name} already exists'
    copy_tags(old, flac)
    retired = RETIRED / old.relative_to(MUSIC)
    retired.parent.mkdir(parents=True, exist_ok=True)
    os.replace(flac, target)
    try:
        shutil.move(str(old), str(retired))
    except OSError:
        os.replace(target, flac)  # put things back as they were
        raise
    return True, ''


# --- one run -----------------------------------------------------------------

def run_once(settings, state):
    started = dt.datetime.now()
    api = matcher.Subsonic(settings.nd_url, settings.nd_user, settings.nd_password, client=CLIENT)
    report = {'new_flac': [], 'new_lossy': [], 'upgraded': [], 'review': [], 'warnings': []}

    step = 'reading the library from Navidrome'
    try:
        api.call('ping')
        library = fetch_library(api)
        playlists = load_playlists()
        if not playlists:
            report['warnings'].append(f'No playlist CSVs in {CONFIG / "playlists"}')
        step = 'checking the playlists'
        missing, in_playlists, _ = check_playlists(api, playlists)

        real = [s for s in library if str(s.get('path', '')).startswith(str(MUSIC) + '/')]
        lossy = [s for s in real if (s.get('suffix') or '').lower() not in LOSSLESS]
        if library and not real:
            report['warnings'].append('Navidrome is not reporting real file paths, so upgrades are off. '
                                      'In Navidrome: Settings > Players > music-sync > Report Real Path.')
        cutoff = (started - dt.timedelta(days=settings.upgrade_retry_days)).isoformat()
        attempts = state.setdefault('upgrade_attempts', {})
        due = [s for s in lossy if attempts.get(s['id'], '') < cutoff]
        due.sort(key=lambda s: (s['id'] not in in_playlists, -(s.get('playCount') or 0), s.get('title', '')))
        # Sockseek needs the length to check it found the same recording.
        due = [s for s in due if float(s.get('duration') or 0) > 0]
        upgrades = due[:settings.upgrade_batch]
        upgrade_rows = [{'Artist': s.get('artist', ''), 'Title': s.get('title', ''), 'Album': s.get('album', ''),
                         'Length': int(round(float(s['duration']))), '_song': s} for s in upgrades]

        summary = [f'Library: {len(library)} songs, {len(lossy)} lossy',
                   f'Playlist songs missing: {len(missing)}',
                   f'Upgrades this run: {len(upgrades)} of {len(lossy)} lossy']

        if settings.dry_run:
            lines = [f'<b>Music sync (dry run)</b> · {started:%d %b %H:%M}'] + summary
            lines += ['', 'Would look for:'] + song_list(missing)
            if upgrade_rows:
                lines += ['', 'Would try to upgrade:'] + song_list(upgrade_rows)
            lines += [f'Warning: {esc(w)}' for w in report['warnings']]
            lines += ['', 'Set SYNC_DRY_RUN=false in arr/.env to start downloading.']
            telegram(settings, '\n'.join(lines))
            return

        step = 'checking free disk space'
        free_gb = shutil.disk_usage(MUSIC).free / 1e9
        if free_gb < settings.min_free_gb:
            raise RuntimeError(f'only {free_gb:.0f} GB free on the music disk (MIN_FREE_GB={settings.min_free_gb})')

        work = CONFIG / 'run'
        work.mkdir(exist_ok=True)
        STAGING.mkdir(exist_ok=True)
        problems = []

        def note(name, result):
            code, timed_out = result
            if timed_out:
                problems.append(f'{name}: stopped at the {settings.sockseek_timeout_min:g}-minute limit')
            elif code not in (0, None) and not _stop:
                problems.append(f'{name}: Sockseek exited with code {code}')

        # Pass 1: FLAC for missing songs.
        idx_flac = CONFIG / 'index-missing-flac.csv'
        if missing:
            step = 'downloading missing songs in FLAC'
            write_csv(work / 'missing.csv', missing)
            before = read_index(idx_flac)
            note('FLAC pass', run_sockseek(settings, work / 'missing.csv', MUSIC, idx_flac,
                                           ['--format', 'flac', '--skip-music-dir', str(MUSIC)]))
            after = read_index(idx_flac)
            for row in missing:
                k = row_key(row)
                if after.get(k, (0,))[0] == DONE and before.get(k, (0,))[0] != DONE:
                    report['new_flac'].append(row)

        # Pass 2: FLAC or high-bitrate lossy for what is still missing.
        flac_done = read_index(idx_flac)
        still = [r for r in missing if flac_done.get(row_key(r), (0,))[0] not in (DONE, ALREADY_EXISTS)]
        idx_any = CONFIG / 'index-missing-any.csv'
        if still:
            step = 'downloading missing songs in any quality'
            write_csv(work / 'still-missing.csv', still)
            before = read_index(idx_any)
            note('Lossy pass', run_sockseek(settings, work / 'still-missing.csv', MUSIC, idx_any,
                                            ['--format', LOSSY_FORMATS, '--cond', f'br>={settings.lossy_min_kbps}',
                                             '--pref-min-bitrate', str(settings.lossy_min_kbps),
                                             '--skip-music-dir', str(MUSIC)]))
            after = read_index(idx_any)
            for row in still:
                k = row_key(row)
                if after.get(k, (0,))[0] == DONE and before.get(k, (0,))[0] != DONE:
                    (report['new_flac'] if after[k][1].lower().endswith('.flac')
                     else report['new_lossy']).append(row)

        # Pass 3: FLAC upgrades, into staging. No --skip-music-dir: the song
        # is in the library on purpose.
        if upgrade_rows:
            step = 'downloading FLAC upgrades'
            idx_up = CONFIG / 'index-upgrades.csv'
            write_csv(work / 'upgrades.csv', upgrade_rows, with_length=True)
            note('Upgrade pass', run_sockseek(settings, work / 'upgrades.csv', STAGING, idx_up,
                                              ['--format', 'flac', '--length-tol', str(settings.length_tol)]))
            got = read_index(idx_up)
            step = 'swapping in FLAC upgrades'
            for row in upgrade_rows:
                song = row['_song']
                attempts[song['id']] = started.isoformat()
                state_, fp = got.get(row_key(row), (0, ''))
                if state_ != DONE or not fp or not Path(fp).is_file():
                    continue
                try:
                    ok, reason = apply_upgrade(settings, song, fp)
                except Exception as e:
                    ok, reason = False, f'error: {e}'
                if ok:
                    report['upgraded'].append(row)
                    attempts.pop(song['id'], None)
                else:
                    report['review'].append(dict(row, Reason=reason, File=fp))
        report['warnings'] += [p + ' (details: /configs/music-sync/sockseek.log)' for p in problems]

        changed = report['new_flac'] or report['new_lossy'] or report['upgraded']
        if changed:
            step = 'scanning in Navidrome'
            if not scan_and_wait(api):
                report['warnings'].append('Navidrome scan did not finish within 30 minutes')
        step = 'rebuilding the playlists'
        if playlists:
            missing_after, _, per_list = check_playlists(api, playlists)
            write_playlists(api, settings.nd_user, per_list)
            summary[1] = f'Playlist songs missing: {len(missing_after)}'
        if changed:
            library = fetch_library(api)
            lossy_now = [s for s in library if (s.get('suffix') or '').lower() not in LOSSLESS]
            summary[0] = f'Library: {len(library)} songs, {len(lossy_now)} lossy'
            summary[2] = f'Lossy songs left to upgrade: {len(lossy_now)}'

        since = state.setdefault('since_summary', {})
        for k in ('new_flac', 'new_lossy', 'upgraded'):
            since[k] = since.get(k, 0) + len(report[k])
        since['runs'] = since.get('runs', 0) + 1

        took = (dt.datetime.now() - started).total_seconds() / 60
        if changed or report['review'] or report['warnings']:
            lines = [f'<b>Music sync</b> · {started:%d %b %H:%M} · {took:.0f} min',
                     f"New FLAC: {len(report['new_flac'])}   New {settings.lossy_min_kbps}: "
                     f"{len(report['new_lossy'])}   Upgraded: {len(report['upgraded'])}"] + summary
            for title, key in (('New FLAC', 'new_flac'), (f'New {settings.lossy_min_kbps} kbps', 'new_lossy'),
                               ('Upgraded to FLAC (old file in /data/music-retired)', 'upgraded')):
                if report[key]:
                    lines += ['', f'{title}:'] + song_list(report[key])
            if report['review']:
                lines += ['', 'Upgrade downloaded but not used (file kept in staging):']
                lines += [f"- {esc(r['Artist'])} - {esc(r['Title'])}: {esc(r['Reason'])}"
                          for r in report['review'][:10]]
            lines += [f'Warning: {esc(w)}' for w in report['warnings']]
            telegram(settings, '\n'.join(lines))

        today = started.date().isoformat()
        if started.hour >= settings.daily_summary_hour and state.get('last_daily_summary') != today:
            telegram(settings, '\n'.join([
                f'<b>Music sync daily</b> · {today}',
                f"Last 24 h: {since.get('runs', 0)} runs, {since.get('new_flac', 0)} new FLAC, "
                f"{since.get('new_lossy', 0)} new {settings.lossy_min_kbps}, {since.get('upgraded', 0)} upgraded",
            ] + summary), quiet=True)
            state['last_daily_summary'] = today
            state['since_summary'] = {}
    except Stopped:
        log(f'Stopped while {step}; files already downloaded are kept and listed in the index')
    except Exception as e:
        log(traceback.format_exc())
        telegram(settings, f'<b>Music sync failed</b> while {esc(step)}:\n<code>{esc(e)}</code>')


def stop(signum, _frame):
    global _stop
    _stop = True
    log(f'Signal {signum}: stopping after cleanup')
    if _child is not None:
        _child.terminate()


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    settings = Settings()
    CONFIG.mkdir(parents=True, exist_ok=True)
    (CONFIG / 'playlists').mkdir(exist_ok=True)
    once = '--once' in sys.argv
    while not _stop:
        # One run at a time, also across `docker exec ... --once`: two Sockseek
        # logins on one Soulseek account disconnect each other.
        with open(CONFIG / 'run.lock', 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                log('Another run is in progress; skipping this one')
            else:
                state = load_state()
                log('Run starting' + (' (dry run)' if settings.dry_run else ''))
                run_once(settings, state)
                save_state(state)
                log('Run finished')
        if once:
            break
        wake = time.time() + settings.interval_h * 3600
        while not _stop and time.time() < wake:
            time.sleep(min(30, wake - time.time()))


if __name__ == '__main__':
    main()
