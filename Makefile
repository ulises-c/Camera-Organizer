# Makefile for Camera Organizer — uv + PySide6
SHELL := /bin/bash
APP_NAME := camera-organizer
PYTHON_VERSION := 3.12

.PHONY: help doctor sync run video-dry video-run lint test clean

help:
	@printf "Camera Organizer — commands\n\n"
	@printf "  make doctor      - Check uv + ffmpeg are present\n"
	@printf "  make sync        - Create .venv and install deps (uv sync)\n"
	@printf "  make run         - Launch the PySide6 app\n"
	@printf "  make video-dry DIR=path - Video converter dry-run\n"
	@printf "  make video-run DIR=path - Video converter real encode\n"
	@printf "  make lint        - ruff check\n"
	@printf "  make test        - pytest\n"
	@printf "  make clean       - Remove caches\n"

doctor:
	@command -v uv >/dev/null 2>&1 && echo "✅ uv: $$(uv --version)" || (echo "❌ uv missing — https://docs.astral.sh/uv/" && exit 1)
	@command -v ffmpeg >/dev/null 2>&1 && echo "✅ ffmpeg present" || echo "⚠️  ffmpeg missing (needed by video_converter): brew install ffmpeg"

sync:
	@uv sync --extra ssim

run: sync
	@uv run $(APP_NAME)

video-dry:
	@uv run python -m photo_organizer.video_converter.cli "$(DIR)" --dry-run

video-run:
	@uv run python -m photo_organizer.video_converter.cli "$(DIR)" --run

lint:
	@uv run ruff check src

test:
	@uv run pytest -q

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"
