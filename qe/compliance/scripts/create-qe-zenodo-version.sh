#!/bin/bash
# Create a new Zenodo version with HAFiscal-QE replication package
#
# This script:
# 1. Creates a zip file of the HAFiscal-QE repository (excluding .git, etc.)
# 2. Creates a new version of the existing Zenodo record
# 3. Uploads the zip file to the new version
# 4. Adds the ES community
# 5. Sets up metadata for QE submission
#
# Usage:
#   ./create-qe-zenodo-version.sh [ZENODO_ACCESS_TOKEN]
#
# Or set environment variable:
#   export ZENODO_ACCESS_TOKEN="your-token"
#   ./create-qe-zenodo-version.sh

set -euo pipefail

# Configuration
ZENODO_ACCESS_TOKEN="${ZENODO_ACCESS_TOKEN:-${1:-}}"
ORIGINAL_RECORD_ID="17861977"  # From DOI: 10.5281/zenodo.17861977
ES_COMMUNITY_ID="es-replication-repository"

# Paths (assuming script is run from HAFiscal-dev)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HAFISCAL_DEV="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
HAFISCAL_QE="${HAFISCAL_DEV}/HAFiscal-QE"
TEMP_DIR=$(mktemp -d)
ZIP_FILE="${TEMP_DIR}/HAFiscal-QE-replication.zip"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
if [[ -z "$ZENODO_ACCESS_TOKEN" ]]; then
    log_error "Zenodo access token required"
    echo ""
    echo "Get your token from: https://zenodo.org/account/settings/applications/"
    echo ""
    echo "Usage:"
    echo "  export ZENODO_ACCESS_TOKEN='your-token-here'"
    echo "  $0"
    echo ""
    echo "Or:"
    echo "  $0 your-token-here"
    exit 1
fi

if [[ ! -d "$HAFISCAL_QE" ]]; then
    log_error "HAFiscal-QE directory not found: $HAFISCAL_QE"
    echo "Please run this script from HAFiscal-dev directory"
    exit 1
fi

echo "======================================================================="
echo "Create New Zenodo Version with QE Replication Package"
echo "======================================================================="
echo ""
echo "Original Record ID: $ORIGINAL_RECORD_ID"
echo "HAFiscal-QE Path: $HAFISCAL_QE"
echo ""

# Step 1: Create zip file of HAFiscal-QE
log_info "Step 1: Creating zip file of HAFiscal-QE repository..."

cd "$HAFISCAL_QE"

# Exclude patterns for zip (similar to .gitignore)
EXCLUDE_PATTERNS=(
    ".git"
    ".gitignore"
    ".DS_Store"
    "__pycache__"
    "*.pyc"
    ".venv*"
    "venv*"
    "*.log"
    ".cursor*"
    "node_modules"
    ".idea"
    ".vscode"
)

# Build exclude arguments for zip
EXCLUDE_ARGS=()
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    EXCLUDE_ARGS+=("-x" "$pattern" "-x" "$pattern/*")
done

if command -v zip >/dev/null 2>&1; then
    log_info "Creating zip file (this may take a while)..."
    zip -r "$ZIP_FILE" . "${EXCLUDE_ARGS[@]}" -q || {
        log_error "Failed to create zip file"
        exit 1
    }
else
    log_error "zip command not found. Please install zip utility."
    exit 1
fi

ZIP_SIZE=$(du -h "$ZIP_FILE" | awk '{print $1}')
log_success "Created zip file: $ZIP_FILE ($ZIP_SIZE)"

# Step 2: Create new version via API
log_info "Step 2: Creating new version of Zenodo record..."

python3 <<PYTHON_SCRIPT
import requests
import os
import json

access_token = os.environ.get('ZENODO_ACCESS_TOKEN')
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

# Create new version
original_record_id = "$ORIGINAL_RECORD_ID"
create_version_url = f"https://zenodo.org/api/records/{original_record_id}/versions"
response = requests.post(create_version_url, headers=headers, json={})

if response.status_code == 201:
    new_record = response.json()
    new_record_id = str(new_record["id"])
    print(f"✅ Created new version: {new_record_id}")
    
    # Save new record ID to file for next steps
    with open("${TEMP_DIR}/new_record_id.txt", "w") as f:
        f.write(new_record_id)
