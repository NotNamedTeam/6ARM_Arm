"""Restore the user's original calibrated pose; keep positional PWM enabled."""

import json
import termios
import time

import serial

from test_saved_plus30 import AXES, PINS, ramp, set_angle, status


HOME = (0, 82, 75, 30, 90, 0)
LAST_TEST = (0, 82, 90, 90, 90, 45)


class PreserveModemLinesSerial(serial.Serial):
    # Do not issue separate DTR/RTS transitions: their intermediate states can
    # reset an ESP32 through its auto-program circuit. Opening a particular USB
    # driver can nevertheless reset a board; the operator must support the arm.
    def _update_dtr_state(self):
        pass

    def _update_rts_state(self):
        pass


def main():
    report = {"target_angles": dict(zip(PINS, HOME)),
              "feedback": "command_acknowledgements_only",
              "gpio19_skipped": True, "completed_axes": []}
    port = PreserveModemLinesSerial(port=None, baudrate=115200, timeout=0.1,
                                   write_timeout=1, exclusive=True)
    port.port = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
    try:
        port.open()
        attrs = termios.tcgetattr(port.fileno())
        attrs[2] &= ~termios.HUPCL
        termios.tcsetattr(port.fileno(), termios.TCSANOW, attrs)
        time.sleep(2)
        startup = port.read_all().decode(errors="replace").strip()
        if startup:
            print(startup, flush=True)
        line, initial, active = status(port)
        print(line, flush=True)
        if initial not in (LAST_TEST, HOME) or active[4]:
            raise RuntimeError("Неожиданное состояние платы; новых движений не отправлено.")
        report["initial_status"] = line
        # If opening reset the board, re-enable the last commanded pose first.
        # This is not a measured physical position; the user supports the arm.
        for axis in AXES:
            if not active[axis]:
                set_angle(port, axis, initial[axis], attach=True)
                print(f"GPIO{PINS[axis]}: удержание включено на {initial[axis]}°.", flush=True)
        for axis in AXES:
            start, target = initial[axis], HOME[axis]
            print(f"GPIO{PINS[axis]}: {start} -> {target}°, удержание ON.", flush=True)
            if start != target:
                ramp(port, axis, start, target)
            time.sleep(0.5)
            report["completed_axes"].append(PINS[axis])
        line, angles, enabled = status(port)
        if angles != HOME or not all(enabled[i] for i in AXES) or enabled[4]:
            raise RuntimeError("Итоговое состояние не подтверждено: " + line)
        report.update(result="original_pose_commanded_hold_on", final_status=line)
        print("ГОТОВО: исходная калибровка, пять позиционных приводов удерживают.", flush=True)
        print(line, flush=True)
    except KeyboardInterrupt:
        report.update(result="interrupted_holding_last_command")
        print("ПРЕРВАНО. Удержание не отключаю, дальнейшего возврата нет.", flush=True)
    except Exception as error:
        report.update(result="stopped_on_error", error=str(error))
        print("ОСТАНОВЛЕНО: " + str(error), flush=True)
        print("Команды отключения удержания не отправлялись.", flush=True)
    finally:
        if port.is_open:
            port.close()
        print("RESULT_JSON " + json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
