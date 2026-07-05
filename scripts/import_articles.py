#!/usr/bin/env python3
"""
One-shot importer: pulls a curated set of SlabWiki articles from the live
MediaWiki API, lifts their {{Infobox ...}} into YAML front matter, downloads
referenced images, and converts the prose to Markdown via pandoc.

Writes into the current content/<server>/<season>/<category>/ layout (all
KEEPERS are Survival-world pages). An `aliases` entry preserves the old flat
/articles/<slug>/ URL. Re-runnable, but will overwrite hand-edited files at
the slug it computes - if a page has since been renamed or reseasoned by
hand, either update KEEPERS to match or skip re-running it for that title.

Skips near-empty pages. Usage: python3 scripts/import_articles.py
"""
import json, os, re, subprocess, sys, urllib.parse, urllib.request

API = "https://wiki.slabserver.org/w/api.php"
UA = "SlabWikiArchiver/1.0 (static-site migration)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = "survival"
CONTENT = os.path.join(ROOT, "content", SERVER)
IMG = os.path.join(ROOT, "static", "images", "articles")

# Curated keepers (main namespace) mapped to a category + season.
# category drives the taxonomy; season falls back to this when the infobox
# has none. Prune / retune freely.
KEEPERS = {
    "Public Iron Farm":      ("Farms", "Season 4"),
    "Public Blaze farm":     ("Farms", "Season 4"),
    "Public Froglight Farm": ("Farms", "Season 4"),
    "Public Shulker Farm":   ("Farms", "Season 4"),
    "(Gibb's) Witch Farm":   ("Farms", "Season 4"),
    "Ender Ender":           ("Farms", "Season 4"),
    "S4Spawn":               ("Builds", "Season 4"),
    "S4Spawn/Storage":       ("Builds", "Season 4"),
    "Season3 Spawn":         ("Builds", "Season 3"),
    "S4 Games District":     ("Events", "Season 4"),
    "S4 Outposts":           ("Builds", "Season 4"),
    "SurvivalS4 Puzzle":     ("Puzzles", "Season 4"),
    "The Disc 11 Puzzle":    ("Puzzles", "Season 4"),
    "The Passage":           ("Puzzles", "Season 4"),
    "The Tunnel":            ("Puzzles", "Season 4"),
    "Survival Puzzles":      ("Puzzles", "Season 4"),
    "Decked Out":            ("Events", "Season 4"),
    "Fish Cult":             ("Community", "Season 4"),
    "TFC Gamenight 2024":    ("Events", "Season 4"),
    "Season2":               ("Community", "Season 2"),
    "Season3":               ("Community", "Season 3"),
    "SurvivalS3":            ("Community", "Season 3"),
    "SurvivalS4":            ("Community", "Season 4"),
}

# Boilerplate templates to strip from the body entirely.
NOISE = re.compile(
    r"\{\{\s*(Under construction|Shop Import Message|Ambox|Distinguish|"
    r"BreadCrumbs[^}]*|Documentation|Clear|TOC[^}]*)\s*[^}]*\}\}",
    re.I,
)


