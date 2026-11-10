#!/usr/bin/env python3
"""Generate the dashboard's art. Optional: the kit ships these files ready made, so nothing here runs at install.

  python make_art.py --out art/web                     everything: flames, stars, icons, avatars and mascot
  python make_art.py --out art/web --small-only        everything except the three large flame GIFs
  python make_art.py --out art/web --seed "my project" a different set of avatars for this project name
  python make_art.py --out art/web --originals my_art  also make page copies of your own images (png or jpg)

Needs numpy and Pillow, unlike the rest of the kit. The same input gives the same output. Your images are never changed.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

PAINTING_WIDTH = 1200

# The colors, chosen together: near-black, crimson at hue 350, ice blue at hue 200.
# Blue is always much lighter than red and meets it through white, so the two never vibrate.
RAMP_RED = [(0.00, "#000000"), (0.20, "#1c0208"), (0.40, "#6e0a1c"), (0.58, "#d3122f"),
            (0.74, "#ff4d5e"), (0.86, "#ffc2c8"), (0.93, "#ffffff"), (1.00, "#8fe0ff")]
RAMP_BLUE = [(0.00, "#000000"), (0.22, "#04121c"), (0.44, "#0b3f63"), (0.64, "#1f8fd0"),
             (0.82, "#70d0ff"), (0.94, "#e8fbff"), (1.00, "#ffffff")]
RAMP_TEXT = [(0.00, "#7a0c1e"), (0.30, "#d3122f"), (0.55, "#ff5a6b"), (0.75, "#ffd9dd"),
             (0.85, "#ffffff"), (1.00, "#8fe0ff")]
BLACK, RED, RED_DEEP, BLUE, BLUE_HOT, WHITE = "#050407", "#d3122f", "#5c0a1a", "#70d0ff", "#e8fbff", "#ffffff"

# A small pixel frog for the mascot: B body, D dark, W eye, K pupil, R mouth.
MASCOT = ("....WWW....WWW....",
          "...WKKWW..WWKKW...",
          "...WKKWW..WWKKW...",
          "..BBBBBBBBBBBBBB..",
          ".BBBBBBBBBBBBBBBB.",
          ".BBBBBBBBBBBBBBBB.",
          "BBRRRRRRRRRRRRRRBB",
          "BBBRRRRRRRRRRRRBBB",
          ".BBBBBBBBBBBBBBBB.",
          "..DDBBBBBBBBBBDD..",
          ".DDD.DBB..BBD.DDD.",
          "DDD..DD....DD..DDD")
MASCOT_COLORS = {"B": BLUE, "D": "#1f8fd0", "W": WHITE, "K": BLACK, "R": RED}


def hex_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def ramp_palette(stops, count=64):
    """Interpolate color stops into a flat GIF palette, darkest index first."""
    positions = [s[0] for s in stops]
    channels = np.array([hex_rgb(s[1]) for s in stops], dtype=float)
    points = np.linspace(0, 1, count)
    table = np.stack([np.interp(points, positions, channels[:, c]) for c in range(3)], axis=1)
    return [int(round(v)) for v in table.flatten()]


def periodic_noise(rng, width, height, cells_x, cells_y, octaves=3):
    """Smooth noise that wraps at both edges, so strips tile and animations loop without a seam."""
    total = np.zeros((height, width))
    weight, amount = 0.0, 1.0
    for octave in range(octaves):
        nx, ny = cells_x * 2 ** octave, cells_y * 2 ** octave
        grid = rng.random((ny, nx))
        xs = np.linspace(0, nx, width, endpoint=False)
        ys = np.linspace(0, ny, height, endpoint=False)
        x0, y0 = xs.astype(int), ys.astype(int)
        fx, fy = xs - x0, ys - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        x1, y1 = (x0 + 1) % nx, (y0 + 1) % ny
        upper = grid[np.ix_(y0, x0)] * (1 - fx) + grid[np.ix_(y0, x1)] * fx
        lower = grid[np.ix_(y1, x0)] * (1 - fx) + grid[np.ix_(y1, x1)] * fx
        total += amount * (upper * (1 - fy)[:, None] + lower * fy[:, None])
        weight += amount
        amount *= 0.5
    return total / weight


def palette_image(field, palette):
    image = Image.fromarray(np.clip(field, 0, 63).astype(np.uint8)).convert("P")
    image.putdata(np.clip(field, 0, 63).astype(np.uint8).flatten().tolist())
    image.putpalette(palette)
    return image


def spreading_fire(seed, width, height, frames, palette, decay=4, steps=2, warmup=160, blend=10):
    """The classic 90s fire: heat climbs one row at a time, drifting sideways and cooling at random.

    Columns wrap, so the strip tiles. The last frames fade into the first, so the loop has no jump.
    """
    rng = np.random.default_rng(seed)
    hidden = 3  # rows below the visible strip, where the fire is fed
    rows = height + hidden
    heat = np.zeros((rows, width))
    columns = np.arange(width)
    feed = periodic_noise(rng, width, frames + blend + warmup, 18, 6, octaves=2)
    kept = []
    for tick in range(warmup + frames + blend):
        for _ in range(steps):
            heat[-1, :] = 63 * np.clip(0.8 + (feed[tick, :] - 0.5) * 1.25, 0, 1)
            for y in range(rows - 1):
                drift = rng.integers(0, 3, width)
                cool = (rng.random(width) < 0.42) * rng.integers(1, decay + 1, width)
                heat[y, (columns - drift + 1) % width] = np.maximum(heat[y + 1, columns] - cool, 0)
        if tick >= warmup:
            kept.append(heat[:height].copy())
    images = []
    for index in range(frames):
        field = kept[index]
        if index < blend:
            share = index / blend
            field = kept[index] * share + kept[frames + index] * (1 - share)
        below = np.vstack([field[1:], field[-1:]])
        field = (2 * field + np.roll(field, 1, 1) + np.roll(field, -1, 1) + below) / 5  # less speckle
        images.append(palette_image(field, palette))
    return images


def fire_frames(seed, width, height, frames, palette, base=1.28, licks=1.75, power=1.25, cells_x=14, floor=0.0):
    """Rising flame as a looping, tileable set of palette images. Hottest at the bottom."""
    rng = np.random.default_rng(seed)
    period = height * 2  # the pattern scrolls exactly this far in one loop, so the loop has no seam
    slow = periodic_noise(rng, width, period, cells_x, 3)
    fast = periodic_noise(rng, width, period, cells_x * 2, 5)
    warp = periodic_noise(rng, width, period, 6, 2, octaves=2)
    rows = np.arange(height)
    falloff = (rows / (height - 1)) ** power
    result = []
    columns = np.arange(width)
    for frame in range(frames):
        offset = frame * period // frames
        wobble = ((warp[(rows + offset) % period, :] - 0.5) * 22).astype(int)
        sampled_x = (columns[None, :] + wobble) % width
        first = slow[((rows + offset) % period)[:, None], sampled_x]
        second = fast[((rows + 2 * offset) % period)[:, None], sampled_x]
        noise = 0.62 * first + 0.38 * second - 0.5
        heat = falloff[:, None] * base + noise * licks * (0.45 + 0.55 * (1 - falloff[:, None]))
        heat = np.clip(heat, floor, 1.0)
        result.append(palette_image(heat * 63, palette))
    return result


def save_gif(frames, path, delay):
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=delay, loop=0,
                   optimize=False, disposal=1)


def star_layers(dim_path, bright_path, size=256):
    """A tiling starfield in two layers. The page fades the bright one in and out to twinkle."""
    rng = np.random.default_rng(1999)
    dim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bright = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for _ in range(70):
        x, y = (int(v) for v in rng.integers(0, size, 2))
        level = int(rng.integers(70, 170))
        dim.putpixel((x, y), (level, level, min(255, level + 25), 255))
    colors = [(255, 255, 255, 255)] * 4 + [(112, 208, 255, 255)] * 3 + [(255, 90, 107, 255)] * 2
    for _ in range(26):
        x, y = (int(v) for v in rng.integers(2, size - 2, 2))
        color = colors[int(rng.integers(0, len(colors)))]
        bright.putpixel((x, y), color)
        if rng.random() < 0.45:
            faded = color[:3] + (130,)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                bright.putpixel((x + dx, y + dy), faded)
    dim.save(dim_path)
    bright.save(bright_path)


def flame_icon(path, width=20, height=26, frames=10):
    """A small torch flame for bullets and badges: the same fire, narrowed to a teardrop."""
    palette = ramp_palette(RAMP_RED)
    rng = np.random.default_rng(66)
    period = height * 2
    noise = periodic_noise(rng, width, period, 5, 3, octaves=2)
    ys, xs = np.mgrid[0:height, 0:width]
    v = ys / (height - 1)  # 0 at the tip, 1 at the base
    u = (xs - (width - 1) / 2) / (width / 2)
    images = []
    for frame in range(frames):
        offset = frame * period // frames
        lick = noise[(ys + offset) % period, xs] - 0.5
        half_width = 0.98 * np.sin(np.clip(v, 0.001, 1) ** 0.72 * np.pi * 0.86)
        body = 1.0 - np.abs(u + lick * (1 - v) * 1.1) / np.maximum(half_width, 0.04)
        heat = np.clip(body * (0.72 + 0.5 * v) + lick * 0.42 + 0.08, 0, 1)
        heat[body <= 0] = 0
        images.append(palette_image(heat * 63, palette))
    save_gif(images, path, 80)


def sword_cursor(path):
    """A flaming sword pointer, its tip at the top left."""
    scale = 4
    size = 32 * scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def line(a, b, color, width):
        draw.line([(a[0] * scale, a[1] * scale), (b[0] * scale, b[1] * scale)],
                  fill=color, width=width * scale)
    for sparkle in ((12, 3), (4, 12), (16, 8), (8, 16)):
        line(sparkle, sparkle, (112, 208, 255, 255), 1)
    line((2, 2), (19, 19), (0, 0, 0, 255), 5)        # outline, so it shows on any background
    line((18, 26), (26, 18), (0, 0, 0, 255), 5)
    line((20, 20), (28, 28), (0, 0, 0, 255), 5)
    line((2, 2), (19, 19), (112, 208, 255, 255), 3)  # blade
    line((3, 3), (18, 18), (232, 251, 255, 255), 1)  # white-hot edge
    line((18, 26), (26, 18), (211, 18, 47, 255), 3)  # guard
    line((21, 21), (27, 27), (110, 10, 28, 255), 2)  # grip
    line((28, 28), (28, 28), (255, 77, 94, 255), 3)  # pommel
    image.resize((32, 32), Image.NEAREST).save(path)


def avatars(out, seed, count=8, cells=8, size=120):
    """Mirrored pixel faces for the friends, each from its own hash of the seed. No project art in them."""
    for index in range(1, count + 1):
        digest = hashlib.sha256(f"{seed}:{index}".encode("utf-8")).digest()
        ink = [hex_rgb(RED), hex_rgb(BLUE), hex_rgb(BLUE_HOT), hex_rgb("#ff4d5e")][digest[0] % 4]
        back = hex_rgb(RED_DEEP) if ink in (hex_rgb(BLUE), hex_rgb(BLUE_HOT)) else hex_rgb("#0b3f63")
        image = Image.new("RGB", (cells, cells), back)
        half = (cells + 1) // 2
        for y in range(cells):
            for x in range(half):
                if digest[1 + (y * half + x) % 30] % 5 < 2:
                    image.putpixel((x, y), ink)
                    image.putpixel((cells - 1 - x, y), ink)
        image.resize((size, size), Image.NEAREST).save(out / f"avatar_{index}.png", optimize=True)


def die(path, size=64):
    image = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((6, 6, size * 2 - 7, size * 2 - 7), 22, fill=hex_rgb(RED) + (255,), outline=hex_rgb(WHITE) + (255,), width=5)
    for x, y in ((32, 32), (96, 32), (64, 64), (32, 96), (96, 96)):
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=hex_rgb(WHITE) + (255,))
    image.resize((size, size), Image.LANCZOS).save(path, optimize=True)


def emblem(path, size=96):
    """A flame in a ring: the spinning badge in the profile box."""
    scale = 4
    big = size * scale
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((12, 12, big - 13, big - 13), outline=hex_rgb(BLUE) + (255,), width=20)
    middle = big // 2

    def drop(top, bottom, half, color):
        draw.polygon([(middle, top), (middle + half, bottom - half), (middle + half // 2, bottom),
                      (middle - half // 2, bottom), (middle - half, bottom - half)], fill=hex_rgb(color) + (255,))
    drop(big // 6, big - big // 6, big // 4, RED)
    drop(big // 3, big - big // 6, big // 6, "#ff4d5e")
    drop(big // 2, big - big // 6, big // 11, WHITE)
    image.resize((size, size), Image.LANCZOS).save(path, optimize=True)


def mascot(path, scale=6):
    height, width = len(MASCOT), len(MASCOT[0])
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for y, row in enumerate(MASCOT):
        for x, cell in enumerate(row):
            if cell in MASCOT_COLORS:
                image.putpixel((x, y), hex_rgb(MASCOT_COLORS[cell]) + (255,))
    image.resize((width * scale, height * scale), Image.NEAREST).save(path, optimize=True)


def placeholder(path, width=480, height=300):
    """Shown when no painting or friend picture exists. It says so, and does not pretend to be art."""
    image = Image.new("RGB", (width, height), hex_rgb(BLACK))
    draw = ImageDraw.Draw(image)
    for offset in range(-height, width, 40):
        draw.line([(offset, height), (offset + height, 0)], fill=hex_rgb(RED_DEEP), width=12)
    draw.rectangle((width // 2 - 96, height // 2 - 20, width // 2 + 96, height // 2 + 20), fill=hex_rgb(BLACK), outline=hex_rgb(BLUE), width=2)
    draw.text((width // 2, height // 2), "NO PICTURE YET", fill=hex_rgb(BLUE), anchor="mm")
    image.convert("P", palette=Image.ADAPTIVE, colors=16).save(path, optimize=True)


def own_paintings(folder, out):
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            image = Image.open(path).convert("RGB")
            ratio = min(1.0, PAINTING_WIDTH / image.width)
            image.resize((round(image.width * ratio), round(image.height * ratio)), Image.LANCZOS).save(
                out / f"{path.stem}.jpg", quality=84, optimize=True, progressive=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="the folder to write into")
    parser.add_argument("--seed", default="workspace dashboard", help="changes the avatars, for example a project's name")
    parser.add_argument("--small-only", action="store_true", help="skip the three large flame GIFs")
    parser.add_argument("--originals", help="a folder of your own images to make page copies of")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not args.small_only:
        save_gif(spreading_fire(7, 320, 48, 28, ramp_palette(RAMP_RED)), out / "fire_red.gif", 60)
        save_gif(spreading_fire(21, 320, 48, 28, ramp_palette(RAMP_BLUE)), out / "fire_blue.gif", 60)
        save_gif(fire_frames(33, 240, 60, 20, ramp_palette(RAMP_TEXT), base=0.88, licks=1.15, power=0.8, cells_x=10),
                 out / "fire_text.gif", 80)
    star_layers(out / "stars.png", out / "stars_twinkle.png")
    flame_icon(out / "flame_icon.gif")
    sword_cursor(out / "cursor_sword.png")
    avatars(out, args.seed)
    die(out / "die.png")
    emblem(out / "emblem.png")
    mascot(out / "mascot.png")
    placeholder(out / "placeholder.png")
    if args.originals:
        own_paintings(args.originals, out)
    for path in sorted(out.iterdir()):
        print(f"{path.stat().st_size // 1024:6d} KB  {path.name}")


if __name__ == "__main__":
    main()
