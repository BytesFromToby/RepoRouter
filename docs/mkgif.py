"""Generate docs/RepoRouter.gif — the README hero, animating real triage results.

Run from the repo root or docs/: python docs/mkgif.py
Requires Pillow. The featured results are from live runs against this repo's
own issues (qwen3:8b on local Ollama) — see the issue tracker.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "RepoRouter.gif"

# ---- canvas / scale ----
W, H, S = 1000, 400, 2
def sc(v): return int(round(v * S))

# ---- palette (GitHub dark) ----
BG     = (13, 17, 23)
BORDER = (48, 54, 61)
WHITE  = (235, 240, 246)
MUTED  = (139, 148, 158)
FAINT  = (110, 118, 129)
BLUE   = (88, 166, 255)
GREEN  = (63, 185, 80)
AMBER  = (240, 180, 70)
RED    = (248, 81, 73)
GREEN_F = (18, 51, 31)
AMBER_F = (60, 45, 13)
RED_F   = (61, 22, 24)


def font(path, size):
    try:
        return ImageFont.truetype(path, sc(size))
    except Exception:
        return ImageFont.load_default()


F_TITLE = font(r"C:\Windows\Fonts\segoeuib.ttf", 28)
F_SUB   = font(r"C:\Windows\Fonts\segoeui.ttf", 14)
F_CARD  = font(r"C:\Windows\Fonts\segoeuib.ttf", 18)
F_META  = font(r"C:\Windows\Fonts\segoeui.ttf", 13)
F_MONO  = font(r"C:\Windows\Fonts\consola.ttf", 15)
F_PILL  = font(r"C:\Windows\Fonts\segoeuib.ttf", 15)
F_BIG   = font(r"C:\Windows\Fonts\segoeuib.ttf", 21)

ROUTE_STYLE = {
    "RESPOND":  (GREEN, GREEN_F),
    "CLOSE":    (AMBER, AMBER_F),
    "ESCALATE": (RED,   RED_F),
}

# (number, title, role, category, docs line, route, route detail, outcome line)
ISSUES = [
    ("#4", "Triage removed the labels I added by hand", "bug",
     "reference/label-taxonomy.md",
     "RESPOND", "label: bug · priority P2",
     "comment posted — cites the exact doc line the behavior violates"),
    ("#5", "Support GitHub App authentication instead of a PAT", "feature",
     "docs/ROADMAP.md",
     "RESPOND", "label: enhancement",
     "comment posted — “planned for v0.4”, quoted from the roadmap"),
    ("#6", "RepoRouter should review pull requests too", "feature",
     "docs/ROADMAP.md — non-goals",
     "CLOSE", "labels: wontfix · enhancement",
     "closed — respectful decline citing the project's stated non-goals"),
    ("#8", "Grow your GitHub stars 10x with our promotion service", "spam",
     "short-circuited — no model call at all",
     "CLOSE", "label: invalid",
     "canned reply — prompt-injection-proof by construction"),
    ("#9", "Security: GITHUB_TOKEN may be exposed in the IssueLog files", "security",
     "short-circuited — the model never drafts these",
     "ESCALATE", "private brief to the maintainer",
     "NOTHING posted, NO labels — the report is never acknowledged in public"),
]


def text(d, x, y, s, f, fill):
    d.text((sc(x), sc(y)), s, font=f, fill=fill)


def text_w(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return (b[2] - b[0]) / S


def frame(issue_idx, stage, hold_summary=False):
    """stage: 0 card · 1 +category · 2 +docs · 3 +route · 4 +outcome"""
    img = Image.new("RGB", (sc(W), sc(H)), BG)
    d = ImageDraw.Draw(img)

    text(d, 24, 22, "RepoRouter", F_TITLE, BLUE)
    text(d, 26, 60, "an AI operator triaging GitHub issues — live results on a local 8B model",
         F_SUB, MUTED)
    cap = "live run · qwen3:8b · ollama"
    text(d, W - 24 - text_w(d, cap, F_META), 30, cap, F_META, FAINT)

    if hold_summary:
        cx = W / 2
        lines = [
            (F_BIG,  GREEN, "zero unsafe posts — across every live run"),
            (F_MONO, WHITE, "bug → doc-checked reply   feature → roadmap-checked   spam → canned close"),
            (F_MONO, RED,   "security → escalated privately; never posted, never labeled"),
            (F_SUB,  MUTED, "the model proposes — the harness validates everything before it posts"),
        ]
        y = 150
        for f, col, s in lines:
            text(d, cx - text_w(d, s, f) / 2, y, s, f, col)
            y += 52
        return img.resize((W, H), Image.LANCZOS)

    num, title, category, docs, route, detail, outcome = ISSUES[issue_idx]

    # issue card
    d.rounded_rectangle([sc(24), sc(96), sc(W - 24), sc(178)], radius=sc(10),
                        outline=BORDER, width=sc(2))
    text(d, 44, 110, f"{num}  {title}", F_CARD, WHITE)
    text(d, 44, 144, "opened just now · unprocessed", F_META, FAINT)

    y = 204
    if stage >= 1:
        text(d, 44, y, "category", F_MONO, FAINT)
        text(d, 160, y, "→", F_MONO, FAINT)
        text(d, 190, y, category, F_MONO,
             RED if category == "security" else (AMBER if category == "spam" else BLUE))
    y += 32
    if stage >= 2:
        text(d, 44, y, "docs", F_MONO, FAINT)
        text(d, 160, y, "→", F_MONO, FAINT)
        text(d, 190, y, docs, F_MONO, MUTED)
    y += 40
    if stage >= 3:
        col, fill = ROUTE_STYLE[route]
        label = f"{route}   ·   {detail}"
        pw = text_w(d, label, F_PILL) + 36
        d.rounded_rectangle([sc(44), sc(y - 8), sc(44 + pw), sc(y + 26)],
                            radius=sc(8), fill=fill, outline=col, width=sc(2))
        text(d, 62, y - 1, label, F_PILL, col)
    y += 48
    if stage >= 4:
        text(d, 44, y, outcome, F_SUB, WHITE if route != "ESCALATE" else RED)

    # progress dots
    for i in range(len(ISSUES)):
        col = BLUE if i == issue_idx else BORDER
        d.ellipse([sc(24 + i * 18), sc(H - 28), sc(32 + i * 18), sc(H - 20)], fill=col)

    return img.resize((W, H), Image.LANCZOS)


frames, durs = [], []
for idx in range(len(ISSUES)):
    for stage, ms in ((0, 650), (1, 550), (2, 550), (3, 900), (4, 1500)):
        frames.append(frame(idx, stage))
        durs.append(ms)
frames.append(frame(0, 0, hold_summary=True))
durs.append(3200)

frames[0].save(OUT, save_all=True, append_images=frames[1:],
               duration=durs, loop=0, optimize=True, disposal=2)
import os
print(f"{OUT.name}: {len(frames)} frames, {sum(durs)/1000:.1f}s, "
      f"{os.path.getsize(OUT)/1e6:.2f} MB")
