"""Query the attached ESP32 without sending any motion or enable command.

RTS/DTR are deasserted before opening. Some USB boards can still reset when
opened; the operator must support the arm. Reported angles are commanded
setpoints, not measured shaft positions.
"""

import json
import time

import serial


def collect(port, seconds):
    deadline = time.monotonic() + seconds
    chunks = []
    while time.monotonic() < deadline:
        data = port.read(port.in_waiting or 1)
        if data:
            chunks.append(data)
    return b"".join(chunks).decode(errors="replace")


def main():
    print("Проверка ESP32. Команды движения НЕ отправляются.", flush=True)
    print("Продолжайте поддерживать манипулятор при подключении к порту.", flush=True)
    port = serial.Serial(port=None, baudrate=115200, timeout=0.1,
                         write_timeout=1, exclusive=True)
    port.dtr = False
    port.rts = False
    port.port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
    try:
        port.open()
        startup = collect(port, 2)
        if startup.strip():
            print("При подключении: " + startup.strip(), flush=True)
        port.write(b"STATUS\n")
        port.flush()
        response = collect(port, 3)
        print("Ответ STATUS: " + (response.strip() or "НЕТ ОТВЕТА"), flush=True)
        if "CENTER GPIO 17" in response:
            kind = "single_gpio17_only"
        elif "STATUS" in response and ":ON" in response:
            kind = "multi_axis_calibration"
        elif "STATUS" in response and ":OFF" in response:
            kind = "multi_axis_calibration_outputs_off"
        elif "STATUS ENABLED" in response or "STATUS STOPPED" in response:
            kind = "multi_axis_wifi"
        else:
            kind = "unrecognized_no_motion_allowed"
        print(json.dumps({"firmware_kind": kind, "startup": startup,
                          "status": response, "motion_commands_sent": 0},
                         ensure_ascii=False), flush=True)
    finally:
        if port.is_open:
            port.close()


if __name__ == "__main__":
    main()
