#!/bin/bash
# discover-packages.sh - Compile standalone files and record package dependencies
# This script compiles each .tex file in Tables/, Figures/, and Subfiles/
# and records the packages that MiKTeX auto-installs for each file
#
# By default, pauses after each file to show what was installed and ask permission to continue.
# Use --no-pause flag or set MIKTEX_NO_PAUSE=1 environment variable to skip pausing.

set -e

# Parse command line arguments
NO_PAUSE=0
if [[ "$1" == "--no-pause" ]] || [[ "${MIKTEX_NO_PAUSE}" == "1" ]]; then
    NO_PAUSE=1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Directories to scan
SCAN_DIRS=("Tables" "Figures" "Subfiles")

# Output directory for .pkgs files
PKGS_DIR="$SCRIPT_DIR"
LOGS_DIR="$PKGS_DIR/logs"
mkdir -p "$LOGS_DIR"

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅${NC} $1"
}

warning() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ❌${NC} $1"
}

info() {
    echo -e "${CYAN}[$(date '+%H:%M:%S')] ℹ️${NC} $1"
}

# Function to extract package installations from MiKTeX log
extract_packages_from_log() {
    local logfile="$1"
    local pkgsfile="$2"
    
    # Initialize empty package list
    > "$pkgsfile"
    
    # Add header
    echo "# Package dependencies extracted from compilation" >> "$pkgsfile"
    echo "# Format: package_name (source: installation|font-generation)" >> "$pkgsfile"
    echo "" >> "$pkgsfile"
    
    # Extract package installations (packages that were installed via mpm)
    if [ -f "$logfile" ]; then
        # Look for package installations in the log
        grep -i "installing package" "$logfile" 2>/dev/null | \
            sed 's/.*installing package[: ]*\([^ ]*\).*/\1/' | \
            sort -u | \
            while read -r pkg; do
                echo "${pkg} (installation)" >> "$pkgsfile"
            done
        
        # Look for font generation (METAFONT activity)
        grep -i "Running miktex-makemf" "$logfile" 2>/dev/null | \
            sed 's/.*miktex-makemf --mfmode.*--mfopt.*--name[= ]*\([^ ]*\).*/\1/' | \
            sort -u | \
            while read -r font; do
                echo "${font} (font-generation)" >> "$pkgsfile"
            done
        
        # Look for loaded packages (from \usepackage or \RequirePackage)
        grep "^Package: " "$logfile" 2>/dev/null | \
            awk '{print $2}' | \
            sort -u | \
            while read -r pkg; do
                echo "${pkg} (loaded)" >> "$pkgsfile"
            done
    fi
    
    # Count entries
    local count=$(grep -v "^#" "$pkgsfile" | grep -v "^$" | wc -l)
    echo "$count"
}

