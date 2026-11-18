"""One coordinated six-axis movement from the observed upright pose, then restore it.

GPIO19 is a continuous-rotation servo: 100 is a brief speed command, not an
absolute position. It is returned to neutral and detached in all cases.
"""

import time

import serial


PORT = "/dev/ttyUSB0"
BAUD = 115200
EXPECTED = ("16:0:ON", "17:82:ON", "5:75:ON", "18:30:ON", "19:90:OFF", "21:0:ON")
UPRIGHT = ((0, 0), (1, 82), (2, 75), (3, 30), (5, 0))
TEST = ((0, 45), (1, 127), (2, 120), (3, 75), (5, 45))


def command(port, line, delay=0.06):
    port.write((line + "\n").encode())
    port.flush()
    time.sleep(delay)
    answer = port.read_all().decode(errors="replace").strip()
    if answer:
        print(f"{line}: {answer}", flush=True)
    return answer


def frame(port, positions, rotation, hold_seconds):
    # One serial burst makes the six commands begin within a few milliseconds.
    lines = [f"S {axis} {angle}" for axis, angle in positions]
    lines.append(f"S 4 {rotation}")
    port.write(("\n".join(lines) + "\n").encode())
    port.flush()
    time.sleep(hold_seconds)
    print(" | ".join(lines), flush=True)
    print(port.read_all().decode(errors="replace").strip(), flush=True)


with serial.Serial(PORT, BAUD, timeout=0.2) as port:
    time.sleep(2)
    port.reset_input_buffer()
    status = command(port, "STATUS", 0.2)
    if not all(piece in status for piece in EXPECTED):
        raise SystemExit("Unexpected starting pose; no motion attempted")

    command(port, "A 4 90", 0.3)
    try:
        frame(port, TEST, 100, 0.8)
        frame(port, UPRIGHT, 90, 0.6)
    finally:
        command(port, "S 4 90", 0.1)
        command(port, "STOP 4", 0.1)
        command(port, "STATUS", 0.2)
