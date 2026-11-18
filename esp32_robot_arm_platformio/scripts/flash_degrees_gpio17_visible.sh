#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Разовый тест MG90S D17 В ГРАДУСАХ: 0° → 180° → 90°.\nВведите пароль Ubuntu для доступа к USB.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" -u "$script_root/flash_test_gpio17.py" --degrees 2>&1 | tee "$script_root/../gpio17_degree_test.log"
degree_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$degree_status"
read -r
exit "$degree_status"
