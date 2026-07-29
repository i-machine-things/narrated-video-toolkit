#!/usr/bin/env python3
"""Builds a narrated, animated ITAR/EAR export-control training video.

Narration WAVs are generated separately by generate_narration.py (run inside
the vibevoice venv) and must already exist in OUT as narr_00.wav .. narr_12.wav
before this script is run.
"""
import os
import subprocess
import textwrap
import json

from PIL import Image, ImageDraw, ImageFont

WORK = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(WORK, "out")
os.makedirs(OUT, exist_ok=True)

W, H = 1280, 720
FONT_DIR = "/usr/share/fonts/truetype/noto"
F_BOLD = os.path.join(FONT_DIR, "NotoSans-Bold.ttf")
F_REG = os.path.join(FONT_DIR, "NotoSans-Regular.ttf")
GOLD = (212, 175, 55)
NAVY = (11, 31, 58)
WHITE = (240, 240, 245)

def font(path, size):
    return ImageFont.truetype(path, size)

SCENES = [
    dict(
        id="title",
        icon="shield",
        bg=((13, 27, 51), (25, 48, 82)),
        accent=GOLD,
        title="ITAR & EAR Export Control Training",
        bullets=["A Sample Employee Introduction", "Export Compliance Basics"],
        narration=(
            "Welcome to this introduction to U.S. export control rules. "
            "In the next few minutes, you'll learn what I.T.A.R. and E.A.R. are, "
            "why they matter, and what they mean for your day to day work."
        ),
    ),
    dict(
        id="what_is",
        icon="globe",
        bg=((15, 35, 40), (20, 60, 65)),
        accent=(90, 200, 190),
        title="What Is Export Control?",
        bullets=[
            "U.S. laws restricting the transfer of items, software,",
            "and technical data to foreign countries or persons",
            "Exist to protect national security and foreign policy",
            "\"Export\" includes emails, cloud storage, travel, and conversations",
        ],
        narration=(
            "Export control laws restrict sending items, software, or technical "
            "information to foreign countries or foreign persons. They exist to "
            "protect national security and foreign policy interests. An export "
            "isn't just a shipment - it can be an email, a file in the cloud, "
            "a laptop you carry abroad, or even a conversation."
        ),
    ),
    dict(
        id="itar",
        icon="document",
        bg=((40, 18, 18), (70, 30, 30)),
        accent=(220, 90, 80),
        title="ITAR: Arms Regulations",
        bullets=[
            "International Traffic in Arms Regulations",
            "Administered by the U.S. State Department (D.D.T.C.)",
            "Covers defense articles, services, and technical data",
            "Governed by the U.S. Munitions List (U.S.M.L.)",
        ],
        narration=(
            "I-TAR stands for International Traffic in Arms Regulations. It's "
            "administered by the State Department's Directorate of Defense Trade "
            "Controls, or D.D.T.C. I-TAR governs defense articles, defense services, "
            "and related technical data listed on the United States Munitions List."
        ),
    ),
    dict(
        id="ear",
        icon="globe",
        bg=((16, 30, 46), (24, 52, 78)),
        accent=(100, 160, 230),
        title="EAR: Dual-Use Items",
        bullets=[
            "Export Administration Regulations",
            "Administered by the Commerce Department (B.I.S.)",
            "Covers \"dual-use\" commercial and military items",
            "Uses the Commerce Control List and E.C.C.N. codes",
        ],
        narration=(
            "EE-A-R stands for Export Administration Regulations, administered by "
            "the Commerce Department's Bureau of Industry and Security, or B.I.S. "
            "EE-A-R covers dual-use items - things with both commercial and military "
            "applications - classified using the Commerce Control List and E.C.C.N. codes."
        ),
    ),
    dict(
        id="differences",
        icon="scale",
        bg=((30, 24, 45), (52, 40, 74)),
        accent=(190, 140, 230),
        title="Key Differences",
        bullets=[
            "ITAR: inherently military, no minimum-content exception",
            "EAR: broader dual-use scope, some license exceptions apply",
            "Both require knowing your item's classification first",
            "When unsure, ask Export Compliance for a determination",
        ],
        narration=(
            "I-TAR items are inherently military, with almost no exceptions once "
            "something is on the list. EE-A-R covers a broader range of dual-use items "
            "and allows more license exceptions. Either way, the first step is always "
            "knowing your item's classification - and when you're not sure, ask your "
            "export compliance team for a determination."
        ),
    ),
    dict(
        id="license_requirements",
        icon="lock",
        bg=((36, 30, 14), (60, 50, 20)),
        accent=(230, 190, 90),
        title="Licensing & Screening",
        bullets=[
            "Determine if a license is required before you export",
            "Screen recipients against Denied Persons, Entity, and SDN lists",
            "ITAR transfers often need a Technical Assistance or",
            "Manufacturing License Agreement already on file",
            "Classification and licensing decisions belong to Export Compliance",
        ],
        narration=(
            "Before anything ships, sends, or travels, someone has to determine "
            "whether a license is required. That includes screening the recipient "
            "against restricted party lists, like the Entity List, the Denied "
            "Persons List, and the Specially Designated Nationals list. I-TAR "
            "transfers often require a Technical Assistance Agreement or "
            "Manufacturing License Agreement already on file. Classification and "
            "licensing decisions belong to your export compliance team, not to "
            "individual employees."
        ),
    ),
    dict(
        id="daily",
        icon="laptop",
        bg=((18, 36, 30), (28, 58, 48)),
        accent=(120, 210, 140),
        title="Where This Shows Up Day-to-Day",
        bullets=[
            "Emailing drawings or specs to an overseas office",
            "Foreign national coworkers viewing controlled data ('deemed export')",
            "Traveling internationally with a work laptop",
            "Describing controlled technology on a facility tour",
        ],
        narration=(
            "This shows up more often than people expect. Emailing a drawing to an "
            "overseas office is one example. Letting a foreign national colleague "
            "view controlled technical data counts as a, quote, deemed export. So "
            "does traveling internationally with a work laptop, or describing "
            "controlled technology out loud during a facility tour."
        ),
    ),
    dict(
        id="red_flags",
        icon="flag",
        bg=((42, 24, 12), (68, 40, 18)),
        accent=(235, 150, 70),
        title="Red Flags to Watch For",
        bullets=[
            "Customer is evasive about final destination or end use",
            "Order pattern doesn't match the customer's normal business",
            "Request to remove or disable safety or security features",
            "Shipment routed through an unrelated third country",
        ],
        narration=(
            "Watch for red flags. A customer who's evasive about the final "
            "destination or end use. An order that doesn't match the customer's "
            "normal line of business. A request to strip out safety or security "
            "features. Or a shipment routed through a country that has nothing to "
            "do with the deal. Any one of these is a reason to pause and loop in "
            "export compliance before you proceed."
        ),
    ),
    dict(
        id="penalties",
        icon="warning",
        bg=((45, 20, 15), (75, 32, 20)),
        accent=(240, 130, 60),
        title="Real Violations, Real Penalties",
        bullets=[
            "Civil penalties can reach into the millions of dollars",
            "Criminal penalties can include prison time",
            "Companies can lose export privileges entirely",
            "Individuals are personally liable, not just the company",
        ],
        narration=(
            "Violations are taken seriously. Civil penalties can reach into the "
            "millions of dollars per violation. Criminal violations can mean prison "
            "time. Companies can be debarred, losing export privileges altogether. "
            "And individual employees can be held personally liable, not just the company."
        ),
    ),
    dict(
        id="responsibilities",
        icon="check",
        bg=((14, 34, 40), (20, 56, 64)),
        accent=(90, 210, 200),
        title="Your Responsibilities",
        bullets=[
            "Know the classification before you share anything",
            "Verify citizenship and location before granting data access",
            "Don't discuss controlled details with uncleared foreign nationals",
            "When in doubt: STOP and ask your Export Compliance Officer",
        ],
        narration=(
            "Here's what's expected of you. Know the classification before "
            "sharing anything. Verify citizenship and location before granting "
            "access to controlled data. Don't discuss controlled technical details "
            "with uncleared foreign nationals. And above all - when in doubt, stop "
            "and ask your export compliance officer before you act."
        ),
    ),
    dict(
        id="quiz",
        icon="question",
        bg=((22, 22, 44), (38, 38, 72)),
        accent=(160, 170, 240),
        title="Quick Knowledge Check",
        bullets=[
            "Showing a controlled drawing to a foreign coworker? -> Deemed export",
            "Carrying a work laptop with controlled data abroad? -> Yes, it counts",
            "Who decides if a license is needed? -> Export Compliance, not you alone",
        ],
        narration=(
            "Quick knowledge check. Is showing a controlled drawing to a foreign "
            "national coworker an export? Yes - that's a deemed export. Does "
            "carrying a work laptop abroad count? Yes, if it holds controlled "
            "technical data. And who decides whether you need a license? Export "
            "compliance - not you alone. If any of those surprised you, that's "
            "exactly why this training exists."
        ),
    ),
    dict(
        id="summary",
        icon="list",
        bg=((20, 20, 40), (36, 36, 68)),
        accent=GOLD,
        title="Key Takeaways",
        bullets=[
            "ITAR = military items, regulated by the State Department",
            "EAR = dual-use items, regulated by the Commerce Department",
            "Deemed exports and travel count as real exports",
            "When in doubt, always ask before you share, send, or travel",
        ],
        narration=(
            "Let's recap. I-TAR covers military items and is regulated by the State "
            "Department. EE-A-R covers dual-use items and is regulated by the Commerce "
            "Department. Deemed exports, and even international travel, count as real "
            "exports. And when in doubt, always ask before you share, send, or travel."
        ),
    ),
    dict(
        id="closing",
        icon="shield",
        bg=((13, 27, 51), (25, 48, 82)),
        accent=GOLD,
        title="Thank You",
        bullets=[
            "Contact your Export Compliance Officer with questions",
            "This is a sample training - pair with your company's real policy",
        ],
        narration=(
            "Thank you for completing this introduction. Contact your export "
            "compliance officer with any questions. Remember, this is a sample "
            "training only, and should be paired with your organization's actual "
            "export compliance policy and qualified legal counsel."
        ),
    ),
]

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
        draw.polygon(
            [(cx - r * 0.6, cy - r), (cx + r, cy - r * 0.6), (cx - r * 0.6, cy - r * 0.2)],
            fill=color,
        )
    elif kind == "question":
        qfont = font(F_BOLD, int(size * 1.3))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=6)
        bbox = draw.textbbox((0, 0), "?", font=qfont)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), "?", font=qfont, fill=color)

