#!/usr/bin/env bash
set -euo pipefail

# -------- config --------
TAG_PREFIX="BASELINED_"
REMOTE="origin"
# ------------------------

usage() {
  echo "Usage: $0 <version> [--push]"
  echo "Example:"
  echo "  $0 0.2.0"
  echo "  $0 0.2.0 --push"
  exit 1
}

# -------- args --------
[[ $# -lt 1 || $# -gt 2 ]] && usage

VERSION="$1"
TAG="${TAG_PREFIX}${VERSION}"
PUSH=false

if [[ "${2:-}" == "--push" ]]; then
  PUSH=true
elif [[ $# -eq 2 ]]; then
  usage
fi

echo "🏷️  Baseline tag: $TAG"
echo "📌 Mode: $( $PUSH && echo 'create + push' || echo 'create only' )"
echo

# ---------- PHASE 1: validation ----------
echo "🔍 Phase 1 — validation"

git fetch --tags

git submodule foreach --recursive '
  git fetch --tags
'

echo "✔ Validation complete"
echo

# ---------- PHASE 2: create tags if missing ----------
echo "🏗️  Phase 2 — ensure tag exists everywhere"

# Root repo
echo "▶ Root repository"
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "  ℹ Tag already exists"
else
  git tag "$TAG"
  echo "  ✔ Created tag at $(git rev-parse --short HEAD)"
fi

echo

# Submodules
git submodule foreach --recursive '
  echo "▶ $name"
  if git rev-parse '"$TAG"' >/dev/null 2>&1; then
    echo "  ℹ Tag already exists"
  else
    git tag '"$TAG"'
    echo "  ✔ Created tag at $(git rev-parse --short HEAD)"
  fi
'

echo

# ---------- PHASE 3: push (optional) ----------
if $PUSH; then
  echo "🚀 Phase 3 — pushing tags to $REMOTE"

  echo "▶ Root repository"
  git push "$REMOTE" "$TAG"

  echo

  git submodule foreach --recursive '
    echo "▶ $name"
    git push '"$REMOTE"' '"$TAG"'
  '

  echo
  echo "✅ Tags pushed successfully"
else
  echo "ℹ Push skipped (use --push to push tags)"
fi

echo
echo "🎉 Baseline '$TAG' processed successfully."
