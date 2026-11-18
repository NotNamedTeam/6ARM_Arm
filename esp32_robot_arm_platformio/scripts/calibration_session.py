"""Bounded manual calibration session; preserve PWM and the serial connection.

Only GPIO17/5/18/21 may be jogged, at most ten command degrees per request.
No flash, attach, detach, homing, shell execution, or continuous-rotation moves.
Elevated access is used only to open/configure the serial device; privileges
are permanently dropped before reading requests or writing session files.
"""

import argparse
import json
import os
from pathlib import Path
import termios
import time

from restore_first_calibration import PreserveModemLinesSerial
from test_saved_plus30 import AXES, PINS, ramp, status


def drop_privileges():
    if os.geteuid() == 0:
        uid = int(os.environ["SUDO_UID"])
        gid = int(os.environ["SUDO_GID"])
        if uid <= 0 or gid <= 0:
            raise RuntimeError("Не определён обычный пользователь для сессии.")
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-dir", required=True)
    args = parser.parse_args()
    port = PreserveModemLinesSerial(port=None, baudrate=115200, timeout=0.1,
                                   write_timeout=1, exclusive=True)
    port.port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
    state = {"pid": os.getpid(), "phase": "opening", "last_request_id": 0,
             "feedback": "command_acknowledgements_only"}
    session_dir = None

    def save():
        if session_dir is not None:
            pending = session_dir / "state.pending.json"
            pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            pending.replace(session_dir / "state.json")

    def snapshot():
        line, angles, enabled = status(port)
        if not all(enabled[i] for i in AXES) or enabled[4]:
            raise RuntimeError("Удержание изменилось; движение отменено: " + line)
        state["board_status"] = line
        state["commanded_angles"] = dict(zip(PINS, angles))
        return angles

    try:
        port.open()
        attrs = termios.tcgetattr(port.fileno())
        attrs[2] &= ~termios.HUPCL
        termios.tcsetattr(port.fileno(), termios.TCSANOW, attrs)
        drop_privileges()
        session_dir = Path(args.session_dir).resolve(strict=True)
        if session_dir.stat().st_uid != os.getuid():
            raise RuntimeError("Папка сессии принадлежит другому пользователю.")
        time.sleep(1)
        startup = port.read_all().decode(errors="replace").strip()
        if startup:
            print(startup, flush=True)
        snapshot()
        state["phase"] = "ready"
        save()
        print("Сессия открыта. Удержание ON. Ctrl+C — завершить с удержанием.", flush=True)
        print(state["board_status"], flush=True)
        last_activity = time.monotonic()
        while time.monotonic() - last_activity < 600:
            try:
                request = json.loads((session_dir / "request.json").read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(0.1)
                continue
            request_id = request.get("id")
            if type(request_id) is not int or request_id <= state["last_request_id"]:
                time.sleep(0.1)
                continue
            state["last_request_id"] = request_id
            last_activity = time.monotonic()
            action = request.get("action")
            if action == "end":
                state["phase"] = "ended_holding"
                break
            current = snapshot()
            if action == "status":
                state["last_result"] = {"id": request_id, "result": "status"}
                save()
                continue
            pin, delta = request.get("gpio"), request.get("delta")
            expected = request.get("expected_angle")
            if (action != "jog" or type(pin) is not int or pin not in (17, 5, 18, 21)
                    or type(delta) is not int or not 1 <= abs(delta) <= 10):
                raise RuntimeError("Недопустимая команда калибровки; движение отменено.")
            axis = PINS.index(pin)
            if type(expected) is not int or expected != current[axis]:
                raise RuntimeError("Исходный угол не совпадает с ожидаемым; движение отменено.")
            target = current[axis] + delta
            if not 0 <= target <= 180:
                raise RuntimeError("Цель вне диапазона 0..180; движение отменено.")
            print(f"GPIO{pin}: {current[axis]} -> {target}°, остальные удерживают.", flush=True)
            state["phase"] = "moving"
            save()
            ramp(port, axis, current[axis], target)
            time.sleep(0.4)
            final = snapshot()
            expected_final = list(current)
            expected_final[axis] = target
            if final != tuple(expected_final):
                raise RuntimeError("Состояние после движения не совпало с командой.")
            state["phase"] = "ready"
            state["last_result"] = {"id": request_id, "gpio": pin,
                                    "from": current[axis], "to": target,
                                    "result": "command_confirmed_hold_on"}
            save()
            print(state["board_status"], flush=True)
        else:
            state["phase"] = "expired_holding"
    except KeyboardInterrupt:
        state["phase"] = "interrupted_holding"
    except Exception as error:
        state.update(phase="stopped_on_error", error=str(error))
        print("ОСТАНОВЛЕНО: " + str(error), flush=True)
    finally:
        if port.is_open:
            port.close()
        save()
        print("Сессия завершена. Команд отключения удержания не отправлялось.", flush=True)


if __name__ == "__main__":
    main()
