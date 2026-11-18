#!/usr/bin/env bash
set -o pipefail
TASK_PROJECT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_PYTHON="${ROBOT_ARM_PYTHON:-python3}"
printf '%s\n' 'Старая рука: по одному +30 градусов от сохранённых углов и возврат.' 'GPIO16: 0→30→0; GPIO17: 82→112→82; GPIO5: 90→120→90;' 'GPIO18: 90→120→90; GPIO21: 45→75→45. GPIO19 пропускается.' 'Поддерживайте руку. Первый реальный поворот может быть больше 30 градусов.' 'После ввода пароля тест начнётся автоматически. Ctrl+C — остановить с удержанием.'
sudo "$TASK_PYTHON" -u "$TASK_PROJECT/scripts/test_saved_plus30.py" 2>&1 | tee "$TASK_PROJECT/saved_plus30_test.log"
TASK_RESULT=${PIPESTATUS[0]}
printf '\nКод завершения: %s\n' "$TASK_RESULT"
read -r -p 'Enter — закрыть окно. ' TASK_UNUSED
