#!/bin/bash
# Fix Zenodo version by discarding incorrect draft and creating proper version

set -euo pipefail

if [[ -z "${ZENODO_ACCESS_TOKEN:-}" ]]; then
    echo "ERROR: ZENODO_ACCESS_TOKEN is not set"
    echo "Set it in your environment before running this script."
    exit 1
fi
ORIGINAL_ID="17861977"
INCORRECT_DRAFT="18065765"

echo "Step 1: Discarding incorrect draft ${INCORRECT_DRAFT}..."
echo "   (This must be done manually in web interface)"
echo ""
echo "   Go to: https://zenodo.org/deposit/${INCORRECT_DRAFT}"
echo "   Click 'Discard version' button (bottom right, red button)"
echo ""
read -r -p "Press Enter after you have discarded the draft..."

echo ""
echo "Step 2: Creating proper version of record ${ORIGINAL_ID}..."

python3 <<PYTHON
import requests
import os

access_token = os.environ.get('ZENODO_ACCESS_TOKEN')
original_id = "${ORIGINAL_ID}"

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

# Create new version properly
create_version_url = f'https://zenodo.org/api/records/{original_id}/versions'
response = requests.post(create_version_url, headers=headers, json={})

if response.status_code == 201:
    new_version = response.json()
    new_version_id = str(new_version['id'])
    print(f'Created proper version: {new_version_id}')
    print(f'   Draft URL: https://zenodo.org/deposit/{new_version_id}')
    print()
    print('This version should:')
    print('  - Use the same DOI as parent (10.5281/zenodo.17861977)')
    print('  - Be properly linked as a version')
    print('  - Not have DOI reservation issues')
    print()
    print('Next steps:')
    print('  1. Upload the zip file')
    print('  2. Add ES community')
    print('  3. Populate metadata')
    print('  4. Set resource type to Dataset')
    print('  5. Publish')
else:
    print(f'Failed: {response.status_code}')
    print(response.text)
PYTHON

