"""Songs you mark in Navidrome: the "Delete" and "Wrong" playlists.

Add a song to one of these playlists, from the Navidrome web UI or any app
that edits playlists. music-sync checks them every MARKS_INTERVAL_MINUTES.

Delete  The file (and its .lrc) moves to /retired/deleted/<same path>. The
        song goes to deleted.csv, so no playlist or like downloads it again.
Wrong   The file moves to /retired/wrong/<same path>. music-sync searches
        again, without the Soulseek user who sent the wrong file, and skips
        any file of the same size (the same rip from another user). If it
        finds nothing, it tries again on each 6-hour run.

In both cases the song leaves the playlist, and its "missing" entry is
removed from Navidrome after a scan. Nothing is deleted for good: undo by
moving the file back from /data/music-retired.

This module gets the music_sync module as `ms`, to use its paths and helpers
without a circular import.
"""
import csv
import datetime as dt
import json
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

AUDIO = {'flac', 'wav', 'alac', 'aiff', 'aif', 'ape', 'wv', 'mp3', 'm4a', 'aac', 'ogg', 'opus', 'wma'}
SIDECARS = ('.lrc',)
SOURCE_FIELDS = ['path', 'user', 'remote']
# Sockseek logs every finished download at Debug level, and its log file always
# gets Debug lines:  ... download succeeded from USER\REMOTE to 'OUTPUT': SONG
SUCCEEDED = re.compile(r"download succeeded from ([^\\]+)\\(.*?) to '(.*)': ")


# --- where each file came from -------------------------------------------------

def record_sources(ms):
    """Read the new part of sockseek.log and append each download's Soulseek
    user to sources.csv. Called after every Sockseek run."""
    log_path = ms.CONFIG / 'sockseek.log'
    offset_path = ms.CONFIG / 'sources.offset'
    if not log_path.exists():
        return
    try:
        offset = int(offset_path.read_text())
    except (OSError, ValueError):
        offset = 0
    size = log_path.stat().st_size
    if size < offset:  # the log was replaced or cut
        offset = 0
    rows = []
    with log_path.open(encoding='utf-8', errors='replace') as f:
        f.seek(offset)
        for line in f:
            m = SUCCEEDED.search(line)
            if m:
                rows.append({'path': m.group(3), 'user': m.group(1), 'remote': m.group(2)})
        offset_path.write_text(str(f.tell()))
    add_sources(ms, rows)


def add_sources(ms, rows):
    if not rows:
        return
    path = ms.CONFIG / 'sources.csv'
    new = not path.exists()
    with path.open('a', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=SOURCE_FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)


