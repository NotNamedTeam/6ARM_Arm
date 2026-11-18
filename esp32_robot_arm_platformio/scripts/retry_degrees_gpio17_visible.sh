#!/usr/bin/env bash
set -uo pipefail
script_root="$(cd -- "$(dirname -- "$0")" && pwd)"
printf 'Один плавный повтор D17 БЕЗ перепрошивки: 0° → 180° → 90°.\nПроверенный диапазон 500–2500 мкс, затем удержание середины.\nВведите пароль Ubuntu для доступа к USB.\n\n'
sudo "${ROBOT_ARM_PYTHON:-/usr/bin/python3}" -u "$script_root/flash_test_gpio17.py" --degrees --no-flash --ramp --pause .5 2>&1 | tee "$script_root/../gpio17_degree_retry.log"
retry_status=${PIPESTATUS[0]}
printf '\nКод результата: %s. Нажмите Enter, чтобы закрыть окно.\n' "$retry_status"
read -r
exit "$retry_status"
