#!/bin/bash
# HAFiscal LaTeX Document Reproduction Script
# 
# This script provides comprehensive document compilation following research reproduction best practices.
# Consolidates functionality from multiple reproduction scripts into a single, maintainable solution.

set -eo pipefail

# Configuration with sensible defaults
BUILD_MODE="${BUILD_MODE:-LONG}"
ONLINE_APPENDIX_HANDLING="${ONLINE_APPENDIX_HANDLING:-LINK_ONLY}"
LATEX_OPTS="${LATEX_OPTS:-}"
REPRODUCTION_MODE="${REPRODUCTION_MODE:-full}"
VERBOSE=false
CLEAN_FIRST=false
DRY_RUN=false
SCOPE="main"

show_help() {
    cat << 'EOF'
HAFiscal LaTeX Document Reproduction Script

USAGE:
    ./reproduce_documents.sh [OPTIONS] [TARGETS...]

OPTIONS:
    --help, -h              Show this help message
    --quick, -q             Quick compilation (single pass)
    --verbose, -v           Verbose output
    --clean, -c             Clean build artifacts before compilation
    --single DOCUMENT       Compile only specified document
    --list                  List available documents
    --dry-run               Show commands that would be executed without running them
    --scope SCOPE           Compilation scope (main|all|figures|tables|subfiles, default: main)
                            main: only repo root files
                            all: root + Figures/ + Tables/ + Subfiles/
                            figures: root + Figures/
                            tables: root + Tables/
                            subfiles: root + Subfiles/

TARGETS:
    main                    HAFiscal.tex (main paper)
    slides                  HAFiscal-Slides.tex
    appendix-hank          Subfiles/Appendix-HANK.tex
    appendix-nosplurge     Subfiles/Appendix-NoSplurge.tex
    all                    All documents (default)

EXAMPLES:
    ./reproduce_documents.sh                    # Compile all documents
    ./reproduce_documents.sh main slides       # Compile specific documents
    ./reproduce_documents.sh --single HAFiscal.tex
    ./reproduce_documents.sh --quick           # Fast compilation
EOF
}

log_info() { echo "📋 $*"; }
log_success() { echo "✅ $*"; }
log_error() { echo "❌ ERROR: $*" >&2; }
log_warning() { echo "⚠️  WARNING: $*"; }

# Function to clean up auxiliary files after document compilation
cleanup_auxiliary_files() {
    local doc_path="$1"
    local doc_name="$2"
    
    if [[ "$DRY_RUN" == true ]]; then
        return 0
    fi
    
    log_info "Cleaning auxiliary files for $doc_name..."
    
    # Get the directory containing the document
    local doc_dir
    doc_dir=$(dirname "$doc_path")
    local doc_basename
    doc_basename=$(basename "$doc_path" .tex)
    
    # Run standard latexmk cleanup
    if [[ -n "$doc_dir" && "$doc_dir" != "." ]]; then
        (cd "$doc_dir" && latexmk -c "$(basename "$doc_path")" >/dev/null 2>&1) || true
        
        # For non-root documents, also remove .txt and .dep files
        (cd "$doc_dir" && rm -f "${doc_basename}.txt" "${doc_basename}.dep" >/dev/null 2>&1) || true
    else
        latexmk -c "$doc_path" >/dev/null 2>&1 || true
    fi
    
    return 0
}

# Function to resolve document target to file path
resolve_document() {
    case "$1" in
        "main") echo "HAFiscal.tex" ;;
        "slides") echo "HAFiscal-Slides.tex" ;;
        "appendix-hank") echo "Subfiles/Appendix-HANK.tex" ;;
        "appendix-nosplurge") echo "Subfiles/Appendix-NoSplurge.tex" ;;
        *) echo "$1" ;;  # Return as-is for direct file paths
    esac
}

list_documents() {
    echo "Available document targets:"
    echo "  main -> HAFiscal.tex"
    echo "  slides -> HAFiscal-Slides.tex"
    echo "  appendix-hank -> Subfiles/Appendix-HANK.tex"
    echo "  appendix-nosplurge -> Subfiles/Appendix-NoSplurge.tex"
}

