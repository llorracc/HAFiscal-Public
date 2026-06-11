#!/bin/bash
# Verify Zenodo DOI Compliance with Econometric Society Journals Requirements
#
# This script verifies that a Zenodo DOI meets the specific requirements
# for replication packages submitted to Econometric Society Journals
# (Econometrica, Quantitative Economics, Theoretical Economics).
#
# Usage:
#   ./verify-zenodo-doi-compliance.sh [DOI]
#   If DOI not provided, extracts from README.md and titlepage
#
# Requirements checked:
#   1. DOI format is correct (10.5281/zenodo.XXXXX)
#   2. DOI resolves to a valid Zenodo record
#   3. Record is in Econometric Society Journals' Community
#   4. Record has required metadata (title, authors, license)
#   5. Record has required files (README, code, data instructions)
#   6. License allows unrestricted access and replication use

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ES_COMMUNITY_ID="es-replication-repository"
ES_COMMUNITY_URL="https://zenodo.org/communities/${ES_COMMUNITY_ID}"
ZENODO_API_BASE="https://zenodo.org/api"

# Functions
log_info() {
    echo "INFO: $1"
}

log_success() {
    echo "OK: $1"
}

log_warning() {
    echo "WARN: $1"
}

log_error() {
    echo "ERROR: $1"
}

# Extract DOI from text
extract_doi() {
    local text="$1"
    # Match pattern: 10.5281/zenodo.XXXXX
    echo "$text" | grep -oE "10\.5281/zenodo\.[0-9]+" | head -1
}

# Get Zenodo record ID from DOI
get_zenodo_record_id() {
    local doi="$1"
    # Extract numeric ID from DOI (e.g., 17861977 from 10.5281/zenodo.17861977)
    echo "$doi" | grep -oE "[0-9]+$"
}

# Fetch Zenodo record metadata via API
fetch_zenodo_record() {
    local record_id="$1"
    local api_url="${ZENODO_API_BASE}/records/${record_id}"
    
    log_info "Fetching Zenodo record metadata for record ID: ${record_id}"
    
    if ! curl -s -f "${api_url}" > /tmp/zenodo_record.json 2>/dev/null; then
        log_error "Failed to fetch Zenodo record from API"
        return 1
    fi
    
    if [[ ! -s /tmp/zenodo_record.json ]]; then
        log_error "Zenodo API returned empty response"
        return 1
    fi
    
    # Check if record exists
    if grep -q '"status": 404' /tmp/zenodo_record.json 2>/dev/null; then
        log_error "Zenodo record not found (404)"
        return 1
    fi
    
    return 0
}

# Check if record is in ES Community
check_es_community() {
    local record_json="$1"
    
    log_info "Checking if record is in Econometric Society Journals' Community..."
    
    # Check communities field
    if grep -q "\"${ES_COMMUNITY_ID}\"" "$record_json" 2>/dev/null; then
        log_success "Record is in ES Journals' Community (${ES_COMMUNITY_ID})"
        return 0
    fi
    
    # Alternative: check communities array
    if python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    communities = data.get('metadata', {}).get('communities', [])
    identifiers = [c.get('identifier', '') for c in communities]
    if '${ES_COMMUNITY_ID}' in identifiers:
        sys.exit(0)
    else:
        print('Found communities:', identifiers)
        sys.exit(1)
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
" 2>/dev/null; then
        log_success "Record is in ES Journals' Community"
        return 0
    fi
    
    log_error "Record is NOT in Econometric Society Journals' Community"
    log_warning "Expected community: ${ES_COMMUNITY_ID}"
    log_warning "Community URL: ${ES_COMMUNITY_URL}"
    return 1
}

