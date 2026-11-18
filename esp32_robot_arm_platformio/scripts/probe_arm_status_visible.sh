#!/usr/bin/env bash
set -o pipefail
TASK_PROJECT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_PYTHON="${ROBOT_ARM_PYTHON:-python3}"
printf '%s\n' 'ESP32: только проверка состояния, без движения.' 'Введите пароль Linux, если sudo его запросит. Ввод пароля не отображается.'
sudo "$TASK_PYTHON" -u "$TASK_PROJECT/scripts/probe_arm_status.py" 2>&1 | tee "$TASK_PROJECT/arm_status_probe.log"
TASK_RESULT=${PIPESTATUS[0]}
printf '\nКод завершения: %s\n' "$TASK_RESULT"
read -r -p 'Проверка закончена. Enter — закрыть окно. ' TASK_UNUSED
