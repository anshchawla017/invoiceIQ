"""
src/intro.py
------------
Cinematic opening screen for InvoiceIQ (about 7 seconds, pure CSS, no video file).

What plays:
  0.0s  fade up from black onto a night skyline of glass towers; the camera slowly pushes in
  1.0s  glowing cyan diamonds drift up through the glass
  2.0s  the InvoiceIQ mark draws itself, then the letters resolve out of a blur
  3.6s  a light sweep crosses the title
  4.2s  one line underneath: "Every invoice, checked."
  6.0s  the scene zooms through and fades out, revealing the app
  7.2s  the overlay is removed from view and stops blocking clicks

It is shown once per browser session (see show_intro in app.py). People who have
"reduce motion" switched on in their operating system never see it.
"""

from __future__ import annotations

import random

import streamlit as st

TITLE = "InvoiceIQ"
TAGLINE = "Every invoice, checked."

_CSS = """
<style>
[data-testid="stElementContainer"]:has(.iq-intro), .element-container:has(.iq-intro) {position: absolute; height: 0; margin: 0; padding: 0;}

.iq-intro {
  position: fixed; inset: 0; z-index: 2147483000; overflow: hidden; pointer-events: auto;
  background: #020610; color: #eaf7ff;
  animation: iqi-exit 1.2s cubic-bezier(.6, 0, .3, 1) 6s forwards;
}
@keyframes iqi-exit {
  0% {opacity: 1; visibility: visible; transform: scale(1); filter: blur(0);}
  99% {opacity: 0; visibility: visible; transform: scale(1.14); filter: blur(6px);}
  100% {opacity: 0; visibility: hidden; transform: scale(1.14); pointer-events: none;}
}

/* sky and glow behind the towers */
.iq-intro .sky {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 70% 55% at 50% 8%, rgba(56, 189, 248, .38), transparent 70%),
    radial-gradient(ellipse 90% 40% at 50% 100%, rgba(14, 116, 144, .45), transparent 70%),
    linear-gradient(180deg, #06172b 0%, #04101f 55%, #020814 100%);
}

/* towers: the whole stage slowly pushes in, like a dolly shot */
.iq-intro .stage {
  position: absolute; inset: -6%; transform-origin: 50% 62%;
  animation: iqi-push 7.2s cubic-bezier(.25, .1, .25, 1) forwards;
}
@keyframes iqi-push {from {transform: scale(1);} to {transform: scale(1.16);}}
.iq-intro .towers {position: absolute; left: 0; right: 0; bottom: 0; height: 100%; width: 100%;}
.iq-intro .towers .far {fill: #0a2540; opacity: .75;}
.iq-intro .towers .mid {fill: #0c3050;}
.iq-intro .towers .near {fill: #071a30;}
.iq-intro .towers .glass {fill: url(#iqi-glass);}
.iq-intro .towers .edge {stroke: rgba(125, 211, 252, .55); stroke-width: 1.2; fill: none;}

/* fade up from black */
.iq-intro .curtain {
  position: absolute; inset: 0; background: #000; pointer-events: none;
  animation: iqi-curtain 1.6s ease-out .1s forwards;
}
@keyframes iqi-curtain {to {opacity: 0;}}

/* slow diagonal light sweeping over the glass */
.iq-intro .beam {
  position: absolute; top: -20%; bottom: -20%; width: 22%; left: -30%;
  background: linear-gradient(90deg, transparent, rgba(186, 230, 253, .22), transparent);
  transform: skewX(-18deg);
  animation: iqi-beam 3.4s ease-in-out .6s forwards;
}
@keyframes iqi-beam {to {left: 130%;}}

/* holographic diamonds */
.iq-intro .gem {
  position: absolute; bottom: -8%; left: var(--x); width: var(--s); height: var(--s);
  clip-path: polygon(50% 0, 100% 50%, 50% 100%, 0 50%);
  background: linear-gradient(135deg, rgba(186, 240, 255, .95), rgba(34, 211, 238, .35) 55%, rgba(56, 189, 248, .8));
  filter: drop-shadow(0 0 6px rgba(56, 189, 248, .9));
  opacity: 0;
  animation: iqi-gem var(--t) ease-in-out var(--d) forwards;
}
@keyframes iqi-gem {
  0% {opacity: 0; transform: translateY(0) rotate(0) scale(.6);}
  15% {opacity: .95;}
  70% {opacity: .9;}
  100% {opacity: 0; transform: translateY(-115vh) rotate(var(--r)) scale(1.15);}
}
.iq-intro .net {position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; animation: iqi-net 4.6s ease-in-out 1.2s forwards;}
.iq-intro .net line {stroke: rgba(103, 232, 249, .35); stroke-width: 1;}
.iq-intro .net circle {fill: #a5f3fc;}
@keyframes iqi-net {0% {opacity: 0;} 25%, 75% {opacity: 1;} 100% {opacity: 0;}}

/* centre: mark + title + line */
.iq-intro .center {
  position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1.1rem;
  text-align: center;
}
.iq-intro .mark {width: clamp(120px, 16vw, 190px); height: auto; overflow: visible; filter: drop-shadow(0 0 14px rgba(56, 189, 248, .8));}
.iq-intro .mark path {
  fill: none; stroke: #7dd3fc; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round;
  stroke-dasharray: 420; stroke-dashoffset: 420;
  animation: iqi-draw 1.5s cubic-bezier(.5, 0, .2, 1) 1.7s forwards;
}
.iq-intro .mark path.b {animation-delay: 1.95s; stroke: #22d3ee;}
.iq-intro .mark .core {fill: #e0f7ff; stroke: none; opacity: 0; transform-origin: 60px 60px; animation: iqi-core 1s ease-out 3s forwards;}
@keyframes iqi-draw {to {stroke-dashoffset: 0;}}
@keyframes iqi-core {0% {opacity: 0; transform: scale(.2);} 60% {opacity: 1; transform: scale(1.4);} 100% {opacity: 1; transform: scale(1);}}

.iq-intro .title {
  position: relative; display: flex; font-family: 'Sora', 'DM Sans', 'Segoe UI', system-ui, sans-serif;
  font-weight: 700; font-size: clamp(2.6rem, 8.5vw, 6.4rem); letter-spacing: .02em; line-height: 1;
  padding: .1em .25em; overflow: hidden;
}
.iq-intro .title span {
  display: inline-block; opacity: 0; transform: translateY(.35em) scale(1.25); filter: blur(14px);
  background: linear-gradient(180deg, #ffffff 10%, #a5e8ff 55%, #38bdf8 100%); -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; color: transparent;
  text-shadow: none; animation: iqi-letter .9s cubic-bezier(.2, .8, .2, 1) calc(2.4s + var(--i) * .09s) forwards;
}
@keyframes iqi-letter {to {opacity: 1; transform: none; filter: blur(0) drop-shadow(0 0 16px rgba(56, 189, 248, .75));}}
.iq-intro .title::after {
  content: ""; position: absolute; top: 0; bottom: 0; left: -40%; width: 30%;
  background: linear-gradient(100deg, transparent, rgba(255, 255, 255, .85), transparent);
  mix-blend-mode: overlay; transform: skewX(-18deg);
  animation: iqi-sweep 1.1s ease-in-out 3.6s forwards;
}
@keyframes iqi-sweep {to {left: 130%;}}

.iq-intro .rule {height: 2px; width: 0; background: linear-gradient(90deg, transparent, #38bdf8, transparent); animation: iqi-rule 1.2s ease-out 3.7s forwards;}
@keyframes iqi-rule {to {width: min(56vw, 420px);}}
.iq-intro .tag {
  font-family: 'DM Sans', 'Segoe UI', system-ui, sans-serif; font-size: clamp(.95rem, 1.7vw, 1.2rem); letter-spacing: .14em;
  color: #bfe9fb; opacity: 0; transform: translateY(8px); animation: iqi-tag 1s ease-out 4.2s forwards;
}
@keyframes iqi-tag {to {opacity: .92; transform: none;}}

/* soft vignette keeps focus on the centre */
.iq-intro .vig {position: absolute; inset: 0; pointer-events: none; background: radial-gradient(ellipse at center, transparent 45%, rgba(0, 0, 0, .7) 100%);}

@media (prefers-reduced-motion: reduce) {.iq-intro {display: none !important;}}
@media (max-width: 640px) {.iq-intro .tag {letter-spacing: .08em;}}
</style>
"""