def load_sources(ms):
    """{absolute file path: (user, remote file)}; later lines win."""
    path = ms.CONFIG / 'sources.csv'
    out = {}
    if path.exists():
        with path.open(encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                out[str(Path(r['path']))] = (r['user'], r['remote'])
    return out


# --- Navidrome ------------------------------------------------------------------

class NativeApi:
    """The small part of Navidrome's own REST API (not Subsonic) we need."""

    def __init__(self, url, user, password):
        self.url = url.rstrip('/')
        self.user, self.password = user, password
        self.token = None

    def _login(self):
        body = json.dumps({'username': self.user, 'password': self.password}).encode()
        req = urllib.request.Request(self.url + '/auth/login', data=body,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            self.token = json.load(resp)['token']

    def delete_missing(self, ids):
        """Remove the 'missing' entries of these songs. Navidrome deletes only
        rows that are missing AND have one of these IDs. Without IDs it would
        delete every missing entry, so an empty list is refused here."""
        ids = [i for i in ids if i]
        if not ids:
            raise ValueError('delete_missing needs at least one id')
        if self.token is None:
            self._login()
        query = urllib.parse.urlencode([('id', i) for i in ids])
        req = urllib.request.Request(f'{self.url}/api/missing?{query}', method='DELETE',
                                     headers={'X-ND-Authorization': f'Bearer {self.token}'})
        with urllib.request.urlopen(req, timeout=60):
            pass


def marked(api, name, user):
    """(playlist id, entries) of the user's playlist with this name. Creates the
    playlist, empty, if it does not exist yet, so you only have to add songs."""
    for pl in api.playlists():
        if pl.get('name') == name and pl.get('owner') == user:
            body = api.call('getPlaylist', [('id', pl['id'])])
            return pl['id'], body.get('playlist', {}).get('entry', []) or []
    api.call('createPlaylist', [('name', name)])
    return None, []


def unmark(api, playlist_id, indexes):
    if indexes:
        api.call('updatePlaylist', [('playlistId', playlist_id)] +
                 [('songIndexToRemove', i) for i in sorted(indexes)])


# --- files ------------------------------------------------------------------------

def library_path(ms, song):
    """The song's file if it is a real path inside /music (not staging), else None."""
    raw = song.get('path') or ''
    if not raw.startswith('/'):
        return None
    path = Path(raw)
    try:
        rel = path.resolve().relative_to(ms.MUSIC.resolve())
    except ValueError:
        return None
    if rel.parts and rel.parts[0] == ms.STAGING.name:
        return None
    return ms.MUSIC / rel


def move_out(ms, path, kind):
    """Move a song file, its sidecars, and an album folder left with no audio
    to /retired/<kind>/<same path>. Returns where the song file went."""
    rel = path.relative_to(ms.MUSIC)
    dest = ms.RETIRED / kind / rel
    if dest.exists():
        dest = dest.with_name(f'{dest.stem}.{dt.datetime.now():%Y%m%d%H%M%S}{dest.suffix}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    for ext in SIDECARS:
        side = path.with_suffix(ext)
        if side.exists():
            shutil.move(str(side), str(dest.with_suffix(ext)))
    folder = path.parent
    if folder != ms.MUSIC and folder.is_dir() and not any(
            p.suffix.lower().lstrip('.') in AUDIO for p in folder.rglob('*') if p.is_file()):
        for p in list(folder.iterdir()):  # covers, .nfo, .cue
            target = dest.parent / p.name
            if p.is_file() and not target.exists():
                shutil.move(str(p), str(target))
        try:
            folder.rmdir()
            if folder.parent != ms.MUSIC:
                folder.parent.rmdir()  # the artist folder, only if now empty
        except OSError:
            pass
    return dest


def song_row(song):
    return {'Artist': song.get('artist', ''), 'Title': song.get('title', ''),
            'Album': song.get('album', ''), 'Length': int(float(song.get('duration') or 0))}


def rows_for(ms, state, song):
    """The playlist CSV rows that matched this song on the last run, plus a row
    from the song's own tags (they can differ: CSV rows come from YouTube Music)."""
    rows = [dict(v['row']) for v in state.get('present', {}).values() if v.get('id') == song['id']]
    own = song_row(song)
    if ms.row_key(own) not in {ms.row_key(r) for r in rows}:
        rows.append(own)
    return rows


# --- the two playlists ------------------------------------------------------------

def process(ms, settings, state, api):
    """Handle both playlists. Returns report lines (empty if nothing was marked)."""
    lines, gone_ids = [], []
    today = dt.date.today().isoformat()
    present = state.setdefault('present', {})

    pid, entries = marked(api, settings.delete_playlist, settings.nd_user)
    done = []
    for i, song in enumerate(entries):
        path = library_path(ms, song)
        if path is None:
            lines.append(f"Delete: {ms.esc(song.get('title', '?'))}: no real path inside /music; left in the playlist")
            continue
        if path.exists():
            move_out(ms, path, 'deleted')
        rows = rows_for(ms, state, song)
        ms.add_deleted(rows, today)
        for k in [k for k, v in present.items() if v.get('id') == song['id']]:
            present.pop(k)
        gone_ids.append(song['id'])
        done.append(i)
        lines.append(f"Deleted: {ms.esc(song.get('artist', ''))} - {ms.esc(song.get('title', ''))}")
    if pid:
        unmark(api, pid, done)

    pid, entries = marked(api, settings.wrong_playlist, settings.nd_user)
    sources = load_sources(ms)
    wrong = state.setdefault('wrong', {})
    done = []
    for i, song in enumerate(entries):
        path = library_path(ms, song)
        if path is None or not path.exists():
            lines.append(f"Wrong: {ms.esc(song.get('title', '?'))}: file not found inside /music; left in the playlist")
            continue
        user = (sources.get(str(path)) or (None, None))[0]
        size = path.stat().st_size
        move_out(ms, path, 'wrong')
        for row in rows_for(ms, state, song):
            entry = wrong.setdefault(key_str(ms.row_key(row)), {'row': row, 'banned': [], 'sizes': [], 'tries': 0})
            if user and user not in entry['banned']:
                entry['banned'].append(user)
            if size not in entry['sizes']:
                entry['sizes'].append(size)
        for k in [k for k, v in present.items() if v.get('id') == song['id']]:
            present.pop(k)
        gone_ids.append(song['id'])
        done.append(i)
        lines.append(f"Wrong: {ms.esc(song.get('artist', ''))} - {ms.esc(song.get('title', ''))}"
                     + (f' (sent by {ms.esc(user)}, now skipped for this song)' if user
                        else ' (sender unknown: not downloaded by music-sync)'))
    if pid:
        unmark(api, pid, done)

    if gone_ids:
        if ms.scan_and_wait(api):
            try:
                NativeApi(settings.nd_url, settings.nd_user, settings.nd_password).delete_missing(gone_ids)
            except Exception as e:  # cosmetic: the entries also show in Settings > Missing Files
                lines.append(f'Could not remove the missing entries in Navidrome: {ms.esc(e)}')
        else:
            lines.append('Navidrome scan did not finish; missing entries left in Settings > Missing Files')
    return lines


def key_str(key):
    return '\x1f'.join(key)


def retry_wrong(ms, settings, state, api):
    """Search again for each song marked Wrong. Returns report lines."""
    wrong = state.get('wrong', {})
    if not wrong:
        return []
    lines, work = [], ms.CONFIG / 'run'
    work.mkdir(exist_ok=True)
    for k, entry in list(wrong.items()):
        row = entry['row']
        found = False
        for _ in range(settings.wrong_max_tries):
            entry['tries'] += 1
            csv_path, index = work / 'wrong.csv', work / 'index-wrong.csv'
            index.unlink(missing_ok=True)  # a fresh index: the old Done row would skip the song
            ms.write_csv(csv_path, [row], with_length=bool(row.get('Length')))
            extra = ['--format', ms.LOSSY_FORMATS, '--cond', f'br>={settings.lossy_min_kbps}',
                     '--strict-title', '--length-tol', str(settings.length_tol)]
            if entry['banned']:
                extra += ['--banned-users', ','.join(entry['banned'])]
            ms.run_sockseek(settings, csv_path, ms.MUSIC, index, extra)
            state_, fp = ms.read_index(index).get(ms.row_key(row), (0, ''))
            if state_ != ms.DONE or not fp or not Path(fp).is_file():
                break  # no candidate left for now
            new = Path(fp)
            user = (load_sources(ms).get(str(new)) or (None, None))[0]
            if new.stat().st_size in entry['sizes']:
                # The same file again, from another user: put it aside and go on.
                entry['banned'] += [user] if user and user not in entry['banned'] else []
                move_out(ms, new, 'wrong')
                continue
            found = True
            lines.append(f"Replaced: {ms.esc(row['Artist'])} - {ms.esc(row['Title'])}"
                         + (f' (now from {ms.esc(user)})' if user else ''))
            break
        if found:
            wrong.pop(k)
        else:
            lines.append(f"No other source yet: {ms.esc(row['Artist'])} - {ms.esc(row['Title'])}"
                         f" (tried {entry['tries']} time{'' if entry['tries'] == 1 else 's'}; will try again next run)")
    return lines
