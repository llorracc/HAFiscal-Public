#!/usr/bin/env python3
"""
Populate Zenodo metadata from HAFiscal-QE repository sources

This script extracts metadata from:
- README.md
- Subfiles/HAFiscal-titlepage.tex
- codemeta.json (if exists)
- CITATION.cff (if exists)

And populates Zenodo record fields accordingly.
"""

import sys
import os
import re
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
ZENODO_API_BASE = "https://zenodo.org/api"
DRAFT_ID = "18065765"  # Current draft ID


def get_access_token() -> str:
    """Get access token from environment."""
    token = os.environ.get("ZENODO_ACCESS_TOKEN")
    if not token:
        print("❌ ERROR: ZENODO_ACCESS_TOKEN environment variable not set")
        sys.exit(1)
    return token


def read_file_safe(filepath: Path) -> Optional[str]:
    """Safely read a file, return None if not found."""
    try:
        return filepath.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None


def extract_title_from_titlepage(titlepage_content: str) -> str:
    """Extract title from titlepage.tex."""
    # Look for \title{...}
    match = re.search(r'\\title\{([^}]+)\}', titlepage_content, re.DOTALL)
    if match:
        title = match.group(1)
        # Clean up LaTeX commands and newlines
        title = re.sub(r'\\\\', ' ', title)
        title = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title
    return ""


