"""Render Yasuo defending a crystal from a looping, animated minion wave."""

from __future__ import annotations

import math
import random
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "yasuo.gif"
MINION = ROOT / "assets" / "minion-pixel.png"
CRYSTAL = ROOT / "assets" / "home-crystal-pixel.png"
OUTPUT = ROOT / "assets" / "yasuo-q-combo.gif"

WIDTH, HEIGHT = 760, 211
FRAME_MS = 80
FRAME_COUNT = 90
CYCLE = FRAME_COUNT * FRAME_MS / 1000
WALK_SPEED = 110
ENTRY_X = 730
# Three minions arrive for Q3. The next two enter after the tornado and
# become the Q1 and Q2 targets when the GIF loops.
SPAWN_RULES = ((1.3, "wind"), (2.3, "wind"), (3.3, "wind"), (5.3, "q1"), (6.8, "q2"))
TORNADO_START = 3.85
TORNADO_START_X = 270
TORNADO_SPEED = 400
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


def walking_sprites(sprite: Image.Image) -> list[Image.Image]:
    """Move the two original pixel-art boots independently in four clear steps."""
    torso = sprite.crop((0, 0, sprite.width, 83))
    front = sprite.crop((39, 77, 73, 100))
    rear = sprite.crop((73, 77, 109, 100))
    poses = []
    for front_dx, front_dy, rear_dx, rear_dy in ((-7, -2, 6, 0), (-2, 0, 2, -2), (7, 0, -7, -2), (2, -2, -2, 0)):
        pose = Image.new("RGBA", sprite.size, (0, 0, 0, 0))
        pose.paste(rear, (73 + rear_dx, 77 + rear_dy), rear)
        pose.paste(torso, (0, 0), torso)
        pose.paste(front, (39 + front_dx, 77 + front_dy), front)
        poses.append(pose)
    return poses


def paste_minion(
    canvas: Image.Image,
    sprite: Image.Image,
    body_x: float,
    lift: int = 0,
    flash: bool = False,
    fade: float = 1,
    angle: float = 0,
) -> None:
    minion = sprite.copy()
    if flash:
        alpha = minion.getchannel("A")
        minion = Image.new("RGBA", minion.size, (231, 250, 248, 0))
        minion.putalpha(alpha)
    if fade < 1:
        minion.putalpha(minion.getchannel("A").point(lambda v: round(v * fade)))
    if angle:
        minion = minion.rotate(angle, Image.Resampling.NEAREST, expand=True)
        x = round(body_x) - minion.width // 2
    else:
        x = round(body_x) - 68
    y = HEIGHT - minion.height - lift
    canvas.paste(minion, (x, y), minion)


def wind_hit_time(phase: float) -> float:
    return (ENTRY_X + TORNADO_SPEED * TORNADO_START + WALK_SPEED * phase - TORNADO_START_X) / (TORNADO_SPEED + WALK_SPEED)


def draw_defeat(canvas: Image.Image, sprite: Image.Image, body_x: float, death_age: float, kind: str, seed: int) -> None:
    wind = kind == "wind"
    if wind:
        if death_age < 0.32:
            lift = round(62 * death_age / 0.32)
        elif death_age < 0.75:
            lift = round(62 * (1 - (death_age - 0.32) / 0.43))
        else:
            lift = 0
        angle = -min(82, death_age * 112)
        fade = 1 if death_age < 0.74 else max(0, 1 - (death_age - 0.74) / 0.24)
        drift = death_age * 34
    else:
        lift = round(20 * math.sin(math.pi * min(death_age / 0.55, 1)))
        angle = -min(78, death_age * 120)
        fade = 1 if death_age < 0.55 else max(0, 1 - (death_age - 0.55) / 0.30)
        drift = death_age * 20

    if fade > 0:
        paste_minion(canvas, sprite, body_x + drift, lift, death_age < 0.08, fade, angle)
    draw = ImageDraw.Draw(canvas)
    if death_age < 0.35:
        draw_spark(draw, round(body_x), 152 - lift, death_age, seed, blue=True)
    elif 0.55 < death_age < 0.89:
        # Pixel armor fragments and a short dust burst make the fall readable.
        draw_spark(draw, round(body_x + drift), 193, death_age - 0.55, seed + 100)


def minions_at(canvas: Image.Image, sprites: list[Image.Image], t: float) -> None:
    draw = ImageDraw.Draw(canvas)
    for wave in (-1, 0):
        for index, (phase, kind) in enumerate(SPAWN_RULES):
            spawn = wave * CYCLE + phase
            age = t - spawn
            if age < 0:
                continue
            hit = wave * CYCLE + wind_hit_time(phase) if kind == "wind" else spawn + 2.9
            death_age = t - hit
            if death_age > 0.98:
                continue
            body_x = ENTRY_X - WALK_SPEED * min(age, hit - spawn)
            if body_x - 68 > WIDTH or body_x + 42 < 0:
                continue
            if death_age < 0:
                step = int(age / 0.12) % len(sprites)
                bob = (0, 2, 0, 2)[step]
                draw.ellipse((body_x - 26, 207, body_x + 29, 210), fill=(95, 86, 81))
                paste_minion(canvas, sprites[step], body_x, bob)
            else:
                draw_defeat(canvas, sprites[1], body_x, death_age, kind, 300 + wave * 10 + index)


def draw_attack_effects(canvas: Image.Image, t: float, twisters: list[Image.Image]) -> None:
    draw = ImageDraw.Draw(canvas)
    for hit in (1.0, 2.5):
        age = abs(t - hit)
        if age < 0.12:
            draw.line(((350, 149), (420, 147)), fill=(189, 241, 243), width=4)
            draw.line(((367, 146), (425, 145)), fill=(235, 252, 251), width=2)
            draw_spark(draw, 411, 145, age, round(hit * 10), blue=True)

    tornado_age = t - TORNADO_START
    if 0 <= tornado_age < 1.23:
        tornado_x = TORNADO_START_X + TORNADO_SPEED * tornado_age
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
    sprites = walking_sprites(sprite)
    crystal = Image.open(CRYSTAL).convert("RGBA")
    twisters = [tornado_sprite(i) for i in range(4)]
    output = []
    for index in range(FRAME_COUNT):
        t = index * FRAME_MS / 1000
        pose = pose_at(t)
        canvas = backdrop(frames[pose])
        canvas.paste(crystal, (42, 36), crystal)
        minions_at(canvas, sprites, t)
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
