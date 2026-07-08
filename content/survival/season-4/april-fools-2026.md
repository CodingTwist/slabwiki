---
title: 'April Fools 2026: The Great Slabbening'
author: GamingTwist
categories: [events, april-fools]
date: 2026-04-01
description: 'The year every block in the Season 4 world became a slab, and the Python that did it.'
summary: "For a server called Slabserver, there was really only one April Fools joke to make. Here's the idea, and how a whole world got turned into slabs."
infobox:
  image: '/images/articles/s4-april-fools-after.jpg'
  Started: '2026-03-29'
  Finished: '2026-04-01'
  Builders: GamingTwist
---
The server is called Slabserver. So {{< playerhead "GamingTwist" >}}(me) took that personally for April Fools 2026, and kicked off a pretty technical challenge that, if I'd known how much work it would be from the start, I probably wouldn't have started: every block in the Season 4 world got halved into a slab of itself. Stone into a stone slab, oak planks into an oak slab, the lot. The whole world. The joke was framed as "saving storage," and alongside the world, half of every player's inventory was randomly removed. The server icon was also halved.

{{< compare before="/images/articles/s4-april-fools-before.jpg" after="/images/articles/s4-april-fools-after.jpg" alt="Spawn before and after the Great Slabbening" >}}

# Starting Small

It started as small as it goes: get one block type, in one chunk, to turn into another block. For the first test that was dirt into diamond block. If I was able to get this working, the idea was most likely doable.

