# SlabWiki

The community wiki & shop directory for **Slabserver**, a Minecraft SMP. A Hugo
static site styled with Tailwind CSS v4, themed after the "SlabServer Wiki 1B"
design: Silkscreen pixel display type, chunky near-black borders, hard offset
shadows, a pixelated checkerboard background, and a light/dark theme toggle.

## Requirements

- [Hugo](https://gohugo.io/) (extended not required)
- Node.js (for the Tailwind CLI)

```bash
npm install        # installs @tailwindcss/cli
npm run dev        # Tailwind watch + hugo server -D on http://localhost:1313
npm run build      # production build → ./public (purged, minified CSS)
```

`npm run dev` compiles the CSS once, then runs the Tailwind `--watch` compiler
and the Hugo dev server together. `npm run build` recompiles the CSS and runs
`hugo --gc --minify`.

## How the styling is wired

CSS lives in `assets/css/` and is compiled by the Tailwind CLI, **not** Hugo
Pipes for the Tailwind step:

- `assets/css/main.css` - the source: `@import "tailwindcss"`, the theme
  tokens, and all component classes. This is the file you edit.
- `assets/css/app.css` - the compiled output (generated; do not edit).
- `assets/css/mc-items.css` - the Minecraft item sprite sheet (hand-maintained;
  drives `partials/mc-icon.html`).

Hugo then fingerprints and minifies `app.css` / `mc-items.css` via
`resources.Get` in `layouts/_default/baseof.html`. Because the Tailwind CLI
reads `main.css` directly (Hugo isn't in that loop), the source points the
scanner at the templates explicitly:

```css
@source "../../layouts";
```

Keep that line - without it Tailwind can't see which classes the templates use
and will purge them.

## How theming works

One palette, two sets of values, driven by a `data-theme` attribute on `<html>`:

1. **Tokens** - `@theme` in `main.css` maps Tailwind color utilities to CSS
   variables, e.g. `--color-grass: var(--c-grass)`. Utilities like `bg-grass`
   or `border-line` therefore resolve through a live `var()`, so flipping the
   theme re-colors everything without a rebuild.
2. **Palettes** - the `--c-*` variables are defined three times:
   - `:root, :root[data-theme="dark"]` → the **dark** palette (the default).
   - `:root[data-theme="light"]` → the **light** palette.
   - a `prefers-color-scheme: light` block for visitors who haven't chosen.
3. **Dark variant** - `@custom-variant dark { … }` makes Tailwind's `dark:`
   utilities apply whenever the resolved theme is dark (explicit or OS).
4. **Toggle** - `partials/theme-toggle.html` writes the choice to
   `localStorage('slab-theme')` and sets `data-theme`. A tiny script in the
   `<head>` of `baseof.html` reads that value **before paint** to avoid a flash
   of the wrong theme.

To retune a color, edit the `--c-*` value in both the dark and light blocks (and
the `prefers-color-scheme` block) in `main.css`. Don't hardcode hex in
templates - use the `bg-*` / `text-*` / `border-*` utilities so both themes
stay in sync.

### Signature component classes

Defined in the `@layer components` block of `main.css`, reused across templates
instead of inline styles:

| Class | Purpose |
|---|---|
| `.mc-frame` | The page wrapper - 4px border + `12px 12px 0` hard shadow |
| `.mc-panel` / `.mc-panel-grass` | Heavy panels (hero, article, infobox); grass variant for the header |
| `.mc-card` + `.mc-card-hover` | Blocky card with hard offset shadow and steppy hover nudge |
| `.mc-btn` (+ `-grass` / `-gold` / `-dark`) | Chunky pixel buttons |
| `.mc-badge` (+ `-grass` / `-gold`) | Pixel tag chips (season, FEATURED, NEW/EDIT) |
| `.mc-input` | Inset search field |
| `.checker-bg` | Pixelated checkerboard page background |
| `.stripe-grass` / `.stripe-divider` | Repeating grass accent bar / title rule |
| `.section-h` | Pixel section heading with a soft underline |
| `.pixel` / `.pixel-label` | Silkscreen display type / micro-labels |

## Project structure

```
assets/css/          main.css (source), app.css (built), mc-items.css (sprites)
data/sections.yaml    the section list - worlds + workshop (drives Explore nav + sidebar)
content/
  <server>/_index.md      section root; cascades a `server` param to children
  <server>/<season>/      a season, e.g. survival/season-4
    <category>/           a category under that season, e.g. builds, farms, shops
      _index.md           category index (title + icon)
      my-page.md           an actual wiki page
  server-info/        cross-server reference (rules, guides)
layouts/
  _default/baseof.html   chrome: frame, header, breadcrumb strip, footer
  _default/single.html   article + infobox
  _default/list.html     section index (server / season / category listing)
  index.html             home page (hero, stats, servers, featured, recent)
  index.json             client-side search index (emitted as /index.json)
  shops/                 shop list (with client-side filter) + shop single
  server-info/           server-info list + single
  partials/
    theme-toggle.html    light/dark toggle chip
    breadcrumbs.html     breadcrumb content (rendered in the baseof strip)
    sidebar.html         server-aware nav + server-status panel
    server-status.html   live player count (mcsrvstat.us) with graceful fallback
    entry-card.html      the reusable card used by grids
    mc-icon.html         renders a sprite from mc-items.css
```

### Content model in brief

There are no Hugo taxonomies (`[taxonomies]` is explicitly emptied in
`hugo.toml`) - the hierarchy is just nested sections:

- **Sections** are the top axis (`content/survival/`, `content/nexus/`,
  `content/workshop/`). Most are game worlds; Workshop is the general blog -
  tech write-ups, updates, or anything else the crew wants to post (flagged
  `kind: blog` in the data file). Each `content/<slug>/_index.md`
  cascades a `server` param that templates and the sidebar key off.
  `data/sections.yaml` drives the Explore nav, sidebar, and each section's
  icon/quicklinks.
- **Seasons** (`content/survival/season-4/`) and **categories**
  (`.../season-4/builds/`) are just nested sections underneath a server, each
  with its own `_index.md` for title/icon. `params.currentSeason` in
  `hugo.toml` is informational only (used to badge the current season).

## Adding a new wiki page

1. Create a Markdown file under the right server/season/category, e.g.
   `content/survival/season-4/builds/my-build.md`:

   ```markdown
   ---
   title: 'My Build'
   description: 'One-line summary shown on cards and in search.'
   infobox:                     # optional - renders the right-hand infobox
     image: '/images/articles/my-build.png'
     Status: 'Complete'
     Builders: 'yourname'
     Coordinates: '123 -45'     # a "Coordinates" key becomes a copy-chip
   ---

   Write the article body in Markdown. `## Headings` become pixel section
   headers automatically.
   ```

2. Drop any images under `static/images/…` (referenced from `/images/…`).
3. Run `npm run dev` and the page appears on its category/season listing, in
   search, and (if flagged) on the home page.

To add a whole new **category**, create the folder with an `_index.md`
(`title` + an `item` icon slug from `assets/css/mc-items.css`) under the
right season. To add a whole new **server**, add an entry to
`data/sections.yaml` and create `content/<slug>/_index.md`.

## Notes

- The live server status panel reads `params.serverAddress` in `hugo.toml` and
  queries mcsrvstat.us client-side; if the API is unreachable it degrades to a
  quiet "status unavailable" line.
- Shop pages are generated at build time from a published Google Sheet CSV -
  see `params.shopsCsvUrl` and
  `content/survival/season-4/shops/_content.gotmpl`. It fails gracefully
  (renders no shops) if the sheet is unreachable at build time.
- `scripts/import_articles.py` is a one-shot script that imported the original
  MediaWiki content into an earlier flat `content/articles/` layout; it
  predates the current server/season/category structure and would need
  updating before it could be re-run.

## License

See [`LICENSE`](LICENSE): the code is MIT, the original site imagery and
visual theme are CC BY-SA 4.0, and the wiki content itself (articles, shop
listings, player/build data) belongs to the Slabserver community and isn't
covered by either license.
