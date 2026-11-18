#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'MG90S на GPIO17: только середина диапазона (1500 мкс).\nВведите пароль Ubuntu для доступа к USB.\n\n'
sudo /usr/bin/python3 "$script_root/center_gpio17.py" 2>&1 | tee "$script_root/../gpio17_center.log"
center_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$center_status"
read -r
exit "$center_status"
