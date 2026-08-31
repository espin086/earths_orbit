"""Build the static, self-contained index.html for GitHub Pages.

Run: uv run src/generate_site.py
Output: docs/index.html

v2: dropped Plotly entirely. Plotly's frame animation forces either a full
redraw (janky) or restyle-only updates (can't do highlights, banners, or
smooth zoom). Everything now renders on <canvas> driven by
requestAnimationFrame, with planet data computed here in Python and embedded
as JSON. The Kepler solver is duplicated in ~15 lines of JS so the page can
compute positions at any time step without shipping thousands of frames.
"""

import json
from pathlib import Path

from orbital_mechanics import EARTH_AXIAL_TILT_DEG, PLANETS

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

FUN_FACTS = {
    "Mercury": "A year on Mercury is only 88 days, but one Mercury day (sunrise to sunrise) lasts 176 Earth days!",
    "Venus": "Venus spins backwards, and it's the hottest planet — about 465°C, hot enough to melt lead.",
    "Earth": "Home! Earth is the only planet not named after a Greek or Roman god.",
    "Mars": "Mars has the tallest volcano in the solar system: Olympus Mons, almost 3× the height of Mt. Everest.",
    "Jupiter": "Jupiter is so big that all the other planets could fit inside it. Its Great Red Spot is a storm bigger than Earth.",
    "Saturn": "Saturn's rings are made of billions of chunks of ice, from dust-size to house-size.",
    "Uranus": "Uranus rolls around the Sun on its side, like a bowling ball.",
}

# Light-travel time from the Sun, minutes (distance / c).
C_KM_PER_MIN = 299_792.458 * 60


