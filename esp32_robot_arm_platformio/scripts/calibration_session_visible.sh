#!/usr/bin/env bash
set -o pipefail
TASK_PROJECT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_PYTHON="${ROBOT_ARM_PYTHON:-python3}"
TASK_SESSION_DIR=$1
printf '%s\n' 'Калибровка старой руки, начиная с плеча GPIO17.' 'Первая команда: 82 -> 87 градусов. Остальные приводы удерживают.' 'Поддерживайте руку при подключении. После пароля команда выполнится автоматически.' 'Оставьте это окно открытым для дальнейших подстроек. Ctrl+C — завершить с удержанием.'
sudo "$TASK_PYTHON" -u "$TASK_PROJECT/scripts/calibration_session.py" --session-dir "$TASK_SESSION_DIR" 2>&1 | tee "$TASK_SESSION_DIR/session.log"
TASK_RESULT=${PIPESTATUS[0]}
printf '\nКод завершения: %s\n' "$TASK_RESULT"
read -r -p 'Enter — закрыть окно. ' TASK_UNUSED
