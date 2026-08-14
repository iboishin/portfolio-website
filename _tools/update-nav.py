#!/usr/bin/env python3
"""Stamp the canonical menus into every page.

The site carries the same menu twice on each of 1,445 pages: the desktop bar
(<nav id="site-navigation">) and the mobile flyout (the <nav> holding
#menu-flyout-menu-1). Editing a menu item by hand means 2,890 edits, so instead
the canonical copies live in _nav-desktop.html / _nav-mobile.html and this
script writes them into every page.

Three things vary per page and are preserved:
  {{BASE}}   the ../ prefix for the page's depth
  {{SELF}}   the "About Me" parent links at the page's own canonical URL + #
  current-*  WordPress marks the active menu item; the classes are read back
             out of each page before its nav is replaced, then re-applied

Usage:
    python3 _tools/update-nav.py --check     compare, change nothing
    python3 _tools/update-nav.py --apply     write the pages
    python3 _tools/update-nav.py --extract   rebuild the canonical files

Files under _tools/ and the _nav-*.html templates start with an underscore, so
Jekyll leaves them out of the published site.
"""
import os, re, sys, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP = os.path.join(ROOT, '_nav-desktop.html')
MOBILE = os.path.join(ROOT, '_nav-mobile.html')
SOURCE_PAGE = os.environ.get('NAV_SOURCE', 'index.html?p=1561.html')

ABSOLUTE = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//|#|data:)', re.I)
LI_OPEN = re.compile(r'<li\b[^>]*>')
ATTR = re.compile(r'\b(href|src)="([^"]*)"')


def nav_blocks(html):
    """Return (kind, start, end) for the desktop and mobile menu blocks."""
    out = {}
    for m in re.finditer(r'<nav\b[^>]*>', html):
        end = html.find('</nav>', m.end())
        if end == -1:
            continue
        end += len('</nav>')
        body = html[m.start():end]
        if 'id="site-navigation"' in m.group(0):
            out['desktop'] = (m.start(), end)
        elif 'menu-flyout-menu' in body:
            out['mobile'] = (m.start(), end)
    return out


def page_depth(rel):
    return rel.replace(os.sep, '/').count('/')


def self_target(html, blocks):
    """The page's own self-link, as used by the menu's dropdown parents.

    Usually the page's canonical URL, but paginated archives use a different
    one, so it is read out of the menu itself and only falls back to canonical.
    """
    if 'desktop' in blocks:
        s, e = blocks['desktop']
        for m in re.finditer(r'href="([^"]*)#"', html[s:e]):
            if m.group(1):
                return m.group(1)
    return canonical_target(html)


def canonical_target(html):
    """The page's own canonical URL, minus any ../ prefix."""
    for m in re.finditer(r'<link\b[^>]*>', html):
        tag = m.group(0)
        if 'canonical' not in tag:
            continue
        h = re.search(r'href="([^"]+)"', tag)
        if h:
            return re.sub(r'^(?:\.\./)+', '', h.group(1))
    return None


def item_key(class_value):
    """Identify a menu item by its menu-item-NNNN class token.

    The desktop <li>s also carry id="menu-item-NNNN", but the mobile flyout's
    do not, so the class token is the only key both menus share.
    """
    toks = re.findall(r'\bmenu-item-(\d+)\b', class_value)
    return toks[-1] if toks else None


ARIA = ' aria-current="page"'


def li_segments(block):
    """Yield (start, end, item_key) for each <li> ... up to the next <li>."""
    opens = list(LI_OPEN.finditer(block))
    for i, m in enumerate(opens):
        end = opens[i + 1].start() if i + 1 < len(opens) else len(block)
        cm = re.search(r'class="([^"]*)"', m.group(0))
        yield m.start(), end, (item_key(cm.group(1)) if cm else None)


def strip_aria(block):
    """Pull off aria-current="page"; return (clean_block, {menu item keys}).

    Keyed by menu item rather than by href: several dropdown parents link to the
    page itself, so matching on the target would mark all of them.
    """
    marked = {k for s, e, k in li_segments(block) if k and 'aria-current' in block[s:e]}
    return block.replace(ARIA, ''), marked


def apply_aria(block, marked):
    if not marked:
        return block
    out, last = [], 0
    for s, e, k in li_segments(block):
        if k not in marked:
            continue
        seg = block[s:e]
        fixed = re.sub(r'<a\b', '<a' + ARIA, seg, count=1)
        out.append(block[last:s]); out.append(fixed); last = e
    out.append(block[last:])
    return ''.join(out)