def render_slide(scene, idx, total, path):
    img = gradient_bg(*scene["bg"])
    draw = ImageDraw.Draw(img)

    title_font = font(F_BOLD, 56)
    bullet_font = font(F_REG, 30)
    footer_font = font(F_REG, 20)

    margin_x = 70
    draw.text((margin_x, 70), scene["title"], font=title_font, fill=WHITE)
    tb = draw.textbbox((margin_x, 70), scene["title"], font=title_font)
    line_y = tb[3] + 18
    draw.line([(margin_x, line_y), (margin_x + 340, line_y)], fill=scene["accent"], width=6)

    by = line_y + 55
    for b in scene["bullets"]:
        wrapped = textwrap.wrap(b, width=46)
        draw.ellipse([margin_x, by + 10, margin_x + 14, by + 24], fill=scene["accent"])
        for wi, line in enumerate(wrapped):
            draw.text((margin_x + 34, by), line, font=bullet_font, fill=WHITE)
            by += 42
        by += 20

    draw_icon(draw, scene["icon"], W - 190, H // 2 - 20, 130, scene["accent"])

    draw.rectangle([0, H - 50, W, H], fill=(0, 0, 0))
    draw.text((margin_x, H - 38), "ITAR & EAR EXPORT CONTROL TRAINING", font=footer_font, fill=(180, 180, 190))
    counter = f"{idx + 1} / {total}"
    cb = draw.textbbox((0, 0), counter, font=footer_font)
    draw.text((W - margin_x - (cb[2] - cb[0]), H - 38), counter, font=footer_font, fill=(180, 180, 190))

    img.save(path)

def run(cmd, input_text=None):
    subprocess.run(cmd, check=True, input=input_text,
                    text=True if input_text is not None else None)

def probe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())

