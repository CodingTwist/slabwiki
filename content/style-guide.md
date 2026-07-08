---
title: 'Design & Style Guide'
type: style-guide
description: 'The SlabWiki visual system — tokens, components, and conventions for building pages.'
noSearch: true
---

SlabWiki looks like the game it documents: **chunky Minecraft blocks, earth
tones, hard pixel drop-shadows, and zero rounded corners.** Everything on this
page is rendered with the *real* site classes and reads the *live* CSS
variables — so it re-themes with the dark/light toggle and never drifts from the
code.

**Source of truth:** all tokens and component classes live in
`assets/css/main.css` (the file you edit).
`assets/css/app.css` is the **generated** Tailwind output — never hand-edit it;
run `npm run css` to rebuild. For the build wiring, theming mechanics, and the
"adding a new page" walkthrough, see the repo `README.md`.
