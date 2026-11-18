#!/usr/bin/env bash
set -euo pipefail
TASK_PROJECT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_PYTHON="${ROBOT_ARM_PYTHON:-python3}"
printf '%s\n' 'Python-калибровка по одному приводу, БЕЗ перепрошивки ESP32.' 'Подоприте все звенья. После входа все управляющие сигналы OFF.' 'Измените углы в manual_calibration.py, Ctrl+S, затем GO в этой консоли.'
set +e
"$TASK_PYTHON" -B -u "$TASK_PROJECT/manual_calibration.py" 2>&1 | tee "$TASK_PROJECT/python_calibration_console.log"
TASK_RESULT=${PIPESTATUS[0]}
printf '\nКод завершения: %s\n' "$TASK_RESULT"
exit "$TASK_RESULT"
