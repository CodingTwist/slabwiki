#!/usr/bin/env python3
"""
Phase 2 of the SlabWiki import: maps cached wikitext (from
fetch_wiki_cache.py - run that first) into content/<server>/<season>/<category>/
markdown. Touches no network; every image it needs was already pulled into
scripts/wiki_cache/images/ by phase 1.

Handles the inline templates actually used in the curated pages' bodies
(not just the leading {{Infobox}}): {{Player|name}} and {{Item|slug}} become
{{< playerhead >}} / {{< mcicon >}} shortcode calls (see layouts/shortcodes/),
which wrap the site's existing playerhead.html / mc-icon.html partials so
there's a single source of truth for that markup. {{Quote|text=...}} becomes
a markdown blockquote, and
[[File:...]] images inside the body (not just the infobox image) are copied
into static/images/articles/ and rewritten to point at them - pandoc's
mediawiki reader doesn't know any of these templates and silently drops
their contents, which previously produced pages missing every player name
and item icon and pointing at nonexistent bare image filenames.

Writes into content/<server>/<season>/<category>/. Re-runnable, but will
overwrite hand-edited files at the slug it computes - if a page has since
been renamed or reseasoned by hand, either update KEEPERS (in
fetch_wiki_cache.py) to match or skip re-running it for that title.

Usage: python3 scripts/fetch_wiki_cache.py && python3 scripts/import_articles.py
"""
import json, os, re, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = "survival"
CONTENT = os.path.join(ROOT, "content", SERVER)
IMG = os.path.join(ROOT, "static", "images", "articles")
CACHE = os.path.join(ROOT, "scripts", "wiki_cache")
CACHE_PAGES = os.path.join(CACHE, "pages")
CACHE_IMAGES = os.path.join(CACHE, "images")
MANIFEST_PATH = os.path.join(CACHE, "manifest.json")

# Titles whose auto-slug was hand-renamed after import (the season prefix is
# redundant once nested under content/survival/<season>/, e.g. "S4Spawn" ->
# spawn.md). Re-running would otherwise recreate the old-slug file alongside
# the renamed one.
SLUG_OVERRIDES = {
    "S4Spawn": "spawn",
    "S4Spawn/Storage": "spawn-storage",
}

# Boilerplate templates to strip from the body entirely.
NOISE = re.compile(
    r"\{\{\s*(Under construction|Shop Import Message|Ambox|Distinguish|"
    r"BreadCrumbs[^}]*|Documentation|Clear|TOC[^}]*)\s*[^}]*\}\}",
    re.I,
)


