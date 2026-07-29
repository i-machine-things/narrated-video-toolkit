"""Core rendering pipeline: turns (reference audio, script text) into a narrated,
animated MP4. Generalized from the original build_video.py/generate_narration.py
one-off scripts so a web frontend can drive it with arbitrary user input."""
import os
import re
import subprocess
import textwrap
from dataclasses import dataclass
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FONT_DIR = "/usr/share/fonts/truetype/noto"
F_BOLD = os.path.join(FONT_DIR, "NotoSans-Bold.ttf")
F_REG = os.path.join(FONT_DIR, "NotoSans-Regular.ttf")
WHITE = (240, 240, 245)

MAX_SCENES = 30
MAX_SCRIPT_CHARS = 20000

# Rotating palette + icon set so auto-generated slides still look varied,
# without needing per-scene hand-authored metadata like the original video had.
PALETTES = [
    ((13, 27, 51), (25, 48, 82), (212, 175, 55)),   # navy / gold
    ((15, 35, 40), (20, 60, 65), (90, 200, 190)),   # teal
    ((40, 18, 18), (70, 30, 30), (220, 90, 80)),    # red
    ((16, 30, 46), (24, 52, 78), (100, 160, 230)),  # blue
    ((30, 24, 45), (52, 40, 74), (190, 140, 230)),  # purple
    ((18, 36, 30), (28, 58, 48), (120, 210, 140)),  # green
    ((42, 24, 12), (68, 40, 18), (235, 150, 70)),   # orange
    ((14, 34, 40), (20, 56, 64), (90, 210, 200)),   # cyan
    ((22, 22, 44), (38, 38, 72), (160, 170, 240)),  # indigo
]
ICONS = ["shield", "globe", "document", "scale", "laptop", "warning", "check", "list", "lock", "flag", "question"]


@dataclass
class Scene:
    title: str
    body: str
    bg_top: tuple
    bg_bottom: tuple
    accent: tuple
    icon: str


