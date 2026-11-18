#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_LOCK="$TASK_ROOT/../../tools/freecad/freecad-gui.lock"
printf '%s\n' 'FreeCAD v5: мотор SM300 3 В по вашим размерам Ø25 × 13, вал выступает 9 мм.' 'Без SG90, ремней и возвратных муфт. Шестерни протяжки остаются 1:1.' 'Старая версия сохраняется и закрывается штатно. ESP32 не подключается.'
for attempt in {1..50}; do
    if flock -n "$TASK_LOCK" true; then break; fi
    sleep 0.2
done
"$TASK_ROOT/open_freecad.sh" "$TASK_ROOT/label_applicator/LabelApplicator_v5_SM300.FCMacro" 2>&1 | tee "$TASK_ROOT/label_applicator/visible_build_v5.log"
printf '%s\n' 'Окно FreeCAD закрыто. Enter — закрыть терминал.'
read -r
