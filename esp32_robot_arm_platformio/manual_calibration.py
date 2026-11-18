

# ===================== УГЛЫ =====================
TARGET_ANGLES = {
    16: 0,    # Основание, диапазон команд 0..270.
    17: 88,   # Плечо — второй привод, начинаем с него.
    5: 75,    # Локоть.
    18: 85,   # Наклон кисти.
    19: 90,   # Непрерывный поворот: 90 = нейтраль, НЕ угол. Не менять.
    21: 0,    # Захват.
}
ACTIVE_GPIO = 18         # Какой ОДИН привод проверять по команде GO.
MOVE_SECONDS = 1.2           # Время подачи сигнала, НЕ регулировка скорости.
HOLD_AFTER_MOVE = False      # False — после теста выключить управляющий сигнал.
# ========================================================

PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
BAUD = 115200

import argparse
import ast
import os
from pathlib import Path
import re
import select
import sys
import termios
import time

import serial

PINS = (16, 17, 5, 18, 19, 21)
POSITIONAL_PINS = (16, 17, 5, 18, 21)
SETTINGS = ("TARGET_ANGLES", "ACTIVE_GPIO", "MOVE_SECONDS", "HOLD_AFTER_MOVE")


def validate_target(gpio, angle):
    if type(gpio) is not int or gpio not in POSITIONAL_PINS:
        raise ValueError("Выберите GPIO16, 17, 5, 18 или 21. GPIO19 не управляется углом.")
    limit = 270 if gpio == 16 else 180
    if type(angle) is not int or not 0 <= angle <= limit:
        raise ValueError(f"Для GPIO{gpio} допустима команда 0..{limit} градусов.")


def load_settings(path=None):
    # Перечитываем только литералы настроек, без выполнения изменённого кода.
    tree = ast.parse(Path(path or __file__).read_text(encoding="utf-8"))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in SETTINGS:
                    result[target.id] = ast.literal_eval(node.value)
    if set(result) != set(SETTINGS):
        raise ValueError("Не найдены четыре настройки в начале файла.")
    angles = result["TARGET_ANGLES"]
    if not isinstance(angles, dict) or set(angles) != set(PINS):
        raise ValueError("В TARGET_ANGLES нужны ровно GPIO16, 17, 5, 18, 19, 21.")
    for gpio in POSITIONAL_PINS:
        validate_target(gpio, angles[gpio])
    if type(angles[19]) is not int or angles[19] != 90:
        raise ValueError("GPIO19 непрерывный: оставьте 90. Его угловая калибровка заблокирована.")
    active = result["ACTIVE_GPIO"]
    if type(active) is not int or active not in POSITIONAL_PINS:
        raise ValueError("ACTIVE_GPIO: выберите 16, 17, 5, 18 или 21.")
    validate_target(active, angles[active])
    seconds = result["MOVE_SECONDS"]
    if type(seconds) not in (int, float) or not 0.1 <= seconds <= 3.0:
        raise ValueError("MOVE_SECONDS должен быть от 0.1 до 3.0 секунды.")
    if type(result["HOLD_AFTER_MOVE"]) is not bool:
        raise ValueError("HOLD_AFTER_MOVE должен быть True или False.")
    return result


class PreserveModemLinesSerial(serial.Serial):
    # Не переключаем RTS/DTR по отдельности: это может сбрасывать ESP32.
    # Драйвер USB всё равно способен вызвать сброс; звенья нужно подпереть.
    def _update_dtr_state(self):
        pass

    def _update_rts_state(self):
        pass


class Controller:
    def __init__(self, port):
        self.port = port

    def exchange(self, command, expected):
        self.port.write((command + "\n").encode("ascii"))
        self.port.flush()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            reply = self.port.readline().decode(errors="replace").strip()
            if not reply:
                continue
            if "ERR" in reply or "READY" in reply:
                raise RuntimeError("Плата сообщила ошибку/перезапуск: " + reply)
            if expected(reply):
                return reply
        raise RuntimeError("Нет подтверждения: " + command)

    def status(self):
        line = self.exchange("STATUS", lambda value: value.startswith("STATUS "))
        parts = re.findall(r"(\d+):(\d+):(ON|OFF)", line)
        if tuple(int(part[0]) for part in parts) != PINS:
            raise RuntimeError("Нужна прежняя esp32-calibration с командами A/S/STOP: " + line)
        return line, tuple(part[2] == "ON" for part in parts)

    def off(self):
        self.exchange("STOP", lambda value: value == "OK ALL STOPPED")
        line, enabled = self.status()
        if any(enabled):
            raise RuntimeError("Не подтверждено отключение всех сигналов: " + line)
        print("Все сигналы OFF. Напряжение питания остаётся.", flush=True)

    def test(self, gpio, angle, seconds, hold, wait=None):
        self.off()
        validate_target(gpio, angle)
        if type(seconds) not in (int, float) or not 0.1 <= seconds <= 3.0:
            raise ValueError("Допустимое время теста: 0.1..3.0 секунды.")
        axis = PINS.index(gpio)
        expected = f"OK ACTIVE {axis} GPIO {gpio} ANGLE {angle}"
        self.exchange(f"A {axis} {angle}", lambda value: value == expected)
        line, enabled = self.status()
        if enabled != tuple(pin == gpio for pin in PINS):
            raise RuntimeError("Включён не только выбранный привод: " + line)
        print(f"GPIO{gpio}: задано {angle}°, только этот привод ON, окно {seconds} с.", flush=True)
        completed = (wait or wait_for_test)(seconds)
        if not completed or not hold:
            self.off()
        else:
            print("Только выбранный привод удерживает. OFF — отключить.", flush=True)


