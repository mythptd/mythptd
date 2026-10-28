"""Render the looping Q1 / Q2 / Q3 scene used by the profile README."""

from __future__ import annotations

import math
import random
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "yasuo.gif"
MINION = ROOT / "assets" / "minion-pixel.png"
OUTPUT = ROOT / "assets" / "yasuo-q-combo.gif"

WIDTH, HEIGHT = 760, 211
FRAME_MS = 80
FRAME_COUNT = 65
CYCLE = FRAME_COUNT * FRAME_MS / 1000
WALK_SPEED = 110
ENTRY_X = 785
SPAWN_PHASES = (0.8, 2.8, 4.3)
KILL_AFTER = 3.4
BACKDROP = (122, 114, 109)


def source_frames() -> tuple[list[Image.Image], list[Image.Image]]:
    source = Image.open(SOURCE)
    frames = []
    masks = []
    for index in range(source.n_frames):
        source.seek(index)
        frame = source.convert("RGB")
        frames.append(frame)
        mask = Image.new("L", frame.size)
        src_px = frame.load()
        mask_px = mask.load()
        for y in range(frame.height):
            for x in range(100, frame.width):
                r, g, b = src_px[x, y]
                if abs(r - BACKDROP[0]) + abs(g - BACKDROP[1]) + abs(b - BACKDROP[2]) > 75:
                    mask_px[x, y] = 255
        masks.append(mask)
    return frames, masks


def pose_at(t: float) -> int:
    # Both ordinary Q attacks use the original GIF's straight sword thrust.
    for start in (0.64, 2.14):
        phase = t - start
        if 0 <= phase < 0.12:
            return 1
        if 0.12 <= phase < 0.24:
            return 2
        if 0.24 <= phase < 0.48:
            return 3
        if 0.48 <= phase < 0.60:
            return 9

    # The third Q replays the supplied GIF's full overhead sweep.
    third_q = t - 3.40
    if 0 <= third_q < 1.04:
        sequence = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12)
        return sequence[min(int(third_q / 0.08), len(sequence) - 1)]
    return 0