def slugify(title):
    s = title.lower().replace("/", "-")
    s = re.sub(r"[’']", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def dash_slug(s):
    """'Season 4' -> 'season-4', 'Farms' -> 'farms'."""
    return re.sub(r"\s+", "-", s.strip().lower())


def split_top_level_pipes(body):
    """Split a {{...}} template's inner text on top-level `|` only."""
    parts, depth, buf = [], 0, ""
    for ch in body:
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "|" and depth == 0:
            parts.append(buf); buf = ""
        else:
            buf += ch
    parts.append(buf)
    return parts


def find_infobox(text):
    """Return (infobox_type, {k:v}, rest_of_text) for a leading {{Infobox ...}}."""
    m = re.match(r"\s*\{\{\s*(Infobox[^\n|}]*)", text)
    if not m:
        return None, {}, text
    start = text.index("{{")
    depth, i = 0, start
    while i < len(text):
        if text[i : i + 2] == "{{":
            depth += 1; i += 2; continue
        if text[i : i + 2] == "}}":
            depth -= 1; i += 2
            if depth == 0:
                break
            continue
        i += 1
    block, rest = text[start:i], text[i:]
    kind = m.group(1).strip()
    fields = {}
    for p in split_top_level_pipes(block[2:-2])[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            v = v.strip()
            if v:
                fields[k.strip()] = v
    return kind, fields, rest


def scan_templates(text):
    """Yield (start, end, name, params, positional) for every top-level
    {{...}} template (balanced-brace aware, so nested templates inside an
    unrecognised outer template are not yielded separately)."""
    i = 0
    while i < len(text):
        if text[i : i + 2] == "{{":
            start = i
            depth, j = 0, i
            while j < len(text):
                if text[j : j + 2] == "{{":
                    depth += 1; j += 2; continue
                if text[j : j + 2] == "}}":
                    depth -= 1; j += 2
                    if depth == 0:
                        break
                    continue
                j += 1
            end = j
            name_parts = split_top_level_pipes(text[start + 2 : end - 2])
            name = name_parts[0].strip()
            params, positional = {}, []
            for p in name_parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k.strip().lower()] = v.strip()
                else:
                    positional.append(p.strip())
            yield start, end, name, params, positional
            i = end
        else:
            i += 1


PLACEHOLDER_RE = re.compile(r"XWIKITPLACEHOLDERX(\d+)X")


def extract_inline_templates(body):
    """Replace {{Player|..}}, {{item|..}}, {{Quote|..}} with placeholder
    tokens that survive a pandoc round-trip unscathed, returning the
    rewritten body plus a list of what each placeholder holds."""
    placeholders = []
    out, last = [], 0
    for start, end, name, params, positional in scan_templates(body):
        lname = name.strip().lower()
        if lname == "player":
            ign = (positional[0] if positional else params.get("1", "")).strip()
            if not ign:
                continue
            data = ("player", ign)
        elif lname == "item":
            arg = (positional[0] if positional else params.get("1", "")).strip()
            if not arg:
                continue
            data = ("item", arg)
        elif lname == "quote":
            text_ = params.get("text") or params.get("quote") or (positional[0] if positional else "")
            sign = params.get("sign") or params.get("cite") or (positional[1] if len(positional) > 1 else "")
            source = params.get("source") or (positional[2] if len(positional) > 2 else "")
            data = ("quote", text_, sign, source)
        elif lname.startswith("infobox"):
            # A per-section infobox embedded mid-body (the page-level leading
            # infobox was already stripped by find_infobox before this runs).
            data = ("infobox", params)
        else:
            continue
        token = f"XWIKITPLACEHOLDERX{len(placeholders)}X"
        placeholders.append(data)
        out.append(body[last:start]); out.append(token); last = end
    out.append(body[last:])
    return "".join(out), placeholders


def to_markdown(wikitext):
    p = subprocess.run(["pandoc", "-f", "mediawiki", "-t", "gfm", "--wrap=none"],
                       input=wikitext, capture_output=True, text=True)
    return p.stdout.strip()


def player_html(ign):
    return f'{{{{< playerhead "{ign}" >}}}}'


def item_html(arg):
    slug = dash_slug(re.sub(r"[^a-zA-Z0-9 ]+", "", arg))
    return f'{{{{< mcicon "{slug}" >}}}}'


# Fields common to a {{Infobox ...}} template, in display order. Shared by
# the page-level front-matter infobox and the inline {{< infobox >}}
# shortcode used for per-section infoboxes embedded mid-body (e.g. a page
# listing several builds, each with its own {{Infobox Project}}).
INFOBOX_FIELD_MAP = [
    ("status", "Status"), ("builders", "Builders"), ("designers", "Designers"),
    ("world", "World"), ("date_started", "Started"), ("date_completed", "Completed"),
    ("owners", "Owners"), ("project_type", "Type"),
]


def infobox_fields(fields, manifest_images):
    out = []
    img_field = fields.get("image", "")
    if img_field:
        local = resolve_image(img_field, manifest_images)
        if local:
            out.append(("image", local))
    for k, label in INFOBOX_FIELD_MAP:
        if fields.get(k):
            v = re.sub(r"[\[\]]", "", fields[k])
            # builders/designers/owners are literal IGNs (which may
            # themselves start with an underscore, e.g. "_P0ny") - only
            # other fields use "_" as a MediaWiki space encoding.
            if k not in ("builders", "designers", "owners"):
                v = v.replace("_", " ")
            out.append((label, v))
    coords = [fields[c] for c in ("world_x", "world_y", "world_z") if fields.get(c)]
    if coords:
        out.append(("Coordinates", " ".join(coords)))
    return out


def infobox_map(fields, manifest_images):
    """Build an ordered {label: value} map for a per-section infobox, with a
    leading `title` (the {{Infobox|name=...}}). Returns None if it has no
    renderable fields at all (e.g. an empty {{Infobox}})."""
    pairs = infobox_fields(fields, manifest_images)
    if not pairs:
        return None
    box = {}
    name = fields.get("name", "").strip().replace("_", " ")
    if name:
        box["title"] = name
    for k, v in pairs:
        box[k] = v
    return box


def resolve_placeholders(md, placeholders, manifest_images):
    def repl(m):
        data = placeholders[int(m.group(1))]
        kind = data[0]
        if kind == "player":
            return player_html(data[1])
        if kind == "item":
            return item_html(data[1])
        if kind == "infobox":
            # Pulled out of the body and rendered in the sidebar (see main);
            # drop the placeholder from the prose entirely.
            return ""
        # quote: recursively process the quoted text (it's raw wikitext -
        # may itself contain formatting or a nested {{Player}} signature)
        _, text_, sign, source = data
        inner_body, inner_ph = extract_inline_templates(text_)
        inner_md = resolve_placeholders(to_markdown(inner_body), inner_ph, manifest_images)
        lines = ["> " + ln for ln in inner_md.splitlines()] or ["> "]
        if sign:
            attrib = f"— {sign}" + (f", {source}" if source else "")
            lines += [">", "> " + attrib]
        # the {{Quote}} template may appear mid-sentence in the source
        # wikitext; blockquotes are block-level, so force paragraph breaks
        # around it or it just renders as a literal "> " inline.
        return "\n\n" + "\n".join(lines) + "\n\n"
    return PLACEHOLDER_RE.sub(repl, md)


def resolve_image(filename, manifest_images):
    """Look up a raw MediaWiki File: name in the phase-1 image cache, copy it
    into static/images/articles/ under a slugified name, and return the
    public path (or None if it was never fetched)."""
    entry = (manifest_images.get(filename) or manifest_images.get(filename.replace("_", " "))
             or manifest_images.get(filename.replace(" ", "_")))
    if not entry:
        return None
    cache_file = entry["cache_file"]
    ext = os.path.splitext(cache_file)[1]
    out_name = slugify(os.path.splitext(filename)[0]) + ext
    dst = os.path.join(IMG, out_name)
    if not os.path.exists(dst):
        os.makedirs(IMG, exist_ok=True)
        shutil.copyfile(os.path.join(CACHE_IMAGES, cache_file), dst)
    return "/images/articles/" + out_name


IMG_MD_RE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)')