def planet_json() -> str:
    data = []
    for p in PLANETS:
        data.append(
            dict(
                name=p.name,
                a=p.semi_major_axis_au,
                e=p.eccentricity,
                period=p.period_days,
                color=p.color,
                distKm=p.semi_major_axis_km,
                lightMin=p.semi_major_axis_km / C_KM_PER_MIN,
                fact=FUN_FACTS[p.name],
            )
        )
    return json.dumps(data)


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Earth's Orbit — An Interactive Explorer for 5th Grade</title>
<meta name="description" content="Interactive explorer for Earth's orbit, Kepler's laws, the true scale of the solar system, and why we have seasons — built for a 5th grade classroom." />
<style>
  :root {
    --bg-deep: #0b1026;
    --bg-panel: #141a35;
    --bg-card: #1b2246;
    --text: #eef1ff;
    --text-muted: #a6adcf;
    --accent: #4fd1c5;
    --accent-warm: #ff8fa3;
    --sun: #ffd166;
    --grid: #2a3260;
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    background: var(--bg-deep);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    line-height: 1.55;
    overflow-x: hidden;
  }
  header { padding: 2.2rem 1rem 1rem; text-align: center; max-width: 860px; margin: 0 auto; }
  header h1 { font-size: clamp(1.4rem, 4.5vw, 2.1rem); margin: 0 0 0.4rem; }
  header p { color: var(--text-muted); font-size: clamp(0.95rem, 2.5vw, 1.05rem); margin: 0; }

  main { max-width: 1000px; margin: 0 auto; padding: 0 0.75rem 3rem; }
  section { margin: 0 0 2.8rem; }

  .panel {
    background: var(--bg-panel);
    border: 1px solid var(--grid);
    border-radius: 14px;
    padding: clamp(0.75rem, 2.5vw, 1.25rem);
  }
  .panel h2 { font-size: clamp(1.1rem, 3.5vw, 1.45rem); margin: 0 0 0.35rem; }
  .panel .subtitle { color: var(--text-muted); font-size: clamp(0.88rem, 2.4vw, 0.98rem); margin: 0 0 0.9rem; }

  .canvas-wrap { position: relative; width: 100%; }
  canvas { display: block; width: 100%; border-radius: 10px; background: #0d1330; touch-action: manipulation; }

  /* Controls row: wraps cleanly on narrow screens instead of overlapping. */
  .controls { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin: 0.75rem 0 0; }
  button.ctl {
    background: var(--bg-card); color: var(--text); border: 1px solid var(--grid);
    border-radius: 8px; padding: 0.45rem 0.9rem; font-size: 0.95rem; cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  button.ctl:hover { border-color: var(--accent); }
  button.ctl.primary { background: var(--accent); color: #06281f; border-color: var(--accent); font-weight: 600; }
  button.ctl.active { background: var(--accent); color: #06281f; border-color: var(--accent); }
  .ctl-label { color: var(--text-muted); font-size: 0.85rem; }
  input[type=range] { accent-color: var(--accent); }

  /* Live banner: the "what's happening right now" text under each animation. */
  .banner {
    margin-top: 0.7rem; padding: 0.6rem 0.9rem; border-radius: 10px;
    background: rgba(79,209,197,0.10); border: 1px solid rgba(79,209,197,0.35);
    font-size: clamp(0.9rem, 2.4vw, 1rem); min-height: 2.6rem;
  }
  .banner strong { color: var(--accent); }
  .banner.warm { background: rgba(255,143,163,0.10); border-color: rgba(255,143,163,0.4); }
  .banner.warm strong { color: var(--accent-warm); }

  /* Planet info popup card (click a planet in panel 1). */
  .info-card {
    position: absolute; top: 10px; right: 10px; max-width: min(300px, 70%);
    background: var(--bg-card); border: 1px solid var(--accent); border-radius: 10px;
    padding: 0.7rem 0.9rem; font-size: 0.88rem; display: none; z-index: 5;
    box-shadow: 0 6px 24px rgba(0,0,0,0.5);
  }
  .info-card h3 { margin: 0 0 0.3rem; font-size: 1rem; }
  .info-card .close { position: absolute; top: 4px; right: 8px; cursor: pointer; color: var(--text-muted); background: none; border: none; font-size: 1rem; }
  .info-card p { margin: 0.25rem 0; color: var(--text-muted); }
  .info-card p b { color: var(--text); }

  .caption { max-width: 760px; color: var(--text-muted); font-size: clamp(0.88rem, 2.4vw, 0.96rem); margin: 0.8rem 0 0; }
  .caption strong { color: var(--text); }

  /* Glossary words: dotted underline + tap/hover tooltip. */
  .gl { border-bottom: 1px dotted var(--accent); cursor: help; position: relative; color: var(--text); }
  .gl:hover::after, .gl:focus::after {
    content: attr(data-def);
    position: absolute; left: 50%; transform: translateX(-50%); bottom: 130%;
    background: var(--bg-card); color: var(--text); border: 1px solid var(--accent);
    border-radius: 8px; padding: 0.5rem 0.7rem; width: max-content; max-width: min(260px, 80vw);
    font-size: 0.82rem; line-height: 1.4; z-index: 20; box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  }

  .glossary { background: var(--bg-panel); border: 1px solid var(--grid); border-radius: 14px; padding: 1rem 1.25rem; margin-bottom: 2.5rem; }
  .glossary h2 { font-size: 1.1rem; margin: 0 0 0.5rem; }
  .glossary dl { display: grid; grid-template-columns: auto 1fr; gap: 0.3rem 0.9rem; margin: 0; font-size: 0.9rem; }
  .glossary dt { color: var(--accent); font-weight: 600; white-space: nowrap; }
  .glossary dd { margin: 0; color: var(--text-muted); }
  @media (max-width: 520px) { .glossary dl { grid-template-columns: 1fr; } .glossary dt { margin-top: 0.4rem; } }

  /* Kepler 3 planet chips + equation cards. */
  .chips { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.6rem 0 1rem; }
  .chip {
    border: 2px solid var(--grid); background: var(--bg-card); color: var(--text);
    border-radius: 999px; padding: 0.35rem 0.85rem; cursor: pointer; font-size: 0.92rem;
    transition: border-color 0.15s, transform 0.1s;
  }
  .chip:hover { transform: translateY(-1px); }
  .chip.done { border-color: var(--chip-color, var(--accent)); }
  .eq-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
  @media (max-width: 640px) { .eq-grid { grid-template-columns: 1fr; } }
  .eq-card { background: var(--bg-card); border: 1px solid var(--grid); border-radius: 10px; padding: 0.8rem 1rem; }
  .eq-card h4 { margin: 0 0 0.35rem; font-size: 0.95rem; color: var(--text-muted); font-weight: 600; }
  .eq-card .math { font-size: clamp(1rem, 3vw, 1.25rem); font-family: ui-monospace, Menlo, monospace; overflow-x: auto; white-space: nowrap; padding-bottom: 0.2rem; }
  .eq-bar-track { background: var(--bg-deep); border-radius: 6px; height: 26px; margin-top: 0.55rem; overflow: hidden; }
  .eq-bar { height: 100%; width: 0%; border-radius: 6px; transition: width 0.9s ease; display: flex; align-items: center; padding-left: 8px; font-size: 0.8rem; font-weight: 700; color: #06281f; white-space: nowrap; }
  .verdict { margin-top: 0.9rem; font-size: clamp(0.95rem, 2.6vw, 1.05rem); min-height: 1.6rem; }
  .verdict b { color: var(--accent); }

  footer { text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 2rem 1rem 3rem; }
  footer a { color: var(--accent); }
</style>
</head>
<body>
<header>
  <h1>🌍 Earth's Orbit — An Interactive Explorer</h1>
  <p>Press Play on each picture, drag the sliders, and click the planets. Words with a <span class="gl" data-def="Like this! Hover or tap a dotted word to see what it means.">dotted line</span> under them show their meaning when you tap them.</p>
</header>

<main>

<div class="glossary">
  <h2>🔤 Words to know</h2>
  <dl>
    <dt>orbit</dt><dd>The path a planet follows as it travels around the Sun.</dd>
    <dt>AU</dt><dd>"Astronomical Unit" — the distance from Earth to the Sun, about 150 million km. It's our measuring stick for space.</dd>
    <dt>ellipse</dt><dd>A stretched circle (an oval). Every planet's orbit is an ellipse, not a perfect circle.</dd>
    <dt>axis</dt><dd>The invisible line a planet spins around, like the rod through a spinning top.</dd>
    <dt>equinox</dt><dd>The two days each year (March &amp; September) when day and night are the same length everywhere.</dd>
    <dt>solstice</dt><dd>The longest day of the year (June, for us) or the shortest (December).</dd>
    <dt>a (semi-major axis)</dt><dd>A planet's average distance from the Sun, measured in AU.</dd>
    <dt>T (period)</dt><dd>How long one full trip around the Sun takes — the planet's "year."</dd>
  </dl>
</div>

<!-- ══════════════════ PANEL 4: TRUE SCALE ══════════════════ -->
<section>
  <div class="panel">
    <h2>1. How Far Is Far? Reading Giant Numbers With Exponents</h2>
    <p class="subtitle">This strip shows the real spacing of the planets — no shrinking the gaps. The distances get so big that scientists write them with <span class="gl" data-def="A short way to write huge numbers using a power of 10. The little raised number (the exponent) tells you how many times to multiply by 10 — or how many zeros to write.">exponents</span> instead of a wall of zeros. Press Play to watch the numbers grow as you head out from the Sun.</p>
    <div class="canvas-wrap">
      <canvas id="cv4" height="300"></canvas>
      <div class="info-card" id="info4">
        <button class="close" aria-label="Close">✕</button>
        <h3 id="info4-name"></h3>
        <p><b id="info4-dist"></b> from the Sun</p>
        <p>As an exponent: <b id="info4-sci"></b></p>
        <p>Light takes <b id="info4-light"></b> to get here</p>
        <p id="info4-fact"></p>
      </div>
    </div>
    <div class="controls">
      <button class="ctl primary" id="play4">▶ Ride the light beam</button>
      <button class="ctl" id="reset4">↺ Back to the Sun</button>
      <span class="ctl-label">Zoom:</span>
      <button class="ctl zoom4 active" data-zoom="Mars">Inner planets</button>
      <button class="ctl zoom4" data-zoom="Jupiter">To Jupiter</button>
      <button class="ctl zoom4" data-zoom="Uranus">Whole strip</button>
      <span class="ctl-label">Trip speed:</span>
      <input type="range" id="speed4" min="1" max="10" step="1" value="4" />
    </div>
    <div class="banner warm" id="banner4">Earth sits <strong>1.5 × 10⁸ km</strong> from the Sun — that's a 1.5 with <strong>8 zeros</strong> after it. Every time that little exponent goes up by 1, the real number gets <strong>10 times bigger</strong>. <strong>Click any planet</strong> to see its distance both ways.</div>
    <p class="caption"><strong>This is your relative size idea in action:</strong> Uranus isn't small, it just looks small because it's far away — the same reason a plane looks tiny in the sky even though it's huge up close. <strong>Look how squished the rocky planets are!</strong> Mercury, Venus, Earth, and Mars all crowd near the Sun, then space gets emptier and emptier. <strong>Watch the exponent, not just the number:</strong> Earth is 1.5 × 10⁸ km out, Jupiter is 7.79 × 10⁸ km (same-size exponent, bigger first number), but Uranus jumps to 2.87 × 10⁹ km — that exponent flipping from <span class="gl" data-def="10⁸ means 1 followed by 8 zeros: 100,000,000.">8 to 9</span> means Uranus is over <strong>10 times farther</strong> than Earth, not just a little farther.</p>
  </div>
</section>

<!-- ══════════════════ PANEL 5: SEASONS ══════════════════ -->
<section>
  <div class="panel">
    <h2>2. Why We Have Seasons</h2>
    <p class="subtitle">Earth is tilted 23.4° — and that tilt <strong>always points the same way in space</strong> as Earth circles the Sun. Press Play and watch the season change at each labeled stop.</p>
    <div class="canvas-wrap"><canvas id="cv5" height="560"></canvas></div>
    <div class="controls">
      <button class="ctl primary" id="play5">▶ Play</button>
      <span class="ctl-label">Jump to:</span>
      <button class="ctl jump5" data-deg="180">June ☀️</button>
      <button class="ctl jump5" data-deg="270">September 🍂</button>
      <button class="ctl jump5" data-deg="0">December ❄️</button>
      <button class="ctl jump5" data-deg="90">March 🌸</button>
    </div>
    <div class="banner" id="banner5">The four labeled stops are the four "corner days" of the year: two <strong>equinoxes</strong> (equal day &amp; night) and two <strong>solstices</strong> (longest and shortest days).</div>
    <p class="caption"><strong>The big idea:</strong> seasons are NOT about being closer to the Sun. They happen because the tilt makes the northern half of Earth lean <em>toward</em> the Sun in June (more direct sunlight = summer) and <em>away</em> in December (slanted sunlight = winter). The yellow glow on the little Earth shows which side faces the Sun.</p>
  </div>
</section>


</main>

<footer>
  Built with Python (NumPy for the orbital mechanics) and hand-rolled canvas animation —
  <a href="https://github.com/espin086/earths_orbit">source on GitHub</a>. Static page, no server required.
</footer>

<script>
"use strict";
const PLANETS = __PLANET_DATA__;
const EARTH = PLANETS[2];
const TILT_DEG = __TILT__;

// ---------- shared math ----------
function solveE(M, e) {           // Kepler's equation, Newton's method
  let E = M;
  for (let i = 0; i < 20; i++) {
    const d = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    E -= d;
    if (Math.abs(d) < 1e-8) break;
  }
  return E;
}
function posAt(p, day) {          // [x, y] in AU, Sun at origin (focus)
  const M = 2 * Math.PI * ((day % p.period) / p.period);
  const E = solveE(M, p.e);
  return [p.a * (Math.cos(E) - p.e), p.a * Math.sqrt(1 - p.e * p.e) * Math.sin(E)];
}
function orbitPath(p, n = 180) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const E = solveE(2 * Math.PI * i / n, p.e);
    pts.push([p.a * (Math.cos(E) - p.e), p.a * Math.sqrt(1 - p.e * p.e) * Math.sin(E)]);
  }
  return pts;
}
function fmt(n, d = 2) { return n.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }); }
function fmtInt(n) { return Math.round(n).toLocaleString("en-US"); }
const SUPER = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹" };
function sciNotation(km) {                 // "7.79 x 10^8 km" -> readable exponent form
  if (km <= 0) return "0 km";
  const exp = Math.floor(Math.log10(km));
  const mant = km / Math.pow(10, exp);
  const expDigits = String(exp).split("").map(c => SUPER[c] || c).join("");
  return `${fmt(mant, 2)} × 10${expDigits} km`;
}

// Crisp canvas on any screen; re-renders on resize (fixes the overlap /
// non-responsive complaint — the canvas always matches its container).
function fitCanvas(cv, aspect) {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth;
  const h = Math.max(240, Math.round(w * aspect));
  cv.width = w * dpr;
  cv.height = h * dpr;
  cv.style.height = h + "px";
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

const C = { bg: "#0d1330", grid: "#2a3260", text: "#eef1ff", muted: "#a6adcf", sun: "#ffd166", accent: "#4fd1c5", warm: "#ff8fa3" };

function drawSun(ctx, x, y, r) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r * 2.2);
  g.addColorStop(0, "#fff3c4"); g.addColorStop(0.35, C.sun); g.addColorStop(1, "rgba(255,209,102,0)");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(x, y, r * 2.2, 0, 7); ctx.fill();
  ctx.fillStyle = C.sun;
  ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
}

