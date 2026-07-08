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

## Design system & style guide

There is a **live, in-site style guide at `/style-guide/`** - the source of
truth for the visual system. It renders the real components (not a static spec)
so it re-themes with the dark/light toggle and never drifts. It's a Hugo
section: `content/style-guide/*.md` pages (each with `type: style-guide` +
`noSearch: true` and a `sections:` list) dispatch to
`layouts/partials/style-guide/*.html` via `layouts/style-guide/`. Tabs:
**Foundations** (palette + typography + theming), **Components**, **Blocks**
(a curated draft set - candidates kept or cut), and **Iconography**. **Read it
before extending `layouts/` or `main.css`, and update it when you add/change a
component.**

The design language ("game-y Minecraft"):

- **Hard corners** - never `rounded`.
- **Hard OFFSET shadows only** - no blur. Scale by elevation:
  `mc-card` 4px -> `mc-panel` 8px -> `mc-frame` 12px, all `Npx Npx 0 var(--c-shadow)`
  (or `--c-card-sh`).
- **Chunky `border-line` borders** (2/3/4px).
- **Pixel font (Silkscreen, `var(--font-pixel)`) on all headings/labels/buttons**;
  Nunito Sans for body. Sprites/maps use `image-rendering: pixelated`; stepped
  `steps(2)` hover transitions.
- **Never hardcode hex in templates** - use `bg-*`/`text-*`/`border-*` utilities
  so both themes stay in sync. Colors are `@theme` tokens mapping `--color-*` ->
  `var(--c-*)`, defined in three blocks in `main.css` (dark / `[data-theme="light"]`
  / `prefers-color-scheme:light`); to retune a color, edit all three. Text sitting
  on the fixed grass panel is the one "constant" case - use `text-on-grass` /
  `text-on-grass-dim` (identical across themes, since `--c-grass` is), not a raw hex.
- **Adding a component:** put it in the `@layer components` block of `main.css`,
  compose with `@apply` + tokens (not raw hex), keep the `mc-`/feature-prefix
  naming, `npm run css` to rebuild, then document + render it on the style guide.

## Content model

Hierarchy is `content/<server>/<season>/` - an article lives **directly under
its season** (e.g. `content/survival/season-4/spawn.md`). Category is **not a
folder**: it's a `categories` **taxonomy tag** (`hugo.toml [taxonomies]`
`category = 'categories'`), so a page carries one or more of build / farm /
event / puzzle / community and can be nested in subfolders freely without that
dictating its category. `data/categories.yaml` maps each category slug to its
display title + sprite icon; `partials/category.html` resolves a page's primary
category and `partials/season.html` resolves its season (by "Season N"
ancestry). The entry-card chip, single-page tag row, and the season-portal
grouping in `layouts/_default/list.html` all key off the tag, not the path.
Exceptions kept as season-nested folders: `shops/`, `public-resources/`,
`tunnels/` (data-driven) and the season `_index.md` hub pages.
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
