#!/usr/bin/env bash
set -euo pipefail
TASK_PYTHON="${ROBOT_ARM_PYTHON:-python3}"
TASK_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
printf '%s\n' 'Консоль НОВОЙ индивидуальной калибровки, 115200, Newline.' 'Сначала загрузите esp32-manual-calibration. Здесь загрузка не выполняется.' 'Подоприте звенья. GO — тест одного привода; S 1 85 — плечо на 85°.' 'OFF — прекратить сигналы. STATUS — состояние. Ctrl+] — выйти из консоли.'
exec sudo "$TASK_PYTHON" -B -m serial.tools.miniterm \
  --dtr 0 --rts 0 --echo --eol LF "$TASK_PORT" 115200
