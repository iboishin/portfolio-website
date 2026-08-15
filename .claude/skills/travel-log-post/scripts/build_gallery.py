#!/usr/bin/env python3
"""Import photos and rewrite a page's FooGallery block from a manifest.

The manifest is the source of truth for what the gallery contains and in what
order, so reordering items or fixing a caption means editing it and running this
again. Photos already imported are left alone, which makes reruns cheap.

    python3 build_gallery.py manifest.json
    python3 build_gallery.py manifest.json --dry-run

manifest.json:
{
  "page": "travel-log/oudon-france/index.html",
  "gallery_id": "20260815",
  "source_dir": "/Users/petitcochon/Downloads",
  "year_month": "2026/08",
  "photos": [
    {"file": "20260815_115958", "caption": "Oudon sits right on the Loire…"}
  ]
}

Paths are relative to the repo root. A caption may contain newlines; pair them
with `white-space: pre-line` on .fg-caption-title or they collapse to spaces.
"""
import argparse, html, json, os, re, shutil, subprocess, sys

SVG = ("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20"
       "width%3D%22150%22%20height%3D%22150%22%20viewBox%3D%220%200%20150%20150%22%3E%3C%2Fsvg%3E")
LONG_EDGE, QUALITY, THUMB = 1500, 68, 150


def repo_root(*starts):
    """Find the site repo, trying the working directory before the script's own home.

    The manifest is often written somewhere scratch, so its location is a poor
    clue; the script itself lives inside the repo, which makes a good fallback.
    """
    for start in starts:
        d = os.path.abspath(start)
        while d != '/':
            if os.path.isdir(os.path.join(d, '.git')):
                return d
            d = os.path.dirname(d)
    sys.exit('not inside the site repo — run from the repo, or keep this script in it')


def dims(p):
    o = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', p],
                       capture_output=True, text=True).stdout
    w = int([l for l in o.splitlines() if 'pixelWidth' in l][0].split(':')[1])
    h = int([l for l in o.splitlines() if 'pixelHeight' in l][0].split(':')[1])
    return w, h


def import_photo(root, src_dir, ym, name):
    """Resize to the site's convention and build a square thumbnail.

    Deliberately never rotates. Phone photos carry an EXIF orientation tag that
    browsers honour and sips ignores, so a portrait photo looks sideways to sips
    while being upright on the site; "correcting" it is what tips it over.
    A centre crop is the same region whichever way the tag rotates it.
    """
    full_rel = f'wp-content/uploads/{ym}/{name}.jpg'
    thumb_rel = f'wp-content/uploads/cache/{ym}/{name}/150x150.jpg'
    full, thumb = os.path.join(root, full_rel), os.path.join(root, thumb_rel)

    if not os.path.exists(full):
        src = os.path.join(src_dir, f'{name}.jpg')
        if not os.path.exists(src):
            sys.exit(f'missing source photo: {src}')
        os.makedirs(os.path.dirname(full), exist_ok=True)
        shutil.copy2(src, full)
        subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', str(QUALITY),
                        '-Z', str(LONG_EDGE), full, '--out', full], capture_output=True)
    if not os.path.exists(thumb):
        os.makedirs(os.path.dirname(thumb), exist_ok=True)
        shutil.copy2(full, thumb)
        n = min(dims(full))
        subprocess.run(['sips', '-c', str(n), str(n), thumb], capture_output=True)
        subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '75',
                        '-Z', str(THUMB), thumb, '--out', thumb], capture_output=True)
    return full_rel, thumb_rel


def item_html(gid, i, caption, full_rel, thumb_rel, page_dir):
    """One gallery item. The caption appears three times and must stay identical."""
    cap = html.escape(caption, quote=True)
    href = os.path.relpath(full_rel, page_dir).replace(os.sep, '/')
    thumb = os.path.relpath(thumb_rel, page_dir).replace(os.sep, '/')
    return (f'<div class="fg-item fg-type-image fg-idle"><figure class="fg-item-inner">'
            f'<a class="fg-thumb" data-attachment-id="{gid}{i:02d}" data-caption-title="{cap}" '
            f'href="{href}"><span class="fg-image-wrap">'
            f'<img class="skip-lazy fg-image" data-src-fg="{thumb}" decoding="async" '
            f'height="150" src="{SVG}" title="{cap}" width="150"/></span>'
            f'<span class="fg-image-overlay"></span></a><figcaption class="fg-caption">'
            f'<div class="fg-caption-inner"><div class="fg-caption-title">{cap}</div></div>'
            f'</figcaption></figure><div class="fg-loader"></div></div>')


def replace_gallery(page_text, items):
    """Swap the gallery block, matching divs so nested markup does not truncate it."""
    start = page_text.find('<div class="foogallery')
    if start < 0:
        sys.exit('no foogallery container on that page')
    depth, end = 0, None
    for t in re.finditer(r'<div\b|</div>', page_text[start:]):
        depth += 1 if t.group(0) == '<div' else -1
        if depth == 0:
            end = start + t.end()
            break
    open_tag = re.match(r'<div[^>]*>', page_text[start:]).group(0)
    return page_text[:start] + open_tag + '\n' + '\n'.join(items) + '\n</div>' + page_text[end:]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('manifest')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    m = json.load(open(a.manifest, encoding='utf-8'))
    root = repo_root(os.getcwd(), os.path.dirname(os.path.abspath(__file__)))
    page_rel = m['page']
    page_dir = os.path.dirname(page_rel)
    gid = str(m['gallery_id'])

    items = []
    for i, p in enumerate(m['photos'], 1):
        full_rel, thumb_rel = import_photo(root, m['source_dir'], m['year_month'], p['file'])
        w, h = dims(os.path.join(root, full_rel))
        items.append(item_html(gid, i, p['caption'], full_rel, thumb_rel, page_dir))
        print(f'  {p["file"]}  {w}x{h}  {os.path.getsize(os.path.join(root, full_rel)) // 1024} KB')

    page_path = os.path.join(root, page_rel)
    text = open(page_path, encoding='utf-8', errors='ignore').read()
    new = replace_gallery(text, items)
    new = re.sub(r'foogallery-gallery-\d+', f'foogallery-gallery-{gid}', new)

    if a.dry_run:
        print(f'\n  dry run: {len(items)} items would be written to {page_rel}')
        return
    open(page_path, 'w', encoding='utf-8').write(new)
    print(f'\n  wrote {len(items)} items to {page_rel}')
    if any('\n' in p['caption'] for p in m['photos']):
        print('  a caption spans paragraphs: make sure the page has\n'
              f'    #foogallery-gallery-{gid} .fg-caption-title {{ white-space: pre-line; }}')


if __name__ == '__main__':
    main()
