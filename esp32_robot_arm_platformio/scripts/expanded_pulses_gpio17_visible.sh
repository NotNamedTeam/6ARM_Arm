#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Только D17: расширенный тест 600 → 2400 → 1500 мкс.\nПлавные переходы, короткие остановки на краях, затем центр.\nПри щелчках или сильном гудении без движения отключите питание сервы.\nВведите пароль Ubuntu.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" -u "$script_root/flash_test_gpio17.py" --pulses 600 2400 1500 --ramp --pause .5 2>&1 | tee "$script_root/../gpio17_expanded_pulse_test.log"
expanded_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$expanded_status"
read -r
exit "$expanded_status"