def strip_current(block):
    """Remove current-* classes; return (clean_block, {item key: full class})."""
    state = {}

    def fix(m):
        tag = m.group(0)
        if 'current' not in tag:
            return tag
        cm = re.search(r'class="([^"]*)"', tag)
        if not cm:
            return tag
        key = item_key(cm.group(1))
        if not key:
            return tag
        state[key] = cm.group(1)
        kept = ' '.join(c for c in cm.group(1).split() if 'current' not in c)
        return tag.replace(f'class="{cm.group(1)}"', f'class="{kept}"')

    return LI_OPEN.sub(fix, block), state


def apply_current(block, state):
    def fix(m):
        tag = m.group(0)
        cm = re.search(r'class="([^"]*)"', tag)
        if not cm:
            return tag
        key = item_key(cm.group(1))
        if key is None or key not in state:
            return tag
        return tag.replace(f'class="{cm.group(1)}"', f'class="{state[key]}"')

    return LI_OPEN.sub(fix, block)


def templatise(block, depth, self_target):
    """Turn one page's rendered block into a template."""
    block, _ = strip_current(block)
    block, _ = strip_aria(block)
    prefix = '../' * depth

    def fix(m):
        attr, val = m.group(1), m.group(2)
        if ABSOLUTE.match(val):
            return m.group(0)
        # The dropdown parents link to the page itself. That href is relative to
        # the page's own directory, not the site root, so it takes no {{BASE}}
        # and is copied verbatim from whichever page is being stamped.
        if val.endswith('#') and val != '#':
            return f'{attr}="{{{{SELF}}}}#"'
        rest = val[len(prefix):] if prefix and val.startswith(prefix) else val
        rest = re.sub(r'^(?:\.\./)+', '', rest)
        return f'{attr}="{{{{BASE}}}}{rest}"'

    return ATTR.sub(fix, block)


def render(template, depth, self_target, state, marked):
    out = template.replace('{{BASE}}', '../' * depth).replace('{{SELF}}', self_target or '')
    return apply_aria(apply_current(out, state), marked)


def pages():
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d != '.git' and not d.startswith('_')]
        for fn in fns:
            if fn.lower().endswith('.html') and not fn.startswith('_'):
                yield os.path.relpath(os.path.join(dp, fn), ROOT).replace(os.sep, '/')


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8', errors='ignore') as fh:
        return fh.read()


def do_extract():
    html = read(SOURCE_PAGE)
    blocks = nav_blocks(html)
    self_t = self_target(html, blocks)
    for kind, path in (('desktop', DESKTOP), ('mobile', MOBILE)):
        s, e = blocks[kind]
        tpl = templatise(html[s:e], page_depth(SOURCE_PAGE), self_t)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(tpl)
        print(f'wrote {os.path.basename(path)}  ({len(tpl)} B) from {SOURCE_PAGE}')


def run(apply):
    tpl = {'desktop': open(DESKTOP, encoding='utf-8').read(),
           'mobile': open(MOBILE, encoding='utf-8').read()}
    same = diff = written = skipped = 0
    mismatches = []
    for p in pages():
        html = read(p)
        blocks = nav_blocks(html)
        if 'desktop' not in blocks:
            skipped += 1
            continue
        depth = page_depth(p)
        self_t = self_target(html, blocks)
        new_html, changed = html, False
        # replace last block first so earlier offsets stay valid whatever
        # order the two menus appear in
        for kind, (s, e) in sorted(blocks.items(), key=lambda kv: -kv[1][0]):
            current = html[s:e]
            _, state = strip_current(current)
            _, marked = strip_aria(current)
            out = render(tpl[kind], depth, self_t, state, marked)
            if out == current:
                same += 1
            else:
                diff += 1
                if len(mismatches) < 6:
                    mismatches.append((p, kind, current, out))
                changed = True
            new_html = new_html[:s] + out + new_html[e:]
        if apply and changed:
            with open(os.path.join(ROOT, p), 'w', encoding='utf-8') as fh:
                fh.write(new_html)
            written += 1
    print(f'blocks identical: {same}   differing: {diff}   pages without a menu: {skipped}')
    if apply:
        print(f'pages rewritten: {written}')
    for p, kind, cur, out in mismatches:
        i = next((i for i in range(min(len(cur), len(out))) if cur[i] != out[i]), 0)
        print(f'\n  {p} [{kind}] first difference at {i}:')
        print(f'    page: …{cur[max(0,i-60):i+60]!r}')
        print(f'    tool: …{out[max(0,i-60):i+60]!r}')
    return diff


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--extract', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    if a.extract:
        do_extract()
    if a.check or a.apply:
        sys.exit(1 if run(a.apply) and a.check else 0)
