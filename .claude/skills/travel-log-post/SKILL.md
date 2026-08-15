---
name: travel-log-post
description: Build a new travel-log post for this static portfolio site from photos and spoken notes — importing and resizing images, transcribing and translating voice memos (usually Bulgarian) with whisper, writing FooGallery captions, creating the page, and adding the menu entry. Use this whenever Iva mentions a trip, a new city, photos to add, voice notes or recordings to turn into captions, a new gallery, or wants an existing travel-log page extended — even if the words "travel log", "gallery" or "skill" are never used. Also use it when someone asks how photos or captions get added to this site.
---

# Adding a travel-log post

This site is a static export of a WordPress install. There is no CMS behind it —
every page is hand-edited HTML, the menu is duplicated on all ~1,180 pages, and
FooGallery markup is written by hand. That sounds worse than it is, because the
work is mechanical and two bundled scripts cover the fiddly parts.

The author dictates notes in Bulgarian while travelling and expects English
captions in her own voice. Getting the facts right matters more than speed: this
is her portfolio, and a confidently wrong historical claim is worse than a
missing one.

## What you are given

Photos and voice notes land in `~/Downloads`. Recordings are named after the
photos they describe:

```
A 20260815_105529 and 20260815_110307.m4a   two photos, one recording
D 20260815_111742.m4a                       one photo
C 20260815_111825 and for info received_2107468589849913.m4a
```

The letter is just ordering. **`for info <name>` means that image is context the
author mentioned, not a photo to publish** — do not import it.

When a recording covers several photos, split the transcript by looking at the
photos. The notes follow the walk, so the order of names in the filename is
usually the order of the content, but read the images before deciding.

## Step 1 — Transcribe

```bash
python3 .claude/skills/travel-log-post/scripts/transcribe_notes.py ~/Downloads
```

It converts to 16 kHz mono, repairs the header, normalises the level and runs
whisper, printing one transcript per recording. Requires `whisper-cpp`
(`brew install whisper-cpp`) and a model at `~/.cache/whisper/ggml-medium.bin`.

Four things were learned the hard way and are baked into the script:

| Symptom | Cause |
|---|---|
| whisper refuses to read the file | phone recorders write a WAV header declaring 4 KB of audio in a 5 MB file; the script rewrites the RIFF and data sizes |
| a 60-second note yields one sentence | the recording is very quiet (peak ~1% of full scale); the script normalises before transcribing |
| output is a fragment, or "[music] Thank you for watching" | the `-nt` (no timestamps) flag is broken in this build — always transcribe **with** timestamps and strip them afterwards |
| proper nouns are mangled | `medium` handles Bulgarian; `small` does not. For stubborn audio add `-bs 8 -bo 8` (beam search) |

If a recording still yields nothing, check its level before blaming the model.
A note recorded at peak RMS ~180 is unrecoverable — ask for a re-record rather
than guessing at content.

## Step 2 — Translate and draft captions

Whisper's Bulgarian output will be rough: place names especially come through
mangled ("Нод" for Nantes, "Задюкс в Ритни" for the Dukes of Brittany). Work out
the meaning, then write the caption in English.

Match the voice of the existing captions — first person, conversational,
happy to be wry, and never breathless. A real one for calibration:

> One of the mornings in Athens, I noticed a smoothie store. I was pleasantly
> surprised to see that it was all freshly squeezed fruit with no sugary syrups.

**Where accuracy is concerned, ask rather than guess.** Names, dates and
historical claims that came through garbled should be surfaced to the author
with what you heard and what you think it means. In practice she corrects about
one fact per recording — a mis-remembered decade, an ally named wrongly, a
château spelled from memory. Photos often contain an information panel; cropping
and reading it is faster than asking, and it settled two questions on the Oudon
post.

Anything you add that she did not say — a historical detail you happen to know,
a closing flourish — flag it explicitly so she can cut it.

## Step 3 — Import the photos

```bash
python3 .claude/skills/travel-log-post/scripts/build_gallery.py manifest.json
```

The manifest names the page and lists photos in display order:

```json
{
  "page": "travel-log/oudon-france/index.html",
  "gallery_id": "20260815",
  "source_dir": "/Users/petitcochon/Downloads",
  "year_month": "2026/08",
  "photos": [
    {"file": "20260815_115958", "caption": "Oudon sits right on the Loire…"},
    {"file": "20260815_105132", "caption": "Le château de la Boulavière…"}
  ]
}
```

It resizes to the site's convention (1500 px long edge, quality 68), builds a
150×150 centre-cropped thumbnail, and rewrites the gallery block in the page.
Running it again is safe — photos already imported are left alone, so it is the
normal way to reorder items or fix a caption.

**Never rotate the pixels.** Phone photos carry an EXIF orientation tag that
browsers apply and `sips` ignores. A portrait photo therefore looks sideways in
`sips` and in most preview tools while being perfectly upright in a browser.
Rotating it to "fix" that tips it on its side on the live site. Verify
orientation by loading the file in a browser and reading `naturalWidth` /
`naturalHeight`, not by looking at a preview.

## Step 4 — The page

Extending an existing post needs nothing beyond step 3. For a new city, see
`references/new-page.md` — it lists every field that identifies a page and has
to be swapped when copying one, which is more than it first appears (JSON-LD,
social share links, tags, previous/next post, canonical).

## Step 5 — The menu

Menu entries live in `_nav-desktop.html` and `_nav-mobile.html` at the repo
root. **Both must be edited** — the desktop bar and the mobile flyout are
separate copies of the same menu. Then:

```bash
python3 _tools/update-nav.py --check    # preview
python3 _tools/update-nav.py --apply    # write to every page
```

See `_tools/README.md` for the placeholders and what the script preserves. Cities
are grouped by country under Travel Log, and a département with several towns
gets its own submenu — copy the shape of an existing parent entry.

## Step 6 — Verify before committing

Serve the site and check, rather than assuming:

```bash
python3 -m http.server 8765
```

- every link on the new page resolves to a file that exists
- `update-nav.py --check` reports `differing: 0`
- in a browser: no broken images, portrait photos report `naturalHeight >
  naturalWidth`, and each lightbox target returns 200
- no phrase is repeated across the intro and captions — it is easy to say the
  same thing on two photos when the notes circle back to a subject

## Step 7 — Commit and deploy

`main` is what GitHub Pages publishes, so a push deploys. Wait for it and check
the live URL rather than reporting success on the push alone.

Two recurring traps: HTML is cached for ten minutes, so a page can keep showing
the old version after a deploy — hard-refresh before believing a bug report. And
a 404 on a new page usually just means the build has not finished; poll for a
minute before investigating.

## Conventions worth not rediscovering

**Captions are inserted with `.text()`**, so HTML in them is shown literally.
For a paragraph break, put a real newline in the caption and add, scoped to the
gallery:

```css
#foogallery-gallery-<id> .fg-caption-title { white-space: pre-line; }
```

**Caption text appears three times per item** — `data-caption-title`, the `img`
`title`, and the visible `.fg-caption-title` div. The script keeps them in sync;
hand-editing one of the three is how they drift apart.

**Images live at** `wp-content/uploads/<year>/<month>/` with thumbnails under
`wp-content/uploads/cache/<year>/<month>/<name>/`. Keep to it: the site was
recently rebuilt around these paths and stray files break the tooling that
checks them.

**The site carries no external dependencies any more.** Everything it needs is
in the repo, and it should stay that way — resist pointing anything at an
outside host, however convenient.
