#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Разовый тест MG90S D17: 1000 → 2000 → 1500 мкс. Только D17.\nВведите пароль Ubuntu для доступа к USB.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" -u "$script_root/flash_test_gpio17.py" 2>&1 | tee "$script_root/../gpio17_endpoint_test.log"
test_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$test_status"
read -r
exit "$test_status"
