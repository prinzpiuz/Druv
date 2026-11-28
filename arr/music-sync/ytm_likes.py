"""Add YouTube Music liked songs to a playlist CSV for music-sync.

The likes are read with ytmusicapi and browser authentication (a copy of the
request headers of a signed-in music.youtube.com tab). New likes are added at
the top of the CSV. Nothing is ever removed: to get rid of a song, delete its
file, and music-sync records it as deleted (see deleted.csv) and never
downloads it again.

The CSV has the same columns as the other playlist CSVs, plus VideoId, which
is used to see which likes are already in the file.
"""
import csv
import os
from pathlib import Path

FIELDS = ['Position', 'Artist', 'Artists', 'Title', 'Album', 'Original', 'VideoId']


def read_rows(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    """Write atomically, so a stop in the middle never leaves half a file."""
    tmp = path.with_suffix('.csv.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        for i, row in enumerate(rows, 1):
            w.writerow(dict(row, Position=i))
    os.replace(tmp, path)


def track_row(track):
    """A ytmusicapi playlist item as a playlist CSV row, or None if unusable."""
    title = (track.get('title') or '').strip()
    artists = [a.get('name', '').strip() for a in track.get('artists') or [] if a.get('name')]
    if not title or not artists:
        return None
    album = (track.get('album') or {}).get('name') or ''
    return {'Artist': artists[0], 'Artists': ';'.join(artists), 'Title': title, 'Album': album,
            'Original': f"{', '.join(artists)} - {title}", 'VideoId': track.get('videoId') or ''}


def merge(existing, tracks, key, deleted):
    """New likes (newest first, as YouTube Music returns them) go on top of the
    existing rows. Returns (rows, added rows)."""
    seen_ids = {r.get('VideoId') for r in existing if r.get('VideoId')}
    seen_keys = {key(r) for r in existing}
    added = []
    for track in tracks:
        row = track_row(track)
        if row is None:
            continue
        k = key(row)
        if (row['VideoId'] and row['VideoId'] in seen_ids) or k in seen_keys or k in deleted:
            continue
        seen_ids.add(row['VideoId'])
        seen_keys.add(k)
        added.append(row)
    return added + existing, added


def fetch_likes(auth_file, limit):
    """Liked songs, newest first. limit=None reads all of them."""
    from ytmusicapi import YTMusic  # imported here, so music-sync runs without it when likes are off
    return YTMusic(str(auth_file)).get_liked_songs(limit=limit).get('tracks') or []


def sync_likes(auth_file, csv_path, recent, key, deleted, write=True):
    """Returns (all rows, added rows), or None when no auth file is set up.
    The first run reads every like; later runs read only the newest `recent`.
    write=False (dry run) changes nothing on disk."""
    auth_file, csv_path = Path(auth_file), Path(csv_path)
    if not auth_file.exists():
        return None
    existing = read_rows(csv_path)
    tracks = fetch_likes(auth_file, None if not existing else recent)
    rows, added = merge(existing, tracks, key, deleted)
    if added and write:
        write_rows(csv_path, rows)
    return rows, added
