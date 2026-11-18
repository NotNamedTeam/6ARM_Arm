#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
printf '%s\n' 'FreeCAD: версия 2 — убираем средний ролик и пружину.' 'Добавляем один компактный N20 на намотку подложки. ESP32 не подключается.' 'Старая версия сохранена отдельным файлом.'
if [ -r /proc/21461/cmdline ] && tr '\0' '\n' < /proc/21461/cmdline | rg -Fxq "$TASK_ROOT/label_applicator/LabelApplicator_v1.FCMacro"; then
    kill -TERM 21461
    for attempt in {1..30}; do
        if ! kill -0 21461 2>/dev/null; then break; fi
        sleep 0.2
    done
fi
"$TASK_ROOT/open_freecad.sh" "$TASK_ROOT/label_applicator/LabelApplicator_v2_N20.FCMacro" 2>&1 | tee "$TASK_ROOT/label_applicator/visible_build_v2.log"
printf '%s\n' 'Окно FreeCAD закрыто. Журнал выше; Enter — закрыть терминал.'
read -r
