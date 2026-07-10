# SlabWiki

The community wiki & shop directory for **Slabserver**, a Minecraft SMP. A
Hugo static site styled with Tailwind CSS v4. Content is organized by server
(e.g. Survival, Nexus), then by season, then by category (builds, farms,
events, puzzles, shops).

## Project structure

```
content/    the wiki content itself, e.g. content/survival/season-4/builds/
data/       sections.yaml (nav), categories.yaml (icons/labels), and other data-driven config
layouts/    Hugo templates - partials, list/single views, the style guide
assets/     main.css (Tailwind source) + TypeScript sources
static/     images and other files served as-is
scripts/    one-off/import scripts
```

## Requirements

- [Hugo](https://gohugo.io/) extended, v0.163.3+
- Node.js (for Tailwind + the TypeScript build)

## Clone & run locally

```bash
git clone https://github.com/CodingTwist/slabwiki.git
cd slabwiki
npm install
npm run dev
```

`npm run dev` compiles CSS and TypeScript once, then watches both alongside
`hugo server -D` at [http://localhost:1313](http://localhost:1313). Draft
pages (`draft: true` in front matter) only show up in this mode.

## Production build

```bash
npm run build   # -> ./public
```

Runs the Tailwind and TypeScript builds, then `hugo --gc --minify`. `./public`
is the deployable output - static files only, no server required.

## Deployment

Pushing to `main` triggers [`.github/workflows/`](.github/workflows/), which
runs `npm run build` and publishes `./public` to GitHub Pages. No manual
deploy step. If you need to force a rebuild without a code change (e.g. the
shop spreadsheet changed), trigger the workflow manually from the Actions tab.

## Contributing

Content and code both go through a normal git PR - see
[`/contributing`](content/contributing.md) for the policy on AI-assisted
contributions. The live style guide at `/style-guide/` is the source of truth
for the visual system.

## License

See [`LICENSE`](LICENSE): the code is MIT, the original site imagery and
visual theme are CC BY-SA 4.0, and the wiki content itself (articles, shop
listings, player/build data) belongs to the Slabserver community and isn't
covered by either license.