def wait_for_test(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        timeout = max(0, min(0.05, deadline - time.monotonic()))
        readable, _, _ = select.select([sys.stdin], [], [], timeout)
        if readable:
            command = sys.stdin.readline()
            if not command or command.strip().upper() in ("Q", "EXIT"):
                raise EOFError
            if command.strip().upper() in ("OFF", "STOP"):
                return False
            print("Сейчас идёт тест. OFF и Enter — остановить.", flush=True)
    return True


def drop_privileges():
    if os.geteuid() == 0:
        uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
        if uid <= 0 or gid <= 0:
            raise RuntimeError("Не найден обычный пользователь для сессии.")
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)


def ensure_serial_access():
    """Request access for this run only; leave groups and USB rules unchanged."""
    if not Path(PORT).exists():
        raise RuntimeError("ESP32 не найдена по USB. Проверьте кабель и подключение платы.")
    if os.geteuid() == 0 or os.access(PORT, os.R_OK | os.W_OK):
        return
    print("Linux требует разрешение на USB-порт ESP32.", flush=True)
    print("Введите пароль Linux в этом терминале. Символы при вводе не отображаются.", flush=True)
    print("Права администратора будут сброшены после открытия порта. Движений без GO нет.", flush=True)
    os.execvp("sudo", ["sudo", sys.executable, "-B", "-u",
                        str(Path(__file__).resolve()), *sys.argv[1:]])
    raise RuntimeError("Не удалось получить доступ к USB-порту.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="проверить настройки БЕЗ робота")
    args = parser.parse_args()
    settings = load_settings()
    if args.check:
        print("Настройки корректны. USB не открывался, команды не отправлялись.")
        print(settings)
        return
    if not sys.stdin.isatty():
        raise SystemExit("Запустите задачу VS Code «ESP32: Python — калибровка по одному».")
    ensure_serial_access()
    print("ПОДОПРИТЕ ВСЕ ЗВЕНЬЯ. При старте сигналы всех серв будут отключены.", flush=True)
    port = PreserveModemLinesSerial(port=None, baudrate=BAUD, timeout=0.1,
                                   write_timeout=1, exclusive=True)
    port.port = PORT
    controller = None
    try:
        port.open()
        attrs = termios.tcgetattr(port.fileno())
        attrs[2] &= ~termios.HUPCL
        termios.tcsetattr(port.fileno(), termios.TCSANOW, attrs)
        drop_privileges()
        time.sleep(1)
        port.read_all()
        controller = Controller(port)
        print(controller.status()[0], flush=True)
        controller.off()
        print("GO — прочитать настройки из файла и проверить выбранный привод.")
        print("S 17 85 — только GPIO17 на 85°; OFF — снять сигналы; STATUS; Q — выход.")
        print("Меняйте углы в файле, Ctrl+S, затем GO. Без GO движения нет.")
        while True:
            try:
                command = input("Калибровка> ").strip().upper()
                if command in ("Q", "EXIT"):
                    break
                if not command:
                    continue
                if command in ("OFF", "STOP"):
                    controller.off()
                    continue
                if command == "STATUS":
                    print(controller.status()[0], flush=True)
                    continue
                if command == "GO" or command.startswith("S "):
                    controller.off()
                    settings = load_settings()
                    gpio = settings["ACTIVE_GPIO"]
                    angle = settings["TARGET_ANGLES"][gpio]
                    if command.startswith("S "):
                        parts = command.split()
                        if len(parts) != 3:
                            raise ValueError("Формат: S <GPIO> <угол>, например S 17 85")
                        gpio, angle = map(int, parts[1:])
                    controller.test(gpio, angle, settings["MOVE_SECONDS"], settings["HOLD_AFTER_MOVE"])
                else:
                    print("Команды: GO, S <GPIO> <угол>, OFF, STATUS, Q")
            except (ValueError, SyntaxError) as error:
                controller.off()
                print("Настройки/команда отклонены: " + str(error), flush=True)
            except KeyboardInterrupt:
                controller.off()
                print("Тест прерван, все сигналы OFF. Q — выйти.", flush=True)
            except EOFError:
                break
    finally:
        if controller is not None and port.is_open:
            try:
                controller.off()
            except Exception as error:
                print("НЕ УДАЛОСЬ подтвердить OFF: " + str(error), flush=True)
                print("Поддержите руку и отключите питание серв физически.", flush=True)
        if port.is_open:
            port.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit("Калибровка остановлена: " + str(error))
