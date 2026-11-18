"""One bounded test per positional axis, using this board's saved setpoints.

The operator authorized an unknown first physical movement from detached axes.
There is no preliminary homing and no claim of measured shaft displacement.
GPIO19 is never enabled. Cancellation holds the last commanded positions.
"""

import json
import re
import termios
import time

import serial


PINS = (16, 17, 5, 18, 19, 21)
AXES = (0, 1, 2, 3, 5)
NAMES = ("Основание", "Плечо", "Локоть", "Наклон кисти", "Поворот кисти", "Захват")
EXPECTED = (0, 82, 90, 90, 90, 45)  # Last observed saved values on the board.
LIMITS = (270, 180, 180, 180, 180, 180)


def exchange(port, command, expected):
    port.write((command + "\n").encode())
    port.flush()
    until = time.monotonic() + 2
    while time.monotonic() < until:
        line = port.readline().decode(errors="replace").strip()
        if not line:
            continue
        if "READY" in line or "ERR" in line:
            raise RuntimeError("Перезапуск/ошибка платы: " + line)
        if expected(line):
            return line
    raise RuntimeError("Нет подтверждения команды: " + command)


def status(port):
    line = exchange(port, "STATUS", lambda line: line.startswith("STATUS "))
    parts = re.findall(r"(\d+):(\d+):(ON|OFF)", line)
    if tuple(int(p[0]) for p in parts) != PINS:
        raise RuntimeError("Неизвестный формат состояния: " + line)
    return line, tuple(int(p[1]) for p in parts), tuple(p[2] == "ON" for p in parts)


def set_angle(port, axis, angle, attach=False):
    if attach:
        response = f"OK ACTIVE {axis} GPIO {PINS[axis]} ANGLE {angle}"
        command = f"A {axis} {angle}"
    else:
        response = f"OK S {axis} {angle}"
        command = f"S {axis} {angle}"
    exchange(port, command, lambda line: line == response)


def ramp(port, axis, start, end):
    step = 1 if end > start else -1
    for angle in range(start + step, end + step, step):
        set_angle(port, axis, angle)
        time.sleep(0.06)


def main():
    report = {"completed_axes": [], "feedback": "command_acknowledgements_only",
              "preliminary_homing": False, "gpio19_skipped": True}
    port = serial.Serial(port=None, baudrate=115200, timeout=0.1,
                         write_timeout=1, exclusive=True)
    port.dtr = False
    port.rts = False
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
        line, saved, active = status(port)
        print(line, flush=True)
        if saved != EXPECTED or active[4]:
            raise RuntimeError("Состояние отличается от проверенного; движения отменены.")
        if any(saved[i] + 30 > LIMITS[i] for i in AXES):
            raise RuntimeError("Цель выходит за диапазон команд; движения отменены.")
        report["saved_angles"] = dict(zip(PINS, saved))
        print("Тест начинается. Ctrl+C — прервать, не отключая удержание.", flush=True)
        for axis in AXES:
            origin, away = saved[axis], saved[axis] + 30
            print(f"\n{NAMES[axis]}, GPIO{PINS[axis]}: {origin} -> {away} -> {origin} градусов", flush=True)
            if active[axis]:
                ramp(port, axis, origin, away)
            else:
                print("Первое включение сразу на тестовый угол; реальный начальный угол неизвестен.", flush=True)
                set_angle(port, axis, away, attach=True)
            time.sleep(0.8)
            ramp(port, axis, away, origin)
            time.sleep(0.5)
            final, angles, enabled = status(port)
            if angles[axis] != origin or not enabled[axis] or enabled[4]:
                raise RuntimeError("Не подтверждён возврат команды: " + final)
            report["completed_axes"].append(PINS[axis])
            print(f"GPIO{PINS[axis]}: возврат команды на {origin}, удержание ON.", flush=True)
        final, angles, enabled = status(port)
        if angles != saved or not all(enabled[i] for i in AXES):
            raise RuntimeError("Не подтверждено итоговое состояние: " + final)
        report.update(result="passed_command_test", final_status=final)
        print("\nТест команд завершён. Пять приводов удерживают исходные сохранённые углы.", flush=True)
        print(final, flush=True)
    except KeyboardInterrupt:
        report.update(result="interrupted_holding_last_command")
        print("\nПРЕРВАНО. Команды отключения и автоматического возврата НЕ отправлялись.", flush=True)
    except Exception as error:
        report.update(result="stopped_on_error", error=str(error))
        print("\nОСТАНОВЛЕНО: " + str(error), flush=True)
        print("Новых движений и отключения удержания не отправляю.", flush=True)
    finally:
        if port.is_open:
            port.close()
        print("RESULT_JSON " + json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
