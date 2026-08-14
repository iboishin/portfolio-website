# Editing the site menu

This site is static HTML exported from WordPress, so the navigation menu is
copied into every page rather than pulled from one place at render time. It
appears **twice on each of the 1,445 pages**:

| | Element | Size |
|---|---|---|
| Desktop bar | `<nav id="site-navigation">` | ~32 KB |
| Mobile flyout | the `<nav>` holding `<ul id="menu-flyout-menu-1">` | ~20 KB |

That is 2,890 copies of the same 89-item menu. Editing them by hand is not
realistic, so the menu is kept in two canonical files and stamped into the
pages by a script.

```
_nav-desktop.html      the desktop bar, as a template
_nav-mobile.html       the mobile flyout, as a template
_tools/update-nav.py   writes both into every page
```

Everything here starts with an underscore, so Jekyll leaves it out of the
published site. The files live in the repo but are never served.

## Changing the menu

1. Edit `_nav-desktop.html` and `_nav-mobile.html`. Both hold the same menu in
   different markup, so **a menu change has to be made in both files.**
2. Preview what would change:

   ```bash
   python3 _tools/update-nav.py --check
   ```

3. Write it into the pages:

   ```bash
   python3 _tools/update-nav.py --apply
   ```

4. Commit. A menu change touches roughly 1,445 files; that is normal.

Run `--check` again afterwards — it should report `differing: 0`, because
stamping is idempotent. If it does not, something in the templates cannot be
reproduced and the output is worth reading before committing.

## The placeholders

The templates are not literal HTML. Two placeholders are filled in per page:

- `{{BASE}}` — the `../` prefix for the page's depth. Every link to somewhere
  else on the site is written `{{BASE}}path/from/site/root.html`. A page at the
  root gets `""`, a page two directories deep gets `"../../"`.
- `{{SELF}}` — the URL the dropdown parents ("About Me", "Hobbies", …) point at,
  which is the page's own address. It takes **no** `{{BASE}}` prefix because it
  is relative to the page's own directory, and it is not always the page's
  canonical URL — paginated archives use a different one — so it is copied out
  of each page rather than derived.

If you add a link to the menu, write its href as `{{BASE}}` plus the path from
the site root, matching the links already there.

## What the script preserves

WordPress marked the menu item you were currently on, and that state differs on
every page. The script reads it out of each page *before* replacing the menu and
puts it back afterwards, so it survives a stamp:

- `current-menu-item`, `current-page-ancestor` and friends on the `<li>`
- `aria-current="page"` on the active `<a>`

Both are matched by the `menu-item-NNNN` class token, which is the only
identifier the desktop and mobile menus share — the mobile `<li>`s have no `id`
attribute. **Do not renumber or remove those class tokens**; they are how a
page's active-item state finds its way back to the right item.

## Rebuilding the templates

If the canonical files are ever lost or you want to re-derive them from a page:

```bash
python3 _tools/update-nav.py --extract
```

This reads the menu out of one page (`index.html?p=1561.html` by default,
override with `NAV_SOURCE=some/page.html`) and turns it into the two templates.
It overwrites `_nav-desktop.html` and `_nav-mobile.html`, so any hand edits in
them are lost. You rarely want this.

Note that pages were exported with inconsistent indentation and attribute
order, so the source page's formatting becomes the formatting of every page's
menu after the next `--apply`. That is cosmetic and does not change rendering.

## Verifying a change

Beyond `--check` reporting zero differences, two checks are worth running after
a menu edit. That every link in every menu still points at a real file:

```bash
python3 - <<'EOF'
import os, re, urllib.parse, importlib.util
spec = importlib.util.spec_from_file_location('nv', '_tools/update-nav.py')
nv = importlib.util.module_from_spec(spec); spec.loader.exec_module(nv)
files = {os.path.relpath(os.path.join(dp, f), '.').replace(os.sep, '/')
         for dp, dn, fns in os.walk('.') if '.git' not in dp for f in fns}
bad = checked = 0
for p in nv.pages():
    html = nv.read(p)
    for kind, (s, e) in nv.nav_blocks(html).items():
        for m in re.finditer(r'href="([^"]+)"', html[s:e]):
            h = m.group(1)
            if re.match(r'^(?:[a-z]+:|//|#)', h, re.I): continue
            t = urllib.parse.unquote(h.split('#')[0])
            if not t: continue
            checked += 1
            if os.path.normpath(os.path.join(os.path.dirname(p), t)).replace(os.sep, '/') not in files:
                bad += 1; print('missing:', h)
print(f'{checked} links checked, {bad} unresolved')
EOF
```

And that the active-item markers did not get lost, by comparing against the
commit before your change:

```bash
git grep -o 'current-menu-item' HEAD -- '*.html' | wc -l
grep -ro 'current-menu-item' --include='*.html' . | wc -l
```

The two numbers should match.

## Adding new pages

A new page needs both menus in it to look like the rest of the site. The
simplest route is to copy an existing page at the same directory depth and
replace its content — the menu blocks then already carry the right `../`
prefixes, and `--apply` will keep them in step from then on.
