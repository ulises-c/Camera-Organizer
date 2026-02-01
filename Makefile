# Makefile for Photo Organizer Suite
# Cross-platform support for macOS and Linux
SHELL := /bin/bash
PYTHON_VERSION := 3.12
APP_NAME := photo-organizer
OS := $(shell uname -s)

# Colors (only if TTY)
ifeq ($(shell test -t 1 && echo yes),yes)
	BOLD   := \033[1m
	RESET  := \033[0m
	GREEN  := \033[32m
	YELLOW := \033[33m
	RED    := \033[31m
else
	BOLD   :=
	RESET  :=
	GREEN  :=
	YELLOW :=
	RED    :=
endif

.PHONY: help doctor setup install verify run run-dev clean reset ensure-venv

help:
	@printf "$(BOLD)Photo Organizer - Development Commands$(RESET)\n\n"
	@printf "  $(GREEN)make doctor$(RESET)       - Check system dependencies\n"
	@printf "  $(GREEN)make setup$(RESET)        - Complete setup (creates local .venv)\n"
	@printf "  $(GREEN)make ensure-venv$(RESET)  - Ensure in-project .venv exists\n"
	@printf "  $(GREEN)make verify$(RESET)       - Run comprehensive environment checks\n"
	@printf "  $(GREEN)make run$(RESET)          - Launch the application\n"
	@printf "  $(GREEN)make run-dev$(RESET)      - Run in development mode\n"
	@printf "  $(GREEN)make reset$(RESET)        - Nuclear option: remove all envs and reinstall\n"
	@printf "  $(GREEN)make clean$(RESET)        - Remove caches only\n"
	@printf "\n$(YELLOW)First-time setup: make reset && make verify$(RESET)\n"

doctor:
	@printf "$(BOLD)Checking Development Environment...$(RESET)\n\n"
	@printf "Operating System: $(OS)\n\n"
	@command -v poetry >/dev/null 2>&1 \
		&& printf "✅ Poetry installed\n" \
		|| (printf "$(RED)❌ Poetry missing$(RESET) - install from: https://python-poetry.org/\n" && exit 1)
	@command -v pyenv >/dev/null 2>&1 \
		&& printf "✅ pyenv installed\n" \
		|| printf "$(YELLOW)⚠️  pyenv not found (recommended)$(RESET)\n"
	@which python3 >/dev/null 2>&1 \
		&& python3 --version \
		|| printf "$(RED)❌ Python 3 not found$(RESET)\n"
ifeq ($(OS),Darwin)
	@printf "\n$(BOLD)macOS Requirements:$(RESET)\n"
	@printf "  brew install tcl-tk pyenv poetry\n\n"
	@printf "$(YELLOW)If tkinter fails, rebuild Python with tcl-tk:$(RESET)\n"
	@printf "  export LDFLAGS=\"-L$$(brew --prefix tcl-tk)/lib\"\n"
	@printf "  export CPPFLAGS=\"-I$$(brew --prefix tcl-tk)/include\"\n"
	@printf "  pyenv install $(PYTHON_VERSION)\n"
endif

setup: doctor
	@printf "\n$(BOLD)Step 1: Configuring Poetry for in-project virtualenv$(RESET)\n"
	@poetry config virtualenvs.in-project true --local
	
	@printf "\n$(BOLD)Step 2: Removing any existing cached environments$(RESET)\n"
	@poetry env remove --all 2>/dev/null || true
	
	@printf "\n$(BOLD)Step 3: Setting Python version$(RESET)\n"
	@if command -v pyenv >/dev/null 2>&1; then \
		pyenv local $(PYTHON_VERSION); \
		poetry env use $$(pyenv which python); \
	else \
		poetry env use python3; \
	fi
	
	@printf "\n$(BOLD)Step 4: Installing dependencies$(RESET)\n"
	@poetry install
	@if [ -d ".venv" ]; then \
		printf "\n$(GREEN)✅ Success: .venv created locally.$(RESET)\n"; \
	fi

ensure-venv:
	@printf "$(BOLD)Ensuring in-project .venv exists...$(RESET)\n"
	@poetry config virtualenvs.in-project true --local 2>/dev/null || \
		poetry config virtualenvs.in-project true 2>/dev/null || true
	@if [ ! -d ".venv" ]; then \
		printf "Creating .venv...\n"; \
		poetry env use $$(command -v python3 || command -v python) 2>/dev/null || true; \
		poetry install --no-interaction; \
	else \
		printf "$(GREEN)✅ .venv already exists$(RESET)\n"; \
	fi

install:
	@poetry install --no-interaction

verify:
	@printf "$(BOLD)Running Comprehensive Environment Verification$(RESET)\n\n"
	@if [ -f ".venv/bin/python" ]; then \
		.venv/bin/python helper_tools/env_sanity_check.py; \
	else \
		poetry run python helper_tools/env_sanity_check.py; \
	fi

run: verify
	@printf "\n$(GREEN)🚀 Launching $(APP_NAME)...$(RESET)\n"
	@poetry run $(APP_NAME)

run-dev:
	@printf "$(GREEN)🚀 Launching in development mode...$(RESET)\n"
	@poetry run python -m photo_organizer.launcher

reset:
	@printf "$(RED)$(BOLD)Performing Nuclear Reset...$(RESET)\n"
	@printf "$(BOLD)Step 1: Configuring Poetry for in-project virtualenv$(RESET)\n"
	@poetry config virtualenvs.in-project true --local
	@printf "$(BOLD)Step 2: Removing all Poetry-managed environments$(RESET)\n"
	@poetry env remove --all 2>/dev/null || true
	@printf "$(BOLD)Step 3: Cleaning local artifacts$(RESET)\n"
	@rm -rf .venv
	@rm -f poetry.lock
	@printf "$(BOLD)Step 4: Rebuilding environment$(RESET)\n"
	@$(MAKE) setup

clean:
	@printf "Cleaning caches...\n"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)✅ Cleanup complete$(RESET)\n"
