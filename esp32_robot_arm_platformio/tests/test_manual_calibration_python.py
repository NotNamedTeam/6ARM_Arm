"""Protocol/policy tests only. No USB or real actuator is opened."""

from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("manual_calibration", ROOT / "manual_calibration.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class FakePort:
    def __init__(self):
        self.angles = [0, 87, 75, 30, 90, 0]
        self.enabled = set()
        self.commands = []
        self.replies = []

    def write(self, data):
        command = data.decode().strip()
        self.commands.append(command)
        parts = command.split()
        if command == "STOP":
            self.enabled.clear()
            reply = "OK ALL STOPPED"
        elif command == "STATUS":
            reply = "STATUS" + "".join(
                f" {pin}:{self.angles[i]}:{'ON' if i in self.enabled else 'OFF'}"
                for i, pin in enumerate(app.PINS))
        elif parts[0] == "A":
            axis, angle = map(int, parts[1:])
            self.angles[axis] = angle
            self.enabled.add(axis)
            reply = f"OK ACTIVE {axis} GPIO {app.PINS[axis]} ANGLE {angle}"
        else:
            reply = "ERR unexpected command"
        self.replies.append((reply + "\n").encode())

    def flush(self):
        pass

    def readline(self):
        return self.replies.pop(0) if self.replies else b""


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.output = redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_one_joint_then_all_off(self):
        port = FakePort()
        port.enabled = {0, 1, 2, 3, 5}
        app.Controller(port).test(17, 85, 1.2, False, wait=lambda _: True)
        self.assertEqual(port.enabled, set())
        self.assertEqual([c for c in port.commands if c.startswith("A ")], ["A 1 85"])
        self.assertEqual(port.commands[0], "STOP")

    def test_hold_only_selected_joint(self):
        port = FakePort()
        controller = app.Controller(port)
        controller.test(5, 76, 1.2, True, wait=lambda _: True)
        self.assertEqual(port.enabled, {2})
        controller.off()
        self.assertEqual(port.enabled, set())

    def test_cancel_detaches_even_when_hold_requested(self):
        port = FakePort()
        app.Controller(port).test(18, 31, 1.2, True, wait=lambda _: False)
        self.assertEqual(port.enabled, set())

    def test_continuous_rotation_never_enabled(self):
        port = FakePort()
        with self.assertRaises(ValueError):
            app.Controller(port).test(19, 95, 1.2, False, wait=lambda _: True)
        self.assertFalse(any(c.startswith("A ") for c in port.commands))

    def test_bad_angle_and_duration_rejected_before_attach(self):
        for gpio, angle, seconds in ((17, 181, 1), (16, 271, 1), (17, 85, 30), (17, True, 1)):
            port = FakePort()
            with self.assertRaises(ValueError):
                app.Controller(port).test(gpio, angle, seconds, False, wait=lambda _: True)
            self.assertFalse(any(c.startswith("A ") for c in port.commands))

    def test_rereads_edited_target_without_executing_file(self):
        first = "TARGET_ANGLES={16:0,17:87,5:75,18:30,19:90,21:0}\nACTIVE_GPIO=17\nMOVE_SECONDS=1.2\nHOLD_AFTER_MOVE=False\n"
        second = first.replace("17:87", "17:85") + "raise RuntimeError('must not execute')\n"
        with patch.object(Path, "read_text", side_effect=[first, second]):
            self.assertEqual(app.load_settings()["TARGET_ANGLES"][17], 87)
            self.assertEqual(app.load_settings()["TARGET_ANGLES"][17], 85)

    def test_check_mode_does_not_open_usb(self):
        with patch.object(app.sys, "argv", ["manual_calibration.py", "--check"]):
            with patch.object(app, "PreserveModemLinesSerial") as constructor:
                with patch.object(app, "ensure_serial_access") as access:
                    app.main()
                    access.assert_not_called()
                constructor.assert_not_called()

    def test_missing_device_does_not_request_sudo(self):
        with patch.object(Path, "exists", return_value=False):
            with patch.object(app.os, "execvp") as execute:
                with self.assertRaises(RuntimeError):
                    app.ensure_serial_access()
                execute.assert_not_called()

    def test_accessible_device_does_not_request_sudo(self):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(app.os, "geteuid", return_value=1000):
                with patch.object(app.os, "access", return_value=True):
                    with patch.object(app.os, "execvp") as execute:
                        app.ensure_serial_access()
                        execute.assert_not_called()

    def test_permission_denied_relaunches_only_current_program(self):
        class RelaunchRequested(Exception):
            pass

        with patch.object(Path, "exists", return_value=True):
            with patch.object(app.os, "geteuid", return_value=1000):
                with patch.object(app.os, "access", return_value=False):
                    with patch.object(app.sys, "argv", [str(ROOT / "manual_calibration.py")]):
                        with patch.object(app.os, "execvp", side_effect=RelaunchRequested) as execute:
                            with self.assertRaises(RelaunchRequested):
                                app.ensure_serial_access()
                            command, arguments = execute.call_args.args
                            self.assertEqual(command, "sudo")
                            self.assertEqual(arguments, ["sudo", app.sys.executable, "-B", "-u",
                                                         str(ROOT / "manual_calibration.py")])


if __name__ == "__main__":
    unittest.main()