// Label placement that avoids collisions: try 8 spots around the dot, pick
// the first that doesn't overlap an already-placed label box.
function placeLabels(ctx, items, fontPx) {
  ctx.font = `${fontPx}px 'Segoe UI', sans-serif`;
  const placed = [];
  const offsets = [[0, -1.6], [1.4, -1], [1.4, 1.2], [0, 1.9], [-1.4, 1.2], [-1.4, -1], [2, 0], [-2, 0]];
  for (const it of items) {
    const tw = ctx.measureText(it.text).width;
    let box = null;
    for (const [ox, oy] of offsets) {
      const cx = it.x + ox * it.r * 3, cy = it.y + oy * it.r * 3;
      const b = { x0: cx - tw / 2 - 2, x1: cx + tw / 2 + 2, y0: cy - fontPx / 2 - 2, y1: cy + fontPx / 2 + 2, cx, cy };
      if (!placed.some(p => b.x0 < p.x1 && b.x1 > p.x0 && b.y0 < p.y1 && b.y1 > p.y0)) { box = b; break; }
    }
    if (!box) { const cx = it.x, cy = it.y - it.r * 3; box = { x0: cx, x1: cx, y0: cy, y1: cy, cx, cy }; }
    placed.push(box);
    ctx.fillStyle = it.color || C.muted;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(it.text, box.cx, box.cy);
  }
}

