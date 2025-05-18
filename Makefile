# Makefile for setting up Python environment using pyenv and Poetry

# Usage:
# make setup
# make clean
# make activate
# make run

# Define variables
PYTHON_VERSION = 3.11
PYENV = pyenv

# Check for required tools
check-tools:
	@command -v $(PYENV) >/dev/null 2>&1 || { echo "pyenv is required but not installed. Install from https://github.com/pyenv/pyenv#installation"; exit 1; }
	@command -v poetry >/dev/null 2>&1 || { echo "poetry is required but not installed. Install from https://python-poetry.org/docs/#installation"; exit 1; }


# NOTE: Certain fixes are required for macOS users to install Python with pyenv with a working Tkinter module.
# This assumes you have pyenv and tcl-tk installed via Homebrew.
# The tcl-tk version may need to be adjusted based on your system.
# To check the installed version of tcl-tk, run: `brew info tcl-tk`

# Install the desired Python version using pyenv and set it as local
install-python: check-tools
	@echo "Installing Python $(PYTHON_VERSION) using pyenv..."
	env \
	    LDFLAGS="-L$(brew --prefix tcl-tk)/lib" \
	    CPPFLAGS="-I$(brew --prefix tcl-tk)/include" \
	    PKG_CONFIG_PATH="$(brew --prefix tcl-tk)/lib/pkgconfig" \
	    PYTHON_CONFIGURE_OPTS="--with-tcltk-includes='-I$(brew --prefix tcl-tk)/include' --with-tcltk-libs='-L$(brew --prefix tcl-tk)/lib -ltcl9.0 -ltk9.0'" \
	    $(PYENV) install -s $(PYTHON_VERSION)
	$(PYENV) local $(PYTHON_VERSION)

# Configure Poetry to use an in-project virtual environment and set it to use the current Python.
create-env: install-python
	@echo "Using Python version: $$(pyenv which python)"
	@echo "Configuring Poetry for an in-project virtual environment..."
	poetry config virtualenvs.in-project true
	poetry env use $$(pyenv which python)

# Update the lock file based on pyproject.toml
lock:
	@echo "Updating Poetry lock file..."
	poetry lock

# Install project dependencies as defined in pyproject.toml.
install: create-env lock
	@echo "Checking dependencies with Poetry..."
	poetry check
	@echo "Installing dependencies with Poetry..."
	poetry install

# Instructions to activate the Poetry shell.
activate:
	@echo "To activate your Poetry virtual environment, run:"
	@echo "source .venv/bin/activate"
	@echo "Also try: poetry env activate"
	@echo "To deactivate, run: `deactivate` or `exit`"

# Run your Python script using Poetry's script entry point.
run:
	@echo "Running application..."
	poetry run start

clean:
	@echo "Cleaning Poetry environment..."
	poetry env remove $(PYTHON_VERSION) || true
	rm -rf .venv

setup: install
	@echo "Python environment setup with Poetry is complete!"
