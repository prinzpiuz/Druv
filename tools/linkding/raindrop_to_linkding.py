#!/usr/bin/env python3
"""Convert a Raindrop.io HTML export into a linkding import file.

linkding imports Netscape bookmark files, but it ignores folders. Raindrop
writes each collection as a folder, so a plain import loses them. This
script keeps them as tags: a bookmark in "Dev / Python" gets the tags "dev"
and "python", plus any tags it already had in Raindrop.

Usage:
    python3 raindrop_to_linkding.py raindrop.html linkding.html
    python3 raindrop_to_linkding.py raindrop.html linkding.html --skip-folder Unsorted

Only the Python standard library is used.
"""
import argparse
import html
import sys
from html.parser import HTMLParser

DEFAULT_SKIP = ['Unsorted', 'Trash']


def tag_name(name):
    """linkding tags cannot contain spaces or commas."""
    return '-'.join(name.replace(',', ' ').split()).lower()


class RaindropParser(HTMLParser):
    """Reads a Netscape bookmark file and tracks the folder path of each link."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.folders = []        # open folder names, outermost first
        self.pending_folder = None
        self.in_h3 = False
        self.current = None      # bookmark being read
        self.in_a = False
        self.in_dd = False
        self.bookmarks = []

    def handle_starttag(self, tag, attrs):
        attrs = {k.lower(): v or '' for k, v in attrs}
        if tag == 'h3':
            self.in_h3, self.pending_folder = True, ''
        elif tag == 'dl':
            # A <DL> right after an <H3> holds that folder's contents.
            self.folders.append(self.pending_folder)
            self.pending_folder = None
        elif tag == 'a' and attrs.get('href'):
            self.current = {'attrs': attrs, 'title': '', 'desc': '', 'folders': [f for f in self.folders if f]}
            self.bookmarks.append(self.current)
            self.in_a = True
        elif tag == 'dd' and self.current is not None:
            self.in_dd = True

    def handle_endtag(self, tag):
        if tag == 'h3':
            self.in_h3 = False
        elif tag == 'a':
            self.in_a = False
        elif tag == 'dl':
            self.in_dd = False
            if self.folders:
                self.folders.pop()
        elif tag == 'dt':
            self.in_dd = False

    def handle_data(self, data):
        if self.in_h3:
            self.pending_folder += data.strip()
        elif self.in_a:
            self.current['title'] += data
        elif self.in_dd:
            self.current['desc'] += data


def convert(bookmarks, skip):
    skip = {s.lower() for s in skip}
    out = ['<!DOCTYPE NETSCAPE-Bookmark-file-1>',
           '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
           '<TITLE>Bookmarks</TITLE>', '<H1>Bookmarks</H1>', '<DL><p>']
    skipped = 0
    for b in bookmarks:
        a = b['attrs']
        if b['folders'][:1] and b['folders'][0].lower() == 'trash':
            skipped += 1
            continue
        tags = [tag_name(f) for f in b['folders'] if f.lower() not in skip]
        tags += [tag_name(t) for t in a.get('tags', '').split(',') if t.strip()]
        tags = sorted(set(t for t in tags if t))
        fields = [f'HREF="{html.escape(a["href"])}"']
        for key in ('add_date', 'last_modified'):
            if a.get(key):
                fields.append(f'{key.upper()}="{html.escape(a[key])}"')
        fields.append(f'TAGS="{html.escape(",".join(tags))}"')
        fields.append('PRIVATE="1"')
        out.append(f'<DT><A {" ".join(fields)}>{html.escape(b["title"].strip())}</A>')
        if b['desc'].strip():
            out.append(f'<DD>{html.escape(b["desc"].strip())}')
    out.append('</DL><p>')
    return '\n'.join(out) + '\n', skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('source', help='Raindrop HTML export')
    ap.add_argument('target', help='file to write for linkding import')
    ap.add_argument('--skip-folder', action='append', default=None,
                    help=f'collection that gives no tag (repeatable; default: {", ".join(DEFAULT_SKIP)}). '
                         'Bookmarks in Trash are left out.')
    args = ap.parse_args()
    parser = RaindropParser()
    with open(args.source, encoding='utf-8') as f:
        parser.feed(f.read())
    text, skipped = convert(parser.bookmarks, args.skip_folder or DEFAULT_SKIP)
    with open(args.target, 'w', encoding='utf-8') as f:
        f.write(text)
    folders = {'/'.join(b['folders']) for b in parser.bookmarks
               if b['folders'] and b['folders'][0].lower() != 'trash'}
    print(f'{len(parser.bookmarks) - skipped} bookmarks written, {skipped} in Trash left out, '
          f'{len(folders)} collections turned into tags.', file=sys.stderr)


if __name__ == '__main__':
    main()
