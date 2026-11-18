#!/usr/bin/env bash
set -euo pipefail
variant_root="$(cd -- "$(dirname -- "$0")" && pwd)"
exec "$variant_root/../../open_freecad.sh" "$variant_root/freecad/MG996R_Layout_Review.FCStd"
