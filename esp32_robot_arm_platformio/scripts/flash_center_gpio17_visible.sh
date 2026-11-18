#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Временная прошивка: только MG90S на D17, середина 1500 мкс.\nПеред загрузкой сохраняется резервная копия платы.\nВведите пароль Ubuntu ниже.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" "$script_root/flash_center_gpio17.py" 2>&1 | tee "$script_root/../gpio17_center_flash.log"
flash_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$flash_status"
read -r
exit "$flash_status"
