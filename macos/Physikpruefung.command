#!/bin/bash
# Doppelklick im Finder: startet die App im Hintergrund und öffnet den Browser.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
exec /bin/bash "$DIR/pruefung" --background
