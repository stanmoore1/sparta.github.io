#!/usr/bin/env python3
"""Check that every internal link in the built site resolves.

Both halves of a link matter.  The file has to be there, and so does the
anchor: an anchor name is part of a URL, renaming one breaks an inbound
link just as surely as deleting the page, and it is the failure this
migration was most at risk of.

This runs against the build alone, with no reference to the txt2html
manual, so unlike parity-check.py and equation-check.py it keeps working
after the migration is over.  It is what CI runs.

Usage:
    link-check.py HTML_DIR
"""
import argparse
import html
import pathlib
import re
import sys

# <a name="..."> is the anchor form the conversion kept for the names the
# old manual published; id="..." on any element is Sphinx's own.  Scoped to
# inside a tag, because the manual's prose contains things like
# 'the default mixture has an ID = "all"', which is text, not an anchor.
NAME = re.compile(r'<a\b[^>]*?\bname\s*=\s*"([^"]+)"', re.I)
TAG = re.compile(r'<[a-zA-Z][^>]*>')
ID = re.compile(r'\bid\s*=\s*"([^"]+)"', re.I)
HREF = re.compile(r'<a\b[^>]*?href\s*=\s*"([^"]*)"', re.I)

# The manual is a separate Sphinx project, in the SPARTA repository, whose
# built pages are copied in under doc/ when a release is made.  It is
# legitimately absent from a build of the site alone, so links into it are
# counted separately rather than reported as broken -- but only links into
# doc/, and only when doc/ is not there at all.  Once it has been copied in
# they are checked like any other link.
MANUAL = 'doc'

# Links that were already broken on the published site before the
# conversion, each checked against it.  They are recorded rather than
# fixed because fixing them changes what the site says, which is a
# separate job from changing how it is written; and recorded rather than
# ignored so that this check stays useful -- anything not on this list is
# a link the conversion broke.
KNOWN_BROKEN = {
    # a manual page linked without the doc/ prefix
    'bug.html': {'compute_distsurf_grid.html', 'fix_ave_time.html',
                 'fix_emit_face_file.html', 'global.html',
                 'stats_style.html',
                 # patch files that are not in the repository
                 'patches/files.11Jun16', 'patches/files.24May16',
                 'patches/files.4Apr17'},
    # ":link(pizza,...)" is defined on other pages but not on this one,
    # and the download page belongs to a different site
    'other.html': {'pizza', '../download.html'},
    'pictures.html': {'movies/rti_longtime.mov'},
    # anchors bench.txt links to and never defines
    'bench.html': {'#interpret', '#machine'},
}


def anchors(text):
    found = set(NAME.findall(text))
    for tag in TAG.finditer(text):
        found |= set(ID.findall(tag.group(0)))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html_dir')
    args = ap.parse_args()
    root = pathlib.Path(args.html_dir)
    if not root.is_dir():
        print(f'no such directory: {root}', file=sys.stderr)
        return 2

    have = {p.name: anchors(p.read_text(errors='replace'))
            for p in root.glob('*.html')}

    bad = []
    known = 0
    unbuilt = set()
    for page in sorted(root.glob('*.html')):
        text = page.read_text(errors='replace')
        for m in HREF.finditer(text):
            href = html.unescape(m.group(1))
            if href.startswith(('http', 'mailto', 'ftp', 'javascript:')):
                continue
            target, _, frag = href.partition('#')
            allowed = KNOWN_BROKEN.get(page.name, ())
            if href in allowed or (target and target in allowed):
                known += 1
                continue
            if target and not (root / target).exists():
                # The manual is a separate project, copied in under doc/ at
                # release time, so it is legitimately absent from a build of
                # the site alone.  Only doc/, and only when it is not there.
                if target.split('/')[0] == MANUAL and not (root / MANUAL).is_dir():
                    unbuilt.add(target)
                    continue
                bad.append(f'{page.name} -> {target} (no such file)')
                continue
            dest = target or page.name
            if frag and dest in have and frag not in have[dest]:
                if '#' + frag in allowed:
                    known += 1
                    continue
                bad.append(f'{page.name} -> {href} (no such anchor)')

    for b in sorted(set(bad)):
        print(f'  {b}')
    if known:
        print(f'  note: {known} link(s) already broken before the conversion, '
              f'listed in KNOWN_BROKEN')
    if unbuilt:
        print(f'  note: {len(unbuilt)} link(s) into doc/ not checked; the '
              f'manual is copied in from the SPARTA repository at release')
    n = len(set(bad))
    print(f'  {n} dead internal link(s) or anchor(s) in {len(have)} pages')
    return 1 if n else 0


if __name__ == '__main__':
    sys.exit(main())
