"""Before/after conversion manifest.

Reads each source clip and its produced outputs (master + share) straight off
disk and records what changed: color science, codec, resolution, pixel format,
file size, bitrate, and file locations. Emits both a machine-readable JSON and a
human-readable Markdown table so a run is fully auditable after the fact.

Usable standalone (does not require the encode to have gone through this module):

    uv run python -m photo_organizer.video_converter.report "/path/to/footage"
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from photo_organizer.video_converter.engine import DEFAULT_OPTIONS
from photo_organizer.video_converter.probe import ffprobe_bin, probe_clip


def _human_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024:
            return f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


def _probe_output(path: Path) -> dict:
    """ffprobe an output file for the fields that describe 'after'."""
    out = subprocess.run(
        [ffprobe_bin(), "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    info = {"exists": True, "size_bytes": path.stat().st_size,
            "size_human": _human_size(path.stat().st_size)}
    try:
        data = json.loads(out.stdout)
        v = next(s for s in data["streams"] if s.get("codec_type") == "video")
        info.update({
            "codec": v.get("codec_name", ""),
            "resolution": f"{v.get('width')}x{v.get('height')}",
            "pix_fmt": v.get("pix_fmt", ""),
            "color_space": v.get("color_space", "unknown"),
            "color_transfer": v.get("color_transfer", "unknown"),
            "color_primaries": v.get("color_primaries", "unknown"),
            "bit_rate": int(data["format"].get("bit_rate", 0) or 0),
            "duration_s": round(float(data["format"].get("duration", 0) or 0), 2),
        })
    except Exception:
        pass
    return info


@dataclass
class ClipManifest:
    name: str
    # BEFORE (source)
    source_file: str
    source_location: str
    source_size: str
    source_codec: str
    source_resolution: str
    source_pix_fmt: str
    source_gamma: str
    source_gamut: str
    is_log: bool
    color_transform: str          # LUT applied, or "none (native Rec709)"
    # AFTER (share deliverable)
    output_file: str = ""
    output_location: str = ""
    output_size: str = ""
    output_codec: str = ""
    output_resolution: str = ""
    output_color: str = ""        # space/transfer/primaries
    output_bitrate_mbps: float = 0.0
    size_reduction: str = ""      # e.g. "7.5x smaller"
    master_file: str = ""
    master_size: str = ""


def build_manifest(folder: Path, options: dict | None = None) -> dict:
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    folder = Path(folder)
    master_dir = folder / opts["master_dirname"]
    share_dir = folder / opts["share_dirname"]
    lut_name = Path(opts["explicit_lut"]).stem if opts.get("explicit_lut") else "auto"

    clips = []
    for src in sorted(folder.glob("*.MP4")) + sorted(folder.glob("*.mov")):
        if src.parent != folder:
            continue
        c = probe_clip(src)
        stem = src.stem
        transform = (f"S-Log3/S-Gamut3.Cine → Rec709 (LUT: {lut_name})"
                     if c.is_log else "none (native Rec709)")
        m = ClipManifest(
            name=stem,
            source_file=src.name,
            source_location=str(src),
            source_size=_human_size(src.stat().st_size),
            source_codec=f"{c.codec} {c.pix_fmt}".strip(),
            source_resolution=f"{c.width}x{c.height}",
            source_pix_fmt=c.pix_fmt,
            source_gamma=c.gamma or "?",
            source_gamut=c.gamut or "?",
            is_log=c.is_log,
            color_transform=transform,
        )

        master = master_dir / f"{stem}.mov"
        if master.exists():
            m.master_file = master.name
            m.master_size = _human_size(master.stat().st_size)

        share = share_dir / f"{stem}_{opts['share_height']}p.mp4"
        if share.exists():
            o = _probe_output(share)
            m.output_file = share.name
            m.output_location = str(share)
            m.output_size = o["size_human"]
            m.output_codec = f"{o.get('codec','')} {o.get('pix_fmt','')}".strip()
            m.output_resolution = o.get("resolution", "")
            m.output_color = (f"{o.get('color_space','?')}/"
                              f"{o.get('color_transfer','?')}/"
                              f"{o.get('color_primaries','?')}")
            m.output_bitrate_mbps = round(o.get("bit_rate", 0) / 1e6, 1)
            if o["size_bytes"]:
                ratio = src.stat().st_size / o["size_bytes"]
                m.size_reduction = f"{ratio:.1f}x smaller"
        clips.append(m)

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source_folder": str(folder),
        "master_folder": str(master_dir),
        "share_folder": str(share_dir),
        "lut": lut_name,
        "summary": {
            "clips": len(clips),
            "log_clips": sum(1 for c in clips if c.is_log),
            "native_clips": sum(1 for c in clips if not c.is_log),
            "converted": sum(1 for c in clips if c.output_file),
            "total_source": _human_size(sum(
                Path(c.source_location).stat().st_size for c in clips)),
            "total_share": _human_size(sum(
                (share_dir / f"{c.name}_{opts['share_height']}p.mp4").stat().st_size
                for c in clips
                if (share_dir / f"{c.name}_{opts['share_height']}p.mp4").exists())),
        },
        "clips": [asdict(c) for c in clips],
    }


def to_markdown(manifest: dict) -> str:
    s = manifest["summary"]
    lines = [
        f"# Conversion Report — {manifest['source_folder']}",
        "",
        f"_Generated {manifest['generated']}_  ",
        f"LUT: `{manifest['lut']}`",
        "",
        "## Summary",
        (f"- **{s['clips']}** clips: {s['log_clips']} S-Log3 (LUT applied), "
         f"{s['native_clips']} native Rec709 (no LUT)"),
        f"- **{s['converted']}** converted to 1080p HEVC share files",
        f"- Source total: **{s['total_source']}** → Share total: **{s['total_share']}**",
        f"- Masters: `{manifest['master_folder']}`",
        f"- Shares: `{manifest['share_folder']}`",
        "",
        "## Per-clip (before → after)",
        "",
        "| Clip | Before (codec / res / color) | Size | Transform | After (codec / res / color) | Size | Bitrate | Saved |",
        "|------|------------------------------|------|-----------|------------------------------|------|---------|-------|",
    ]
    for c in manifest["clips"]:
        before = f"{c['source_codec']} / {c['source_resolution']} / {c['source_gamma']}·{c['source_gamut']}"
        after = (f"{c['output_codec']} / {c['output_resolution']} / {c['output_color']}"
                 if c["output_file"] else "—")
        lines.append(
            f"| {c['name']} | {before} | {c['source_size']} | "
            f"{'LUT' if c['is_log'] else 'native'} | {after} | "
            f"{c['output_size'] or '—'} | "
            f"{str(c['output_bitrate_mbps']) + ' Mbps' if c['output_bitrate_mbps'] else '—'} | "
            f"{c['size_reduction'] or '—'} |"
        )
    return "\n".join(lines) + "\n"


def write_reports(folder: Path, options: dict | None = None,
                  json_path: Path | None = None,
                  md_path: Path | None = None) -> tuple[Path, Path]:
    manifest = build_manifest(folder, options)
    folder = Path(folder)
    json_path = json_path or folder / "convert" / "conversion_report.json"
    md_path = md_path or folder / "convert" / "conversion_report.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(manifest, indent=2))
    md_path.write_text(to_markdown(manifest))
    return json_path, md_path


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Generate a before/after conversion manifest.")
    p.add_argument("folder", type=Path)
    p.add_argument("--lut", type=Path, default=None)
    args = p.parse_args(argv)
    opts = dict(DEFAULT_OPTIONS)
    if args.lut:
        opts["explicit_lut"] = args.lut
    jp, mp = write_reports(args.folder, opts)
    print(f"JSON → {jp}\nMarkdown → {mp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
