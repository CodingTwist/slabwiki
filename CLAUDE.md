# SlabWiki

Hugo static site: community wiki & shop directory for Slabserver (a Minecraft SMP).

## Stack

- Hugo (extended, v0.163.3+)  no theme; all layouts are custom under `layouts/`.
- Tailwind CSS v4 via the standalone `@tailwindcss/cli`, **not** Hugo Pipes.
  `assets/css/main.css` is the source (edit this); `assets/css/app.css` is
  compiled output (generated, do not edit by hand). Run `npm run css` /
  `npm run dev` to rebuild it.
- `assets/css/mc-items.css` is a hand-maintained Minecraft item sprite sheet
  that drives `layouts/partials/mc-icon.html`.

## Content model

No Hugo taxonomies  `[taxonomies]` is explicitly emptied in `hugo.toml`.
Hierarchy is plain nested sections: `content/<server>/<season>/<category>/`.
`content/<server>/_index.md` cascades a `server` param used by templates and
the sidebar. `data/sections.yaml` drives the Explore nav, sidebar, and each
section's icon/quicklinks (worlds + the Workshop general blog). See `README.md` for the full breakdown and the
"adding a new page" walkthrough.

## Commands

```bash
npm run dev     # Tailwind watch + hugo server -D (http://localhost:1313)
npm run build   # npm run css && hugo --gc --minify
```

## Things to know before touching content or images

- Season 4 shop pages (`content/survival/season-4/shops/_content.gotmpl`) are
  generated at build time from a published Google Sheet CSV
  (`params.shopsCsvUrl`), matched to images in `static/images/season-4/` and
  `static/images/season-4-shops/` by normalized filename via `os.ReadDir`.
  Don't delete images in those two directories without checking the shops
  list page still renders correctly.
- Season 3 shop pages (`content/survival/season-3/shops/`) are **static**
  committed markdown (117 files + `_index.md`), one per shop, since S3 ended and
  no longer updates. Regenerate them with `python3 scripts/build_s3_shops.py`
  (reads the cargo `Shop` table live + cached page bodies in
  `scripts/wiki_cache/s3_bodies.json`). Each S3 wiki page bundles three things,
  split into Hugo's data/content model: the `{{Infobox Shop}}` becomes front
  matter (title/owners/loc/image); the inline `{{Shop Item}}` blocks become the
  front-matter `items:` list (name/material/inStock - these never populated the
  `Shop_Item` cargo table, so they exist only in the wikitext) which drives the
  list-page search, item dropdown, card preview icons, and the single page's
  stock UI; and the prose body becomes the markdown body, rendered by
  `layouts/shops/single.html` via `.Content`. Item `material` icon slugs are
  best-effort derived from item names (British spellings / "Item Set(...)" style
  entries may not match a sprite - harmless empty icon). They reuse the shared
  `layouts/shops/` templates, which are season-aware via the
  `seasonKey`/`seasonLabel` params cascaded from the section `_index.md`
  (defaulting to season-4 / currentSeason when unset). Photos + the 3 inline
  prose images live in `static/images/season-3-shops/`.
- `static/images/farms/`, `arg-puzzles/`, `_superseded/`, and `screenshots/`
  are currently unreferenced by any content/layout but are intentionally kept
  for future use  do not delete them as "unused."
- `scripts/import_articles.py` is a one-shot MediaWiki importer from an
  earlier project iteration; it writes to a flat `content/articles/` layout
  that predates the current server/season/category structure. Don't run it
  expecting it to target the current content layout without updating it first.
- `public/`, `resources/`, `node_modules/`, and `.hugo_build.lock` are
  gitignored build artifacts  never hand-edit or commit them.
