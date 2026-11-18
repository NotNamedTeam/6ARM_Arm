"""Detach all six outputs in the installed calibration firmware; no movement."""

import termios
import time

from restore_first_calibration import PreserveModemLinesSerial
from test_saved_plus30 import exchange, status


port = PreserveModemLinesSerial(port=None, baudrate=115200, timeout=0.1,
                               write_timeout=1, exclusive=True)
port.port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
try:
    port.open()
    attrs = termios.tcgetattr(port.fileno())
    attrs[2] &= ~termios.HUPCL
    termios.tcsetattr(port.fileno(), termios.TCSANOW, attrs)
    time.sleep(1)
    port.read_all()
    initial, _, _ = status(port)
    print(initial, flush=True)
    print(exchange(port, "STOP", lambda line: line == "OK ALL STOPPED"), flush=True)
    final, _, enabled = status(port)
    print(final, flush=True)
    if any(enabled):
        raise RuntimeError("Не подтверждено выключение всех выходов")
    print("ВСЕ СИГНАЛЫ OFF. Напряжение питания физически не отключалось.", flush=True)
finally:
    if port.is_open:
        port.close()