The whole thing was built with [Amulet](https://www.amuletmc.com/), a world editor with a Python library underneath it. That library lets you load a Minecraft world. It gave a nice method to easily do it. [Core example of how this code works](https://amulet-core.readthedocs.io/en/stable/getting_started/blocks/amulet.html)

Python wasn't the obvious pick, since I prefer TypeScript, but the NBT libraries there were lacking and Python had by far the best support for Minecraft NBT. And this was a script that needed to run exactly once and then never again, so none of the usual reasons to reach for a familiar language really applied. It just had to work the one time.

## Finding the right slab

The next problem is that not every block *has* an obvious slab. Stone slab, fine. But what's the slab version of, say, a block that never came in slab form? There isn't one. So "turn everything into a slab" isn't a lookup, it's a decision for every single block type in the game.

The answer was matching by colour. A mapping takes every block and finds the average colour and find the closest slab to it *by colour*, so a block with no real slab equivalent still becomes the slab that looks most like it.

Going through that list by hand caught mistakes the matching logic couldn't see. Leaves were the clearest: they're stored as grey-scale, the colour only gets added by the game as a biome tint at render time. Matched blind, every tree would've come out slabbed dead grey. That one needed a manual override to mossy cobblestone slabs. Anything on the blacklist below was skipped entirely rather than matched, which is why things like air, water, and crops were left alone.

{{% details summary="The blacklist" %}}
```python
BLACKLIST_BLOCKS = {
    "air", "water", "lava", "grass", "fern", "tall_grass", "snow", "snow_layer",
    "oak_sapling", "birch_sapling", "spruce_sapling", "flower", "dandelion",
    "poppy", "rose_bush", "lily_of_the_valley", "wheat", "carrots", "potatoes",
    "beetroots", "crops", "reeds", "sugar_cane", "cactus", "vine",
    "leaves", "leaves2", "tall_flower"
}
```
{{% /details %}}

## A whole chunk

Now I had both these it was time to combine them. A chunk stores its blocks as a little palette of block types plus a grid of indices pointing into it, so the trick is you don't touch thousands of blocks, you build a lookup table over the palette once, `slab id for every palette id`, and then apply it to the whole chunk's block grid in one [NumPy](https://numpy.org/) pass. Fast, and it does the entire chunk at once instead of block by block. For more information [read here](https://minecraft.wiki/w/Chunk_format#Block_format)

{{% details summary="Building the palette lookup table" %}}
```python
def build_chunk_lut(chunk, java_version, name_to_slab_name):
    palette_size = len(chunk.block_palette)
    lut = np.arange(palette_size, dtype=np.uint32)
    for pid in range(palette_size):
        universal_block = chunk.block_palette[pid]
        java_block, _, _ = java_version.block.from_universal(universal_block)
        if isinstance(java_block, list):
            java_block = java_block[0]
        block_name = java_block.base_name
        if block_name in name_to_slab_name:
            slab = Block("minecraft", name_to_slab_name[block_name])
            u_slab, _, _ = java_version.block.to_universal(slab)
            slab_id = chunk.block_palette.get_add_block(u_slab)
            lut[pid] = slab_id
    return lut
```
{{% /details %}}

# The Big convert.

Then it was time to point it at the Season 4 whole world.

*Four days.*

I was hoping the Amulet library had something under the hood to make it fast, but no - it was the chokepoint. I was also banking on the palette trick alone being enough, but no. So it was either push the release to 2027 or speed it up.

## Making it concurrent

The fix was to do many regions at the same time. The catch is Amulet really wants to be the only thing holding a world open, so you can't just point a dozen workers at the same world folder and let them fight over it.

That's when I came up with the huge bodge that saved the project: why not just make more Minecraft worlds and merge the files back together? That way I could keep using Amulet without needing to replace it.

It copies out the world's `level.dat` (which Amulet needs just to recognize the folder as a world) plus the single region file that worker owns, into a temp directory. It processes that region completely on its own, with its own Amulet instance and no shared lock, then moves the finished region file back into the real world and deletes the temp copy. Every worker is isolated, nobody steps on anybody, and the cores all light up.

{{% details summary="Cloning a world per worker" %}}
```python
def make_temp_world(source_world: Path, region_file: Path) -> Path:
    """
    Copy the world's level.dat + just one region file into a fresh temp
    directory. Amulet needs level.dat to identify the world format; the
    region file is the only data we want to touch.
    Returns the temp world path.
    """
    tmp = Path(tempfile.mkdtemp(prefix="slab_worker_"))
    # level.dat is required so Amulet recognises it as a valid world
    shutil.copy2(source_world / "level.dat", tmp / "level.dat")
    region_dir = tmp / "region"
    region_dir.mkdir()
    shutil.copy2(region_file, region_dir / region_file.name)
    return tmp
```
{{% /details %}}

The actual per-chunk work is small enough to live on its own: take a chunk and its lookup table, run the LUT over every sub-chunk, and report back what changed. Pulling it out keeps the region loop readable.

{{% details summary="Converting one chunk" %}}
```python
def convert_chunk(chunk, cx, cz, lut):
    """
    Apply the palette LUT across every sub-chunk. Returns
    (changed, blocks_replaced, first_coords) where first_coords is the
    world position of the first replaced block (for the tp log), or None.
    """
    chunk_changed      = False
    total_replacements = 0
    first_coords       = None

    for cy in chunk.blocks.sub_chunks:
        sub     = chunk.blocks.get_sub_chunk(cy)
        new_sub = lut[sub]
        diff    = new_sub != sub
        if np.any(diff):
            sub[:] = new_sub
            chunk_changed       = True
            total_replacements += int(diff.sum())
            if first_coords is None:
                lx, ly, lz = np.argwhere(diff)[0]
                first_coords = (cx * 16 + int(lx), cy * 16 + int(ly), cz * 16 + int(lz))

    return chunk_changed, total_replacements, first_coords
```
{{% /details %}}

With that out of the way, the region worker is just: clone the world, walk its chunks, convert each one, save, and move the finished region back.

{{% details summary="Processing one region, start to finish" %}}
```python
def process_region(args):
    """
    Worker: copies one region into a temp world, processes it with its own
    Amulet instance (no shared lock), then moves the result back.
    """
    rx, rz, world_path_str, mapping, progress_queue = args

    world_path  = Path(world_path_str)
    region_file = world_path / "region" / f"r.{rx}.{rz}.mca"

    tmp_world = make_temp_world(world_path, region_file)
    tmp_region_out = tmp_world / "region" / region_file.name

    changed_count = 0
    skipped_count = 0
    change_log    = []

    try:
        level        = amulet.load_level(tmp_world)
        java_version = level.translation_manager.get_version("java", (1, 21, 11))

        chunk_coords = [
            (rx * 32 + dx, rz * 32 + dz)
            for dx in range(32)
            for dz in range(32)
        ]

        try:
            for i, (cx, cz) in enumerate(chunk_coords):
                try:
                    chunk = level.get_chunk(cx, cz, DIMENSION)
                except ChunkLoadError:
                    skipped_count += 1
                    progress_queue.put(1)
                    continue

                lut = build_chunk_lut(chunk, java_version, mapping)
                changed, replacements, first = convert_chunk(chunk, cx, cz, lut)

                if changed:
                    chunk.changed = True
                    changed_count += 1
                    fx, fy, fz = first
                    change_log.append({
                        "chunk":          [cx, cz],
                        "tp":             f"/tp {fx} {fy} {fz}",
                        "blocks_changed": replacements,
                    })

                level.put_chunk(chunk, DIMENSION)

                if (i + 1) % SAVE_EVERY_N_CHUNKS == 0:
                    level.save()

                progress_queue.put(1)

        finally:
            level.save()
            level.close()

        # Move the processed region file back to the real world, replacing the original
        shutil.move(str(tmp_region_out), str(region_file))

    finally:
        shutil.rmtree(tmp_world, ignore_errors=True)

    return changed_count, skipped_count, change_log
```
{{% /details %}}

Same conversion. Four days became **about an hour.** Though it did use the entire computer, so I had to open the window.
![Task manager showing every core maxed out during the conversion](/images/articles/s4-april-fools-pc-maxed.png "Every core maxed out during the conversion")

# Extra bits

The passage gave a lot of problems due to the world height and custom biome. I couldn't multithread it without changing the clone process but the world is much smaller so I did it single threaded.

The slabbed world got added to the [Nexus server](https://slabserver.org/documentation/nexus/) afterwards, so if you want to go walk around the Great Slabbening yourself, it's still there.

When it released I forgot to turn off firetick, which is bad when Netherrack gets converted to mangrove slabs.

I added the [Etho Slab](https://minecraft.wiki/w/Etho_Slab), retexturing the petrified oak slab to it.

## Reception

The [original announcement](https://discord.com/channels/146701388234227712/146702455487463424/1488795095351300197) went out on Discord on April 1st. People enjoyed it. It's a great login: you spawn in and the world you know is suddenly half missing, everything you built still recognisable but somehow not. It was funny seeing people's reactions to their builds getting changed.

# The code

Everything above is the interesting part. What's left is the driver: read the config, find every region file, hand them out to the pool, and write the log + tp list once it's done.

{{% details summary="Config, tp log, and the __main__ driver" %}}
```python
from amulet.api.block import Block
from amulet.api.errors import ChunkLoadError
import amulet
import numpy as np
import json
import shutil
import tempfile
from pathlib import Path
import sys
import time
import multiprocessing as mp
from multiprocessing import Pool, Manager

# CONFIG 
WORLD_PATH = Path("slabconvert/SlabserverS4")
DIMENSION = "minecraft:overworld"
BLOCK_TO_SLAB = Path("block_to_slab_edited.json")
SAVE_EVERY_N_CHUNKS = 50
WORKERS = max(1, mp.cpu_count() - 1)


def progress_reporter(total, progress_queue, start_time):
    done = 0
    bar_width = 40
    while done < total:
        progress_queue.get()
        done += 1
        pct     = done / total
        filled  = int(bar_width * pct)
        bar     = "█" * filled + "░" * (bar_width - filled)
        elapsed = time.time() - start_time
        eta_str = ""
        if done > 0:
            eta_sec = elapsed / done * (total - done)
            m, s    = divmod(int(eta_sec), 60)
            eta_str = f"  ETA {m}m{s:02d}s"
        sys.stdout.write(f"\r[{bar}] {done}/{total} ({pct*100:.1f}%){eta_str}   ")
        sys.stdout.flush()
    print()


# Main

if __name__ == "__main__":
    raw_mapping = json.load(open(BLOCK_TO_SLAB))
    mapping = {k: v for k, v in raw_mapping.items() if k not in BLACKLIST_BLOCKS}

    region_dir   = WORLD_PATH / "region"
    region_files = list(region_dir.glob("r.*.*.mca"))
    regions = []
    for f in region_files:
        parts = f.stem.split(".")
        regions.append((int(parts[1]), int(parts[2])))

    total_chunks = len(regions) * 32 * 32
    print(f"Found {len(regions)} region files ({total_chunks} chunk slots)")
    print(f"Running with {WORKERS} parallel workers\n")

    manager        = Manager()
    progress_queue = manager.Queue()
    start_time     = time.time()

    import threading
    bar_thread = threading.Thread(
        target=progress_reporter,
        args=(total_chunks, progress_queue, start_time),
        daemon=True,
    )
    bar_thread.start()

    worker_args = [
        (rx, rz, str(WORLD_PATH), mapping, progress_queue)
        for rx, rz in regions
    ]

    all_changed = 0
    all_skipped = 0
    all_logs    = []

    with Pool(processes=WORKERS) as pool:
        for changed, skipped, log in pool.imap_unordered(process_region, worker_args):
            all_changed += changed
            all_skipped += skipped
            all_logs.extend(log)

    bar_thread.join()

    elapsed = time.time() - start_time
    m, s = divmod(int(elapsed), 60)

    log_path = Path("conversion_log.json")
    tp_path  = Path("tp_commands.txt")

    log_path.write_text(json.dumps(all_logs, indent=2))
    with tp_path.open("w") as f:
        f.write("# Paste into Minecraft chat to jump to each changed chunk\n\n")
        for entry in all_logs:
            cx, cz = entry["chunk"]
            f.write(f"# chunk ({cx}, {cz})  --  {entry['blocks_changed']} blocks changed\n")
            f.write(entry["tp"] + "\n\n")

    print(f"Done in {m}m{s:02d}s  —  {all_changed} chunks modified, {all_skipped} skipped")
    print(f"Conversion log -> {log_path.resolve()}")
    print(f"TP commands    -> {tp_path.resolve()}")
```
{{% /details %}}
