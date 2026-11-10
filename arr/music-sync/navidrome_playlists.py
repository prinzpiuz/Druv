#!/usr/bin/env python3
"""Build Navidrome playlists from CSV files, in the CSV's order.

Each playlists/<Name>.csv becomes the Navidrome playlist <Name>. Every row is
matched to a song in the library through the Subsonic API (title first, then
artist and album to choose between candidates). An existing playlist with the
same name, owned by the same user, has its songs replaced; nothing else in
Navidrome changes. Songs that cannot be matched are listed in a report, so you
can download them and run the script again.

Usage:
  NAVIDROME_PASSWORD=... ./navidrome_playlists.py --url http://localhost:4533 --user prinzpiuz
  (on the homelab use localhost:4533; from elsewhere, https://music.prinzpiuz.in)
  ... --dry-run          match and report only, change nothing
  ... --only "Tamil"     build one playlist (repeatable)
  ... --dry-run --missing missing.csv
                         also write the songs not in the library, once each,
                         as a download list for Sockseek
  ... --upgrade-lossy    with --missing: also list songs you only have as
                         lossy files (mp3, aac, ...), to fetch them in FLAC

Needs only Python 3.8+; no packages.
"""
import argparse
import csv
import difflib
import hashlib
import json
import os
import re
import secrets
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CLIENT = 'ytm-playlist-sync'
# Words that make two recordings different songs. A row that has one of these
# only matches a song that has it too, and the other way round.
VERSION_WORDS = {'male', 'female', 'duet', 'unplugged', 'reprise', 'instrumental', 'remix', 'slowed',
                 'lounge', 'piano', 'acoustic', 'happy', 'sad', 'version', 'live', 'karaoke', 'edit'}


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()


def base_title(title):
    """Title without bracketed parts, 'feat.' credits or ' - From ...' tails."""
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', title or '')
    t = re.sub(r'\s(?:feat|ft)\.?\s.*$', ' ', t, flags=re.I)
    t = re.sub(r'\s-\s(?:from|the)\s.*$', ' ', t, flags=re.I)
    return norm(t)


def version_words(title):
    return {w for w in norm(title).split() if w in VERSION_WORDS} - {'version'}


def similarity(a, b):
    a, b = norm(a).replace(' ', ''), norm(b).replace(' ', '')
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