# Check required metadata
check_metadata() {
    local record_json="$1"
    
    log_info "Checking required metadata..."
    
    local has_title=false
    local has_creators=false
    local has_license=false
    
    # Check for title
    if python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    title = data.get('metadata', {}).get('title', '')
    if title:
        print('Title:', title)
        sys.exit(0)
    sys.exit(1)
except:
    sys.exit(1)
" 2>/dev/null; then
        log_success "Record has title"
        has_title=true
    else
        log_error "Record missing title"
    fi
    
    # Check for creators/authors
    if python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    creators = data.get('metadata', {}).get('creators', [])
    if creators and len(creators) > 0:
        print('Creators:', len(creators))
        sys.exit(0)
    sys.exit(1)
except:
    sys.exit(1)
" 2>/dev/null; then
        log_success "Record has creators/authors"
        has_creators=true
    else
        log_error "Record missing creators/authors"
    fi
    
    # Check for license
    if python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    license_id = data.get('metadata', {}).get('license', {}).get('id', '')
    if license_id:
        print('License:', license_id)
        sys.exit(0)
    sys.exit(1)
except:
    sys.exit(1)
" 2>/dev/null; then
        log_success "Record has license"
        has_license=true
    else
        log_error "Record missing license"
    fi
    
    if [[ "$has_title" == "true" ]] && [[ "$has_creators" == "true" ]] && [[ "$has_license" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Check license allows unrestricted access
check_license() {
    local record_json="$1"
    
    log_info "Checking license allows unrestricted access and replication use..."
    
    # Get license ID
    local license_id=$(python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    license_id = data.get('metadata', {}).get('license', {}).get('id', '')
    print(license_id)
except:
    pass
" 2>/dev/null)
    
    if [[ -z "$license_id" ]]; then
        log_error "No license found in record"
        return 1
    fi
    
    log_info "License ID: ${license_id}"
    
    # Check if license is open (allows unrestricted access)
    # Common open licenses: Apache-2.0, MIT, BSD-3-Clause, CC0-1.0, CC-BY-4.0, etc.
    if echo "$license_id" | grep -qiE "(apache|mit|bsd|cc0|cc-by|gpl|lgpl|mpl)"; then
        log_success "License appears to allow unrestricted access: ${license_id}"
        return 0
    else
        log_warning "License may not allow unrestricted access: ${license_id}"
        log_warning "Verify that license permits replication use by other researchers"
        return 1
    fi
}

# Check for required files
check_files() {
    local record_json="$1"
    
    log_info "Checking for required files (README, code, data instructions)..."
    
    # Get file list
    local file_count=$(python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    files = data.get('files', [])
    print(len(files))
except:
    print(0)
" 2>/dev/null)
    
    if [[ "$file_count" -eq 0 ]]; then
        log_error "No files found in record"
        return 1
    fi
    
    log_info "Record has ${file_count} file(s)"
    
    # Check for README
    local has_readme=false
    if python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    files = data.get('files', [])
    for f in files:
        key = f.get('key', '').lower()
        if 'readme' in key:
            print('Found:', key)
            sys.exit(0)
    sys.exit(1)
except:
    sys.exit(1)
" 2>/dev/null; then
        log_success "README file found"
        has_readme=true
    else
        log_warning "README file not found (may be named differently)"
    fi
    
    # List all files for manual review
    log_info "Files in record:"
    python3 -c "
import json, sys
try:
    data = json.load(open('$record_json'))
    files = data.get('files', [])
    for f in files:
        key = f.get('key', '')
        size = f.get('size', 0)
        print(f'  - {key} ({size} bytes)')
except Exception as e:
    print(f'Error listing files: {e}')
" 2>/dev/null
    
    if [[ "$has_readme" == "true" ]]; then
        return 0
    else
        log_warning "Manual review recommended: verify README, code, and data instructions are present"
        return 1
    fi
}

# Verify DOI resolves
check_doi_resolves() {
    local doi="$1"
    local doi_url="https://doi.org/${doi}"
    
    log_info "Verifying DOI resolves: ${doi_url}"
    
    # Check if DOI resolves (follow redirects)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" -L "${doi_url}" 2>/dev/null || echo "000")
    
    if [[ "$http_code" == "200" ]] || [[ "$http_code" == "302" ]] || [[ "$http_code" == "301" ]]; then
        log_success "DOI resolves successfully (HTTP ${http_code})"
        return 0
    else
        log_error "DOI does not resolve (HTTP ${http_code})"
        return 1
    fi
}

# Main verification function
verify_zenodo_doi() {
    local doi="$1"
    
    echo ""
    echo "======================================================================="
    echo "Zenodo DOI Compliance Verification"
    echo "======================================================================="
    echo ""
    echo "DOI: ${doi}"
    echo "Zenodo Community: ${ES_COMMUNITY_URL}"
    echo ""
    
    local all_checks_passed=true
    
    # Step 1: Verify DOI format
    log_info "Step 1: Verifying DOI format..."
    if echo "$doi" | grep -qE "^10\.5281/zenodo\.[0-9]+$"; then
        log_success "DOI format is correct"
    else
        log_error "DOI format is incorrect (expected: 10.5281/zenodo.XXXXX)"
        all_checks_passed=false
        return 1
    fi
    
    # Step 2: Verify DOI resolves
    if ! check_doi_resolves "$doi"; then
        all_checks_passed=false
        return 1
    fi
    
    # Step 3: Get record ID and fetch metadata
    local record_id=$(get_zenodo_record_id "$doi")
    if [[ -z "$record_id" ]]; then
        log_error "Could not extract record ID from DOI"
        all_checks_passed=false
        return 1
    fi
    
    if ! fetch_zenodo_record "$record_id"; then
        all_checks_passed=false
        return 1
    fi
    
    # Step 4: Check ES Community membership
    if ! check_es_community "/tmp/zenodo_record.json"; then
        all_checks_passed=false
    fi
    
    # Step 5: Check required metadata
    if ! check_metadata "/tmp/zenodo_record.json"; then
        all_checks_passed=false
    fi
    
    # Step 6: Check license
    if ! check_license "/tmp/zenodo_record.json"; then
        all_checks_passed=false
    fi
    
    # Step 7: Check required files
    if ! check_files "/tmp/zenodo_record.json"; then
        all_checks_passed=false
    fi
    
    echo ""
    echo "======================================================================="
    if [[ "$all_checks_passed" == "true" ]]; then
        log_success "ALL CHECKS PASSED: DOI is compliant with ES Journals requirements"
        echo "======================================================================="
        return 0
    else
        log_error "SOME CHECKS FAILED: DOI may not be fully compliant"
        echo "======================================================================="
        echo ""
        log_warning "Review the errors above and verify manually:"
        log_warning "  - Visit: https://doi.org/${doi}"
        log_warning "  - Verify community membership: ${ES_COMMUNITY_URL}"
        log_warning "  - Check license allows unrestricted access"
        log_warning "  - Verify required files (README, code, data) are present"
        return 1
    fi
}

# Main script
main() {
    local doi=""
    
    # Get DOI from command line or extract from files
    if [[ $# -gt 0 ]]; then
        doi="$1"
    else
        log_info "Extracting DOI from README.md and titlepage..."
        
        # Try README.md
        if [[ -f "README.md" ]]; then
            doi=$(extract_doi "$(cat README.md)")
        fi
        
        # Try titlepage if not found
        if [[ -z "$doi" ]] && [[ -f "Subfiles/HAFiscal-titlepage.tex" ]]; then
            doi=$(extract_doi "$(cat Subfiles/HAFiscal-titlepage.tex)")
        fi
        
        if [[ -z "$doi" ]]; then
            log_error "Could not find DOI in README.md or titlepage"
            log_error "Usage: $0 [DOI]"
            log_error "   or: cd HAFiscal-QE && $0"
            exit 1
        fi
        
        log_info "Found DOI: ${doi}"
    fi
    
    # Verify DOI
    if verify_zenodo_doi "$doi"; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"