def _towers_svg() -> str:
    """Three layers of glass towers as one SVG, drawn from a fixed seed so it looks the same every time."""
    rng = random.Random(7)
    w, h = 1600, 900
    layers = []
    for cls, count, lo, hi, base in (("far", 15, 300, 560, h), ("mid", 11, 380, 700, h), ("near", 7, 460, 820, h)):
        x, step = -40.0, (w + 80) / count
        rects, glass, edges = [], [], []
        for _ in range(count):
            bw = step * rng.uniform(.8, 1.05)
            th = rng.uniform(lo, hi)
            y = base - th
            rects.append(f'<rect class="{cls}" x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{th:.0f}"/>')
            if cls != "far":
                glass.append(f'<rect class="glass" x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{th:.0f}"/>')
                for k in range(1, 5):  # vertical glass panel lines
                    lx = x + bw * k / 5
                    edges.append(f'M{lx:.0f} {y:.0f}V{base}')
            edges.append(f'M{x:.0f} {y:.0f}H{x + bw:.0f}')
            x += step
        layers.append("".join(rects) + "".join(glass) + f'<path class="edge" d="{"".join(edges)}" opacity="{.35 if cls == "mid" else .6}"/>')
    return (
        f'<svg class="towers" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">'
        '<defs><linearGradient id="iqi-glass" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#38bdf8" stop-opacity=".28"/><stop offset=".5" stop-color="#0ea5e9" stop-opacity=".05"/>'
        '<stop offset="1" stop-color="#22d3ee" stop-opacity=".22"/></linearGradient></defs>'
        + "".join(layers) + '</svg>'
    )


