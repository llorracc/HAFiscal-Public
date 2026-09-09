#!/bin/bash
# Migration script to convert legacy .venv to platform-specific venvs
# This allows separate venvs for macOS and Linux (DevContainer)

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================"
echo "Migrate to Platform-Specific Venvs"
echo "========================================"
echo ""
echo "This script migrates your existing .venv to platform-specific"
echo "directories (.venv-darwin for macOS, .venv-linux for Linux)."
echo ""
echo "This allows you to maintain separate venvs for:"
echo "  • macOS (local development)"
echo "  • Linux (DevContainer)"
echo ""
echo "Each platform will have its own venv, preventing conflicts when"
echo "switching between environments."
echo ""

# Detect current platform
case "$(uname -s)" in
    Darwin)
        CURRENT_PLATFORM="darwin"
        OTHER_PLATFORM="linux"
        ;;
    Linux)
        CURRENT_PLATFORM="linux"
        OTHER_PLATFORM="darwin"
        ;;
    *)
        echo "❌ Unknown platform: $(uname -s)"
        echo "   This script supports macOS (Darwin) and Linux only"
        exit 1
        ;;
esac

CURRENT_VENV="$PROJECT_ROOT/.venv-$CURRENT_PLATFORM"
OTHER_VENV="$PROJECT_ROOT/.venv-$OTHER_PLATFORM"
LEGACY_VENV="$PROJECT_ROOT/.venv"

echo "Current platform: $CURRENT_PLATFORM"
echo "Current venv path: $CURRENT_VENV"
echo ""

# Check if migration is needed
if [[ -d "$CURRENT_VENV" ]]; then
    echo "✅ Platform-specific venv already exists: $(basename "$CURRENT_VENV")"
    echo ""
    
    if [[ -d "$LEGACY_VENV" ]]; then
        echo "⚠️  Legacy .venv also exists. You can safely remove it:"
        echo "   rm -rf .venv"
        echo ""
    fi
    
    echo "Migration not needed - platform-specific venv already exists."
    exit 0
fi

# Check if legacy .venv exists
if [[ ! -d "$LEGACY_VENV" ]]; then
    echo "❌ No .venv directory found to migrate."
    echo ""
    echo "To create a new platform-specific venv, run:"
    echo "  ./reproduce/reproduce_environment_comp_uv.sh"
    echo ""
    exit 1
fi

# Verify legacy venv is valid
if [[ ! -f "$LEGACY_VENV/bin/python" ]]; then
    echo "❌ Legacy .venv exists but appears incomplete (missing python executable)."
    echo ""
    echo "To recreate it, run:"
    echo "  rm -rf .venv"
    echo "  ./reproduce/reproduce_environment_comp_uv.sh"
    echo ""
    exit 1
fi

# Check if we're in the legacy venv
if [[ -n "${VIRTUAL_ENV:-}" ]] && [[ "$VIRTUAL_ENV" == "$LEGACY_VENV"* ]]; then
    echo "⚠️  You are currently in the legacy .venv environment."
    echo "   Please deactivate it first:"
    echo "   deactivate"
    echo ""
    read -p "Press Enter after deactivating, or Ctrl+C to cancel..."
fi

echo "Migrating .venv to platform-specific location..."
echo ""

# Move legacy venv to platform-specific location
mv "$LEGACY_VENV" "$CURRENT_VENV"

echo "✅ Migration complete!"
echo ""
echo "Your venv has been moved to: $(basename "$CURRENT_VENV")"
echo ""

# Check if other platform's venv exists
if [[ -d "$OTHER_VENV" ]]; then
    echo "✅ Venv for $OTHER_PLATFORM also exists: $(basename "$OTHER_VENV")"
    echo ""
else
    echo "ℹ️  To create a venv for $OTHER_PLATFORM:"
    echo "   1. Switch to that platform (DevContainer or macOS)"
    echo "   2. Run: ./reproduce/reproduce_environment_comp_uv.sh"
    echo ""
fi

echo "To activate the venv on this platform:"
echo "  source $(basename "$CURRENT_VENV")/bin/activate"
echo ""
echo "Or use the reproduce script (it will auto-detect):"
echo "  ./reproduce.sh --envt"
echo ""



