#!/usr/bin/env bash
set -o pipefail
TASK_PROJECT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_PYTHON="${ROBOT_ARM_PYTHON:-python3}"
printf '%s\n' 'Возврат к первой калибровке с удержанием:' 'GPIO16=0°, GPIO17=82°, GPIO5=75°, GPIO18=30°, GPIO21=0°.' 'GPIO19 не включается. Перепрошивки нет.' 'Поддерживайте манипулятор при подключении к порту.' 'После ввода пароля движение начнётся автоматически. Ctrl+C — прервать с удержанием.'
sudo "$TASK_PYTHON" -u "$TASK_PROJECT/scripts/restore_first_calibration.py" 2>&1 | tee "$TASK_PROJECT/first_calibration_restore.log"
TASK_RESULT=${PIPESTATUS[0]}
printf '\nКод завершения: %s\n' "$TASK_RESULT"
read -r -p 'Enter — закрыть окно. ' TASK_UNUSED
