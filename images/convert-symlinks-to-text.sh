#!/usr/bin/env bash
# Convert .relpath symlinks to text files containing paths

set -euo pipefail

count=0
for symlink in *.relpath; do
    [[ -L "$symlink" ]] || continue
    target=$(readlink "$symlink")
    rm "$symlink"
    echo "$target" > "$symlink"
    echo "✓ $symlink → TEXT FILE: '$target'"
    ((count++))
done

echo ""
echo "Converted $count symlinks to text files"
