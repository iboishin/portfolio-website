# Creating a new travel-log page

Read this when a trip needs a page that does not exist yet. Adding photos to an
existing post does not need any of it.

There is no template — a new page is a copy of an existing one with every
identifying field swapped. The catch is that a WordPress export identifies a
page in more places than you would expect, and a missed one leaves the new page
quietly claiming to be the old one to search engines and social networks.

## Pick a source page

Choose a travel-log page at the same directory depth (`travel-log/<city>/`) that
already has a gallery, so the relative paths and the FooGallery scaffolding are
right. Something small keeps the diff readable —
`travel-log/burg-kreuzenstein-austria/` was used for Oudon.

## Swap everything that names the source

The reliable approach is a blanket replacement of the source's slug and title
before touching anything else, because those strings appear in places that are
easy to miss:

```python
s = s.replace('travel-log/burg-kreuzenstein-austria', 'travel-log/oudon-france')
s = s.replace('Burg Kreuzenstein, Austria', 'Oudon, France')
s = s.replace('Burg Kreuzenstein', 'Oudon')
# and the percent-encoded forms, which appear in the share links
s = s.replace(quote('Burg Kreuzenstein, Austria'), quote('Oudon, France'))
```

That covers, in one pass:

| Where | What |
|---|---|
| `<title>`, `og:title`, `og:description`, `name="description"` | page identity |
| `<link rel="canonical">`, `rel="shortlink"` | **must be absolute** — `https://iboishin.github.io/portfolio-website/<path>/` |
| JSON-LD block | `@id`, `url`, `name`, breadcrumb, `potentialAction` — several per page |
| Twitter / email share links | title and URL, percent-encoded |
| `<article id="post-N">`, `postid-N` body class | post identity |
| `<h2 class="single-post-title">` | the visible heading |

Then handle the ones a text swap cannot:

- **Tags** — the source page's tags (`../../tag/burg-kreuzenstein/`) belong to it,
  not to the new page. Remove them, or point them at tags that exist.
- **Active menu state** — the copy carries the source page's `current-menu-item`
  classes and `aria-current="page"`. Strip both; `_tools/update-nav.py --apply`
  will set them correctly once the new page is in the menu.
- **Previous / next post** — these are hand-wired, not generated. Point
  *previous* at the most recent existing travel-log post (find it by comparing
  `datePublished` across `travel-log/*/index.html`) and delete the *next* block,
  since a new post is the newest.
- **Dates** — `datePublished` and `dateModified` in the JSON-LD,
  `article:published_time` and `article:modified_time`, and the visible date in
  the `.meta-date` element. All four, or they disagree.
- **The intro paragraph** — the first `<p>` in `.entry-content` still describes
  the source page. It needs the author's words; a placeholder is fine as long as
  you flag it rather than let it ship unnoticed.

## Check for leftovers

```bash
grep -ci '<source-city>' travel-log/<new-city>/index.html
```

Zero, or something was missed. This caught eighteen remnants on the Oudon page —
JSON-LD, share links, tags and menu state — after the obvious tags were already
correct.
