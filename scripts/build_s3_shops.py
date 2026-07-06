#!/usr/bin/env python3
"""
One-shot generator for the STATIC Season 3 shop pages.

Season 3 has ended, so unlike the build-time-generated S4 shops these pages are
committed markdown. Each S3 shop is a wiki page whose wikitext holds THREE
things, which we split into Hugo's native data/content model:

  * {{Infobox Shop}}      -> front matter (title, owners, loc, image)
  * {{Shop Item}} blocks  -> front matter `items:` (name/material/inStock).
                             These never populated the Shop_Item cargo table for
                             S3, so they only exist inline in the wikitext.
  * prose body            -> the markdown body, rendered by layouts/shops/single.html

Front matter is what the shop LIST page searches/filters on; the body is prose
shown only on the single page. Hugo merges them at build time.

Re-runnable: overwrites content/survival/season-3/shops/*.md (except _index.md)
and fetches any inline [[File:]] images into static/images/season-3-shops/.

Usage: python3 scripts/build_s3_shops.py
"""
import html, json, os, re, urllib.parse, urllib.request

API = "https://wiki.slabserver.org/w/api.php"
UA = "SlabWikiArchiver/1.0 (static-site migration)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOPS_DIR = os.path.join(ROOT, "content", "survival", "season-3", "shops")
IMG_DIR = os.path.join(ROOT, "static", "images", "season-3-shops")
IMG_WEB = "/images/season-3-shops"


def api(params):
    params["format"] = "json"
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def slugify(name):
    s = name.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 -]", "", s)
    s = re.sub(r"[ -]+", "-", s).strip("-")
    return s or "shop"


def material_of(item):
    """Best-effort Minecraft icon slug from a stock item's display name."""
    s = re.sub(r"\([^()]*\)", "", item)          # drop "(all types)", "(Flower Box)"
    s = s.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s


def clean_owners(raw):
    parts = [p.strip().strip(".").strip() for p in html.unescape(raw or "").split(",")]
    return ", ".join(p for p in parts if p)


def yaml_str(v):
    """Quote a scalar for YAML only when needed."""
    if v == "" or re.search(r'[:#\[\]{}",&*!|>%@`]', v) or v != v.strip():
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


ITEM_RE = re.compile(r"\{\{\s*Shop Item\s*(.*?)\}\}", re.I | re.S)


def parse_items(body):
    items, seen = [], set()
    for m in ITEM_RE.finditer(body):
        fields = {}
        for part in m.group(1).split("|")[1:]:
            if "=" in part:
                k, _, val = part.partition("=")
                fields[k.strip().lower()] = val.strip()
        name = html.unescape(fields.get("item", "").strip())
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        status = fields.get("status", "").strip().lower()
        in_stock = status in ("yes", "in stock", "true", "")
        items.append({"name": name, "material": material_of(name), "inStock": in_stock})
    return items