else:
    print(f"❌ Failed to create new version: {response.status_code}")
    print(response.text)
    exit(1)
PYTHON_SCRIPT

NEW_RECORD_ID=$(cat "${TEMP_DIR}/new_record_id.txt")
log_success "New version created: $NEW_RECORD_ID"

# Step 3: Upload zip file
log_info "Step 3: Uploading zip file to new version..."

python3 <<PYTHON_SCRIPT
import requests
import os
import json

access_token = os.environ.get('ZENODO_ACCESS_TOKEN')
new_record_id = "$NEW_RECORD_ID"
zip_file = "$ZIP_FILE"
zip_filename = "HAFiscal-QE-replication.zip"

# First, get the bucket URL from the deposition
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

# Fetch deposition to get bucket URL
deposition_url = f"https://zenodo.org/api/deposit/depositions/{new_record_id}"
response = requests.get(deposition_url, headers=headers)
if response.status_code != 200:
    print(f"❌ Failed to fetch deposition: {response.status_code}")
    print(response.text)
    exit(1)

deposition = response.json()
bucket_url = deposition.get('links', {}).get('bucket', '')

if not bucket_url:
    print("❌ No bucket URL found in deposition")
    exit(1)

# Upload file directly to bucket
print(f"Uploading {zip_filename} ({os.path.getsize(zip_file)} bytes)...")
upload_headers = {'Authorization': f'Bearer {access_token}'}

with open(zip_file, 'rb') as f:
    file_url = f"{bucket_url}/{zip_filename}"
    upload_response = requests.put(file_url, headers=upload_headers, data=f)

if upload_response.status_code in [200, 201]:
    print(f"✅ Successfully uploaded {zip_filename}")
    
    # Verify file was uploaded
    files_response = requests.get(deposition_url, headers=headers)
    if files_response.status_code == 200:
        files = files_response.json().get('files', [])
        print(f"✅ File verified: {len(files)} file(s) in deposition")
else:
    print(f"❌ Upload failed: {upload_response.status_code}")
    print(upload_response.text)
    exit(1)
PYTHON_SCRIPT

# Step 4: Add ES community and update metadata
log_info "Step 4: Adding ES community and updating metadata..."

python3 <<PYTHON_SCRIPT
import requests
import os

access_token = os.environ.get('ZENODO_ACCESS_TOKEN')
new_record_id = "$NEW_RECORD_ID"
es_community = "$ES_COMMUNITY_ID"

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

# Fetch current draft
url = f"https://zenodo.org/api/deposit/depositions/{new_record_id}"
response = requests.get(url, headers=headers)
deposition = response.json()

metadata = deposition.get('metadata', {})

# Add ES community
communities = metadata.get('communities', [])
community_ids = [c.get('identifier', '') for c in communities]

if es_community not in community_ids:
    communities.append({'identifier': es_community})
    metadata['communities'] = communities
    print(f"✅ Added community: {es_community}")
else:
    print(f"ℹ️  Community already present: {es_community}")

# Ensure resource_type is set
if 'resource_type' not in metadata:
    metadata['resource_type'] = 'dataset'
    print("✅ Set resource_type: dataset")

# Update metadata
payload = {'metadata': metadata}
update_response = requests.put(url, headers=headers, json=payload)

if update_response.status_code == 200:
    print("✅ Successfully updated metadata")
else:
    print(f"❌ Failed to update metadata: {update_response.status_code}")
    print(update_response.text)
    exit(1)
PYTHON_SCRIPT

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "======================================================================="
log_success "New Zenodo version created successfully!"
echo "======================================================================="
echo ""
echo "New version ID: $NEW_RECORD_ID"
echo "Draft URL: https://zenodo.org/deposit/$NEW_RECORD_ID"
echo ""
echo "Next steps:"
echo "  1. Go to the draft URL above"
echo "  2. Review the draft (files, metadata, community)"
echo "  3. Click 'Publish' when ready"
echo ""
echo "The DOI will remain: 10.5281/zenodo.$ORIGINAL_RECORD_ID"
echo "(version number will increment)"