def split_script_into_scenes(script_text: str) -> list[str]:
    """Blank-line-separated paragraphs become separate slides/scenes."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", script_text.strip()) if p.strip()]
    return paragraphs


def make_scene_title(paragraph: str, index: int) -> str:
    first_sentence = re.split(r"(?<=[.!?])\s", paragraph, maxsplit=1)[0]
    words = first_sentence.split()
    title = " ".join(words[:7])
    if len(words) > 7:
        title += "..."
    return title or f"Part {index + 1}"


def build_scenes(video_title: str, script_text: str) -> list[Scene]:
    paragraphs = split_script_into_scenes(script_text)
    if not paragraphs:
        raise ValueError("Script is empty.")
    if len(paragraphs) > MAX_SCENES:
        raise ValueError(f"Too many scenes ({len(paragraphs)}). Max is {MAX_SCENES} - "
                          f"combine some paragraphs or split into multiple videos.")

    scenes = [Scene(
        title=video_title or "Untitled",
        body=paragraphs[0],
        bg_top=PALETTES[0][0], bg_bottom=PALETTES[0][1], accent=PALETTES[0][2],
        icon=ICONS[0],
    )]
    for i, para in enumerate(paragraphs[1:], start=1):
        palette = PALETTES[i % len(PALETTES)]
        scenes.append(Scene(
            title=make_scene_title(para, i),
            body=para,
            bg_top=palette[0], bg_bottom=palette[1], accent=palette[2],
            icon=ICONS[i % len(ICONS)],
        ))
    return scenes


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_bg(top, bottom):
    img = Image.new("RGB", (W, H), top)
    px = img.load()
    for y in range(H):
        c = lerp(top, bottom, y / H)
        for x in range(0, W, 4):
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = c
    return img


def draw_icon(draw, kind, cx, cy, size, color):
    r = size // 2
    if kind == "shield":
        pts = [(cx, cy - r), (cx + r, cy - r * 0.5), (cx + r, cy + r * 0.2),
               (cx, cy + r), (cx - r, cy + r * 0.2), (cx - r, cy - r * 0.5)]
        draw.polygon(pts, outline=color, width=6)
        draw.line([(cx - r * 0.4, cy), (cx - r * 0.1, cy + r * 0.35), (cx + r * 0.5, cy - r * 0.35)],
                   fill=color, width=8, joint="curve")
    elif kind == "globe":
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=6)
        draw.ellipse([cx - r * 0.4, cy - r, cx + r * 0.4, cy + r], outline=color, width=5)
        draw.line([(cx - r, cy), (cx + r, cy)], fill=color, width=5)
        draw.line([(cx - r, cy - r * 0.5), (cx + r, cy - r * 0.5)], fill=color, width=4)
        draw.line([(cx - r, cy + r * 0.5), (cx + r, cy + r * 0.5)], fill=color, width=4)
    elif kind == "document":
        x0, y0, x1, y1 = cx - r * 0.6, cy - r, cx + r * 0.6, cy + r
        draw.rectangle([x0, y0, x1, y1], outline=color, width=6)
        for i in range(4):
            yy = y0 + r * 0.4 + i * r * 0.35
            draw.line([(x0 + r * 0.2, yy), (x1 - r * 0.2, yy)], fill=color, width=5)
    elif kind == "scale":
        draw.line([(cx, cy - r), (cx, cy + r * 0.7)], fill=color, width=7)
        draw.line([(cx - r, cy - r * 0.5), (cx + r, cy - r * 0.5)], fill=color, width=7)
        for side in (-1, 1):
            bx = cx + side * r
            draw.line([(bx, cy - r * 0.5), (bx - r * 0.35, cy + r * 0.1)], fill=color, width=5)
            draw.line([(bx, cy - r * 0.5), (bx + r * 0.35, cy + r * 0.1)], fill=color, width=5)
            draw.arc([bx - r * 0.35, cy + r * 0.1 - 20, bx + r * 0.35, cy + r * 0.1 + 40], 0, 180, fill=color, width=5)
        draw.line([(cx - r * 0.5, cy + r * 0.7), (cx + r * 0.5, cy + r * 0.7)], fill=color, width=7)
    elif kind == "laptop":
        draw.rectangle([cx - r, cy - r * 0.6, cx + r, cy + r * 0.3], outline=color, width=6)
        draw.rectangle([cx - r * 1.15, cy + r * 0.3, cx + r * 1.15, cy + r * 0.5], outline=color, width=6)
    elif kind == "warning":
        pts = [(cx, cy - r), (cx + r, cy + r * 0.8), (cx - r, cy + r * 0.8)]
        draw.polygon(pts, outline=color, width=7)
        draw.line([(cx, cy - r * 0.25), (cx, cy + r * 0.2)], fill=color, width=7)
        draw.ellipse([cx - 5, cy + r * 0.42, cx + 5, cy + r * 0.52], fill=color)
    elif kind == "check":
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=6)
        draw.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.4), (cx + r * 0.5, cy - r * 0.4)],
                   fill=color, width=9, joint="curve")
    elif kind == "list":
        for i in range(3):
            yy = cy - r * 0.6 + i * r * 0.6
            draw.ellipse([cx - r, yy - 8, cx - r + 16, yy + 8], fill=color)
            draw.line([(cx - r + 30, yy), (cx + r, yy)], fill=color, width=6)
    elif kind == "lock":
        body_top = cy - r * 0.1
        draw.rectangle([cx - r * 0.7, body_top, cx + r * 0.7, cy + r], outline=color, width=6)
        draw.arc([cx - r * 0.5, cy - r * 1.1, cx + r * 0.5, body_top + r * 0.3], 180, 360, fill=color, width=6)
        draw.ellipse([cx - 10, cy + r * 0.25, cx + 10, cy + r * 0.45], fill=color)
    elif kind == "flag":
        draw.line([(cx - r * 0.6, cy - r), (cx - r * 0.6, cy + r)], fill=color, width=7)
        draw.polygon([(cx - r * 0.6, cy - r), (cx + r, cy - r * 0.6), (cx - r * 0.6, cy - r * 0.2)], fill=color)
    elif kind == "question":
        qfont = ImageFont.truetype(F_BOLD, int(size * 1.3))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=6)
        bbox = draw.textbbox((0, 0), "?", font=qfont)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), "?", font=qfont, fill=color)


def render_slide(scene: Scene, idx: int, total: int, path: str, footer_text: str):
    img = gradient_bg(scene.bg_top, scene.bg_bottom)
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(F_BOLD, 50)
    body_font = ImageFont.truetype(F_REG, 28)
    footer_font = ImageFont.truetype(F_REG, 20)

    margin_x = 70
    title_lines = textwrap.wrap(scene.title, width=38)[:2]
    ty = 70
    for line in title_lines:
        draw.text((margin_x, ty), line, font=title_font, fill=WHITE)
        bbox = draw.textbbox((margin_x, ty), line, font=title_font)
        ty = bbox[3] + 8
    line_y = ty + 12
    draw.line([(margin_x, line_y), (margin_x + 340, line_y)], fill=scene.accent, width=6)

    by = line_y + 45
    wrapped = textwrap.wrap(scene.body, width=62)
    max_lines = 14
    for line in wrapped[:max_lines]:
        draw.text((margin_x, by), line, font=body_font, fill=WHITE)
        by += 38
    if len(wrapped) > max_lines:
        draw.text((margin_x, by), "...", font=body_font, fill=WHITE)

    draw_icon(draw, scene.icon, W - 130, 110, 90, scene.accent)

    draw.rectangle([0, H - 50, W, H], fill=(0, 0, 0))
    draw.text((margin_x, H - 38), footer_text.upper(), font=footer_font, fill=(180, 180, 190))
    counter = f"{idx + 1} / {total}"
    cb = draw.textbbox((0, 0), counter, font=footer_font)
    draw.text((W - margin_x - (cb[2] - cb[0]), H - 38), counter, font=footer_font, fill=(180, 180, 190))

    img.save(path)


def run(cmd):
    subprocess.run(cmd, check=True)


def probe_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def assemble_video(
    scenes: list[Scene],
    narration_wavs: list[str],
    out_dir: str,
    final_path: str,
    footer_text: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
):
    total = len(scenes)
    clip_paths = []
    for idx, (scene, wav) in enumerate(zip(scenes, narration_wavs)):
        slide_png = os.path.join(out_dir, f"slide_{idx:02d}.png")
        clip = os.path.join(out_dir, f"scene_{idx:02d}.mp4")

        render_slide(scene, idx, total, slide_png, footer_text)

        narr_dur = probe_duration(wav)
        pad = 1.0
        dur = narr_dur + pad * 2

        vf = (
            f"scale=1600:-1,"
            f"zoompan=z='min(zoom+0.0012,1.15)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=25,"
            f"fade=t=in:st=0:d=0.6,fade=t=out:st={dur - 0.6:.2f}:d=0.6"
        )
        af = (f"adelay={int(pad * 1000)}|{int(pad * 1000)},apad,"
              f"afade=t=in:st=0:d=0.4,afade=t=out:st={dur - 0.5:.2f}:d=0.5")

        run([
            "ffmpeg", "-y", "-loop", "1", "-i", slide_png, "-i", wav,
            "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
            "-map", "[v]", "-map", "[a]",
            "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            "-c:a", "aac", "-b:a", "160k",
            clip,
        ])
        clip_paths.append(clip)
        if progress_cb:
            progress_cb(idx + 1, total)

    list_path = os.path.join(out_dir, "concat_list.txt")
    with open(list_path, "w") as f:
        for c in clip_paths:
            f.write(f"file '{c}'\n")

    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", final_path])

    # Clean up intermediates, keep only the final MP4.
    for p in clip_paths:
        os.remove(p)
    for idx in range(total):
        slide_png = os.path.join(out_dir, f"slide_{idx:02d}.png")
        if os.path.exists(slide_png):
            os.remove(slide_png)
    os.remove(list_path)

    return probe_duration(final_path)
