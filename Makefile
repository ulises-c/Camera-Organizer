# Makefile for Photo Organizer Suite
# Cross-platform support for macOS and Linux

SHELL := /bin/bash
PYTHON_VERSION := 3.12
APP_NAME := photo-organizer
OS := $(shell uname -s)

# Colors for output
BOLD := \033[1m
RESET := \033[0m
GREEN := \033[32m
YELLOW := \033[33m

.PHONY: help doctor setup install run run-dev clean

help:
	@echo "$(BOLD)Photo Organizer - Development Commands$(RESET)"
	@echo ""
	@echo "  $(GREEN)make doctor$(RESET)       - Check system dependencies and environment"
	@echo "  $(GREEN)make setup$(RESET)        - Complete setup (dependencies + installation)"
	@echo "  $(GREEN)make install$(RESET)      - Install Python dependencies via Poetry"
	@echo "  $(GREEN)make run$(RESET)          - Launch the application"
	@echo "  $(GREEN)make run-dev$(RESET)      - Run in development mode (python -m)"
	@echo "  $(GREEN)make clean$(RESET)        - Remove virtual environment and caches"
	@echo ""
	@echo "$(YELLOW)First time setup:$(RESET)"
	@echo "  1. Run 'make doctor' to check system requirements"
	@echo "  2. Follow any instructions for missing dependencies"
	@echo "  3. Run 'make setup' to install everything"
	@echo "  4. Run 'make run' to launch the app"

doctor:
	@echo "$(BOLD)Checking Development Environment...$(RESET)"
	@echo ""
	@echo "Operating System: $(OS)"
	@echo ""
	@echo "Checking required tools..."
	@command -v poetry >/dev/null 2>&1 && echo "✅ Poetry installed" || (echo "❌ Poetry missing - install from: https://python-poetry.org/docs/#installation" && exit 1)
	@command -v pyenv >/dev/null 2>&1 && echo "✅ pyenv installed" || echo "⚠️  pyenv not found (recommended for Python version management)"
	@echo ""
	@echo "Checking Python environment..."
	@which python3 >/dev/null 2>&1 && python3 --version || echo "❌ Python 3 not found"
	@echo ""
	@echo "$(BOLD)Checking Python libraries...$(RESET)"
	@if [ -d .venv ] || poetry env info >/dev/null 2>&1; then \
		poetry run python -c "import tkinter; print('✅ tkinter available')" 2>/dev/null || \
			echo "❌ tkinter not available - see system dependency instructions below"; \
		poetry run python -c "import PIL; print('✅ Pillow installed')" 2>/dev/null || echo "⚠️  Pillow not installed"; \
		poetry run python -c "import pillow_heif; print('✅ pillow-heif installed')" 2>/dev/null || echo "⚠️  pillow-heif not installed"; \
		poetry run python -c "import ttkbootstrap; print('✅ ttkbootstrap installed')" 2>/dev/null || echo "⚠️  ttkbootstrap not installed"; \
	else \
		echo "⚠️  Virtual environment not created yet - run 'make install'"; \
	fi
	@echo ""
	@echo "$(BOLD)System Dependencies:$(RESET)"
ifeq ($(OS),Darwin)
	@echo "macOS detected. Required packages:"
	@echo "  brew install tcl-tk pyenv poetry"
	@echo ""
	@echo "If tkinter fails, rebuild Python with tcl-tk support:"
	@echo "  export LDFLAGS=\"-L\$$(brew --prefix tcl-tk)/lib\""
	@echo "  export CPPFLAGS=\"-I\$$(brew --prefix tcl-tk)/include\""
	@echo "  export PKG_CONFIG_PATH=\"\$$(brew --prefix tcl-tk)/lib/pkgconfig\""
	@echo "  pyenv install $(PYTHON_VERSION)"
else
	@echo "Linux detected. Required packages (Debian/Ubuntu):"
	@echo "  sudo apt-get update && sudo apt-get install -y \\"
	@echo "    build-essential libssl-dev zlib1g-dev libbz2-dev \\"
	@echo "    libreadline-dev libsqlite3-dev curl git \\"
	@echo "    libncursesw5-dev xz-utils tk-dev libxml2-dev \\"
	@echo "    libxmlsec1-dev libffi-dev liblzma-dev libheif-dev"
	@echo ""
	@echo "For Fedora/RHEL:"
	@echo "  sudo dnf groupinstall 'Development Tools'"
	@echo "  sudo dnf install tk-devel libheif-devel"
endif

setup: doctor
	@echo "$(BOLD)Setting up development environment...$(RESET)"
	@if command -v pyenv >/dev/null 2>&1; then \
		echo "Installing Python $(PYTHON_VERSION) via pyenv..."; \
		pyenv install -s $(PYTHON_VERSION); \
		pyenv local $(PYTHON_VERSION); \
	fi
	@echo "Configuring Poetry..."
	@poetry config virtualenvs.in-project true
	@if command -v pyenv >/dev/null 2>&1; then \
		poetry env use $$(pyenv which python); \
	fi
	@$(MAKE) install
	@echo ""
	@echo "$(GREEN)✅ Setup complete!$(RESET)"
	@echo "Run 'make run' to start the application"

install:
	@echo "Installing dependencies..."
	@poetry install
	@echo "$(GREEN)✅ Dependencies installed$(RESET)"

run:
	@echo "🚀 Launching $(APP_NAME)..."
	@poetry run $(APP_NAME)

run-dev:
	@echo "🚀 Launching in development mode..."
	@poetry run python -m photo_organizer.launcher

clean:
	@echo "Cleaning up..."
	@rm -rf .venv
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .python-version
	@echo "$(GREEN)✅ Cleanup complete$(RESET)"
