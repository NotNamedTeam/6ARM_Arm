#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Только D17: крайние значения ESP32Servo 500 → 2500 → 1500 мкс.\nПлавные переходы и короткие остановки на краях.\nПри щелчках или сильном гудении без движения отключите питание сервы.\nВведите пароль Ubuntu.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" -u "$script_root/flash_test_gpio17.py" --pulses 500 2500 1500 --ramp --pause .5 2>&1 | tee "$script_root/../gpio17_full_pulse_test.log"
full_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$full_status"
read -r
exit "$full_status"
