#!/usr/bin/env bash
# Phase 1 - sync the OpenAlex S3 snapshot to local disk (~712 GB compressed).
#
# The bucket is public, no AWS account or credentials needed. `aws s3 sync` is
# resumable: re-run it to pick up where it left off or to pull a newer release.
#
#   ./download.sh                 # full snapshot
#   ./download.sh works authors   # only these entity directories
#
# Env:
#   OPENALEX_SNAPSHOT  destination dir (default /media/simone/ssd2/openalex/snapshot)
#   AWS                path to the aws CLI (default: aws on PATH, else ~/.local/bin/aws)
set -euo pipefail

DEST="${OPENALEX_SNAPSHOT:-/media/simone/ssd2/openalex/snapshot}"
AWS="${AWS:-$(command -v aws || echo "$HOME/.local/bin/aws")}"

if [[ ! -x "$AWS" ]] && ! command -v "$AWS" >/dev/null 2>&1; then
    echo "aws CLI not found. Install with: pip install --user awscli" >&2
    exit 1
fi
mkdir -p "$DEST"

if [[ $# -gt 0 ]]; then
    # selected entity sub-directories, plus the small top-level metadata files
    for entity in "$@"; do
        echo ">>> syncing data/$entity/"
        "$AWS" s3 sync "s3://openalex/data/$entity/" "$DEST/data/$entity/" \
            --no-sign-request
    done
    "$AWS" s3 cp "s3://openalex/RELEASE_NOTES.txt" "$DEST/" --no-sign-request || true
    "$AWS" s3 cp "s3://openalex/LICENSE.txt" "$DEST/" --no-sign-request || true
else
    # Only data/ -- the bucket also holds a ~290 GB legacy-data/ tree (the
    # retired pre-2024 snapshot format) that none of this tooling reads.
    echo ">>> syncing the full snapshot (data/ only) to $DEST"
    "$AWS" s3 sync "s3://openalex/data" "$DEST/data" --no-sign-request
    "$AWS" s3 cp "s3://openalex/RELEASE_NOTES.txt" "$DEST/" --no-sign-request || true
    "$AWS" s3 cp "s3://openalex/LICENSE.txt" "$DEST/" --no-sign-request || true
fi

echo ">>> done. Snapshot release:"
grep -m1 '^RELEASE' "$DEST/RELEASE_NOTES.txt" 2>/dev/null || true
du -sh "$DEST" 2>/dev/null || true
