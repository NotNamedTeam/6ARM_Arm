#!/usr/bin/env bash
set -euo pipefail
TASK_PROJECT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TASK_WORK="${ROBOT_ARM_TOOLCHAIN_DIR:?Set ROBOT_ARM_TOOLCHAIN_DIR to the directory containing the ESP32 toolchain}"
TASK_PYTHON="$TASK_WORK/platformio-venv-3.14/bin/python"
TASK_PIO="$TASK_WORK/platformio-venv-3.14/bin/pio"
TASK_ESPTOOL="$TASK_WORK/platformio-core/packages/tool-esptoolpy/esptool.py"
TASK_BUILD="$TASK_PROJECT/.pio/build/esp32-manual-calibration"
TASK_BOOT_APP="$TASK_WORK/platformio-core/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin"
TASK_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

printf '%s\n' 'Сборка индивидуальной калибровки. Пока ничего не загружается.'
"$TASK_PIO" run --project-dir "$TASK_PROJECT" --environment esp32-manual-calibration
for TASK_IMAGE in "$TASK_ESPTOOL" "$TASK_BUILD/bootloader.bin" "$TASK_BUILD/partitions.bin" "$TASK_BOOT_APP" "$TASK_BUILD/firmware.bin"; do
  if [[ ! -f "$TASK_IMAGE" ]]; then
    printf 'Не найден обязательный файл: %s\n' "$TASK_IMAGE" >&2
    exit 1
  fi
done
if [[ ! -e "$TASK_PORT" ]]; then
  printf '%s\n' 'ESP32 не найдена. Проверьте USB-подключение.' >&2
  exit 1
fi
if fuser -s "$TASK_PORT"; then
  printf '%s\n' 'USB-порт занят. Закройте консоль (Ctrl+]) и другие мониторы порта.' >&2
  exit 1
fi
printf '%s\n' 'Загрузка сбросит плату. ПОДОПРИТЕ ВСЕ ЗВЕНЬЯ.' 'После загрузки все сигналы останутся OFF, автоматического теста нет.'
sudo "$TASK_PYTHON" -B -u "$TASK_ESPTOOL" --chip esp32 --port "$TASK_PORT" \
  --baud 460800 --before default_reset --after hard_reset \
  write_flash -z --flash_mode keep --flash_freq keep --flash_size keep \
  0x1000 "$TASK_BUILD/bootloader.bin" \
  0x8000 "$TASK_BUILD/partitions.bin" \
  0xe000 "$TASK_BOOT_APP" \
  0x10000 "$TASK_BUILD/firmware.bin"
printf '%s\n' 'Готово. Откройте задачу «ESP32: консоль индивидуальной калибровки».' 'GO — разовый тест выбранного привода. OFF — прекратить сигналы всех приводов.'
