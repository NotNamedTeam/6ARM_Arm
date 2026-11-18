#!/usr/bin/env bash
set -o pipefail
TASK_PROJECT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_PYTHON="${ROBOT_ARM_PYTHON:-python3}"
printf '%s\n' 'Отключение сигналов всех серв. ПОДДЕРЖИВАЙТЕ МАНИПУЛЯТОР.' 'После ввода пароля удержание будет снято, питание серв останется.'
sudo "$TASK_PYTHON" -u "$TASK_PROJECT/scripts/disable_all_servos.py" 2>&1 | tee "$TASK_PROJECT/all_servos_off.log"
TASK_RESULT=${PIPESTATUS[0]}
printf '\nКод завершения: %s\n' "$TASK_RESULT"
read -r -p 'Enter — закрыть окно. ' TASK_UNUSED