def fetch_inline_image(filename):
    """Download a [[File:]] image; return its web path (or None on failure)."""
    local = filename.replace(" ", "_")
    dst = os.path.join(IMG_DIR, local)
    web = f"{IMG_WEB}/{local}"
    if os.path.exists(dst):
        return web
    try:
        d = api({"action": "query", "titles": "File:" + filename,
                 "prop": "imageinfo", "iiprop": "url"})
        src = next(iter(d["query"]["pages"].values()))["imageinfo"][0]["url"]
        req = urllib.request.Request(src, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
            f.write(r.read())
        print(f"    ~ fetched inline image {filename} -> {local}")
        return web
    except Exception as e:
        print(f"    ! inline image failed for {filename}: {e}")
        return None


PLAYER_RE = re.compile(r"\{\{\s*player\s*\|\s*([^}|]+?)\s*\}\}", re.I)


def file_link_to_md(m):
    """[[File:Name.png|thumb|690x690px|Caption|left]] -> ![Caption](web "Caption").
    Both alt and title carry the caption, matching import_articles.py's
    convention - render-image.html only surfaces the `title` attribute, so
    without it the caption text would be silently dropped from the page.
    Captions become plain HTML attribute text, so any {{player|Name}} inside
    one resolves to a bare name here rather than the playerhead shortcode
    (whose <span><img> markup can't nest inside an alt/title string)."""
    inner = m.group(1)
    parts = [p.strip() for p in inner.split("|")]
    fname = parts[0]
    caption = ""
    for p in parts[1:]:
        if re.fullmatch(r"(thumb|thumbnail|frame|frameless|border|left|right|center|none|\d+x?\d*px?)",
                        p, re.I) or not p:
            continue
        caption = p
    web = fetch_inline_image(fname)
    if not web:
        return ""
    caption = PLAYER_RE.sub(r"\1", caption)
    caption_md = caption.replace('"', '\\"')
    title = f' "{caption_md}"' if caption else ""
    return f'\n\n![{caption}]({web}{title})\n\n'


def extract_prose(body):
    s = body
    s = re.sub(r"\{\{\s*Infobox Shop.*?\n\}\}", "", s, flags=re.S | re.I)
    # Remove the innermost {{Shop Item}} blocks first, then the now-emptied
    # {{Shop Stock|Stock=...}} wrapper (no braces left inside it to trip on).
    s = re.sub(r"\{\{\s*Shop Item.*?\}\}", "", s, flags=re.S | re.I)
    s = re.sub(r"\{\{\s*Shop Stock[^{}]*\}\}", "", s, flags=re.S | re.I)
    s = re.sub(r"\{\{\s*Shop Import Message\s*\}\}", "", s, flags=re.I)
    s = re.sub(r"\{\{\s*Under construction\s*\}\}", "", s, flags=re.I)
    s = re.sub(r"\{\{\s*DISPLAYTITLE:[^}]*\}\}", "", s, flags=re.I)
    s = re.sub(r"\[\[Category:[^\]]*\]\]", "", s, flags=re.I)
    # inline images -> markdown (must run before generic [[link]] handling,
    # and before the body-level {{player}} substitution below since captions
    # need the plain-text form, not the shortcode)
    s = re.sub(r"\[\[File:([^\]]+)\]\]", file_link_to_md, s)
    # {{player|Name}} in prose -> {{< playerhead "Name" >}} shortcode, matching
    # the convention import_articles.py already established for other content.
    s = PLAYER_RE.sub(lambda m: f'{{{{< playerhead "{m.group(1).strip()}" >}}}}', s)
    # headings, bold, italic
    s = re.sub(r"^\s*======\s*(.*?)\s*======\s*$", r"###### \1", s, flags=re.M)
    s = re.sub(r"^\s*=====\s*(.*?)\s*=====\s*$", r"##### \1", s, flags=re.M)
    s = re.sub(r"^\s*====\s*(.*?)\s*====\s*$", r"#### \1", s, flags=re.M)
    s = re.sub(r"^\s*===\s*(.*?)\s*===\s*$", r"### \1", s, flags=re.M)
    s = re.sub(r"^\s*==\s*(.*?)\s*==\s*$", r"## \1", s, flags=re.M)
    s = re.sub(r"'''(.+?)'''", r"**\1**", s)
    s = re.sub(r"''(.+?)''", r"*\1*", s)
    # [[Page|text]] / [[Page]] -> text
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = html.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def main():
    # cargo Shop rows: the structured infobox data (source of the front matter)
    rows, off = [], 0
    while True:
        d = api({"action": "cargoquery", "tables": "Shop",
                 "fields": "Shop._pageName=page,Shop.name=name,Shop.image=image,"
                           "Shop.location=location,Shop.owners=owners",
                 "where": "Shop.season='SurvivalS3'", "limit": "500", "offset": str(off)})
        b = d.get("cargoquery", [])
        rows += [r["title"] for r in b]
        if len(b) < 500:
            break
        off += 500
    print(f"cargo Shop rows (S3): {len(rows)}")

    cache = os.path.join(os.path.dirname(__file__), "wiki_cache", "s3_bodies.json")
    raw_bodies = json.load(open(cache)) if os.path.exists(cache) else json.load(
        open("/tmp/claude-1000/-home-sam-slabserver-wiki2/e0640091-e041-43d6-ba38-077eb4e5b4fc/scratchpad/s3_bodies.json"))
    # The wiki API returns titles normalised differently from cargo _pageName
    # (case after apostrophes, underscores vs spaces), so match on a folded key.
    def norm(k):
        return re.sub(r"\s+", " ", html.unescape(k).lower().replace("_", " ")).strip()
    bodies = {norm(k): v for k, v in raw_bodies.items()}

    os.makedirs(IMG_DIR, exist_ok=True)
    # wipe old generated md (keep _index.md)
    for fn in os.listdir(SHOPS_DIR):
        if fn.endswith(".md") and fn != "_index.md":
            os.remove(os.path.join(SHOPS_DIR, fn))

    seen_slug = {}
    n_items = n_prose = 0
    for r in rows:
        name = html.unescape(r.get("name", "").strip())
        page = r.get("page", "")
        body = bodies.get(norm(page), "")
        slug = slugify(name)
        c = seen_slug.get(slug, 0)
        seen_slug[slug] = c + 1
        if c:
            slug = f"{slug}-{c+1}"

        owners = clean_owners(r.get("owners", ""))
        loc = ""
        if r.get("location"):
            loc = r["location"].replace(",", " ").strip()
            loc = re.sub(r"\s+", " ", loc)
        image = ""
        if r.get("image"):
            image = f"{IMG_WEB}/{r['image'].strip().replace(' ', '_')}"

        items = parse_items(body)
        if items:
            n_items += 1
        prose = extract_prose(body)
        if len(prose) > 30:
            n_prose += 1
        else:
            prose = ""

        fm = ["---", f"title: {yaml_str(name)}", "type: shops"]
        if owners:
            fm.append(f"owners: {yaml_str(owners)}")
        if loc:
            fm.append(f"loc: {yaml_str(loc)}")
        if image:
            fm.append(f"image: {image}")
        if items:
            fm.append("items:")
            for it in items:
                fm.append(f"  - name: {yaml_str(it['name'])}")
                fm.append(f"    material: {yaml_str(it['material'])}")
                fm.append(f"    inStock: {'true' if it['inStock'] else 'false'}")
        fm.append("---")
        out = "\n".join(fm) + "\n"
        if prose:
            out += "\n" + prose + "\n"
        with open(os.path.join(SHOPS_DIR, slug + ".md"), "w") as f:
            f.write(out)

    print(f"wrote {len(rows)} shop pages")
    print(f"  with stock items: {n_items}")
    print(f"  with prose body:  {n_prose}")


if __name__ == "__main__":
    main()
