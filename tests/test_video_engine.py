"""Tests for the video converter engine's dry-run and ffmpeg handling."""
from __future__ import annotations

from pathlib import Path

from photo_organizer.video_converter import engine as video_engine
from photo_organizer.video_converter.engine import (
    ffmpeg_available,
    process_video_folder,
)
from photo_organizer.video_converter.probe import Clip


def _clip(tmp_path: Path, name: str, *, is_log: bool) -> Clip:
    path = tmp_path / name
    path.write_bytes(b"video")
    return Clip(
        path=path,
        width=3840,
        height=2160,
        gamma="s-log3" if is_log else "rec709",
        gamut="s-gamut3.cine" if is_log else "rec709",
        is_log=is_log,
    )


def test_preview_builds_plan_without_ffmpeg(tmp_path, monkeypatch):
    clips = [_clip(tmp_path, "A.MP4", is_log=True),
             _clip(tmp_path, "B.MP4", is_log=False)]
    monkeypatch.setattr(video_engine, "probe_dir", lambda _folder: clips)

    def no_ffmpeg():
        raise RuntimeError("ffmpeg not found on PATH.")

    monkeypatch.setattr(video_engine, "ffmpeg_bin", no_ffmpeg)
    # A log clip needs a LUT; give the resolver a real .cube so preview is clean.
    lut = tmp_path / "LC-709TypeA.cube"
    lut.write_text("LUT")
    monkeypatch.setattr(
        video_engine, "resolve_lut",
        lambda *a, **k: video_engine.LutChoice(lut, "Sony LC-709TypeA", "s-log3", "s-gamut3.cine"),
    )

    results = process_video_folder(
        tmp_path,
        {"dry_run": True},
        lambda _pct: None,
        lambda _msg: None,
    )

    assert len(results) == 2
    assert all(r.success for r in results)
    actions = [d.action for r in results for d in r.details]
    assert "STAGE1-LUT" in actions
    assert "STAGE1-NATIVE" in actions


def test_preview_flags_log_clip_with_no_lut(tmp_path, monkeypatch):
    clips = [_clip(tmp_path, "A.MP4", is_log=True)]
    monkeypatch.setattr(video_engine, "probe_dir", lambda _folder: clips)
    monkeypatch.setattr(video_engine, "resolve_lut", lambda *a, **k: None)

    results = process_video_folder(
        tmp_path, {"dry_run": True}, lambda _pct: None, lambda _msg: None
    )

    assert results[0].success is False
    assert results[0].details[0].error == "No matching LUT found"


def test_no_clips_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(video_engine, "probe_dir", lambda _folder: [])

    results = process_video_folder(
        tmp_path, {"dry_run": True}, lambda _pct: None, lambda _msg: None
    )

    assert results == []


def test_ffmpeg_available_reflects_path(monkeypatch):
    monkeypatch.setattr(video_engine.shutil, "which", lambda _name: "/usr/bin/x")
    assert ffmpeg_available() is True
    monkeypatch.setattr(video_engine.shutil, "which", lambda _name: None)
    assert ffmpeg_available() is False
