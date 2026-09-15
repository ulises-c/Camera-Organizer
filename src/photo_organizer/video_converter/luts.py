"""LUT catalog + smart resolution for Sony (and other) Log footage.

Given a clip's detected gamma/gamut, pick the correct .cube colorspace-transform
LUT from the user's LUT library. The GUI can also show `catalog()` so a user can
override the auto-pick.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Default Final Cut LUT library location on this machine. Overridable via options.
DEFAULT_LUT_ROOT = Path.home() / "Documents" / "Final Cut Pro" / "LUTs"


@dataclass(frozen=True)
class LutChoice:
    path: Path
    label: str          # human-readable, e.g. "Sony LC-709TypeA"
    gamma: str          # "s-log3"
    gamut: str          # "s-gamut3.cine"


# Curated known-good picks, in priority order. Each entry is a list of filename
# substrings (all must be present, case-insensitive) that identify the file.
# The first entry that resolves to an existing file wins for that (gamma, gamut).
_SONY_SLOG3_SGAMUT3CINE = [
    (["sgamut3cineslog3", "lc-709typea"], "Sony LC-709TypeA (warm skin)"),
    (["sgamut3cineslog3", "lc-709"],      "Sony LC-709 (natural)"),
    (["s-log 3", "s-gamut3.cine", "rec709", "camera-and-monitor"],
     "Cam2Rec S-Log3/SGamut3.Cine (C&M edition)"),
    (["s-log 3", "s-gamut3.cine", "rec709"],
     "Cam2Rec S-Log3/SGamut3.Cine"),
]


def _find(root: Path, needles: list[str]) -> Path | None:
    if not root.exists():
        return None
    for p in root.rglob("*.cube"):
        name = p.name.lower()
        if all(n.lower() in name for n in needles):
            return p
    return None


def resolve_lut(gamma: str, gamut: str, lut_root: Path | None = None,
                explicit: Path | None = None) -> LutChoice | None:
    """Resolve the best LUT for the given color science.

    `explicit` (if provided and existing) always wins — this is how the GUI/CLI
    lets a user force a specific .cube. Returns None when no LUT is needed or
    none can be found.
    """
    if explicit:
        ep = Path(explicit)
        if ep.exists():
            return LutChoice(ep, ep.stem, gamma, gamut)

    root = Path(lut_root) if lut_root else DEFAULT_LUT_ROOT
    g = (gamma or "").lower()
    gm = (gamut or "").lower()

    # Only S-Log3 / S-Gamut3.Cine is wired up so far (matches the A6700 footage).
    if "s-log3" in g or "slog3" in g:
        for needles, label in _SONY_SLOG3_SGAMUT3CINE:
            hit = _find(root, needles)
            if hit:
                return LutChoice(hit, label, "s-log3", gm or "s-gamut3.cine")
    return None


def catalog(lut_root: Path | None = None) -> list[Path]:
    """All .cube files available, for GUI dropdowns."""
    root = Path(lut_root) if lut_root else DEFAULT_LUT_ROOT
    return sorted(root.rglob("*.cube")) if root.exists() else []
