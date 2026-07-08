---
title: 'Goodbye, MediaWiki'
author: GamingTwist
tags: [meta]
date: 2026-07-06
description: 'Why the community wiki left MediaWiki behind for a static Hugo site.'
summary: "MediaWiki worked, until it didn't. Here's what pushed us to rebuild the wiki on Hugo instead."
---
This wiki used to run on [MediaWiki](https://www.mediawiki.org/), the same software behind [Wikipedia](https://www.wikipedia.org/). If it can hold the sum of human knowledge so it should be able to hold a Minecraft server's shop list, that was the thinking anyway. It was picked at different time in the project, since there have been a lot of issues. So it's moving to Hugo, a static site. Here's what it actually looked like, I'll give a retrospective.

## Getting it running

The install itself wasn't bad. It ran in [Pterodactyl](https://pterodactyl.io/), the same panel we use for every game server, using an normal nginx image for it. Pointed it at a database, walk through the web setup, done. That part took maybe an hour. Everything after "it's installed" is where the actual project started, and where it stopped being that easy.

## Discord login

I wanted people to log in with Discord instead of making separate wiki accounts. Everyone who would edit it was in the Discord, so login should just be that. Then it can stop edits from outside the community.

Doing it meant going into MediaWiki's auth system directly. I managed to get it working using a custom PHP extension I wrote for it. Logins are instant, no separate password to remember. But it was more hours in unfamiliar PHP than a login button should ever cost.

## Structure I couldn't build

What I actually wanted was hierarchy. Servers, then seasons under each server, then categories under each season, then pages under that. A real tree, matching how the wiki is actually organized in my head and how it's organized now on Hugo (this site).

MediaWiki's answer to structured data is [SMW (Semantic MediaWiki)](https://www.semantic-mediawiki.org/) or [Cargo](https://www.mediawiki.org/wiki/Extension:Cargo), extensions that let a page carry fields and get queried like a database. I used both, at different points, trying to get this working. I even bought a book on Cargo, that's how serious the attempt was. They're flat by design. Good for "give me every shop owned by this player". I could store the data. I could query the data. I could not make it nest the way I needed in the URL. I did get something working, but it was not good and every page felt empty.

I also tried to make editing itself as simple as I could, since not everyone wants to learn wikitext just to add a build. I set up [Page Forms](https://www.mediawiki.org/wiki/Extension:Page_Forms) hooked into Cargo, so instead of writing a page by hand you'd fill out an actual form and it would generate the page and the Cargo data from that. It sounded like the answer to a lot of this at once, simple editing and structured data in one move. In practice no one really used this feature.

## Infoboxes needed Lua

The little infobox on the side of a page, that's usually built on [Lua](https://www.lua.org/) modules through the [Scribunto](https://www.mediawiki.org/wiki/Extension:Scribunto) extension on any wiki that's doing it properly. My Docker image could not run Lua.

So getting infoboxes working meant learning how Pterodactyl eggs work, the templates that define what a server image actually installs and runs, and building my own with Lua baked in. A lot of work to just so a page could show a little box of stats in the corner.

## Theming

Found a skin called [Citizen](https://www.mediawiki.org/wiki/Skin:Citizen). Looked a lot better than the MediaWiki default, more modern, less like a 2005 forum. But it wasn't very changeable past its own settings, and it broke in odd ways once other extensions were running alongside it, bugs that only showed up with everything stacked together, not in isolation. Never got it to a point where it felt like it was actually built for this wiki. I wanted a Discord link in the sidebar too but there was no clean way to add one, so I had to it injected with JavaScript instead.

## The custom map

I reverse engineered the in-game map [p3lxmap](https://github.com/pl3xgaming/Pl3xMap), so I could control the frontend and loaded it into MediaWiki's map extension so people could click around and see where shops and builds actually were in the world.

Worked great, until it started throwing errors. The extension plots everything in latitude and longitude, which has a hard cap built in, because normally that's meant for a small area on a real-world map, not a Minecraft world where X and Z just keep climbing the further you build from spawn. Go out far enough and you blow past that cap and the extension just errors out instead of placing anything. So it got split: infoboxes used the real embedded map, the shop list used the custom one since every shop was >1000 away from 0 0.

## Slow all the way through

No single one of these would have been enough to leave. It's the pace. Every feature took longer than it had any right to, and because every feature ate so much time just to get working at all, the navigation never got real attention. It stayed an afterthought the whole time the wiki was live, and it never once felt like a real wiki because of it. It felt like I was fighting MediaWiki more than I was using it.

## Not what the vote promised

The community voted for this. A wiki was something people asked for, and when it came to actually deciding whether to build it, the vote was in favor. That's the part that stings a bit looking back.

Because when it actually existed, when the login worked and the pages were up and anyone could edit, it was a handful of people who ever posted anything. Not the whole community that voted for it. A handful. Everyone else who wanted it built just never came back to use it just not what the site is built around. Everything else was never really "user-generated" in the MediaWiki sense to begin with, it just happened to be hosted on.

I don't say that to guilt anyone, people are busy and a wiki is not owed anyone's time. But it's a real part of why this rebuild happened the way it did. If people had actually been in there editing, I'd have happily stuck with the PHP, headaches and all. But they weren't, and a small group of people were always going to be the ones adding content regardless. Building for "anyone can click edit" was solving a problem that didn't really exist here. Building for "a few people who actually will contribute, working through git" fits what actually happened a lot better than what the vote implied would happen.

## 2,517 edits

My personal wiki's own edit count says 2,517. That's not a number I went looking for, that's just what it landed on, and looking back at it now it's a lot to take in.

There were nights I stayed late after work just to keep working on this. It ate up a real chunk of my free time, more than I probably would have admitted at the time. Eventually I shifted most of my attention over to the Nexus project while the wiki kept running in the background, mostly untouched. But it never really left my head. I always felt like this project could be good, properly good, if it got the chance, even while it sat there quiet for months.

Writing this post is partly about that. It's a way of putting all that time somewhere instead of just letting it disappear when the PHP site comes down. And now, on the other side of it, the maintenance load on the new site is basically zero. No server to keep patched, no database to babysit.

## Months of nothing

The wiki sat idle for months. No edits, no new pages, nothing. Meanwhile a full PHP application and a database sat there running around the clock, burning roughly 200MB of memory just to stay up.

And it wasn't even sitting there quietly.

10GB of traffic a day. *Thanks [ClaudeBot](https://www.theverge.com/2024/7/25/24205943/anthropic-ai-web-crawler-claudebot-ifixit-scraping-training-data)*, crawling every page over and over. Not a single real visitor behind most of that, just an AI crawler hammering a PHP wiki that nobody was reading or editing anymore.

## Hugo

Now it's [Hugo](https://gohugo.io/). Static, built ahead of time, no PHP, no database, no extensions to keep balanced against each other. This didn't feel like fighting the tool at any point. I was fully in control of it the whole way through.

The MediaWiki setup took months to get working, on and off, spread across the auth work, the Lua egg, the theming, the map. This whole rebuild, the entire site you're reading this on, took a week.

None of the actual content got left behind either. Tho a few of the blank pages were ignored. Every page that got moved over to this site, so nothing that was written or built up over that time is gone. It's archived here instead of sitting on a PHP server nobody was touching.

## From UGC to a directory

There's a bigger shift buried in all this that's worth calling out on its own: this stopped being a wiki in the traditional sense and became a directory.

MediaWiki's whole model is user-generated content. Anyone can open a page and change it. That's the point of the software. But almost nothing on this wiki actually worked like that in practice. The shop pages weren't written free-form, they came from a Google Sheet shop owners filled in, matched up to images by filename. Most of what this wiki actually is, is data, arranged and displayed, not articles anyone wandered in and wrote.

So building it as a static site isn't really a downgrade from "real wiki" to "lesser wiki." It's admitting what it already was. A shop list generated from a spreadsheet at build time. That's a directory, not an wiki. Hugo is a much better fit for a directory than MediaWiki ever was, because a directory's job is to take structured data and lay it out well, and that's exactly what a static site generator is built to do.

The parts that were genuinely free-form writing, the actual articles, are still articles, and anyone can still contribute to them. Editing just isn't the focus anymore. It's a git PR now instead of a click-to-edit box, which is a higher bar, but it's still possible, it's just not what the site is built around. Everything else was never really "user-generated" in the MediaWiki sense to begin with, it just happened to be hosted on software built for that.

## What I actually got out of it

Wasn't all pain. A few things stuck.

Honestly, I did enjoy the project. It was so far outside my normal comfort zone, PHP, Lua, MediaWiki's whole ecosystem, none of it was stuff I'd touch day to day. But I like tinkering, and this gave me a lot to tinker with.

Pterodactyl. Before this I used it the normal way: pick an egg, click install, done. Building a custom one for the Lua support meant learning what an egg actually is under the hood. I understand the panel now instead of just using it.

My nginx skills got good too. Between the custom egg and just keeping the thing routed and running, I stopped copy-pasting configs and started actually understanding what they did.

The PHP and auth work carried further than the login button. While I was in there I also tried to get the wiki itself acting as an [OAuth](https://oauth.net/) provider, so a [Kanboard](https://kanboard.org/) board could let people log in with their wiki account. The idea was to use it to help direct people to tasks. That part never worked. But it's where I actually learned OAuth properly.

The Cargo fight taught me what a flat data model can and can't do. That's the direct reason the Hugo site's structure, actually nests the way I wanted from the start instead of faking it with categories again.

I also came out with a better sense of project management. Mainly, don't trust that someone's going to do something just because they said they would. Wait until you actually see them doing it before you plan around them.

And the map reverse engineering didn't go to waste. It is what's running the map on this site right now.

## What we lose

The friendly in-browser editor is gone. That's the real tradeoff, and I'm not going to pretend it isn't one. Editing now works the same way the main site works: through a git PR, not a click-to-edit box anyone with an account could open.

## Thanks

Before I close this out, a few people actually did show up and I want to name them.

{{< playerhead "DaMarine" >}} was the MVP of the whole project. Believed in it when it was just me pushing on it, and wrote some genuinely amazing puzzle pages, like [The Disc](/survival/season-2/the-disc-11-puzzle/) and [The Tunnel](/survival/season-3/the-tunnel/). {{< playerhead "PurpleKiiwi" >}} wrote a great shop page. {{< playerhead "StoryCatBuilds" >}} stepped up more than once and put together some really good pages. That's the handful I mentioned earlier, and they're the reason this wasn't a total waste of time.
