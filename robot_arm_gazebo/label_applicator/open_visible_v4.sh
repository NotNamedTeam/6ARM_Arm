#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
printf '%s\n' 'FreeCAD v4: убираем ремень, ставим SG90 и зубчатую пару роликов.' 'SG90 делает рабочий ход и возвращается через обгонную муфту.' 'Вариант без накопительной катушки: свободный выход подложки.' 'Старая версия v3 сохранена отдельно. Реальные сервы не подключаются.'
if [ -r /proc/23861/cmdline ] && tr '\0' '\n' < /proc/23861/cmdline | rg -Fxq "$TASK_ROOT/label_applicator/LabelApplicator_v3_Nip.FCMacro"; then
    kill -TERM 23861
    for attempt in {1..30}; do
        if ! kill -0 23861 2>/dev/null; then break; fi
        sleep 0.2
    done
fi
"$TASK_ROOT/open_freecad.sh" "$TASK_ROOT/label_applicator/LabelApplicator_v4_SG90.FCMacro" 2>&1 | tee "$TASK_ROOT/label_applicator/visible_build_v4.log"
printf '%s\n' 'Окно FreeCAD закрыто. Enter — закрыть терминал.'
read -r
