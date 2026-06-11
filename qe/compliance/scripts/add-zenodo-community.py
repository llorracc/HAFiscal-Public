#!/usr/bin/env python3
"""
Add Zenodo record to Econometric Society Journals' Community via API

This script uses the Zenodo REST API to add an existing record to the
es-replication-repository community.

Usage:
    python3 add-zenodo-community.py [RECORD_ID] [ACCESS_TOKEN]

    Or set environment variables:
    export ZENODO_ACCESS_TOKEN="your-token-here"
    python3 add-zenodo-community.py 17861977

Requirements:
    - Zenodo Personal Access Token (get from https://zenodo.org/account/settings/applications/)
    - Record ID (extracted from DOI: 10.5281/zenodo.17861977 -> 17861977)
    - Record must be owned by the account associated with the access token
"""

import sys
import os
import json
import requests
from typing import Optional

# Configuration
ZENODO_API_BASE = "https://zenodo.org/api"
ES_COMMUNITY_ID = "es-replication-repository"
RECORD_ID = "17861977"  # From DOI: 10.5281/zenodo.17861977


def get_access_token() -> Optional[str]:
    """Get access token from environment or command line."""
    token = os.environ.get("ZENODO_ACCESS_TOKEN")
    if not token and len(sys.argv) > 2:
        token = sys.argv[2]
    return token


def get_record_id() -> str:
    """Get record ID from command line or use default."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return RECORD_ID


def fetch_record(record_id: str, access_token: str) -> dict:
    """Fetch record metadata from Zenodo API."""
    url = f"{ZENODO_API_BASE}/records/{record_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    print(f"Fetching record {record_id}...")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_deposition(deposition_id: str, access_token: str) -> dict:
    """Fetch draft deposition from Zenodo API."""
    url = f"{ZENODO_API_BASE}/deposit/depositions/{deposition_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_record_communities(record_id: str, access_token: str, communities: list) -> dict:
    """Update record communities via Zenodo API."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Get current record (published or draft)
    record = fetch_record(record_id, access_token)
    
    # Check current communities
    metadata = record.get("metadata", {})
    current_communities = metadata.get("communities", [])
    community_identifiers = [c.get("identifier", "") for c in current_communities]
    
    # Check if community already exists
    if ES_COMMUNITY_ID in community_identifiers:
        print(f"✅ Record is already in community '{ES_COMMUNITY_ID}'")
        return record
    
    print(f"Updating record {record_id}...")
    print(f"Adding communities: {communities}")
    
    # For published records, we need to create a new version
    if record.get("state") == "done":
        print("⚠️  Record is published. Creating new version...")
        # Create new version
        create_version_url = f"{ZENODO_API_BASE}/records/{record_id}/versions"
        response = requests.post(create_version_url, headers=headers, json={})
        if response.status_code == 201:
            new_record = response.json()
            new_record_id = str(new_record["id"])
            print(f"✅ Created new version: {new_record_id}")
            
            # Fetch the new draft deposition
            deposition = fetch_deposition(new_record_id, access_token)
            deposition_metadata = deposition.get("metadata", {})
            
            # Get current communities from deposition (may be empty)
            deposition_communities = deposition_metadata.get("communities", [])
            deposition_community_ids = [c.get("identifier", "") for c in deposition_communities]
            
            # Add new communities
            for community_id in communities:
                if community_id not in deposition_community_ids:
                    deposition_communities.append({"identifier": community_id})
            
            # Update only the communities field
            deposition_metadata["communities"] = deposition_communities
            payload = {"metadata": deposition_metadata}
            
            # Update the deposition
            url = f"{ZENODO_API_BASE}/deposit/depositions/{new_record_id}"
            response = requests.put(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        else:
            print(f"❌ Failed to create new version: {response.status_code}")
            print(response.text)
            sys.exit(1)
    else:
        # Draft record - update directly
        # Fetch the draft deposition
        deposition = fetch_deposition(record_id, access_token)
        deposition_metadata = deposition.get("metadata", {})
        
        # Get current communities
        deposition_communities = deposition_metadata.get("communities", [])
        deposition_community_ids = [c.get("identifier", "") for c in deposition_communities]
        
        # Add new communities
        for community_id in communities:
            if community_id not in deposition_community_ids:
                deposition_communities.append({"identifier": community_id})
        
        # Update only the communities field
        deposition_metadata["communities"] = deposition_communities
        payload = {"metadata": deposition_metadata}
        
        url = f"{ZENODO_API_BASE}/deposit/depositions/{record_id}"
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def main():
    """Main function."""
    print("=" * 70)
    print("Add Zenodo Record to Econometric Society Journals' Community")
    print("=" * 70)
    print()
    
    # Get credentials
    record_id = get_record_id()
    access_token = get_access_token()
    
    if not access_token:
        print("❌ ERROR: Zenodo access token required")
        print()
        print("Get your token from: https://zenodo.org/account/settings/applications/")
        print()
        print("Usage:")
        print("  export ZENODO_ACCESS_TOKEN='your-token-here'")
        print(f"  python3 {sys.argv[0]} {record_id}")
        print()
        print("Or provide token as argument:")
        print(f"  python3 {sys.argv[0]} {record_id} your-token-here")
        sys.exit(1)
    
    print(f"Record ID: {record_id}")
    print(f"Community: {ES_COMMUNITY_ID}")
    print()
    
    try:
        # Fetch current record
        record = fetch_record(record_id, access_token)
        
        # Check current communities
        metadata = record.get("metadata", {})
        current_communities = metadata.get("communities", [])
        community_identifiers = [c.get("identifier", "") for c in current_communities]
        
        print(f"Current communities: {community_identifiers}")
        print()
        
        if ES_COMMUNITY_ID in community_identifiers:
            print(f"✅ Record is already in community '{ES_COMMUNITY_ID}'")
            print("No changes needed.")
            return 0
        
        # Update record
        updated_record = update_record_communities(
            record_id, 
            access_token, 
            [ES_COMMUNITY_ID]
        )
        
        print()
        print("=" * 70)
        print("✅ SUCCESS: Record updated")
        print("=" * 70)
        print()
        print(f"Record URL: https://doi.org/10.5281/zenodo.{record_id}")
        print(f"Community: {ES_COMMUNITY_ID}")
        print()
        print("Note: If record was published, a new version was created.")
        print("      The DOI remains the same (version number increments).")
        print()
        
        return 0
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if e.response.status_code == 403:
            print("   This usually means:")
            print("   - Invalid access token")
            print("   - You don't own this record")
            print("   - Record is published and you need to create a new version")
        elif e.response.status_code == 404:
            print("   Record not found. Check the record ID.")
        print()
        print(f"Response: {e.response.text}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