# Enhanced LaTeX Error Parser
parse_latex_error() {
    local log_file="$1"
    local doc_name="$2"
    
    if [[ ! -f "$log_file" ]]; then
        log_error "$doc_name: Log file not found: $log_file"
        return 1
    fi
    
    printf "\n"
    printf "🔍 LaTeX Error Analysis for %s:\n" "$doc_name"
    printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    local found_errors=false
    local current_file=""
    local line_number=""
    
    # Parse the log file for common error patterns
    while IFS= read -r line; do
        # Track current file being processed
        if [[ "$line" =~ ^\([^\)]+\) ]] || [[ "$line" =~ \([^\)]+\.tex ]]; then
            current_file=$(echo "$line" | grep -o '([^)]*\.tex' | sed 's/^(//' | tail -1)
        fi
        
        # Extract line numbers from error context  
        if [[ "$line" =~ l\.[0-9]+ ]]; then
            line_number=$(echo "$line" | grep -o 'l\.[0-9]\+' | cut -d. -f2)
        fi
        
        # Undefined control sequence
        if [[ "$line" =~ Undefined\ control\ sequence ]]; then
            found_errors=true
            local next_line
            read -r next_line
            local undefined_cmd
            undefined_cmd=$(echo "$next_line" | grep -o '\\[a-zA-Z]*' | head -1)
            echo "❌ Undefined Control Sequence: ${undefined_cmd:-unknown}"
            [[ -n "$current_file" ]] && echo "   📄 File: $current_file"
            [[ -n "$line_number" ]] && echo "   📍 Line: $line_number"
            echo "   💡 Common fixes:"
            case "$undefined_cmd" in
                "\\cite"*|"\\ref"*|"\\label"*)
                    echo "      • Check bibliography (.bib) file exists and is accessible"
                    echo "      • Run bibtex/bibliography compilation step"
                    echo "      • Verify cross-reference labels exist"
                    ;;
                "\\usepackage"*)
                    echo "      • Install missing LaTeX package"
                    echo "      • Check package name spelling"
                    ;;
                "\\begin"*|"\\end"*)
                    echo "      • Check environment name spelling"
                    printf "      • Ensure matching \\\\begin{} and \\\\end{} pairs\n"
                    ;;
                *)
                    echo "      • Check command spelling and syntax"
                    echo "      • Verify required packages are loaded"
                    echo "      • Add missing \\usepackage{} statements"
                    ;;
            esac
            printf "\n"
        fi
        
        # Missing file
        if [[ "$line" =~ File.*not\ found ]] || [[ "$line" =~ I\ couldn\'t\ open\ file\ name ]]; then
            found_errors=true
            local missing_file
            missing_file=$(echo "$line" | grep -o "'[^']*'" | tr -d "'")
            echo "❌ Missing File: ${missing_file:-unknown}"
            [[ -n "$current_file" ]] && echo "   📄 From: $current_file"
            echo "   💡 Common fixes:"
            echo "      • Check file path and spelling"
            echo "      • Ensure file exists in the correct directory"
            echo "      • Verify relative path is correct from document location"
            printf "\n"
        fi
        
        # Missing bibliography
        if [[ "$line" =~ Empty\ bibliography ]] || [[ "$line" =~ I\ couldn\'t\ open\ database\ file ]]; then
            found_errors=true
            echo "❌ Bibliography Issue"
            [[ -n "$current_file" ]] && echo "   📄 File: $current_file"
            echo "   💡 Common fixes:"
            echo "      • Ensure bibliography file (.bib) exists"
            printf "      • Check \\\\bibliography{} command references correct file\n"
            echo "      • Run: bibtex $doc_name"
            printf "\n"
        fi
        
        # Package errors
        if [[ "$line" =~ Package.*Error ]]; then
            found_errors=true
            local package_name
            package_name=$(echo "$line" | grep -o 'Package [^ ]*' | cut -d' ' -f2)
            echo "❌ Package Error: ${package_name:-unknown}"
            [[ -n "$current_file" ]] && echo "   📄 File: $current_file" 
            [[ -n "$line_number" ]] && echo "   📍 Line: $line_number"
            echo "   💡 Common fixes:"
            echo "      • Update LaTeX distribution"
            echo "      • Check package documentation for correct usage"
            echo "      • Verify package compatibility with other loaded packages"
            printf "\n"
        fi
        
        # Compilation stopped
        if [[ "$line" =~ Emergency\ stop ]] || [[ "$line" =~ job\ aborted ]]; then
            found_errors=true
            echo "❌ Compilation Emergency Stop"
            echo "   💡 This usually indicates a serious syntax error above"
            echo "      • Check for unmatched braces { }"
            echo "      • Look for incomplete commands or environments"
            echo "      • Review recent changes to the document"
            printf "\n"
        fi
        
    done < "$log_file"
    
    # Bibliography-specific checks
    if grep -q "Illegal, another.*bibdata command" "$log_file" 2>/dev/null; then
        found_errors=true
        echo "❌ Duplicate Bibliography Command"
        printf "   💡 This indicates multiple \\\\bibliography{} calls\n"
        printf "      • Check for duplicate \\\\smartbib{} usage\n"
        echo "      • Verify subfile bibliography handling"
        echo "      • Try: latexmk -C $doc_name && latexmk $doc_name"
        printf "\n"
    fi
    
    if ! $found_errors; then
        echo "ℹ️  No specific errors detected in log analysis"
        echo "   💡 The issue might be:"
        echo "      • A warning treated as error by latexmk"
        echo "      • Resource constraints (disk space, memory)"
        echo "      • Permission issues with output directory"
        printf "\n"
        echo "🔍 Recent log file excerpts:"
        echo "   Last 10 lines of $log_file:"
        tail -10 "$log_file" | sed 's/^/      /'
    fi
    
    printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    printf "📝 Full log available at: %s\n" "$log_file"
    printf "\n"
}

validate_environment() {
    log_info "Validating compilation environment..."
    
    
    # Allow skipping TeX Live package checks for speed
    if [[ "${SKIP_TEXLIVE_CHECK:-}" == "true" ]] || [[ "${SKIP_ENV_CHECK:-}" == "true" ]]; then
        log_warning "Skipping TeX Live package checks (SKIP_TEXLIVE_CHECK or SKIP_ENV_CHECK set)"
        # Still do minimal checks
        if ! command -v latex >/dev/null 2>&1; then
            log_error "latex command not found - please install TeX Live"
            return 1
        fi
        if ! command -v latexmk >/dev/null 2>&1; then
            log_error "latexmk is not installed or not in PATH"
            return 1
        fi
        if [[ ! -f "HAFiscal.tex" ]]; then
            log_error "HAFiscal.tex not found - run from project root directory"
            return 1
        fi
        log_success "Environment validation completed (minimal checks)"
        return 0
    fi
    # Check TeX Live installation first
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$script_dir/reproduce_environment_texlive.sh" ]]; then
        log_info "Checking TeX Live environment..."
        if ! source "$script_dir/reproduce_environment_texlive.sh"; then
            log_error "TeX Live environment check failed"
            log_error "Please install TeX Live and required packages before continuing"
            return 1
        fi
        log_success "TeX Live environment verified"
    else
        log_warning "TeX Live verification script not found - skipping comprehensive checks"
        
        # Minimal TeX Live check as fallback
        if ! command -v latex >/dev/null 2>&1; then
            log_error "latex command not found - please install TeX Live"
            return 1
        fi
    fi
    
    if ! command -v latexmk >/dev/null 2>&1; then
        log_error "latexmk is not installed or not in PATH"
        return 1
    fi
    
    if [[ ! -f "HAFiscal.tex" ]]; then
        log_error "HAFiscal.tex not found - run from project root directory"
        return 1
    fi
    
    log_success "Environment validation completed"
}

setup_build_environment() {
    log_info "Setting up build environment..."
    
    export BUILD_MODE
    export ONLINE_APPENDIX_HANDLING
    export TEXINPUTS="./qe/:${TEXINPUTS:-}"
    export BSTINPUTS="./qe/:@resources/texlive/texmf-local/bibtex/bst/:${BSTINPUTS:-}"
    
    
    log_info "Build mode: $BUILD_MODE, Appendix handling: $ONLINE_APPENDIX_HANDLING"
}

compile_document() {
    local doc_path="$1"
    local doc_name
    doc_name="$(basename "$doc_path" .tex)"
    
    if [[ ! -f "$doc_path" ]]; then
        log_error "Document not found: $doc_path"
        return 1
    fi
    
    # Configure latexmk options
    local latexmk_opts=()
    if [[ -n "$LATEX_OPTS" ]]; then
        read -ra opts <<< "$LATEX_OPTS"
        latexmk_opts+=("${opts[@]}")
    fi
    
    latexmk_opts+=("-usepretex=\\def\\OnlineAppendixHandling{${ONLINE_APPENDIX_HANDLING}}")
    
    # Handle dry-run mode
    if [[ "$DRY_RUN" == true ]]; then
        # Show the command that would be executed
        echo "# Compiling: $doc_path"
        if [[ "$CLEAN_FIRST" == "true" ]]; then
            echo "latexmk -c \"$doc_path\""
        fi
        
        # Format command with proper shell escaping for copy-paste usage
        local escaped_opts=()
        for opt in "${latexmk_opts[@]}"; do
            # Escape backslashes for shell copy-paste and quote the option if it contains special characters
            if [[ "$opt" == *"\\"* ]] || [[ "$opt" == *"{"* ]] || [[ "$opt" == *"}"* ]]; then
                # Double the backslashes and quote the entire option
                escaped_opt=${opt//\\/\\\\}
                escaped_opts+=("\"$escaped_opt\"")
            else
                escaped_opts+=("$opt")
            fi
        done
        
        echo "latexmk" "${escaped_opts[@]}" "\"$doc_path\""
        echo ""
        return 0
    fi
    
    log_info "Compiling: $doc_path"
    
    if [[ "$CLEAN_FIRST" == "true" ]]; then
        latexmk -c "$doc_path" >/dev/null 2>&1 || true
    fi
    
    # PDF viewer management integration
    
    local start_time
    start_time=$(date +%s)
    
    if [[ "$REPRODUCTION_MODE" == "quick" ]]; then
        # Try compilation first
        if latexmk "${latexmk_opts[@]}" "$doc_path"; then
            local end_time
            end_time=$(date +%s)
            log_success "$doc_name completed in $((end_time - start_time))s (quick mode)"
            cleanup_auxiliary_files "$doc_path" "$doc_name"
        else
            # If latexmk fails, clean and retry once
            log_info "Cleaning and retrying $doc_name..."
            latexmk -c "$doc_path" >/dev/null 2>&1 || true
            if latexmk "${latexmk_opts[@]}" "$doc_path"; then
                local end_time
                end_time=$(date +%s)
                log_success "$doc_name completed in $((end_time - start_time))s (quick mode - retry)"
                cleanup_auxiliary_files "$doc_path" "$doc_name"
            else
                # Check if PDF was generated despite error
                local pdf_output="${doc_path%.tex}.pdf"
                if [[ -f "$pdf_output" ]]; then
                    local end_time
                    end_time=$(date +%s)
                    log_warning "$doc_name: latexmk reported error but PDF was generated"
                    log_success "$doc_name completed in $((end_time - start_time))s (quick mode - with warnings)"
                    cleanup_auxiliary_files "$doc_path" "$doc_name"
                else
                    log_error "$doc_name compilation failed"
                    # Enhanced error analysis
                    local log_file="${doc_path%.tex}.log"
                    if [[ -f "$log_file" ]]; then
                        parse_latex_error "$log_file" "$doc_name"
                    fi
                    return 1
                fi
            fi
        fi
    else
        # Multiple passes for complete cross-reference resolution
        local passes=3
        for ((i=1; i<=passes; i++)); do
            if [[ "$VERBOSE" == "true" ]]; then
                echo "  Pass $i/$passes..."
            fi
            if ! latexmk "${latexmk_opts[@]}" "$doc_path"; then
                log_error "$doc_name compilation failed on pass $i"
                # Enhanced error analysis
                local log_file="${doc_path%.tex}.log"
                if [[ -f "$log_file" ]]; then
                    parse_latex_error "$log_file" "$doc_name"
                fi
                return 1
            fi
        done
        local end_time
        end_time=$(date +%s)
        log_success "$doc_name completed in $((end_time - start_time))s ($passes passes)"
    fi
    
    # Clean up auxiliary files after successful compilation
    cleanup_auxiliary_files "$doc_path" "$doc_name"
    
    # Verify output (after cleanup to avoid any interference)
    local pdf_output="${doc_path%.tex}.pdf"
    if [[ -f "$pdf_output" ]]; then
        local pdf_size
        pdf_size=$(stat -f%z "$pdf_output" 2>/dev/null || stat -c%s "$pdf_output" 2>/dev/null || echo "unknown")
        log_info "Generated: $pdf_output ($pdf_size bytes)"
    fi
    
    # Final cleanup to ensure any files created during verification are removed
    if [[ "$DRY_RUN" != true ]]; then
        local doc_dir
        doc_dir=$(dirname "$doc_path")
        local doc_basename
        doc_basename=$(basename "$doc_path" .tex)
        
        # For non-root documents, ensure .txt and .dep files are removed
        if [[ -n "$doc_dir" && "$doc_dir" != "." ]]; then
            (cd "$doc_dir" && rm -f "${doc_basename}.txt" "${doc_basename}.dep" >/dev/null 2>&1) || true
        fi
    fi
    
    return 0
}

main() {
    local targets=()
    local single_document=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --quick|-q)
                REPRODUCTION_MODE="quick"
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --clean|-c)
                CLEAN_FIRST=true
                shift
                ;;
            --single)
                if [[ -n "${2:-}" ]]; then
                    single_document="$2"
                    shift 2
                else
                    log_error "--single requires a document name"
                    exit 1
                fi
                ;;
            --list)
                list_documents
                exit 0
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --scope)
                if [[ -n "${2:-}" && "$2" =~ ^(main|all|figures|tables|subfiles)$ ]]; then
                    SCOPE="$2"
                    shift 2
                else
                    log_error "--scope requires one of: main, all, figures, tables, subfiles"
                    exit 1
                fi
                ;;
            -*)
                log_error "Unknown option: $1"
                exit 1
                ;;
            *)
                targets+=("$1")
                shift
                ;;
        esac
    done
    
    # Change to project root if we're in reproduce/ directory
    if [[ "$(basename "$(pwd)")" == "reproduce" ]]; then
        cd ..
    fi
    
    # Validate and setup
    if ! validate_environment; then
        exit 1
    fi
    
    setup_build_environment
    
    log_info "Starting HAFiscal document reproduction (mode: $REPRODUCTION_MODE)"
    
    # Handle single document compilation
    if [[ -n "$single_document" ]]; then
        compile_document "$single_document"
        exit $?
    fi
    
    # Set default behavior (no specific targets needed as scope handles discovery)
    if [[ ${#targets[@]} -eq 0 ]]; then
        targets=()  # Empty targets is fine, scope-based discovery handles it
    fi
    
    # Resolve targets to document paths based on scope
    local docs_to_compile=()
    
    # Discover available root files (for validation and potential inclusion)
    local root_tex_files=()
    while IFS= read -r -d '' file; do
        root_tex_files+=("$(basename "$file")")
    done < <(find . -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 | sort -z)
    
    if [[ ${#root_tex_files[@]} -eq 0 ]]; then
        log_error "No .tex files found in repo root directory"
        exit 1
    fi
    
    # Add files to compilation list based on scope
    case "$SCOPE" in
        "main")
            log_info "Scope: main - compiling only repo root files"
            log_info "Found ${#root_tex_files[@]} .tex files in repo root:"
            for file in "${root_tex_files[@]}"; do
                log_info "  - $file"
            done
            docs_to_compile+=("${root_tex_files[@]}")
            ;;
        "all")
            log_info "Scope: all - including Figures/, Tables/, and Subfiles/"
            
            # Include root files
            log_info "Found ${#root_tex_files[@]} .tex files in repo root:"
            for file in "${root_tex_files[@]}"; do
                log_info "  - $file"
            done
            docs_to_compile+=("${root_tex_files[@]}")
            
            # Add .tex files from Figures/
            if [[ -d "Figures" ]]; then
                local figures_files=()
                while IFS= read -r -d '' file; do
                    figures_files+=("$file")
                done < <(find Figures -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#figures_files[@]} -gt 0 ]]; then
                    log_info "Found ${#figures_files[@]} .tex files in Figures/:"
                    for file in "${figures_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${figures_files[@]}")
                fi
            fi
            
            # Add .tex files from Tables/
            if [[ -d "Tables" ]]; then
                local tables_files=()
                while IFS= read -r -d '' file; do
                    tables_files+=("$file")
                done < <(find Tables -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#tables_files[@]} -gt 0 ]]; then
                    log_info "Found ${#tables_files[@]} .tex files in Tables/:"
                    for file in "${tables_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${tables_files[@]}")
                fi
            fi
            
            # Add .tex files from Subfiles/
            if [[ -d "Subfiles" ]]; then
                local subfiles_files=()
                while IFS= read -r -d '' file; do
                    subfiles_files+=("$file")
                done < <(find Subfiles -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#subfiles_files[@]} -gt 0 ]]; then
                    log_info "Found ${#subfiles_files[@]} .tex files in Subfiles/:"
                    for file in "${subfiles_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${subfiles_files[@]}")
                fi
            fi
            ;;
        "figures")
            log_info "Scope: figures - including Figures/"
            
            # Add .tex files from Figures/
            if [[ -d "Figures" ]]; then
                local figures_files=()
                while IFS= read -r -d '' file; do
                    figures_files+=("$file")
                done < <(find Figures -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#figures_files[@]} -gt 0 ]]; then
                    log_info "Found ${#figures_files[@]} .tex files in Figures/:"
                    for file in "${figures_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${figures_files[@]}")
                fi
            fi
            ;;
        "tables")
            log_info "Scope: tables - including Tables/"
            
            # Add .tex files from Tables/
            if [[ -d "Tables" ]]; then
                local tables_files=()
                while IFS= read -r -d '' file; do
                    tables_files+=("$file")
                done < <(find Tables -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#tables_files[@]} -gt 0 ]]; then
                    log_info "Found ${#tables_files[@]} .tex files in Tables/:"
                    for file in "${tables_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${tables_files[@]}")
                fi
            fi
            ;;
        "subfiles")
            log_info "Scope: subfiles - including Subfiles/"
            
            # Add .tex files from Subfiles/
            if [[ -d "Subfiles" ]]; then
                local subfiles_files=()
                while IFS= read -r -d '' file; do
                    subfiles_files+=("$file")
                done < <(find Subfiles -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#subfiles_files[@]} -gt 0 ]]; then
                    log_info "Found ${#subfiles_files[@]} .tex files in Subfiles/:"
                    for file in "${subfiles_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${subfiles_files[@]}")
                fi
            fi
            ;;
    esac
    
    # Handle specific targets if any were provided (legacy behavior)
    local target
    for target in "${targets[@]}"; do
        if [[ "$target" != "all" ]]; then
            local resolved_doc
            resolved_doc=$(resolve_document "$target")
            docs_to_compile+=("$resolved_doc")
        fi
    done
    
    # Remove duplicates
    local unique_docs=()
    local doc existing found
    for doc in "${docs_to_compile[@]}"; do
        found=false
        for existing in "${unique_docs[@]}"; do
            if [[ "$doc" == "$existing" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == "false" ]]; then
            unique_docs+=("$doc")
        fi
    done
    
    # Compile documents
    local success_count=0
    local total_count=${#unique_docs[@]}
    
    log_info "Compiling $total_count document(s)..."
    
    for doc in "${unique_docs[@]}"; do
        echo ""
        if compile_document "$doc"; then
            ((++success_count))
        fi
    done
    
    echo ""
    echo "========================================"
    log_info "Reproduction completed: $success_count/$total_count documents successful"
    
    if [[ $success_count -eq $total_count ]]; then
        log_success "All documents compiled successfully!"
        exit 0
    else
        log_error "Some documents failed to compile"
        exit 1
    fi
}

# Run main function with all arguments
main "$@" 
