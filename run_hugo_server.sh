#!/bin/bash
#
# Local live-preview server for the Hugo site.
#
#   ./run_hugo_server.sh              # preview on http://localhost:1313 (shows drafts + future posts)
#   ./run_hugo_server.sh 8080         # custom port
#   ./run_hugo_server.sh 1313 lan     # also expose on the LAN (0.0.0.0)
#   ./run_hugo_server.sh --prod       # production preview: exactly what the hosted site shows
#                                     #   (no drafts, no future-dated posts) - matches ./build.sh
#
# Serves the site from memory with live reload. It does NOT touch docs/ -
# that folder is only produced by ./build.sh for GitHub Pages. Use this for
# development, use build.sh to publish.

set -euo pipefail

PROD=0
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --prod) PROD=1 ;;
    *)      POSITIONAL+=("$arg") ;;
  esac
done

PORT="${POSITIONAL[0]:-1313}"
BIND_MODE="${POSITIONAL[1]:-local}"     # "local" (127.0.0.1) or "lan" (0.0.0.0)

if ! command -v hugo >/dev/null 2>&1; then
  echo "hugo not found in PATH. Install Hugo (extended) first." >&2
  exit 1
fi

if [ "$BIND_MODE" = "lan" ]; then
  BIND_ADDR="0.0.0.0"
else
  BIND_ADDR="127.0.0.1"
fi

# Base flags, always on.
HUGO_ARGS=(server --disableFastRender --navigateToChanged --port "$PORT" --bind "$BIND_ADDR")

if [ "$PROD" -eq 1 ]; then
  # Match the hosted site exactly. hugo server otherwise still serves a stale
  # public/ built with drafts, so clear it first, then force drafts/future off.
  rm -rf public
  HUGO_ARGS+=(--buildDrafts=false --buildFuture=false --buildExpired=false --environment production)
  MODE="production (no drafts, no future posts - matches the hosted site)"
else
  # Preview: include work-in-progress that the production build omits.
  HUGO_ARGS+=(--buildDrafts --buildFuture)
  MODE="preview (drafts + future posts included)"
fi

echo "Starting Hugo server on http://${BIND_ADDR}:${PORT}  [${MODE}]  (Ctrl+C to stop)"

exec hugo "${HUGO_ARGS[@]}"