def _gems_html() -> str:
    rng = random.Random(21)
    out = []
    for _ in range(22):
        out.append(
            f'<i class="gem" style="--x:{rng.uniform(4, 96):.1f}%;--s:{rng.uniform(10, 34):.0f}px;'
            f'--t:{rng.uniform(3.4, 5.4):.1f}s;--d:{rng.uniform(1.0, 3.2):.2f}s;--r:{rng.randint(-160, 160)}deg"></i>')
    return "".join(out)


def _net_svg() -> str:
    """A few glowing nodes joined by thin lines, like data points connecting."""
    rng = random.Random(5)
    pts = [(rng.uniform(8, 92), rng.uniform(12, 88)) for _ in range(16)]
    lines, dots = [], []
    for i, (x, y) in enumerate(pts):
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r=".35"/>')
        nx, ny = pts[(i * 5 + 3) % len(pts)]
        lines.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{nx:.1f}" y2="{ny:.1f}"/>')
    return ('<svg class="net" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
            + "".join(lines) + "".join(dots) + '</svg>')


def _mark_svg() -> str:
    """Two nested chevrons and a bright core: a stylised 'checked' arrow that echoes the glowing shape in the reference."""
    return (
        '<svg class="mark" viewBox="0 0 120 120" aria-hidden="true">'
        '<path d="M60 8 L108 60 L60 112 L12 60 Z"/>'
        '<path class="b" d="M60 30 L88 60 L60 90 L32 60 Z"/>'
        '<circle class="core" cx="60" cy="60" r="7"/></svg>'
    )


def _build_html() -> str:
    letters = "".join(f'<span style="--i:{i}">{ch}</span>' for i, ch in enumerate(TITLE))
    body = (
        '<div class="iq-intro" role="presentation">'
        '<div class="sky"></div>'
        f'<div class="stage">{_towers_svg()}</div>'
        '<div class="beam"></div>'
        f'{_net_svg()}{_gems_html()}'
        '<div class="vig"></div>'
        f'<div class="center">{_mark_svg()}<div class="title" aria-label="{TITLE}">{letters}</div>'
        f'<div class="rule"></div><div class="tag">{TAGLINE}</div></div>'
        '<div class="curtain"></div>'
        '</div>'
    )
    return _CSS + body


def show_intro() -> None:
    """Play the opening screen once per browser session. Call right after st.set_page_config."""
    if st.session_state.get("iq_intro_played"):
        return
    st.session_state["iq_intro_played"] = True
    st.markdown(_build_html(), unsafe_allow_html=True)
