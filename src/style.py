"""Shared color palette and Plotly layout defaults for the classroom site."""

# Space-themed but high-contrast enough to read on a classroom projector.
BG_DEEP = "#0b1026"
BG_PANEL = "#141a35"
GRID = "#2a3260"
TEXT = "#eef1ff"
TEXT_MUTED = "#a6adcf"
SUN = "#ffd166"
ACCENT = "#4fd1c5"
ACCENT_WARM = "#ff8fa3"

FONT_FAMILY = "'Segoe UI', system-ui, -apple-system, sans-serif"

BASE_LAYOUT = dict(
    paper_bgcolor=BG_DEEP,
    plot_bgcolor=BG_PANEL,
    font=dict(family=FONT_FAMILY, color=TEXT, size=14),
    legend=dict(bgcolor="rgba(20,26,53,0.85)", bordercolor=GRID, borderwidth=1),
    margin=dict(l=60, r=30, t=60, b=50),
)


def axis(**overrides) -> dict:
    """Build an xaxis/yaxis dict with the shared dark-theme defaults."""
    base = dict(gridcolor=GRID, zerolinecolor=GRID, color=TEXT_MUTED)
    base.update(overrides)
    return base
