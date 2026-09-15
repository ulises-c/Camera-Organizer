"""Clip probing: ffprobe stream data + Sony sidecar XML color science.

The XML sidecar (…M01.XML) is authoritative for capture gamma/gamut because the
camera records exactly what picture profile was used. ffprobe fills in codec,
resolution, fps and duration. Together they let `core` decide, per clip, whether
to apply a Log→Rec709 LUT or transcode a native-Rec709 clip untouched.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


class FFmpegNotFound(RuntimeError):
    pass


def ffprobe_bin() -> str:
    exe = shutil.which("ffprobe")
    if not exe:
        raise FFmpegNotFound("ffprobe not found on PATH. Install ffmpeg (brew install ffmpeg).")
    return exe


@dataclass
class Clip:
    path: Path
    width: int = 0
    height: int = 0
    codec: str = ""
    pix_fmt: str = ""
    fps: float = 0.0
    duration: float = 0.0
    # Color science from the Sony sidecar XML:
    gamma: str = ""             # e.g. "s-log3" or "rec709"
    gamut: str = ""             # e.g. "s-gamut3" / "s-gamut3.cine"
    is_log: bool = False        # decision flag used by the pipeline
    xml_lut_ref: str = ""       # LUT the camera referenced, if any

    def as_dict(self) -> dict:
        d = asdict(self)
        d["path"] = str(self.path)
        return d


def _sidecar_xml(mp4: Path) -> Path | None:
    """Sony writes <STEM>M01.XML next to <STEM>.MP4."""
    for cand in (mp4.with_name(mp4.stem + "M01.XML"),
                 mp4.with_name(mp4.stem + "M01.xml")):
        if cand.exists():
            return cand
    return None


def _parse_xml(xml: Path) -> dict:
    txt = xml.read_text(errors="ignore")

    def grab(attr: str) -> str:
        m = re.search(attr + r'"\s+value="([^"]*)"', txt)
        return m.group(1) if m else ""

    gamma = grab("CaptureGammaEquation")
    gamut = grab("CaptureColorPrimaries")
    lut_m = re.search(r'RelatedTo file="([^"]*)"', txt)
    return {
        "gamma": gamma,
        "gamut": gamut,
        "xml_lut_ref": lut_m.group(1) if lut_m else "",
    }


def _is_log_gamma(gamma: str) -> bool:
    g = (gamma or "").lower()
    return any(tok in g for tok in ("s-log", "slog", "log3", "log2"))


def probe_clip(path: Path) -> Clip:
    """Probe a single MP4/MOV into a Clip. XML color science overrides guesses;
    a missing XML yields is_log=False so we NEVER wrongly apply a Log LUT."""
    path = Path(path)
    clip = Clip(path=path)

    out = subprocess.run(
        [ffprobe_bin(), "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode == 0 and out.stdout:
        data = json.loads(out.stdout)
        vstreams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        if vstreams:
            v = vstreams[0]
            clip.width = int(v.get("width", 0) or 0)
            clip.height = int(v.get("height", 0) or 0)
            clip.codec = v.get("codec_name", "") or ""
            clip.pix_fmt = v.get("pix_fmt", "") or ""
            rate = v.get("r_frame_rate", "0/1") or "0/1"
            try:
                num, den = rate.split("/")
                clip.fps = round(int(num) / int(den), 3) if int(den) else 0.0
            except Exception:
                clip.fps = 0.0
        try:
            clip.duration = round(float(data.get("format", {}).get("duration", 0.0)), 3)
        except Exception:
            clip.duration = 0.0

    xml = _sidecar_xml(path)
    if xml:
        meta = _parse_xml(xml)
        clip.gamma = meta["gamma"]
        clip.gamut = meta["gamut"]
        clip.xml_lut_ref = meta["xml_lut_ref"]
        clip.is_log = _is_log_gamma(clip.gamma)
    return clip


def probe_dir(folder: Path, exts=(".mp4", ".mov")) -> list[Clip]:
    folder = Path(folder)
    files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )
    return [probe_clip(p) for p in files]