def extract_abstract_from_titlepage(titlepage_content: str) -> str:
    """Extract abstract from titlepage.tex."""
    # Look for abstract in verbatimwrite or abstract environment
    # First try verbatimwrite
    match = re.search(r'\\begin\{verbatimwrite\}\{HAFiscal-Abstract\.txt\}\s*(.*?)\\end\{verbatimwrite\}', 
                      titlepage_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Try abstract environment
    match = re.search(r'\\begin\{abstract\}\s*(.*?)\\end\{abstract\}', 
                      titlepage_content, re.DOTALL)
    if match:
        abstract = match.group(1)
        # Remove \input command
        abstract = re.sub(r'\\input\{[^}]+\}', '', abstract)
        return abstract.strip()
    
    return ""


def extract_authors_from_titlepage(titlepage_content: str) -> List[Dict]:
    """Extract authors with affiliations from titlepage.tex."""
    authors = []
    
    # Extract from \author command
    author_match = re.search(r'\\author\{([^}]+)\}', titlepage_content)
    if author_match:
        author_line = author_match.group(1)
        # Split by \and
        author_names = [a.strip() for a in author_line.split(r'\and')]
        
        # Extract from authorsinfo environment
        authorsinfo_match = re.search(r'\\begin\{authorsinfo\}(.*?)\\end\{authorsinfo\}', 
                                       titlepage_content, re.DOTALL)
        if authorsinfo_match:
            authorsinfo = authorsinfo_match.group(1)
            
            for i, name in enumerate(author_names):
                # Clean up LaTeX commands
                clean_name = re.sub(r'\\authNum', '', name)
                # Handle special LaTeX characters (do this before other substitutions)
                # Handle {\aa} pattern
                clean_name = re.sub(r'\{?\\aa\}?', 'å', clean_name)
                clean_name = re.sub(r'\\aa', 'å', clean_name)
                clean_name = re.sub(r'\\AA', 'Å', clean_name)
                # Remove LaTeX commands but keep content
                clean_name = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', clean_name)
                # Remove remaining braces
                clean_name = re.sub(r'\{([^}]+)\}', r'\1', clean_name)
                clean_name = clean_name.strip()
                
                # Extract affiliation from authorsinfo
                affiliation = None
                email = None
                
                # Look for this author's info in authorsinfo
                name_parts = clean_name.split()
                if len(name_parts) > 0:
                    last_name = name_parts[-1]
                    # Find matching entry - look for author's last name followed by colon
                    # Pattern: \name{...Lastname: Affiliation, email}
                    pattern = rf'\\name\{{[^}}]*{re.escape(last_name)}:\s*([^,}}]+)'
                    match = re.search(pattern, authorsinfo)
                    if match:
                        affiliation = match.group(1).strip()
                        # Clean up LaTeX href commands (keep the link text)
                        affiliation = re.sub(r'\\href\{[^}]+\}\{([^}]+)\}', r'\1', affiliation)
                        affiliation = re.sub(r'\\texttt\{([^}]+)\}', r'\1', affiliation)
                        # Remove any remaining LaTeX commands
                        affiliation = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', affiliation)
                        affiliation = re.sub(r'\{([^}]+)\}', r'\1', affiliation)
                        # Handle Carroll's special case with "and NBER"
                        if last_name == "Carroll" and "and" in affiliation:
                            # Keep everything before "and" as primary affiliation
                            affiliation = affiliation.split("and")[0].strip()
                        affiliation = affiliation.strip()
                        
                        # Extract email separately
                        email_match = re.search(r'mailto:([^\s}]+)', match.group(0))
                        if email_match:
                            email = email_match.group(1)
                
                author_dict = {
                    "name": clean_name,
                    "affiliation": affiliation or None,
                }
                
                # Add ORCID if available (Carroll has one)
                if "Carroll" in clean_name:
                    author_dict["orcid"] = "0000-0003-3732-9312"
                
                authors.append(author_dict)
    
    return authors


def extract_keywords_from_titlepage(titlepage_content: str) -> List[str]:
    """Extract keywords from titlepage.tex."""
    keywords = []
    
    # Extract from \keywords command
    match = re.search(r'\\keywords\{([^}]+)\}', titlepage_content)
    if match:
        keywords_str = match.group(1)
        # Split by comma
        keywords = [k.strip() for k in keywords_str.split(',')]
    
    return keywords


def extract_jel_codes_from_titlepage(titlepage_content: str) -> List[str]:
    """Extract JEL codes from titlepage.tex."""
    match = re.search(r'\\jelclass\{([^}]+)\}', titlepage_content)
    if match:
        jel_str = match.group(1)
        # Extract codes (format: E21, E62, H31)
        codes = re.findall(r'[A-Z]\d+', jel_str)
        return codes
    return []


def build_description(titlepage_content: str, readme_content: str) -> str:
    """Build comprehensive description for Zenodo."""
    abstract = extract_abstract_from_titlepage(titlepage_content)
    title = extract_title_from_titlepage(titlepage_content)
    
    description = f"""<h1>{title}</h1>

<h2>Abstract</h2>
<p>{abstract}</p>

<h2>Replication Package</h2>
<p>This repository contains the complete replication package for "{title}", submitted to <strong>Quantitative Economics</strong>.</p>

<h2>What's Included</h2>
<ul>
<li>LaTeX source for the paper (HAFiscal.tex)</li>
<li>All code for computational results (Python, HARK framework)</li>
<li>Data files and download scripts</li>
<li>Complete reproduction workflow</li>
<li>Computational environment specifications</li>
</ul>

<h2>Reproduction</h2>
<p>To reproduce all results, see the README.md file in the repository for detailed instructions.</p>
<p><strong>Estimated time to reproduce</strong>: 4-5 days (full replication), ~1 hour (minimal verification)</p>

<h2>Citation</h2>
<p>If you use this replication package, please cite it using the DOI: 10.5281/zenodo.17861977</p>

<h2>License</h2>
<p>Apache License 2.0 - See LICENSE file in repository</p>
"""
    
    return description


def get_metadata_from_sources(hafiscal_qe_path: Path) -> Dict:
    """Extract all metadata from HAFiscal-QE sources."""
    metadata = {}
    
    # Read source files
    titlepage_path = hafiscal_qe_path / "Subfiles" / "HAFiscal-titlepage.tex"
    readme_path = hafiscal_qe_path / "README.md"
    codemeta_path = hafiscal_qe_path / "codemeta.json"
    citation_path = hafiscal_qe_path / "CITATION.cff"
    
    titlepage_content = read_file_safe(titlepage_path)
    readme_content = read_file_safe(readme_path)
    codemeta_content = read_file_safe(codemeta_path)
    citation_content = read_file_safe(citation_path)
    
    if not titlepage_content:
        print("⚠️  Warning: Could not read titlepage.tex")
        return metadata
    
    # Extract metadata
    metadata["title"] = extract_title_from_titlepage(titlepage_content)
    metadata["creators"] = extract_authors_from_titlepage(titlepage_content)
    metadata["keywords"] = extract_keywords_from_titlepage(titlepage_content)
    metadata["description"] = build_description(titlepage_content, readme_content or "")
    
    # Add JEL codes to keywords
    jel_codes = extract_jel_codes_from_titlepage(titlepage_content)
    if jel_codes:
        metadata["keywords"].extend([f"JEL: {code}" for code in jel_codes])
    
    # Add related identifiers
    metadata["related_identifiers"] = [
        {
            "identifier": "https://github.com/llorracc/HAFiscal-QE",
            "relation": "isSupplementTo",
            "resource_type": "software",
            "scheme": "url"
        },
        {
            "identifier": "https://github.com/llorracc/HAFiscal-QE",
            "relation": "isIdenticalTo",
            "resource_type": "software",
            "scheme": "url"
        }
    ]
    
    # Add journal information
    metadata["journal"] = {
        "title": "Quantitative Economics",
        "issue": None,
        "pages": None,
        "volume": None,
        "year": 2025
    }
    
    # Set resource type
    metadata["resource_type"] = "dataset"  # For replication packages
    
    # Add version from README if available
    if readme_content:
        version_match = re.search(r'\*\*Repository Version\*\*:\s*([^\s]+)', readme_content)
        if version_match:
            metadata["version"] = version_match.group(1)
    
    # Add publication date (use current date for now)
    from datetime import date
    metadata["publication_date"] = date.today().isoformat()
    
    return metadata


def update_zenodo_metadata(draft_id: str, access_token: str, metadata: Dict):
    """Update Zenodo draft with new metadata."""
    url = f"{ZENODO_API_BASE}/deposit/depositions/{draft_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Fetch current draft
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch draft: {response.status_code}")
        print(response.text)
        return False
    
    current_draft = response.json()
    current_metadata = current_draft.get("metadata", {})
    
    # Merge new metadata with existing (preserve communities, etc.)
    updated_metadata = current_metadata.copy()
    
    # Update fields
    if "title" in metadata:
        updated_metadata["title"] = metadata["title"]
    
    if "creators" in metadata:
        updated_metadata["creators"] = metadata["creators"]
    
    if "keywords" in metadata:
        # Merge keywords, avoiding duplicates
        existing_keywords = set(updated_metadata.get("keywords", []))
        new_keywords = set(metadata["keywords"])
        updated_metadata["keywords"] = sorted(list(existing_keywords | new_keywords))
    
    if "description" in metadata:
        updated_metadata["description"] = metadata["description"]
    
    if "related_identifiers" in metadata:
        # Merge related identifiers
        existing_related = {r.get("identifier"): r for r in updated_metadata.get("related_identifiers", [])}
        for rel in metadata["related_identifiers"]:
            existing_related[rel["identifier"]] = rel
        updated_metadata["related_identifiers"] = list(existing_related.values())
    
    # Don't update publication_date if it causes validation errors
    # Only update if it's not already set or if we're sure it's valid
    if "publication_date" in metadata:
        # Only update if current metadata doesn't have a date or it's invalid
        if "publication_date" not in updated_metadata or not updated_metadata.get("publication_date"):
            updated_metadata["publication_date"] = metadata["publication_date"]
    
    # Ensure resource_type is set (as string for deposition API)
    updated_metadata["resource_type"] = "dataset"
    
    # Update draft
    payload = {"metadata": updated_metadata}
    response = requests.put(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print("✅ Successfully updated Zenodo metadata")
        return True
    else:
        print(f"❌ Failed to update metadata: {response.status_code}")
        print(response.text)
        return False


def main():
    """Main function."""
    print("=" * 70)
    print("Populate Zenodo Metadata from HAFiscal-QE Sources")
    print("=" * 70)
    print()
    
    # Get access token
    access_token = get_access_token()
    
    # Find HAFiscal-QE directory
    script_dir = Path(__file__).parent
    hafiscal_dev = script_dir.parent.parent.parent.parent
    hafiscal_qe = hafiscal_dev / "HAFiscal-QE"
    
    if not hafiscal_qe.exists():
        print(f"❌ ERROR: HAFiscal-QE directory not found: {hafiscal_qe}")
        sys.exit(1)
    
    print(f"HAFiscal-QE path: {hafiscal_qe}")
    print()
    
    # Extract metadata
    print("Extracting metadata from sources...")
    metadata = get_metadata_from_sources(hafiscal_qe)
    
    print(f"  Title: {metadata.get('title', 'N/A')}")
    print(f"  Authors: {len(metadata.get('creators', []))}")
    print(f"  Keywords: {len(metadata.get('keywords', []))}")
    print()
    
    # Update Zenodo - use DRAFT_ID constant
    draft_id = DRAFT_ID
    print(f"Updating Zenodo draft {draft_id}...")
    success = update_zenodo_metadata(draft_id, access_token, metadata)
    
    if success:
        print()
        print("=" * 70)
        print("✅ Metadata population complete!")
        print("=" * 70)
        print()
        try:
            draft_id = DRAFT_ID
        except NameError:
            draft_id = get_record_id()
        print(f"Draft URL: https://zenodo.org/deposit/{draft_id}")
        print("Review the draft and publish when ready.")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())

