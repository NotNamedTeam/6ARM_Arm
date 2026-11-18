"""Set only GPIO17 to the center pulse, using confirmed calibration firmware."""
import re
import time

import serial


def states(response):
    return {pin: (angle, enabled) for pin, angle, enabled in
            re.findall(r"(\d+):(\d+):(ON|OFF)", response)}


def main():
    port = serial.Serial(port=None, baudrate=115200, timeout=.2, exclusive=True)
    # Set control lines before opening to avoid requesting an ESP32 reset.
    port.dtr = False
    port.rts = False
    port.port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
    try:
        port.open()
        time.sleep(.8)
        port.reset_input_buffer()

        def command(line, delay=.4):
            port.write((line + "\n").encode())
            port.flush()
            time.sleep(delay)
            response = port.read_all().decode(errors="replace")
            print(line + " -> " + response.strip(), flush=True)
            return response

        before = states(command("STATUS"))
        if set(before) != {"16", "17", "5", "18", "19", "21"}:
            raise SystemExit("Прошивка калибровки не подтверждена. Команда движения НЕ отправлена.")
        # Calibration firmware maps 0..180 to 500..2500 us: 90 is 1500 us.
        reply = command("A 1 90", 1.2)
        if "OK ACTIVE 1 GPIO 17 ANGLE 90" not in reply:
            raise SystemExit("ESP32 не подтвердила команду для GPIO17.")
        after = states(command("STATUS"))
        if after.get("17") != ("90", "ON"):
            raise SystemExit("Середина диапазона GPIO17 не подтверждена.")
        if any(after.get(pin) != value for pin, value in before.items() if pin != "17"):
            raise SystemExit("Внимание: состояние другого привода изменилось.")
        print("ГОТОВО: GPIO17 = 1500 мкс (середина диапазона). Удержание включено. "
              "Настройки остальных приводов не изменились.", flush=True)
        print("Подтверждена команда ESP32, а не измеренный угол вала: энкодера нет.", flush=True)
    finally:
        # Do not send STOP or detach: the servo must hold its center for assembly.
        port.close()


if __name__ == "__main__":
    main()