class Subsonic:
    def __init__(self, url, user, password, client=CLIENT):
        self.base = url.rstrip('/') + '/rest/'
        self.user, self.password, self.client = user, password, client

    def call(self, method, params=()):
        salt = secrets.token_hex(8)
        query = [('u', self.user), ('t', hashlib.md5((self.password + salt).encode()).hexdigest()),
                 ('s', salt), ('v', '1.16.1'), ('c', self.client), ('f', 'json')] + list(params)
        # POST keeps long song lists out of the URL.
        req = urllib.request.Request(self.base + method, data=urllib.parse.urlencode(query).encode(),
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        # A long run makes thousands of requests; one dropped connection should
        # not end it. HTTP errors (bad URL, auth) are not retried.
        for attempt in range(1, 5):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.load(resp)['subsonic-response']
                break
            except urllib.error.HTTPError:
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt == 4:
                    raise
                wait = 5 * attempt
                print(f'  {method}: {e}; retrying in {wait}s ({attempt}/3)', file=sys.stderr)
                time.sleep(wait)
        if body.get('status') != 'ok':
            err = body.get('error', {})
            raise RuntimeError(f"{method}: {err.get('message', 'failed')} (code {err.get('code')})")
        return body

    def search(self, query, count=40):
        body = self.call('search3', [('query', query), ('songCount', count),
                                     ('artistCount', 0), ('albumCount', 0)])
        return body.get('searchResult3', {}).get('song', []) or []

    def playlists(self):
        return self.call('getPlaylists').get('playlists', {}).get('playlist', []) or []


def song_artists(song):
    names = [song.get('artist', ''), song.get('displayArtist', ''), song.get('albumArtist', ''),
             song.get('displayAlbumArtist', ''), song.get('displayComposer', '')]
    for field in ('artists', 'albumArtists'):
        names += [a.get('name', '') for a in song.get(field, []) or []]
    return ' / '.join(n for n in names if n)


def score(row, song):
    """0..1. Title decides; artist and album pick between equal titles."""
    want_title, got_title = base_title(row['Title']), base_title(song.get('title', ''))
    t = similarity(want_title, got_title)
    if want_title and got_title and (want_title in got_title or got_title in want_title):
        t = max(t, 0.9)
    if version_words(row['Title']) != version_words(song.get('title', '')):
        t -= 0.3
    artists = [a for a in row.get('Artists', '').split(';') if a.strip()] or [row.get('Artist', '')]
    have = norm(song_artists(song)).replace(' ', '')
    a = 0.0
    for name in artists:
        n = norm(name).replace(' ', '')
        if n and (n in have or similarity(n, have) > 0.8):
            a = 1.0
            break
        # Initials and spacing vary a lot ("A.R. Rahman", "A. R. Rahman", "AR Rahman").
        if n and len(n) > 4 and difflib.SequenceMatcher(None, n, have).find_longest_match(
                0, len(n), 0, len(have)).size >= max(5, int(len(n) * 0.8)):
            a = max(a, 0.8)
    al = similarity(row.get('Album', ''), song.get('album', '')) if row.get('Album') else 0.0
    quality = 0.02 if (song.get('suffix') or '').lower() in ('flac', 'wav', 'alac') else 0.0
    return 0.7 * t + 0.25 * a + 0.05 * al + quality, t, a


def find(api, row, min_score):
    queries = [row['Title'], base_title(row['Title'])]
    if row.get('Artist'):
        queries.append(f"{base_title(row['Title'])} {norm(row['Artist'])}")
    seen, best = set(), None
    for q in queries:
        if not q.strip():
            continue
        for song in api.search(q):
            if song['id'] in seen:
                continue
            seen.add(song['id'])
            total, t, a = score(row, song)
            if best is None or total > best[0]:
                best = (total, t, a, song)
        if best and best[0] >= 0.9:
            break
    if best is None:
        return None, None
    total, t, a, song = best
    # Accept a near-exact title with a matching artist, or an exact title with
    # nothing better on offer. Anything else is reported, not guessed.
    ok = total >= min_score and t >= 0.85 and (a >= 0.8 or t >= 0.97)
    return (song if ok else None), best


def describe(song):
    return f"{song.get('artist', '?')} - {song.get('title', '?')} [{song.get('album', '?')}] ({song.get('suffix', '?')})"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--url', required=True, help='Navidrome URL, e.g. https://music.prinzpiuz.in')
    p.add_argument('--user', required=True)
    p.add_argument('--dir', default=Path(__file__).parent / 'playlists', type=Path)
    p.add_argument('--only', action='append', default=[], help='playlist name to build (repeatable)')
    p.add_argument('--dry-run', action='store_true', help='match and report; do not change playlists')
    p.add_argument('--min-score', type=float, default=0.8)
    p.add_argument('--report', type=Path, default=Path('unmatched.csv'))
    p.add_argument('--missing', type=Path, help='write a Sockseek download list of songs not in the library')
    p.add_argument('--upgrade-lossy', action='store_true',
                   help='with --missing: also list songs present only as lossy files')
    args = p.parse_args()

    password = os.environ.get('NAVIDROME_PASSWORD')
    if not password:
        sys.exit('Set NAVIDROME_PASSWORD in the environment.')
    api = Subsonic(args.url, args.user, password)
    try:
        api.call('ping')
    except (RuntimeError, OSError) as e:
        sys.exit(f'Cannot log in to {args.url}: {e}')

    files = sorted(args.dir.glob('*.csv'))
    if args.only:
        files = [f for f in files if f.stem in args.only]
        missing = set(args.only) - {f.stem for f in files}
        if missing:
            sys.exit(f'No CSV for: {", ".join(sorted(missing))}')
    existing = {pl['name']: pl for pl in api.playlists() if pl.get('owner') == args.user}

    unmatched, summary, missing = [], [], {}
    lossless = {'flac', 'wav', 'alac', 'aiff', 'ape', 'wv'}

    def want(row):
        k = (base_title(row['Title']), norm(row.get('Artist', '')))
        missing.setdefault(k, {'Artist': row.get('Artist', ''), 'Title': row['Title'], 'Album': row.get('Album', '')})
    for path in files:
        name = path.stem
        rows = list(csv.DictReader(path.open(encoding='utf-8')))
        ids = []
        for row in rows:
            song, best = find(api, row, args.min_score)
            if song:
                if song['id'] not in ids:
                    ids.append(song['id'])
                if args.upgrade_lossy and (song.get('suffix') or '').lower() not in lossless:
                    want(row)
                continue
            want(row)
            unmatched.append({'Playlist': name, 'Position': row.get('Position', ''), 'Artist': row.get('Artist', ''),
                              'Title': row['Title'], 'Album': row.get('Album', ''),
                              'Closest': describe(best[3]) if best else '',
                              'Score': f'{best[0]:.2f}' if best else ''})
        action = 'would update' if name in existing else 'would create'
        if not args.dry_run and ids:
            if name in existing:
                # createPlaylist with playlistId replaces the song list.
                api.call('createPlaylist', [('playlistId', existing[name]['id'])] + [('songId', i) for i in ids])
                action = 'updated'
            else:
                api.call('createPlaylist', [('name', name)] + [('songId', i) for i in ids])
                action = 'created'
        elif not ids:
            action = 'skipped (no matches)'
        summary.append(f'{name:20} {len(ids):4}/{len(rows):<4} matched  {action}')

    with args.report.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Playlist', 'Position', 'Artist', 'Title', 'Album', 'Closest', 'Score'])
        w.writeheader()
        w.writerows(unmatched)
    if args.missing:
        with args.missing.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['Artist', 'Title', 'Album'])
            w.writeheader()
            w.writerows(missing.values())
    print('\n'.join(summary))
    if args.missing:
        print(f'{len(missing)} songs to download written to {args.missing}')
    print(f'\n{len(unmatched)} unmatched rows written to {args.report}'
          + (' (dry run: no playlists changed)' if args.dry_run else ''))


if __name__ == '__main__':
    main()