def main():
    total = len(SCENES)
    clip_paths = []

    for idx, scene in enumerate(SCENES):
        slide_png = os.path.join(OUT, f"slide_{idx:02d}.png")
        wav = os.path.join(OUT, f"narr_{idx:02d}.wav")
        clip = os.path.join(OUT, f"scene_{idx:02d}.mp4")

        render_slide(scene, idx, total, slide_png)

        if not os.path.exists(wav):
            raise FileNotFoundError(
                f"{wav} missing - run generate_narration.py (in the vibevoice venv) first"
            )

        narr_dur = probe_duration(wav)
        pad = 1.0
        dur = narr_dur + pad * 2

        vf = (
            f"scale=1600:-1,"
            f"zoompan=z='min(zoom+0.0012,1.15)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=25,"
            f"fade=t=in:st=0:d=0.6,fade=t=out:st={dur-0.6:.2f}:d=0.6"
        )
        af = f"adelay={int(pad*1000)}|{int(pad*1000)},apad,afade=t=in:st=0:d=0.4,afade=t=out:st={dur-0.5:.2f}:d=0.5"

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
        print(f"scene {idx} ({scene['id']}): narration {narr_dur:.1f}s, clip {dur:.1f}s")

    list_path = os.path.join(OUT, "concat_list.txt")
    with open(list_path, "w") as f:
        for c in clip_paths:
            f.write(f"file '{c}'\n")

    final = os.path.join(OUT, "itar_ear_export_control_training.mp4")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy", final,
    ])
    total_dur = probe_duration(final)
    print(f"FINAL: {final} ({total_dur:.1f}s = {total_dur/60:.2f} min)")

if __name__ == "__main__":
    main()
