#!/bin/bash
# HANK-SAM Dashboard Startup Script
# Works in: GitHub Codespaces, local development (UV venv), and Conda environments

set -e

echo "🏦 Starting HANK-SAM Dashboard..."

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Function to detect platform-specific venv path (matches reproduce_environment_comp_uv.sh logic)
get_platform_venv_path() {
    local platform=""
    local arch=""
    
    # Detect platform
    case "$(uname -s)" in
        Darwin)
            platform="darwin"
            ;;
        Linux)
            platform="linux"
            ;;
        *)
            platform=""
            ;;
    esac
    
    # Detect architecture
    if [[ "$(uname -s)" == "Darwin" ]]; then
        if sysctl -n hw.optional.arm64 2>/dev/null | grep -q 1; then
            arch="arm64"
        else
            arch="x86_64"
        fi
    else
        arch="$(uname -m)"
        case "$arch" in
            aarch64) arch="aarch64" ;;
            x86_64) arch="x86_64" ;;
        esac
    fi
    
    if [[ -n "$platform" ]] && [[ -n "$arch" ]]; then
        echo "$PROJECT_ROOT/.venv-$platform-$arch"
    else
        echo ""
    fi
}

# Try to activate environment
VENV_PATH=$(get_platform_venv_path)
ACTIVATED=false

# Try 1: Architecture-specific UV venv (local development)
if [[ -n "$VENV_PATH" ]] && [[ -d "$VENV_PATH" ]]; then
    echo "📦 Activating UV virtual environment: $(basename "$VENV_PATH")"
    source "$VENV_PATH/bin/activate"
    ACTIVATED=true
# Try 2: Conda environment (Codespaces or conda users)
elif command -v conda >/dev/null 2>&1; then
    if [[ -d /opt/miniconda3 ]] || [[ -n "${CONDA_PREFIX:-}" ]]; then
        # Codespaces path
        if [[ -d /opt/miniconda3 ]]; then
            source /opt/miniconda3/etc/profile.d/conda.sh 2>/dev/null || true
        fi
        echo "📦 Activating Conda environment: hafiscal-dashboard"
        if conda activate hafiscal-dashboard 2>/dev/null; then
            ACTIVATED=true
        # Fallback to main hafiscal environment
        elif conda activate hafiscal 2>/dev/null; then
            ACTIVATED=true
        fi
    fi
fi

# If still not activated, warn user
if [[ "$ACTIVATED" == "false" ]]; then
    echo "⚠️  Warning: No virtual environment activated automatically."
    echo "   Please activate your environment manually:"
    if [[ -n "$VENV_PATH" ]]; then
        echo "   UV venv: source $VENV_PATH/bin/activate"
    fi
    echo "   Conda: conda activate hafiscal-dashboard"
    echo ""
    echo "   Continuing anyway..."
fi

# Verify environment
echo "📋 Checking environment..."
python -c "
import sys
sys.path.insert(0, 'dashboard')
try:
    import hank_sam as hs
    import hafiscal
    print('✅ All imports successful!')
except ImportError as e:
    print(f'⚠️  Import warning: {e}')
    print('   Dashboard may not work correctly.')
" 2>&1 || echo "⚠️  Could not verify imports"

echo ""
echo "🚀 Starting Voila dashboard..."
echo "   → Dashboard will be available on port 8866"
if [[ -n "${CODESPACE_NAME:-}" ]]; then
    echo "   → Codespaces will auto-forward the port"
    echo "   → Click the 'Ports' tab to access the dashboard URL"
else
    echo "   → Open http://localhost:8866 in your browser"
fi
echo ""

# Start the dashboard
cd "$PROJECT_ROOT"
voila dashboard/app.ipynb --no-browser --port=8866 --Voila.ip='0.0.0.0' --enable_nbextensions=True