def rewrite_body_images(md, manifest_images):
    def repl(m):
        alt, src, title = m.group(1), m.group(2), m.group(3)
        local = resolve_image(src, manifest_images)
        if not local:
            print(f"    ! inline image not in cache, dropping: {src}")
            return alt
        out = f"![{alt}]({local}"
        if title:
            out += f' "{title}"'
        return out + ")"
    return IMG_MD_RE.sub(repl, md)


def yaml_val(v):
    v = re.sub(r"\\(.)", r"\1", v)
    v = re.sub(r"\s+", " ", v).replace("'", "''").strip()
    return "'" + v + "'"


SEASON_MAP = {"survivals4": "Season 4", "survivals3": "Season 3",
              "survivals2": "Season 2", "survivals1": "Season 1"}


def norm_season(s):
    s = s.strip()
    key = s.lower()
    if key in SEASON_MAP:
        return SEASON_MAP[key]
    m = re.fullmatch(r"(?:season\s*)?(\d+)", key)
    return f"Season {m.group(1)}" if m else s


# slug -> (season, category, output_slug) for kept pages, used to resolve
# internal wikilinks to their real (not nominal-default) location.
KEEPER_SLUGS = {}


def rewrite_wikilinks(md):
    """Rewrite pandoc's [Text](Target "wikilink") into a live internal link
    when we imported the target, otherwise drop to plain text (no dead links)."""
    def repl(m):
        text, target = m.group(1), m.group(2)
        hit = KEEPER_SLUGS.get(slugify(target.replace("_", " ")))
        if hit:
            season, category, slug = hit
            return f"[{text}](/{SERVER}/{dash_slug(season)}/{dash_slug(category)}/{slug}/)"
        return text
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\s+"wikilink"\)', repl, md)


def main():
    if not os.path.exists(MANIFEST_PATH):
        raise SystemExit("No wiki_cache/manifest.json - run scripts/fetch_wiki_cache.py first.")
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    manifest_images = manifest["images"]

    # Pass 1: parse infobox + resolve each page's *actual* season, so
    # internal wikilinks in pass 2 point at where a page really ends up.
    pages = {}
    for title, meta in manifest["pages"].items():
        with open(os.path.join(CACHE_PAGES, meta["cache_file"])) as f:
            text = f.read()
        kind, fields, body = find_infobox(text)
        season = fields.get("season", "")
        season = norm_season(season) if season else meta["season"]
        category = meta["category"]
        slug = SLUG_OVERRIDES.get(title, slugify(title))
        pages[title] = (category, season, fields, body, slug)
        KEEPER_SLUGS[slugify(title)] = (season, category, slug)

    written = 0
    for title, (category, season, fields, body, slug) in pages.items():
        body = NOISE.sub("", body)
        body, placeholders = extract_inline_templates(body)
        section_boxes = [b for b in (infobox_map(p[1], manifest_images)
                                     for p in placeholders if p[0] == "infobox")
                         if b]
        md = to_markdown(body)
        md = resolve_placeholders(md, placeholders, manifest_images)
        md = rewrite_body_images(md, manifest_images)
        md = rewrite_wikilinks(md)
        if len(md) < 120 and not fields:
            print(f"  - skip (too thin): {title}")
            continue

        fm = {"title": title.replace("_", " ")}
        infobox = dict(infobox_fields(fields, manifest_images))

        lines = ["---", f"title: {yaml_val(fm['title'])}"]
        if infobox:
            lines.append("infobox:")
            for k, v in infobox.items():
                lines.append(f"  {k}: {yaml_val(str(v))}")
        if section_boxes:
            lines.append("infoboxes:")
            for box in section_boxes:
                first = True
                for k, v in box.items():
                    prefix = "  - " if first else "    "
                    lines.append(f"{prefix}{k}: {yaml_val(str(v))}")
                    first = False
        lines.append("---\n")
        out = "\n".join(lines) + md + "\n"

        out_dir = os.path.join(CONTENT, dash_slug(season), dash_slug(category))
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, slug + ".md")
        with open(path, "w") as f:
            f.write(out)
        written += 1
        print(f"  ✓ {title}  ->  {os.path.relpath(path, ROOT)}")
    print(f"\nWrote {written} articles.")


if __name__ == "__main__":
    main()
