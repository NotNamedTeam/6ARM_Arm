#!/usr/bin/env bash
set -uo pipefail
variant_root="$(cd -- "$(dirname -- "$0")" && pwd)"
"$variant_root/sim_control.sh" demo 2>&1 | tee "$variant_root/export/motion_demo.log"
result=${PIPESTATUS[0]}
printf '\nПроверка MG996R закончена, код: %s. Enter - закрыть окно.\n' "$result"
read -r
exit "$result"