# Function to wait for user confirmation
wait_for_user() {
    local pkgsfile="$1"
    local relpath="$2"
    
    # Skip if NO_PAUSE is set
    if [ "$NO_PAUSE" -eq 1 ]; then
        return 0
    fi
    
    # Show what was installed/generated
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Dependencies for: $relpath${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    
    # Count by type
    # grep -c returns 0 if no matches, so no need for || echo "0"
    local install_count=$(grep -c "(installation)" "$pkgsfile" 2>/dev/null || true)
    local font_count=$(grep -c "(font-generation)" "$pkgsfile" 2>/dev/null || true)
    local loaded_count=$(grep -c "(loaded)" "$pkgsfile" 2>/dev/null || true)
    
    # Ensure we have valid integers (in case file doesn't exist)
    install_count=${install_count:-0}
    font_count=${font_count:-0}
    loaded_count=${loaded_count:-0}
    
    if [ "$install_count" -gt 0 ]; then
        echo -e "${YELLOW}Installed packages ($install_count):${NC}"
        grep "(installation)" "$pkgsfile" | sed 's/ (installation)//' | sed 's/^/  • /'
    fi
    
    if [ "$font_count" -gt 0 ]; then
        echo -e "${BLUE}Generated fonts ($font_count):${NC}"
        grep "(font-generation)" "$pkgsfile" | sed 's/ (font-generation)//' | sed 's/^/  • /'
    fi
    
    if [ "$loaded_count" -gt 0 ]; then
        echo -e "${GREEN}Loaded packages ($loaded_count):${NC}"
        grep "(loaded)" "$pkgsfile" | head -10 | sed 's/ (loaded)//' | sed 's/^/  • /'
        if [ "$loaded_count" -gt 10 ]; then
            echo "  ... and $((loaded_count - 10)) more"
        fi
    fi
    
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Only pause if there were installations
    if [ "$install_count" -gt 0 ] || [ "$font_count" -gt 0 ]; then
        echo -ne "${YELLOW}Press ENTER to continue to next file (or Ctrl+C to stop)...${NC} "
        read -r
        echo ""
    fi
}

# Function to compile a single .tex file and record dependencies
compile_and_record() {
    local texfile="$1"
    local relpath="$2"
    
    # Get base name without extension
    local basename=$(basename "$texfile" .tex)
    local dirname=$(dirname "$relpath")
    
    # Create .pkgs filename
    local pkgsfile="$PKGS_DIR/${dirname}_${basename}.pkgs"
    local logfile="$LOGS_DIR/${dirname}_${basename}.log"
    
    info "Compiling: $relpath"
    
    # Change to project root for compilation (subfiles need this)
    cd "$PROJECT_ROOT"
    
    # Compile with pdflatex, capturing output
    # Use -interaction=nonstopmode to avoid prompts
    # Redirect output to log file
    local compile_status=0
    if pdflatex -interaction=nonstopmode \
                -output-directory="$LOGS_DIR" \
                -jobname="${dirname}_${basename}" \
                "$texfile" > "$logfile" 2>&1; then
        
        # Extract packages from log
        local pkg_count=$(extract_packages_from_log "$logfile" "$pkgsfile")
        success "Compiled: $relpath ($pkg_count dependencies)"
        compile_status=0
    else
        # Compilation failed, but still extract what we can
        local pkg_count=$(extract_packages_from_log "$logfile" "$pkgsfile")
        warning "Failed to compile: $relpath (but recorded $pkg_count dependencies)"
        compile_status=1
    fi
    
    # Wait for user confirmation (unless --no-pause)
    wait_for_user "$pkgsfile" "$relpath"
    
    return $compile_status
}

# Main script
main() {
    log "═══════════════════════════════════════════════════════════"
    log "  MiKTeX Package Discovery for HAFiscal"
    log "═══════════════════════════════════════════════════════════"
    log ""
    log "Project root: $PROJECT_ROOT"
    log "Output directory: $PKGS_DIR"
    
    if [ "$NO_PAUSE" -eq 1 ]; then
        info "Running in NO-PAUSE mode (--no-pause or MIKTEX_NO_PAUSE=1)"
    else
        info "Interactive mode: Will pause after each file with new installations"
        info "Use --no-pause flag or set MIKTEX_NO_PAUSE=1 to skip pausing"
    fi
    log ""
    
    # Clean up old .pkgs files
    rm -f "$PKGS_DIR"/*.pkgs
    
    # Statistics
    local total_files=0
    local compiled_ok=0
    local compiled_fail=0
    
    # Scan each directory
    for dir in "${SCAN_DIRS[@]}"; do
        local dirpath="$PROJECT_ROOT/$dir"
        
        if [ ! -d "$dirpath" ]; then
            warning "Directory not found: $dir"
            continue
        fi
        
        log "Scanning directory: $dir/"
        
        # Find all .tex files
        while IFS= read -r texfile; do
            total_files=$((total_files + 1))
            
            # Get relative path
            local relpath="${texfile#$PROJECT_ROOT/}"
            
            # Compile and record
            if compile_and_record "$texfile" "$relpath"; then
                compiled_ok=$((compiled_ok + 1))
            else
                compiled_fail=$((compiled_fail + 1))
            fi
            
        done < <(find "$dirpath" -maxdepth 1 -name "*.tex" -type f)
        
        log ""
    done
    
    log "═══════════════════════════════════════════════════════════"
    log "  Compilation Summary"
    log "═══════════════════════════════════════════════════════════"
    log "Total files found: $total_files"
    success "Successfully compiled: $compiled_ok"
    if [ $compiled_fail -gt 0 ]; then
        warning "Failed to compile: $compiled_fail"
    fi
    log ""
    
    # Generate aggregate package list
    log "Generating aggregate package list..."
    local aggregate_file="$PKGS_DIR/aggregate-packages.txt"
    
    # Combine all .pkgs files and remove duplicates
    cat "$PKGS_DIR"/*.pkgs 2>/dev/null | \
        grep -v "^#" | \
        grep -v "^$" | \
        sort -u > "$aggregate_file"
    
    local total_pkgs=$(wc -l < "$aggregate_file")
    success "Aggregate package list created: $aggregate_file"
    log "Total unique dependencies: $total_pkgs"
    log ""
    
    # Show breakdown by type
    log "Dependency breakdown:"
    local install_count=$(grep -c "(installation)" "$aggregate_file" 2>/dev/null || echo "0")
    local font_count=$(grep -c "(font-generation)" "$aggregate_file" 2>/dev/null || echo "0")
    local loaded_count=$(grep -c "(loaded)" "$aggregate_file" 2>/dev/null || echo "0")
    
    log "  - Installed packages: $install_count"
    log "  - Generated fonts: $font_count"
    log "  - Loaded packages: $loaded_count"
    log ""
    
    log "═══════════════════════════════════════════════════════════"
    log "  Package Discovery Complete"
    log "═══════════════════════════════════════════════════════════"
    log ""
    log "Output files:"
    log "  • Individual .pkgs files: $PKGS_DIR/*.pkgs"
    log "  • Aggregate list: $aggregate_file"
    log "  • Compilation logs: $LOGS_DIR/*.log"
    log ""
    log "To install all discovered packages:"
    log "  grep '(installation)' $aggregate_file | cut -d' ' -f1 | xargs -I {} mpm --admin --install={}"
    log ""
    log "Usage examples:"
    log "  ./pkgs/discover-packages.sh              # Interactive mode (pauses after each file)"
    log "  ./pkgs/discover-packages.sh --no-pause   # Non-interactive mode"
    log "  MIKTEX_NO_PAUSE=1 ./pkgs/discover-packages.sh  # Non-interactive via env var"
}

# Run main function
main "$@"

