"""Smooth six-servo out-and-back test using the observed upright setpoints.

The servo on GPIO19 is continuous-rotation, so its command is speed around
neutral (90), not a position. Its physical angle cannot be guaranteed.
"""

import math
import time

import serial


PORT = "/dev/ttyUSB0"
BAUD = 115200
HOME = ((0, 0), (1, 82), (2, 75), (3, 30), (5, 0))
AWAY = ((0, 45), (1, 127), (2, 120), (3, 75), (5, 45))
EXPECTED = ("16:0:ON", "17:82:ON", "5:75:ON", "18:30:ON", "19:90:OFF", "21:0:ON")
DURATION_PER_DIRECTION = 3.0
FRAME_INTERVAL = 0.04


def exchange(port, line, wait=0.2):
    port.write((line + "\n").encode())
    port.flush()
    time.sleep(wait)
    response = port.read_all().decode(errors="replace").strip()
    print(f"{line}: {response}", flush=True)
    return response


def trajectory(port, reverse=False):
    start = time.monotonic()
    frame = 0
    while True:
        elapsed = time.monotonic() - start
        t = min(1.0, elapsed / DURATION_PER_DIRECTION)
        eased = 0.5 - 0.5 * math.cos(math.pi * t)
        ratio = 1.0 - eased if reverse else eased
        lines = []
        for (axis, home), (_, away) in zip(HOME, AWAY):
            angle = round(home + (away - home) * ratio)
            lines.append(f"S {axis} {angle}")
        speed = round(8 * math.sin(math.pi * t))
        lines.append(f"S 4 {90 - speed if reverse else 90 + speed}")
        port.write(("\n".join(lines) + "\n").encode())
        port.flush()
        port.read_all()  # Drain command acknowledgements without flooding the UI.
        if t >= 1.0:
            break
        frame += 1
        time.sleep(max(0, start + frame * FRAME_INTERVAL - time.monotonic()))
    print("Return complete" if reverse else "Outward movement complete", flush=True)


with serial.Serial(PORT, BAUD, timeout=0.2) as port:
    time.sleep(2)
    port.reset_input_buffer()
    status = exchange(port, "STATUS")
    if not all(piece in status for piece in EXPECTED):
        raise SystemExit("Unexpected starting pose; no movement attempted")
    exchange(port, "A 4 90")
    try:
        trajectory(port)
        trajectory(port, reverse=True)
        exchange(port, "S 4 90", 0.1)
    finally:
        exchange(port, "STOP 4", 0.1)
        exchange(port, "STATUS")
