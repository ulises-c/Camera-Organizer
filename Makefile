# Makefile for Photo Organizer Suite
# Cross-platform support for macOS and Linux

SHELL := /bin/bash
PYTHON_VERSION := 3.12
APP_NAME := photo-organizer
OS := $(shell uname -s)

# Enable colors only if stdout is a TTY
ifeq ($(shell test -t 1 && echo yes),yes)
	BOLD   := \033[1m
	RESET  := \033[0m
	GREEN  := \033[32m
	YELLOW := \033[33m
else
	BOLD   :=
	RESET  :=
	GREEN  :=
	YELLOW :=
endif

.PHONY: help doctor setup install run run-dev clean

help:
	@printf "%b\n" "$(BOLD)Photo Organizer - Development Commands$(RESET)"
	@printf "\n"
	@printf "%b\n" "  $(GREEN)make doctor$(RESET)       - Check system dependencies and environment"
	@printf "%b\n" "  $(GREEN)make setup$(RESET)        - Complete setup (dependencies + installation)"
	@printf "%b\n" "  $(GREEN)make install$(RESET)      - Install Python dependencies via Poetry"
	@printf "%b\n" "  $(GREEN)make run$(RESET)          - Launch the application"
	@printf "%b\n" "  $(GREEN)make run-dev$(RESET)      - Run in development mode (python -m)"
	@printf "%b\n" "  $(GREEN)make clean$(RESET)        - Remove virtual environment and caches"
	@printf "\n"
	@printf "%b\n" "$(YELLOW)First time setup:$(RESET)"
	@printf "%b\n" "  1. Run 'make doctor' to check system requirements"
	@printf "%b\n" "  2. Follow any instructions for missing dependencies"
	@printf "%b\n" "  3. Run 'make setup' to install everything"
	@printf "%b\n" "  4. Run 'make run' to launch the app"

doctor:
	@printf "%b\n" "$(BOLD)Checking Development Environment...$(RESET)"
	@printf "\n"
	@printf "Operating System: %s\n" "$(OS)"
	@printf "\n"
	@printf "Checking required tools...\n"
	@command -v poetry >/dev/null 2>&1 \
		&& printf "✅ Poetry installed\n" \
		|| (printf "❌ Poetry missing - install from: https://python-poetry.org/docs/#installation\n" && exit 1)
	@command -v pyenv >/dev/null 2>&1 \
		&& printf "✅ pyenv installed\n" \
		|| printf "⚠️  pyenv not found (recommended for Python version management)\n"
	@printf "\n"
	@printf "Checking Python environment...\n"
	@which python3 >/dev/null 2>&1 \
		&& python3 --version \
		|| printf "❌ Python 3 not found\n"
	@printf "\n"
	@printf "%b\n" "$(BOLD)Checking Python libraries...$(RESET)"
	@if [ -d .venv ] || poetry env info >/dev/null 2>&1; then \
		poetry run python -c "import tkinter; print('✅ tkinter available')" 2>/dev/null \
			|| printf "❌ tkinter not available - see system dependency instructions below\n"; \
		poetry run python -c "import PIL; print('✅ Pillow installed')" 2>/dev/null \
			|| printf "⚠️  Pillow not installed\n"; \
		poetry run python -c "import pillow_heif; print('✅ pillow-heif installed')" 2>/dev/null \
			|| printf "⚠️  pillow-heif not installed\n"; \
		poetry run python -c "import ttkbootstrap; print('✅ ttkbootstrap installed')" 2>/dev/null \
			|| printf "⚠️  ttkbootstrap not installed\n"; \
	else \
		printf "⚠️  Virtual environment not created yet - run 'make install'\n"; \
	fi
	@printf "\n"
	@printf "%b\n" "$(BOLD)System Dependencies:$(RESET)"
ifeq ($(OS),Darwin)
	@printf "macOS detected. Required packages:\n"
	@printf "  brew install tcl-tk pyenv poetry\n"
	@printf "\n"
	@printf "If tkinter fails, rebuild Python with tcl-tk support:\n"
	@printf "  export LDFLAGS=\"-L$$(brew --prefix tcl-tk)/lib\"\n"
	@printf "  export CPPFLAGS=\"-I$$(brew --prefix tcl-tk)/include\"\n"
	@printf "  export PKG_CONFIG_PATH=\"$$(brew --prefix tcl-tk)/lib/pkgconfig\"\n"
	@printf "  pyenv install $(PYTHON_VERSION)\n"
else
	@printf "Linux detected. Required packages (Debian/Ubuntu):\n"
	@printf "  sudo apt-get update && sudo apt-get install -y \\\n"
	@printf "    build-essential libssl-dev zlib1g-dev libbz2-dev \\\n"
	@printf "    libreadline-dev libsqlite3-dev curl git \\\n"
	@printf "    libncursesw5-dev xz-utils tk-dev libxml2-dev \\\n"
	@printf "    libxmlsec1-dev libffi-dev liblzma-dev libheif-dev\n"
	@printf "\n"
	@printf "For Fedora/RHEL:\n"
	@printf "  sudo dnf groupinstall 'Development Tools'\n"
	@printf "  sudo dnf install tk-devel libheif-devel\n"
endif

setup: doctor
	@printf "%b\n" "$(BOLD)Setting up development environment...$(RESET)"
	@if command -v pyenv >/dev/null 2>&1; then \
		printf "Installing Python $(PYTHON_VERSION) via pyenv...\n"; \
		pyenv install -s $(PYTHON_VERSION); \
		pyenv local $(PYTHON_VERSION); \
	fi
	@printf "Configuring Poetry...\n"
	@poetry config virtualenvs.in-project true
	@if command -v pyenv >/dev/null 2>&1; then \
		poetry env use $$(pyenv which python); \
	fi
	@$(MAKE) install
	@printf "\n"
	@printf "%b\n" "$(GREEN)✅ Setup complete!$(RESET)"
	@printf "Run 'make run' to start the application\n"

install:
	@printf "Installing dependencies...\n"
	@poetry install
	@printf "%b\n" "$(GREEN)✅ Dependencies installed$(RESET)"

run:
	@printf "🚀 Launching %s...\n" "$(APP_NAME)"
	@poetry run $(APP_NAME)

run-dev:
	@printf "🚀 Launching in development mode...\n"
	@poetry run python -m photo_organizer.launcher

clean:
	@printf "Cleaning up...\n"
	@rm -rf .venv
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .python-version
	@printf "%b\n" "$(GREEN)✅ Cleanup complete$(RESET)"