// ══════════════════ PANEL 4 ══════════════════
(function panel4() {
  const cv = document.getElementById("cv4");
  const playBtn = document.getElementById("play4");
  const banner = document.getElementById("banner4");
  const speed = document.getElementById("speed4");
  const info = document.getElementById("info4");
  const fullMaxMin = PLANETS[PLANETS.length - 1].lightMin * 1.04;  // full trip, light-minutes
  const KM_PER_LIGHTMIN = PLANETS[0].distKm / PLANETS[0].lightMin;
  let zoomTo = "Mars";                          // which planet's distance sets the visible range
  let maxMin = PLANETS.find(p => p.name === zoomTo).lightMin * 1.15;
  let t = 0, playing = false;   // t = light-minutes elapsed
  let passed = -1;
  let screenPos = [];           // last-drawn planet screen positions, for click detection

  function fmtClock(min) {
    if (min < 60) return `${fmt(min, 1)} minutes`;
    const h = Math.floor(min / 60), m = Math.round(min % 60);
    return `${h} h ${m} min`;
  }

  function draw() {
    const { ctx, w, h } = fitCanvas(cv, Math.min(0.5, Math.max(0.34, 300 / cv.clientWidth)));
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, w, h);
    const padL = 30, padR = 20;
    const trackW = w - padL - padR;
    const yTrack = h * 0.52;
    const X = lm => padL + lm / maxMin * trackW;   // LINEAR in real distance

    // stars
    ctx.fillStyle = "rgba(255,255,255,0.22)";
    for (let i = 0; i < 50; i++) ctx.fillRect((i * 173 % 1000) / 1000 * w, (i * 71 % 1000) / 1000 * h, 1.2, 1.2);

    // track line
    ctx.strokeStyle = C.grid; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(padL, yTrack); ctx.lineTo(padL + trackW, yTrack); ctx.stroke();

    // traveled portion glows
    if (t > 0) {
      ctx.strokeStyle = C.sun; ctx.lineWidth = 3; ctx.globalAlpha = 0.85;
      ctx.beginPath(); ctx.moveTo(padL, yTrack); ctx.lineTo(X(Math.min(t, maxMin)), yTrack); ctx.stroke();
      ctx.globalAlpha = 1;
    }

    drawSun(ctx, padL, yTrack, 10);

    // planets at TRUE linear positions. Labels alternate above/below AND get
    // pushed apart per side so the crowded inner planets never overlap.
    const fs = Math.max(9.5, Math.min(12.5, w / 60));
    ctx.font = `${fs}px 'Segoe UI', sans-serif`; ctx.textAlign = "center";
    const minGap = Math.max(52, fs * 5.2);
    const visible = PLANETS.filter(p => p.lightMin <= maxMin * 1.02);
    const slots = { above: [], below: [] };
    visible.forEach((p, i) => {
      const side = i % 2 === 0 ? "above" : "below";
      slots[side].push({ p, i, px: X(p.lightMin), lx: X(p.lightMin) });
    });
    screenPos = [];
    for (const side of ["above", "below"]) {          // spread labels left-to-right
      const arr = slots[side];
      for (let k = 1; k < arr.length; k++) arr[k].lx = Math.max(arr[k].lx, arr[k - 1].lx + minGap);
      const over = arr.length ? arr[arr.length - 1].lx - (w - 34) : 0;   // keep last label on-screen
      if (over > 0) for (const s of arr) s.lx -= over * (s.lx - arr[0].lx) / Math.max(1, arr[arr.length - 1].lx - arr[0].lx);
    }
    for (const side of ["above", "below"]) {
      const above = side === "above";
      for (const s of slots[side]) {
        const { p, i, px, lx } = s;
        const reached = t >= p.lightMin;
        ctx.fillStyle = p.color; ctx.globalAlpha = reached || !playing ? 1 : 0.45;
        ctx.beginPath(); ctx.arc(px, yTrack, i >= 4 ? 7 : 4.5, 0, 7); ctx.fill();
        ctx.globalAlpha = 1;
        ctx.fillStyle = reached ? C.text : C.muted;
        const ty1 = above ? yTrack - 40 : yTrack + 28;
        const ty2 = above ? yTrack - 26 : yTrack + 42;
        ctx.fillText(p.name, lx, ty1);
        ctx.fillText(fmtClock(p.lightMin), lx, ty2);
        ctx.strokeStyle = C.grid; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(px, yTrack + (above ? -10 : 10)); ctx.lineTo(lx, above ? ty1 + 9 : ty1 - 11); ctx.stroke();
        screenPos.push({ p, px, py: yTrack });
      }
    }

    // the light beam
    if (t > 0 && t < maxMin) {
      const bx = X(t);
      const g = ctx.createRadialGradient(bx, yTrack, 0, bx, yTrack, 14);
      g.addColorStop(0, "#ffffff"); g.addColorStop(0.4, C.sun); g.addColorStop(1, "rgba(255,209,102,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(bx, yTrack, 14, 0, 7); ctx.fill();
      ctx.fillStyle = C.text; ctx.font = "18px sans-serif"; ctx.fillText("✨", bx, yTrack - 16);
    }

    // clock
    ctx.fillStyle = C.text; ctx.font = `600 ${Math.max(13, Math.min(17, w / 44))}px 'Segoe UI', sans-serif`; ctx.textAlign = "left";
    const kmSoFar = Math.min(t, maxMin) * KM_PER_LIGHTMIN;
    ctx.fillText(`📏 Distance so far: ${sciNotation(kmSoFar)}  (${fmtClock(Math.min(t, maxMin))} at light speed)`, padL, 16);
  }

  function tick() {
    if (playing) {
      t += Number(speed.value) * 0.35;
      let idx = -1;
      PLANETS.forEach((p, i) => { if (t >= p.lightMin) idx = i; });
      if (idx > passed) {
        passed = idx;
        const p = PLANETS[idx];
        banner.innerHTML = `✨ Passing <strong>${p.name}</strong> — <strong>${sciNotation(p.distKm)}</strong> from the Sun (${p.name === "Earth" ? "1 AU, our home distance" : fmt(p.a, 1) + " AU"}). That took ${fmtClock(p.lightMin)} at light speed.`;
      }
      if (t >= maxMin) {
        playing = false; playBtn.textContent = "▶ Ride the light beam";
        const finalKm = maxMin * KM_PER_LIGHTMIN;
        banner.innerHTML = `🏁 <strong>You've gone ${sciNotation(finalKm)}.</strong> Try a bigger zoom to watch that exponent climb even higher — all the way out to Uranus it hits <strong>10⁹</strong>.`;
      }
    }
    draw();
    requestAnimationFrame(tick);
  }
  playBtn.addEventListener("click", () => {
    if (t >= maxMin) { t = 0; passed = -1; }
    playing = !playing;
    playBtn.textContent = playing ? "⏸ Pause" : "▶ Ride the light beam";
  });
  document.getElementById("reset4").addEventListener("click", () => {
    t = 0; passed = -1; playing = false; playBtn.textContent = "▶ Ride the light beam";
    banner.innerHTML = "Back at the Sun. Press play to ride out again — watch how long the empty stretches get past Mars.";
  });
  document.querySelectorAll(".zoom4").forEach(b => b.addEventListener("click", () => {
    document.querySelectorAll(".zoom4").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    zoomTo = b.dataset.zoom;
    maxMin = PLANETS.find(p => p.name === zoomTo).lightMin * 1.15;
    t = 0; passed = -1; playing = false; playBtn.textContent = "▶ Ride the light beam";
    draw();
  }));
  cv.addEventListener("click", (ev) => {
    const rect = cv.getBoundingClientRect();
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    let best = null, bestD = 26;
    for (const s of screenPos) {
      const d = Math.hypot(mx - s.px, my - s.py);
      if (d < bestD) { bestD = d; best = s; }
    }
    if (!best) { info.style.display = "none"; return; }
    const p = best.p;
    info.querySelector("#info4-name").textContent = p.name;
    info.querySelector("#info4-dist").textContent = `${fmt(p.distKm / 1e6, 0)} million km (${p.name === "Earth" ? "1 AU" : fmt(p.a, 2) + " AU"})`;
    info.querySelector("#info4-sci").textContent = sciNotation(p.distKm);
    info.querySelector("#info4-light").textContent = fmtClock(p.lightMin);
    info.querySelector("#info4-fact").textContent = p.fact;
    info.style.display = "block";
  });
  info.querySelector(".close").addEventListener("click", () => info.style.display = "none");
  new ResizeObserver(draw).observe(cv);
  requestAnimationFrame(tick);
})();