def tornado_sprite(phase: int) -> Image.Image:
    small = Image.new("RGBA", (30, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(small)
    sway = (-2, 0, 2, 0)[phase % 4]
    d.polygon(((8+sway, 5), (24+sway, 5), (20, 20), (22, 31), (16, 46), (12, 44), (16, 29), (8, 19)), fill=(38, 99, 119, 115))
    for i, y in enumerate((3, 12, 21, 30)):
        radius = (13, 12, 10, 8)[i]
        center = 15 + sway * ((i % 2) * 2 - 1)
        d.arc((center-radius, y, center+radius, y+12), 192, 352, fill=(176, 245, 247, 255), width=3)
        d.arc((center-radius+2, y+2, center+radius-2, y+10), 18, 150, fill=(100, 210, 231, 255), width=2)
        d.line((center-radius+3, y+3, center-radius+6, y+1), fill=(231, 251, 249, 255), width=2)
    d.arc((8, 36, 23, 47), 180, 350, fill=(113, 219, 226, 230), width=2)
    for x, y in ((3+sway, 10), (28-sway, 19), (2, 28), (27, 34)):
        d.rectangle((x, y, x+1, y+1), fill=(194, 251, 251, 220))
    return small.resize((60, 96), Image.Resampling.NEAREST)


def backdrop(frame: Image.Image) -> Image.Image:
    # The supplied GIF changes background color during the attack. Extend its
    # own edge row by row so the wider scene follows each original frame.
    mode = Counter(frame.crop((400, 0, 498, 48)).get_flattened_data()).most_common(1)[0][0]
    canvas = Image.new("RGB", (WIDTH, HEIGHT), mode)
    source_px = frame.load()
    for y in range(HEIGHT):
        clean = all(
            sum(abs(value - base) for value, base in zip(source_px[x, y], mode)) < 65
            for x in range(478, 498)
        )
        if clean:
            strip = frame.crop((478, y, 498, y + 1)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            for x in range(498, WIDTH, strip.width):
                canvas.paste(strip, (x, y))
    canvas.paste(frame, (0, 0))
    return canvas


def draw_spark(draw: ImageDraw.ImageDraw, x: int, y: int, age: float, seed: int, blue: bool = False) -> None:
    rng = random.Random(seed)
    spread = int(age * 94)
    for _ in range(11):
        dx = rng.randint(-24, 24)
        dy = rng.randint(-16, 13)
        px = x + dx + int(math.copysign(spread, dx or 1) * 0.5)
        py = y + dy - int(spread * 0.4)
        size = 3 if rng.random() < 0.3 else 2
        color = (198, 244, 247) if blue else (226, 166, 107)
        draw.rectangle((px, py, px + size, py + size), fill=color)


def paste_minion(canvas: Image.Image, sprite: Image.Image, body_x: float, y: int, flash: bool = False, fade: float = 1) -> None:
    x = round(body_x) - 68
    minion = sprite.copy()
    if flash:
        alpha = minion.getchannel("A")
        minion = Image.new("RGBA", minion.size, (231, 250, 248, 0))
        minion.putalpha(alpha)
    if fade < 1:
        minion.putalpha(minion.getchannel("A").point(lambda v: round(v * fade)))
    canvas.paste(minion, (x, y), minion)


def minions_at(canvas: Image.Image, sprite: Image.Image, t: float) -> None:
    draw = ImageDraw.Draw(canvas)
    for wave in (-1, 0):
        for kind, phase in enumerate(SPAWN_PHASES):
            spawn = wave * CYCLE + phase
            age = t - spawn
            if age < 0 or age > KILL_AFTER + 0.55:
                continue
            body_x = ENTRY_X - WALK_SPEED * min(age, KILL_AFTER)
            if body_x - 68 > WIDTH or body_x + 42 < 0:
                continue
            death_age = age - KILL_AFTER
            if death_age < 0:
                bob = int(age * 11) % 2
                draw.ellipse((body_x - 26, 207, body_x + 29, 210), fill=(95, 86, 81))
                paste_minion(canvas, sprite, body_x, HEIGHT - sprite.height - bob)
            elif kind == 0 and death_age < 0.47:
                # The minion hit by Q3 is lifted into the wind.
                lift = round(67 * min(1, death_age / 0.32))
                paste_minion(canvas, sprite, body_x + death_age * 26, HEIGHT - sprite.height - lift, death_age < 0.10, 1 - death_age / 0.55)
                draw_spark(draw, round(body_x), 151 - lift, death_age, 300 + wave, blue=True)
            elif death_age < 0.10:
                paste_minion(canvas, sprite, body_x + 3, HEIGHT - sprite.height - 4, flash=True)
                draw_spark(draw, round(body_x), 151, death_age, kind + wave * 4)
            elif death_age < 0.34:
                draw_spark(draw, round(body_x), 151, death_age, kind + wave * 4)


def draw_attack_effects(canvas: Image.Image, t: float, twisters: list[Image.Image]) -> None:
    draw = ImageDraw.Draw(canvas)
    for hit in (1.0, 2.5):
        age = abs(t - hit)
        if age < 0.12:
            draw.line(((350, 149), (420, 147)), fill=(189, 241, 243), width=4)
            draw.line(((367, 146), (425, 145)), fill=(235, 252, 251), width=2)
            draw_spark(draw, 411, 145, age, round(hit * 10), blue=True)

    tornado_age = t - 3.85
    if 0 <= tornado_age < 1.23:
        tornado_x = 270 + 400 * tornado_age
        sprite = twisters[int(t / 0.08) % len(twisters)]
        if tornado_x < WIDTH + 50:
            canvas.paste(sprite, (round(tornado_x) - 30, 112 + int(t * 25) % 3), sprite)
            for offset in (-18, -9, 14):
                px = round(tornado_x + offset)
                py = 196 + (offset % 3) * 3
                draw.rectangle((px, py, px + 3, py + 2), fill=(142, 217, 223))


def render() -> None:
    frames, masks = source_frames()
    sprite = Image.open(MINION).convert("RGBA")
    twisters = [tornado_sprite(i) for i in range(4)]
    output = []
    for index in range(FRAME_COUNT):
        t = index * FRAME_MS / 1000
        pose = pose_at(t)
        canvas = backdrop(frames[pose])
        minions_at(canvas, sprite, t)
        canvas.paste(frames[pose], (0, 0), masks[pose])
        draw_attack_effects(canvas, t, twisters)
        output.append(canvas)

    # One palette for every frame avoids color flicker in the loop.
    palette_sample = Image.new("RGB", (WIDTH, HEIGHT * 10))
    for row, index in enumerate((0, 8, 12, 19, 24, 31, 40, 48, 54, 61)):
        palette_sample.paste(output[index], (0, row * HEIGHT))
    palette = palette_sample.quantize(colors=112, method=Image.Quantize.MEDIANCUT)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in output]
    indexed[0].save(
        OUTPUT,
        save_all=True,
        append_images=indexed[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Saved {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, {len(indexed)} frames)")


if __name__ == "__main__":
    render()
