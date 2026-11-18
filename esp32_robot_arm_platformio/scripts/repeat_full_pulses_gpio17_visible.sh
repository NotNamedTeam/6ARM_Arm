#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Повтор только D17 БЕЗ перепрошивки: 500 → 2500 → 1500 мкс.\nПлавные переходы, затем удержание середины.\nВведите пароль Ubuntu для доступа к USB.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" -u "$script_root/flash_test_gpio17.py" --no-flash --pulses 500 2500 1500 --ramp --pause .5 2>&1 | tee "$script_root/../gpio17_full_pulse_retry.log"
repeat_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$repeat_status"
read -r
exit "$repeat_status"
