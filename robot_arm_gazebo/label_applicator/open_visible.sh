#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
printf '%s\n' 'FreeCAD: строим макет лепилки v1. Реальная ESP32 не подключается.' 'Детали появляются в одном окне; исходная рука не изменяется.'
exec "$TASK_ROOT/open_freecad.sh" "$TASK_ROOT/label_applicator/LabelApplicator_v1.FCMacro"
