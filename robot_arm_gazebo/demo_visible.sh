#!/usr/bin/env bash
set -uo pipefail
robot_root="$(cd -- "$(dirname -- "$0")" && pwd)"
"$robot_root/sim_control.sh" demo 2>&1 | tee "$robot_root/export/motion_demo.log"
demo_status=${PIPESTATUS[0]}
printf '\nПроверка завершена, код результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$demo_status"
read -r
exit "$demo_status"
