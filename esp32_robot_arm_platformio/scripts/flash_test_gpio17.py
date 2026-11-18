"""Update the known GPIO17-only firmware; run one 1000 -> 2000 -> 1500 us test."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time

import serial
from flash_center_gpio17 import ROOT, TOOL, BUILD, PORT, user_owned


def open_port():
    port = serial.Serial(port=None, baudrate=115200, timeout=.1, exclusive=True)
    port.dtr = False
    port.rts = False
    port.port = PORT
    port.open()
    time.sleep(.5)
    return port


def get_status(port):
    port.write(b"STATUS\n")
    port.flush()
    time.sleep(.4)
    response = port.read_all().decode(errors="replace")
    print(response.strip(), flush=True)
    return response


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--degrees", action="store_true")
    mode.add_argument("--pulses", nargs="+", type=int)
    parser.add_argument("--no-flash", action="store_true")
    parser.add_argument("--pause", type=float, default=1.5)
    parser.add_argument("--ramp", action="store_true")
    args = parser.parse_args()
    if not .5 <= args.pause <= 5:
        parser.error("Pause must be between 0.5 and 5 seconds")
    if args.pulses and (not 2 <= len(args.pulses) <= 5 or args.pulses[-1] != 1500
                        or any(not 500 <= pulse <= 2500 for pulse in args.pulses)
                        or args.pause > 1.5):
        parser.error("Use 2..5 pulses within 500..2500 us, end at 1500; pause <= 1.5 s")
    if args.ramp and not (args.pulses or args.degrees):
        parser.error("--ramp requires --pulses or --degrees")
    # The original full-flash backup already exists. Do not replace it with
    # another copy of the temporary centering program.
    previous = json.loads((ROOT / "gpio17_center_result.json").read_text())
    from pathlib import Path
    backup = Path(previous["backup"])
    if hashlib.sha256(backup.read_bytes()).hexdigest() != previous["backup_sha256"]:
        raise SystemExit("Резервная копия не прошла проверку; загрузка отменена.")
    if not args.no_flash:
        port = open_port()
        try:
            if "CENTER GPIO 17 PULSE_US 1500 HOLD ON" not in get_status(port):
                raise SystemExit("Текущая прошивка D17 не подтверждена; загрузка отменена.")
        finally:
            port.close()
        print("Загружаю разовый тест только D17. Прежняя резервная копия сохранена.", flush=True)
        subprocess.run([sys.executable, "-u", str(TOOL), "--chip", "esp32",
                        "--port", PORT, "--baud", "460800", "--before", "default_reset",
                        "--after", "hard_reset", "write_flash", "-z",
                        "--flash_mode", "keep", "--flash_freq", "keep", "--flash_size", "keep",
                        "0x10000", str(BUILD / "firmware.bin")], check=True, timeout=120)
        time.sleep(2)
    else:
        print("Повтор через USB БЕЗ перепрошивки. Только GPIO17.", flush=True)
    port = open_port()
    try:
        if "CENTER GPIO 17 PULSE_US 1500 HOLD ON" not in get_status(port):
            raise SystemExit("Новая прошивка не подтвердила середину; тест не запущен.")
        if args.pulses:
            port.write(b"LIMITS\n")
            port.flush()
            time.sleep(.3)
            limits_reply = port.read_all().decode(errors="replace")
            print(limits_reply.strip(), flush=True)
            limits = re.search(r"LIMITS GPIO 17 MIN_US (\d+) MAX_US (\d+) CENTER_US 1500", limits_reply)
            if not limits or any(not int(limits[1]) <= p <= int(limits[2]) for p in args.pulses):
                raise SystemExit("Плата не подтвердила нужный диапазон. Движение отменено.")
            print("ПРЯМЫЕ ИМПУЛЬСЫ GPIO17: " + " → ".join(map(str, args.pulses)) + " мкс.", flush=True)
            current = 1500
            for pulse in args.pulses:
                response = ""
                if args.ramp:
                    print(f"Плавный переход {current} → {pulse} мкс.", flush=True)
                    while current != pulse:
                        current += max(-20, min(20, pulse - current))
                        port.write(f"PULSE {current}\n".encode())
                        port.flush()
                        time.sleep(.02)
                        response += port.read_all().decode(errors="replace")
                        if "ERR" in response:
                            raise SystemExit("Плата отклонила импульс; тест прекращён.")
                    time.sleep(.15)
                else:
                    port.write(f"PULSE {pulse}\n".encode())
                    port.flush()
                    time.sleep(.3)
                    current = pulse
                response += port.read_all().decode(errors="replace")
                print(response.strip().splitlines()[-1] if response.strip() else "Нет ответа", flush=True)
                if f"CENTER GPIO 17 PULSE_US {pulse} HOLD ON" not in response:
                    raise SystemExit("Импульс не подтверждён; дальнейшие команды отменены.")
                time.sleep(max(0, args.pause - (.15 if args.ramp else .3)))
        elif args.degrees:
            port.write(b"LIMITS\n")
            port.flush()
            time.sleep(.3)
            limits_reply = port.read_all().decode(errors="replace")
            print(limits_reply.strip(), flush=True)
            if "LIMITS GPIO 17 MIN_US 500 MAX_US 2500 CENTER_US 1500" not in limits_reply:
                raise SystemExit("Проверенный полный диапазон не подтверждён; движение отменено.")
            print("ЗАПУСК В ГРАДУСАХ: 0° → 180° → 90°. Только D17.", flush=True)
            current_angle = 90
            for angle in (0, 180, 90):
                response = ""
                if args.ramp:
                    print(f"Плавный переход {current_angle}° → {angle}°.", flush=True)
                    while current_angle != angle:
                        current_angle += max(-2, min(2, angle - current_angle))
                        port.write(f"DEG {current_angle}\n".encode())
                        port.flush()
                        time.sleep(.02)
                        response += port.read_all().decode(errors="replace")
                        if "ERR" in response:
                            raise SystemExit("Команда в градусах отклонена; тест прекращён.")
                    time.sleep(.15)
                else:
                    port.write(f"DEG {angle}\n".encode())
                    port.flush()
                    time.sleep(.3)
                    current_angle = angle
                response += port.read_all().decode(errors="replace")
                print(response.strip().splitlines()[-1] if response.strip() else "Нет ответа", flush=True)
                if f"SERVO GPIO 17 ANGLE {angle} HOLD ON" not in response:
                    raise SystemExit("Команда в градусах не подтверждена; дальнейшие движения отменены.")
                time.sleep(max(0, args.pause - (.15 if args.ramp else .3)))
        else:
            print("ЗАПУСК: 1000 мкс → 2000 мкс → 1500 мкс. Смотрите на серву.", flush=True)
            port.write(b"TEST\n")
            port.flush()
            response = ""
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                data = port.read_all().decode(errors="replace")
                if data:
                    print(data, end="", flush=True)
                    response += data
                if "TEST GPIO 17 DONE PULSE_US 1500 HOLD ON" in response:
                    break
                time.sleep(.05)
            expected = ["TEST GPIO 17 STEP 1 PULSE_US 1000",
                        "TEST GPIO 17 STEP 2 PULSE_US 2000",
                        "TEST GPIO 17 DONE PULSE_US 1500 HOLD ON"]
            indices = [response.find(line) for line in expected]
            if min(indices) < 0 or indices != sorted(indices):
                raise SystemExit("Не все этапы подтверждены платой. Автоматических повторов нет.")
        if "CENTER GPIO 17 PULSE_US 1500 HOLD ON" not in get_status(port):
            raise SystemExit("Итоговая середина не подтверждена.")
    finally:
        port.close()
    report = {"result": "commands_confirmed", "physical_motion": "not_verified",
              "gpio": 17, "pulse_sequence_us": args.pulses or ([500, 2500, 1500] if args.degrees else [1000, 2000, 1500]),
              "end_hold_enabled": True, "backup": str(backup),
              "firmware_sha256": hashlib.sha256((BUILD / "firmware.bin").read_bytes()).hexdigest(),
              "finished_at": datetime.now(timezone.utc).isoformat()}
    if args.degrees:
        report.update(command_sequence_deg=[0, 180, 90], library_call="Servo.write(angle)")
    report.update(firmware_uploaded=not args.no_flash, pause_seconds=args.pause)
    if args.ramp:
        report.update(ramp_interval_seconds=.02)
        report["ramp_step_degrees" if args.degrees else "ramp_step_us"] = 2 if args.degrees else 20
    result_path = ROOT / ("gpio17_full_pulse_retry.json" if args.no_flash and args.pulses == [500, 2500, 1500] else
                          "gpio17_full_pulse_test.json" if args.pulses == [500, 2500, 1500] else
                          "gpio17_expanded_pulse_test.json" if args.pulses and args.ramp else
                          "gpio17_direct_pulse_test.json" if args.pulses else
                          "gpio17_degree_retry.json" if args.no_flash and args.degrees else
                          "gpio17_degree_test.json" if args.degrees else "gpio17_endpoint_test.json")
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    user_owned(result_path)
    print(("Плата подтвердила прямые импульсы и возврат к 1500 мкс." if args.pulses else
           "Плата подтвердила команды 0°, 180°, 90°." if args.degrees else
           "Плата подтвердила обе крайние команды и возврат к 1500 мкс.") +
          " Удержание включено. Реальное движение проверяется визуально.", flush=True)


if __name__ == "__main__":
    main()
