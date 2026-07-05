#!/usr/bin/env python3
"""
Phase 1 of the SlabWiki import: pure download, no transformation.

Fetches raw wikitext for every KEEPERS title (see import_articles.py) plus
every image referenced from it (infobox `image=` fields and inline
[[File:...]] links) into scripts/wiki_cache/. Idempotent - re-running only
fetches what isn't already cached. Pass --refresh to force re-fetching
everything.

Phase 2 (import_articles.py) reads only from this cache and never touches
the network, so the hard part (getting the markdown/template conversion
exactly right) can be iterated on without re-hitting the wiki every time.

Usage: python3 scripts/fetch_wiki_cache.py [--refresh]
"""
import json, os, re, sys, urllib.parse, urllib.request

API = "https://wiki.slabserver.org/w/api.php"
UA = "SlabWikiArchiver/1.0 (static-site migration)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "scripts", "wiki_cache")
PAGES_DIR = os.path.join(CACHE, "pages")
IMAGES_DIR = os.path.join(CACHE, "images")
MANIFEST_PATH = os.path.join(CACHE, "manifest.json")

REFRESH = "--refresh" in sys.argv

# Curated keepers (main namespace) mapped to a category + season. Titles are
# exactly as they exist on the wiki (verified live - see fetch_wiki_cache.py
# git history for titles that turned out to be missing/broken redirects and
# were dropped or corrected: "Season3" doesn't exist, "Season2" is a broken
# redirect to a nonexistent "SeasonS2", "SurvivalS4 Puzzle" redirects to
# "The Passage" so it's a duplicate, not a distinct page).
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
    "The Disc 11 Puzzle":    ("Puzzles", "Season 4"),
    "The Passage":           ("Puzzles", "Season 4"),
    "The Tunnel":            ("Puzzles", "Season 4"),
    "Survival Puzzles":      ("Puzzles", "Season 4"),
    "Decked Out":            ("Events", "Season 4"),
    "Fish Cult":             ("Community", "Season 4"),
    "TFC Gamenight 2024":    ("Events", "Season 4"),
    "SurvivalS2":            ("Community", "Season 2"),
    "SurvivalS3":            ("Community", "Season 3"),
    "SurvivalS4":            ("Community", "Season 4"),
}


def api(params):
    params["format"] = "json"
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cache_slug(title):
    return re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_")


def find_image_refs(wikitext):
    """All File: names referenced by this page: inline [[File:...]] links and
    any `image=`/`image =` infobox field."""
    names = set(m.group(1).strip() for m in re.finditer(r"\[\[File:([^\]|]+)", wikitext))
    names |= set(m.group(1).strip() for m in re.finditer(r"\|\s*image\s*=\s*([^|\n}]+)", wikitext))
    return names


def fetch_page(title):
    d = api({"action": "query", "prop": "revisions", "rvprop": "content",
             "rvslots": "main", "titles": title})
    page = next(iter(d["query"]["pages"].values()))
    if "revisions" not in page:
        return None, "missing"
    text = page["revisions"][0]["slots"]["main"]["*"]
    if text.strip().upper().startswith("#REDIRECT"):
        return None, "redirect"
    return text, "ok"


def fetch_image(filename, manifest_images):
    if filename in manifest_images and not REFRESH:
        return
    try:
        d = api({"action": "query", "titles": "File:" + filename,
                 "prop": "imageinfo", "iiprop": "url"})
        page = next(iter(d["query"]["pages"].values()))
        src = page["imageinfo"][0]["url"]
    except Exception as e:
        print(f"    ! image resolve failed for {filename}: {e}")
        return
    ext = os.path.splitext(src)[1] or ".png"
    local_name = cache_slug(os.path.splitext(filename)[0]) + ext
    dst = os.path.join(IMAGES_DIR, local_name)
    if not os.path.exists(dst) or REFRESH:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
                f.write(r.read())
        except Exception as e:
            print(f"    ! image download failed for {filename}: {e}")
            return
    manifest_images[filename] = {"cache_file": local_name, "url": src}
    print(f"    ~ image {filename} -> wiki_cache/images/{local_name}")


def main():
    os.makedirs(PAGES_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    manifest = {"pages": {}, "images": {}}
    if os.path.exists(MANIFEST_PATH) and not REFRESH:
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

    for title, (category, default_season) in KEEPERS.items():
        slug = cache_slug(title)
        page_path = os.path.join(PAGES_DIR, slug + ".wikitext")
        if title in manifest["pages"] and os.path.exists(page_path) and not REFRESH:
            print(f"  = cached: {title}")
            wikitext = open(page_path).read()
        else:
            text, status = fetch_page(title)
            if status != "ok":
                print(f"  ! skip ({status}): {title}")
                manifest["pages"].pop(title, None)
                continue
            with open(page_path, "w") as f:
                f.write(text)
            manifest["pages"][title] = {"cache_file": slug + ".wikitext",
                                         "category": category, "season": default_season}
            wikitext = text
            print(f"  ✓ fetched: {title}")

        for filename in find_image_refs(wikitext):
            fetch_image(filename, manifest["images"])

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    print(f"\nCached {len(manifest['pages'])} pages, {len(manifest['images'])} images.")
    print(f"Manifest: {os.path.relpath(MANIFEST_PATH, ROOT)}")


if __name__ == "__main__":
    main()
