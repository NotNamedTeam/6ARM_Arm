#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
printf '%s\n' 'FreeCAD v3: добавляем два протяжных ролика ПОСЛЕ кромки.' 'Один мотор → протяжка → ремень → проскальзывающая муфта → сбор.' 'Подача: винт и тормозная накладка, без отдельного мотора.' 'Версия v2 сохранена отдельно. ESP32 не подключается.'
if [ -r /proc/22539/cmdline ] && tr '\0' '\n' < /proc/22539/cmdline | rg -Fxq "$TASK_ROOT/label_applicator/LabelApplicator_v2_N20.FCMacro"; then
    kill -TERM 22539
    for attempt in {1..30}; do
        if ! kill -0 22539 2>/dev/null; then break; fi
        sleep 0.2
    done
fi
"$TASK_ROOT/open_freecad.sh" "$TASK_ROOT/label_applicator/LabelApplicator_v3_Nip.FCMacro" 2>&1 | tee "$TASK_ROOT/label_applicator/visible_build_v3.log"
printf '%s\n' 'Окно FreeCAD закрыто. Enter — закрыть терминал.'
read -r