def api(params):
    params["format"] = "json"
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def slugify(title):
    s = title.lower().replace("/", "-")
    s = re.sub(r"[’']", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def dash_slug(s):
    """'Season 4' -> 'season-4', 'Farms' -> 'farms'."""
    return re.sub(r"\s+", "-", s.strip().lower())


def find_infobox(text):
    """Return (infobox_type, {k:v}, rest_of_text) for a leading {{Infobox ...}}."""
    m = re.match(r"\s*\{\{\s*(Infobox[^\n|}]*)", text)
    if not m:
        return None, {}, text
    # balanced-brace scan from the start of the template
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
    # split on top-level pipes only
    body = block[2:-2]
    parts, depth, buf = [], 0, ""
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "|" and depth == 0:
            parts.append(buf); buf = ""
        else:
            buf += ch
    parts.append(buf)
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            v = v.strip()
            if v:
                fields[k.strip()] = v
    return kind, fields, rest


def download_image(filename):
    """Resolve a File: name to its URL and download into static/images/articles."""
    try:
        d = api({"action": "query", "titles": "File:" + filename,
                 "prop": "imageinfo", "iiprop": "url"})
        page = next(iter(d["query"]["pages"].values()))
        src = page["imageinfo"][0]["url"]
    except Exception as e:
        print(f"    ! image resolve failed for {filename}: {e}")
        return None
    ext = os.path.splitext(src)[1] or ".png"
    local = slugify(os.path.splitext(filename)[0]) + ext
    os.makedirs(IMG, exist_ok=True)
    dst = os.path.join(IMG, local)
    if not os.path.exists(dst):
        try:
            req = urllib.request.Request(src, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
                f.write(r.read())
        except Exception as e:
            print(f"    ! image download failed for {filename}: {e}")
            return None
    return "/images/articles/" + local


def to_markdown(wikitext):
    p = subprocess.run(["pandoc", "-f", "mediawiki", "-t", "gfm", "--wrap=none"],
                       input=wikitext, capture_output=True, text=True)
    return p.stdout.strip()


def yaml_val(v):
    # Drop pandoc backslash-escapes (\-, \[ …) and normalise, then single-quote.
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


# slug -> (season, category) for kept pages, used to resolve internal wikilinks
KEEPER_SLUGS = {}


def rewrite_wikilinks(md):
    """Rewrite pandoc's [Text](Target "wikilink") into a live internal link
    when we imported the target, otherwise drop to plain text (no dead links)."""
    def repl(m):
        text, target = m.group(1), m.group(2)
        slug = slugify(target.replace("_", " "))
        hit = KEEPER_SLUGS.get(slug)
        if hit:
            season, category = hit
            return f"[{text}](/{SERVER}/{dash_slug(season)}/{dash_slug(category)}/{slug}/)"
        return text
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\s+"wikilink"\)', repl, md)


def main():
    for t, (cat, season) in KEEPERS.items():
        KEEPER_SLUGS[slugify(t)] = (season, cat)
    written = 0
    for title, (category, default_season) in KEEPERS.items():
        d = api({"action": "query", "prop": "revisions", "rvprop": "content",
                 "rvslots": "main", "titles": title})
        page = next(iter(d["query"]["pages"].values()))
        if "revisions" not in page:
            print(f"  - skip (missing): {title}")
            continue
        text = page["revisions"][0]["slots"]["main"]["*"]
        if text.strip().upper().startswith("#REDIRECT"):
            print(f"  - skip (redirect): {title}")
            continue

        kind, fields, body = find_infobox(text)
        body = NOISE.sub("", body)
        md = rewrite_wikilinks(to_markdown(body))
        if len(md) < 120 and not fields:
            print(f"  - skip (too thin): {title}")
            continue

        # front matter
        season = fields.get("season", "")
        season = norm_season(season) if season else default_season
        slug = slugify(title)
        fm = {"title": title.replace("_", " ")}
        desc = md.split("\n\n", 1)[0]
        desc = re.sub(r"[#*_`>\[\]]", "", desc).strip()
        if desc:
            fm["description"] = desc[:180]

        img_field = fields.get("image", "")
        infobox = {}
        if img_field:
            local = download_image(img_field)
            if local:
                infobox["image"] = local
        # keep a tidy set of infobox facts if present
        for k, label in [("status", "Status"), ("builders", "Builders"),
                         ("designers", "Designers"), ("world", "World"),
                         ("date_started", "Started"), ("date_completed", "Completed"),
                         ("owners", "Owners"), ("project_type", "Type")]:
            if fields.get(k):
                infobox[label] = re.sub(r"[\[\]]", "", fields[k]).replace("_", " ")
        coords = []
        for c in ("world_x", "world_y", "world_z"):
            if fields.get(c):
                coords.append(fields[c])
        if coords:
            infobox["Coordinates"] = " ".join(coords)

        lines = ["---", f"title: {yaml_val(fm['title'])}",
                  f"aliases: [{yaml_val('/articles/' + slug + '/')}]"]
        if "description" in fm:
            lines.append(f"description: {yaml_val(fm['description'])}")
        if infobox:
            lines.append("infobox:")
            for k, v in infobox.items():
                lines.append(f"  {k}: {yaml_val(str(v))}")
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
