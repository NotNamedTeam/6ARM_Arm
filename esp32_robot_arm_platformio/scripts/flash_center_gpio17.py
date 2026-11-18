"""Back up ESP32 flash, install GPIO17-only center firmware, verify its reply."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import serial


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parents[1] / "work"
TOOL = WORK / "platformio-core/packages/tool-esptoolpy/esptool.py"
BUILD = ROOT / ".pio/build/esp32-center-d17"
PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"


def user_owned(path):
    if os.geteuid() == 0 and "SUDO_UID" in os.environ:
        os.chown(path, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))


def main():
    images = [
        ("0x1000", BUILD / "bootloader.bin"),
        ("0x8000", BUILD / "partitions.bin"),
        ("0xe000", WORK / "platformio-core/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin"),
        ("0x10000", BUILD / "firmware.bin"),
    ]
    for _, path in images:
        if not path.is_file():
            raise SystemExit("Нет собранного файла: " + str(path))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / f"esp32_before_center_{stamp}_{os.getpid()}.bin"
    common = [sys.executable, "-u", str(TOOL), "--chip", "esp32", "--port", PORT,
              "--baud", "460800", "--before", "default_reset"]
    print("Сохраняю прежнюю прошивку ESP32, без изменения её содержимого…", flush=True)
    subprocess.run(common + ["--after", "no_reset", "read_flash",
                             "0", "ALL", str(backup)], check=True, timeout=300)
    user_owned(backup)
    if backup.stat().st_size < 1024 * 1024:
        raise SystemExit("Неполная резервная копия: загрузка отменена.")
    print("Резервная копия: " + str(backup), flush=True)
    write = common + ["--after", "hard_reset", "write_flash", "-z",
                      "--flash_mode", "dio", "--flash_freq", "40m", "--flash_size", "detect"]
    for address, image in images:
        write.extend([address, str(image)])
    print("Загружаю: только GPIO17, постоянно 1500 мкс / 50 Гц…", flush=True)
    subprocess.run(write, check=True, timeout=120)
    time.sleep(2)
    port = serial.Serial(port=None, baudrate=115200, timeout=.3, exclusive=True)
    port.dtr = False
    port.rts = False
    port.port = PORT
    confirmed = False
    try:
        port.open()
        time.sleep(.6)
        for _ in range(5):
            port.write(b"STATUS\n")
            port.flush()
            time.sleep(.5)
            response = port.read_all().decode(errors="replace")
            print(response.strip(), flush=True)
            if "CENTER GPIO 17 PULSE_US 1500 HOLD ON" in response:
                confirmed = True
                break
    finally:
        port.close()
    if not confirmed:
        raise SystemExit("Загрузка завершена, но ответ об удержании не получен. Нужна проверка.")
    report = {"result": "passed", "gpio": 17, "pulse_us": 1500,
              "frequency_hz": 50, "hold_enabled": True,
              "source": "ESP32 firmware acknowledgement; physical angle not measured",
              "backup": str(backup),
              "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
              "firmware_sha256": hashlib.sha256((BUILD / "firmware.bin").read_bytes()).hexdigest(),
              "finished_at": datetime.now(timezone.utc).isoformat()}
    report_path = ROOT / "gpio17_center_result.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    user_owned(report_path)
    print("ГОТОВО: ESP32 подтвердила GPIO17 = 1500 мкс; удержание включено. "
          "Остальные GPIO не управляются.", flush=True)


if __name__ == "__main__":
    main()
