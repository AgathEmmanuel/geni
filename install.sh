#!/usr/bin/env sh
set -e

# geni installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/AgathEmmanuel/geni/main/install.sh | sh
#   wget -qO- https://raw.githubusercontent.com/AgathEmmanuel/geni/main/install.sh | sh
#
# Options (environment variables):
#   GENI_VERSION=0.1.0    Install a specific version (default: latest)
#   GENI_INSTALL=pip      Force pip instead of pipx

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

info()  { printf "${BOLD}${GREEN}==>${RESET} ${BOLD}%s${RESET}\n" "$1"; }
warn()  { printf "${BOLD}${YELLOW}==>${RESET} ${BOLD}%s${RESET}\n" "$1"; }
error() { printf "${BOLD}${RED}Error:${RESET} %s\n" "$1" >&2; exit 1; }

# --- Detect OS ---
OS="$(uname -s)"
case "$OS" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    *)       error "Unsupported platform: $OS. Use pip install geni directly." ;;
esac

info "Detected platform: $PLATFORM"

# --- Detect Python ---
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ] 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "  Python 3.10+ is required but was not found."
    echo ""
    if [ "$PLATFORM" = "macos" ]; then
        echo "  Install with Homebrew:"
        echo "    brew install python@3.12"
    else
        echo "  Install with your package manager:"
        echo "    sudo apt install python3    # Debian/Ubuntu"
        echo "    sudo dnf install python3    # Fedora"
        echo "    sudo pacman -S python       # Arch"
    fi
    echo ""
    echo "  Or download from: https://www.python.org/downloads/"
    echo ""
    exit 1
fi

info "Found $PYTHON ($version)"

# --- Determine package spec ---
if [ -n "$GENI_VERSION" ]; then
    PACKAGE="geni==$GENI_VERSION"
else
    PACKAGE="geni"
fi

# --- Install pipx if not present ---
ensure_pipx() {
    if command -v pipx >/dev/null 2>&1; then
        return 0
    fi
    if "$PYTHON" -m pipx --version >/dev/null 2>&1; then
        return 0
    fi

    info "Installing pipx..."
    "$PYTHON" -m pip install --user pipx >/dev/null 2>&1 || return 1
    "$PYTHON" -m pipx ensurepath >/dev/null 2>&1 || true
    return 0
}

install_with_pipx() {
    local pipx_cmd
    if command -v pipx >/dev/null 2>&1; then
        pipx_cmd="pipx"
    else
        pipx_cmd="$PYTHON -m pipx"
    fi

    info "Installing geni with pipx (isolated environment)..."
    $pipx_cmd install "$PACKAGE"
}

install_with_pip() {
    info "Installing geni with pip..."
    "$PYTHON" -m pip install --user "$PACKAGE"
}

# --- Main install logic ---
if [ "$GENI_INSTALL" = "pip" ]; then
    install_with_pip
else
    if ensure_pipx; then
        install_with_pipx
    else
        warn "Could not set up pipx, falling back to pip --user"
        install_with_pip
    fi
fi

# --- Verify ---
printf "\n"

# Refresh PATH to pick up newly installed binaries
export PATH="$HOME/.local/bin:$PATH"

if command -v geni >/dev/null 2>&1; then
    installed_version=$(geni --version 2>&1 | head -1)
    info "geni $installed_version installed successfully!"
    printf "\n"
    echo "  Get started:"
    echo "    geni init        # scaffold a new project"
    echo "    geni -t example  # compile a target"
    echo ""
else
    warn "geni was installed but is not on your PATH."
    echo ""
    echo "  Add this to your shell profile (~/.bashrc, ~/.zshrc):"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "  Then restart your shell and run: geni --version"
    echo ""
fi

# --- Uninstall hint ---
echo "  To uninstall:"
echo "    pipx uninstall geni    # if installed with pipx"
echo "    pip uninstall geni     # if installed with pip"
echo ""