// ══════════════════ PANEL 5 ══════════════════
(function panel5() {
  const cv = document.getElementById("cv5");
  const playBtn = document.getElementById("play5");
  const banner = document.getElementById("banner5");
  const tilt = TILT_DEG * Math.PI / 180;
  let deg = 180, playing = false;          // start at June so it opens on summer
  let lastStation = -1;

  // Axis tilt is drawn leaning toward +x, so the solstices sit on the ±x axis:
  // at 180° (left) the N pole leans toward the Sun (June), at 0° (right) away
  // (December). Equinoxes are on ±y. Travel order with deg increasing:
  // Dec → Mar → Jun → Sep, the real calendar order.
  const stations = [
    { deg: 90,  short: "MARCH EQUINOX",     emoji: "🌸", season: "Spring", text: "<strong>March Equinox (around March 20):</strong> Earth's tilt points sideways to the Sun. Day and night are equal — 12 hours each. Spring begins in the north." },
    { deg: 180, short: "JUNE SOLSTICE",     emoji: "☀️", season: "Summer", text: "<strong>June Solstice (around June 21):</strong> the North Pole leans toward the Sun. Longest day of the year — summer begins in the north." },
    { deg: 270, short: "SEPTEMBER EQUINOX", emoji: "🍂", season: "Fall",   text: "<strong>September Equinox (around Sept 22):</strong> tilt points sideways again. Equal day and night. Fall begins in the north." },
    { deg: 0,   short: "DECEMBER SOLSTICE", emoji: "❄️", season: "Winter", text: "<strong>December Solstice (around Dec 21):</strong> the North Pole leans away from the Sun. Shortest day — winter begins in the north. (Fun fact: Earth is actually CLOSEST to the Sun in early January!)" },
  ];

  function seasonFor(d) {
    const a = ((d % 360) + 360) % 360;
    if (a < 90) return "Winter ❄️"; if (a < 180) return "Spring 🌸"; if (a < 270) return "Summer ☀️"; return "Fall 🍂";
  }

  function drawEarth(ctx, ex, ey, r, sunX, sunY, withAxis) {
    // day/night: lit half faces the Sun
    const ang = Math.atan2(sunY - ey, sunX - ex);
    ctx.save();
    ctx.translate(ex, ey);
    // night side
    ctx.fillStyle = "#1d3a6e";
    ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.fill();
    // day side (half-disc toward the Sun)
    ctx.rotate(ang);
    ctx.fillStyle = "#4f9df7";
    ctx.beginPath(); ctx.arc(0, 0, r, -Math.PI / 2, Math.PI / 2); ctx.fill();
    // sun-glow rim
    ctx.strokeStyle = "rgba(255,209,102,0.9)"; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.arc(0, 0, r + 1.5, -Math.PI / 2.6, Math.PI / 2.6); ctx.stroke();
    ctx.restore();
    if (withAxis) {
      // tilt axis: FIXED direction in space (tilted toward +x), never rotates
      const axLen = r * 1.85;
      const dx = Math.sin(tilt) * axLen, dy = Math.cos(tilt) * axLen;
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.moveTo(ex - dx, ey + dy); ctx.lineTo(ex + dx, ey - dy); ctx.stroke();
      // N arrowhead
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.moveTo(ex + dx, ey - dy);
      ctx.lineTo(ex + dx - 6, ey - dy + 9);
      ctx.lineTo(ex + dx + 4, ey - dy + 10);
      ctx.closePath(); ctx.fill();
      ctx.font = "600 12px 'Segoe UI', sans-serif"; ctx.textAlign = "center";
      ctx.fillText("N", ex + dx + 12, ey - dy - 2);
    }
  }

  function draw() {
    const { ctx, w, h } = fitCanvas(cv, Math.min(0.95, Math.max(0.7, 560 / cv.clientWidth)));
    const cx = w / 2, cy = h / 2;
    const orbitR = Math.min(w, h) * 0.30;
    const er = Math.max(14, Math.min(24, orbitR * 0.14));
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = "rgba(255,255,255,0.22)";
    for (let i = 0; i < 60; i++) ctx.fillRect((i * 211 % 1000) / 1000 * w, (i * 137 % 1000) / 1000 * h, 1.2, 1.2);

    // orbit circle
    ctx.strokeStyle = C.grid; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(cx, cy, orbitR, 0, 7); ctx.stroke();

    drawSun(ctx, cx, cy, 16);

    // 4 stations: clearly labeled ghost-Earths + big text
    const fs = Math.max(10, Math.min(13.5, w / 52));
    for (const s of stations) {
      const rad = s.deg * Math.PI / 180;
      const sx = cx + orbitR * Math.cos(rad), sy = cy - orbitR * Math.sin(rad);
      ctx.globalAlpha = 0.45;
      drawEarth(ctx, sx, sy, er * 0.8, cx, cy, true);
      ctx.globalAlpha = 1;
      // label pushed outward from the orbit, clamped so it never clips off-canvas
      let lx = cx + (orbitR + er * 3.1) * Math.cos(rad);
      let ly = cy - (orbitR + er * 3.1) * Math.sin(rad);
      ctx.font = `700 ${fs}px 'Segoe UI', sans-serif`;
      const halfW = ctx.measureText(`${s.emoji} ${s.short}`).width / 2 + 4;
      lx = Math.min(w - halfW, Math.max(halfW, lx));
      ly = Math.min(h - fs * 1.2, Math.max(fs * 1.6, ly));
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillStyle = C.text;
      ctx.fillText(`${s.emoji} ${s.short}`, lx, ly - fs * 0.7);
      ctx.font = `${fs - 1}px 'Segoe UI', sans-serif`; ctx.fillStyle = C.muted;
      ctx.fillText(`${s.season} begins (north)`, lx, ly + fs * 0.7);
    }

    // animated Earth
    const rad = deg * Math.PI / 180;
    const ex = cx + orbitR * Math.cos(rad), ey = cy - orbitR * Math.sin(rad);
    drawEarth(ctx, ex, ey, er, cx, cy, true);

    // sun rays toward Earth
    ctx.strokeStyle = "rgba(255,209,102,0.5)"; ctx.lineWidth = 1.5; ctx.setLineDash([4, 6]);
    ctx.beginPath(); ctx.moveTo(cx + 22 * Math.cos(rad), cy - 22 * Math.sin(rad)); ctx.lineTo(ex - (er + 6) * Math.cos(rad), ey + (er + 6) * Math.sin(rad)); ctx.stroke();
    ctx.setLineDash([]);

    // live season readout
    const fs2 = Math.max(13, Math.min(17, w / 40));
    ctx.font = `700 ${fs2}px 'Segoe UI', sans-serif`; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.fillStyle = C.text;
    ctx.fillText(`Northern Hemisphere right now: ${seasonFor(deg)}`, 12, 10);
    if (w > 560) {
      ctx.font = `${fs2 - 4}px 'Segoe UI', sans-serif`; ctx.fillStyle = C.muted;
      ctx.fillText("The white axis line never changes direction. That's the whole secret.", 12, 16 + fs2);
    }
  }

  function tick() {
    if (playing) {
      deg = (deg + 0.35) % 360;
      const near = stations.findIndex(s => Math.abs(((deg - s.deg + 540) % 360) - 180) > 176.5);
      if (near >= 0 && near !== lastStation) { lastStation = near; banner.innerHTML = stations[near].text; }
    }
    draw();
    requestAnimationFrame(tick);
  }
  playBtn.addEventListener("click", () => {
    playing = !playing;
    playBtn.textContent = playing ? "⏸ Pause" : "▶ Play";
  });
  document.querySelectorAll(".jump5").forEach(b => b.addEventListener("click", () => {
    deg = Number(b.dataset.deg); playing = false; playBtn.textContent = "▶ Play";
    const s = stations.find(s => s.deg === deg);
    banner.innerHTML = s.text; lastStation = stations.indexOf(s);
  }));
  banner.innerHTML = stations[1].text;   // opens at June
  new ResizeObserver(draw).observe(cv);
  requestAnimationFrame(tick);
})();
</script>
</body>
</html>
"""


def build() -> Path:
    DOCS_DIR.mkdir(exist_ok=True)
    html = (
        PAGE_TEMPLATE
        .replace("__PLANET_DATA__", planet_json())
        .replace("__TILT__", str(EARTH_AXIAL_TILT_DEG))
    )
    out_path = DOCS_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
