#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Только D17: прямые импульсы 900 → 2100 → 1500 мкс.\nРазовый тест, затем удержание центра. Введите пароль Ubuntu.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" -u "$script_root/flash_test_gpio17.py" --pulses 900 2100 1500 --pause 1.5 2>&1 | tee "$script_root/../gpio17_direct_pulse_test.log"
pulse_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$pulse_status"
read -r
exit "$pulse_status"
