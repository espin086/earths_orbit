# Earth's Orbit. An Interactive Explorer

Interactive site for 5th graders: the solar system in motion, Kepler's laws, the true scale of planetary distances, and why we have seasons. Five canvas animations with play buttons, live captions, glossary tooltips, and clickable planets.

**Live site:** https://espin086.github.io/earths_orbit/

## Build

```
uv run src/generate_site.py
```

Writes `docs/index.html`, a single self-contained page (no CDN, no server). Orbital mechanics (Kepler's equation, real JPL orbital elements) computed in Python (`src/orbital_mechanics.py`); animation runs in hand-rolled canvas JS at 60fps.

GitHub Pages serves the `docs/` folder from `main`.
