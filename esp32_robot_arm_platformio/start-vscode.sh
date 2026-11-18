#!/usr/bin/env bash
set -euo pipefail
robot_workspace=""
robot_project="$(cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -f "$robot_workspace" ]; then
  robot_workspace="$robot_project"
fi
exec env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH \
  -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH \
  /usr/bin/code --reuse-window "$robot_workspace"
