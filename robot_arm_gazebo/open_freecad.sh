#!/usr/bin/env bash
set -euo pipefail
robot_root="$(cd -- "$(dirname -- "$0")" && pwd)"
if [ "$#" -eq 0 ]; then
  set -- "$robot_root/freecad/RobotArm_Assembly.FCStd"
fi
exec flock -n "$robot_root/../../tools/freecad/freecad-gui.lock" \
  "$robot_root/../../tools/freecad/launch_freecad.sh" "$@"
