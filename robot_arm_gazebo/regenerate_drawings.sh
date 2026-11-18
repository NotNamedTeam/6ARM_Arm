#!/usr/bin/env bash
set -euo pipefail
robot_root="$(cd -- "$(dirname -- "$0")" && pwd)"
freecad_runner="$robot_root/../../tools/freecad/launch_freecad.sh"
pdf_python="${ROBOT_ARM_PDF_PYTHON:-python3}"
"$freecad_runner" python "$robot_root/extract_drawings.py"
"$freecad_runner" python "$robot_root/extract_assembly_drawing.py"
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$pdf_python" "$robot_root/make_drawings.py"
"$freecad_runner" python "$robot_root/save_drawing_book.py"
printf '\nЧертежи сохранены в %s/drawings. Проверьте листы перед печатью.\n' "$robot_root"
