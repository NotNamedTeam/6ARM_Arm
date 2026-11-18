"""Gazebo-only commands and measured joint-motion demonstration. No serial/Wi-Fi I/O."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import math
import subprocess
import threading
import time

from gz.transport import Node
from gz.msgs.double_pb2 import Double
from gz.msgs.model_pb2 import Model
from gz.msgs.entity_pb2 import Entity
from gz.msgs.entity_factory_pb2 import EntityFactory
from gz.msgs.world_control_pb2 import WorldControl
from google.protobuf.text_format import MessageToString

ROOT = Path(os.environ.get('ROBOT_ARM_ROOT', str(Path(__file__).resolve().parent)))
WORLD = '/world/freecad_robot_arm'
MODEL_NAME = 'robot_arm_freecad'
BASE = '/model/' + MODEL_NAME + '/joint/'


class Arm:
    def __init__(self):
        self.node = Node()
        self.states = {}
        self.lock = threading.Lock()
        self.publishers = {}
        self.results = []
        self.stopping = False
        self.config = {j['name']: j for j in json.loads(
            (ROOT / 'freecad/joint_setup.json').read_text())['joints']}
        self.node.subscribe(Model, '/robot_arm/joint_states', self.on_state)

    def on_state(self, msg):
        with self.lock:
            for joint in msg.joint:
                self.states[joint.name] = {'position': joint.axis1.position, 'velocity': joint.axis1.velocity}

    def close(self):
        # Stop the C++ callback thread before Python finalizes its objects.
        self.node.unsubscribe('/robot_arm/joint_states')
        time.sleep(.1)
        self.publishers.clear()
        self.node = None

    def service(self, suffix, request, timeout=5000):
        # Use the native Gazebo CLI for services; topic publishing and
        # state feedback remain in Python.
        request_text = ('pause: false' if suffix == '/control' and not request.pause
                        else MessageToString(request))
        attempts = 3 if suffix == '/control' else 1
        for attempt in range(attempts):
            reply = subprocess.run(['gz', 'service', '-s', WORLD + suffix,
                                    '--reqtype', request.DESCRIPTOR.full_name,
                                    '--reptype', 'gz.msgs.Boolean', '--timeout', str(timeout),
                                    '--req', request_text], capture_output=True, text=True,
                                    timeout=timeout/1000 + 4)
            if reply.returncode == 0 and 'data: true' in reply.stdout:
                return
            if attempt + 1 < attempts:
                time.sleep(.5)
        raise RuntimeError('Gazebo service failed: ' + suffix)

    def reload(self):
        # One running Gazebo instance is reused; all content comes from the
        # assembly exported by FreeCAD, not from the original print STL files.
        self.service('/control', WorldControl(pause=False))
        entity = Entity(name=MODEL_NAME, type=Entity.MODEL)
        self.service('/remove/blocking', entity)
        factory = EntityFactory(sdf_filename=str(ROOT / 'export/robot_arm_freecad/model.sdf'),
                                name=MODEL_NAME, allow_renaming=False)
        self.service('/create/blocking', factory)
        print('Обновлённая подвижная сборка загружена в текущее окно Gazebo.', flush=True)

    def publish(self, joint, value, velocity=False):
        key = joint + ('/cmd_vel' if velocity else '/0/cmd_pos')
        if key not in self.publishers:
            self.publishers[key] = self.node.advertise(BASE + key, Double)
            deadline = time.monotonic() + 5
            while not self.publishers[key].has_connections() and time.monotonic() < deadline:
                time.sleep(.05)
            if not self.publishers[key].has_connections():
                raise RuntimeError('No Gazebo subscriber connected: ' + BASE + key)
        if not self.publishers[key].publish(Double(data=float(value))):
            raise RuntimeError('Gazebo rejected publishing to ' + BASE + key)

    def targets(self, values):
        for joint, value in values.items():
            self.publish(joint, value)
        # Repeat once after topic discovery; only the target changes, and
        # Gazebo's controller moves continuously at the configured speed.
        time.sleep(.15)
        for joint, value in values.items():
            self.publish(joint, value)

    def wait_ready(self, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                if all(name in self.states for name in self.config):
                    return
            time.sleep(.05)
        raise RuntimeError('Joint-state feedback was not received from Gazebo')

    def settle(self, targets, timeout=25):
        deadline = time.monotonic() + timeout
        stable_since = None
        while time.monotonic() < deadline:
            with self.lock:
                snapshot = dict(self.states)
            errors = {name: abs(snapshot.get(name, {}).get('position', float('inf')) - value)
                      for name, value in targets.items()}
            settled = all(
                error < (.0006 if 'finger_' in name else math.radians(1.0))
                and abs(snapshot[name]['velocity']) < (.002 if 'finger_' in name else .03)
                for name, error in errors.items())
            if settled:
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since >= .3:
                    return snapshot
            else:
                stable_since = None
            if self.stopping:
                raise KeyboardInterrupt
            time.sleep(.05)
        raise RuntimeError('Joints did not settle: ' + str({
            name: {'position_error': error, 'velocity': snapshot.get(name, {}).get('velocity')}
            for name, error in errors.items()}))

    def move(self, label, targets):
        print(label, flush=True)
        with self.lock:
            start = {name: self.states[name]['position'] for name in targets}
        # Smoothstep's peak derivative is 1.5. Keep reference speed below
        # the configured joint limit, including simultaneous movements.
        duration = max(.5, max(1.7 * abs(target - start[name]) / self.config[name]['speed']
                               for name, target in targets.items()))
        begin = time.monotonic()
        while True:
            fraction = min((time.monotonic() - begin) / duration, 1.0)
            blend = fraction * fraction * (3 - 2 * fraction)
            for name, target in targets.items():
                self.publish(name, start[name] + blend * (target - start[name]))
            if fraction >= 1.0:
                break
            time.sleep(.04)
        self.targets(targets)
        actual = self.settle(targets)
        self.results.append({'phase': label, 'targets': targets,
                             'measured': {name: actual[name]['position'] for name in targets}})
        print('  Подтверждено по показаниям суставов Gazebo.', flush=True)
        for name, target in targets.items():
            factor, unit = (1000, 'мм') if 'finger_' in name else (180/math.pi, '°')
            print(f'    {name}: цель {target*factor:.2f}{unit}; '
                  f'факт {actual[name]["position"]*factor:.2f}{unit}', flush=True)
        time.sleep(.65)

    def gripper(self, degrees):
        angle = min(max(math.radians(degrees), 0), .017/.0085)
        return {'gripper_joint': angle, 'finger_left_joint': angle*.0085,
                'finger_right_joint': angle*.0085}

    def stop_roll(self):
        self.publish('wrist_roll_joint', 0, velocity=True)
        time.sleep(.1)
        self.publish('wrist_roll_joint', 0, velocity=True)

    def roll_cycle(self):
        """Use measured rotation, not a wall-clock sleep, at reduced real-time factor."""
        self.wait_ready()
        self.stop_roll()
        readings=[]
        try:
            for direction in (1,-1):
                with self.lock:
                    start=self.states['wrist_roll_joint']['position']
                deadline=time.monotonic()+15
                while True:
                    self.publish('wrist_roll_joint', direction*.6, velocity=True)
                    with self.lock:
                        actual=self.states['wrist_roll_joint']['position']
                    if direction*(actual-start)>=1.0:
                        readings.append({'start':start,'end':actual,'direction':direction})
                        print(f'  Кисть: подтверждено {math.degrees(actual-start):.1f}°.',flush=True)
                        break
                    if time.monotonic()>deadline:
                        raise RuntimeError(f'Wrist did not rotate: start={start}, actual={actual}, direction={direction}')
                    time.sleep(.05)
                self.stop_roll()
                time.sleep(.3)
            self.results.append({'phase':'continuous wrist measured +/-1 radian', 'readings':readings})
        finally:
            self.stop_roll()

    def home(self):
        self.service('/control', WorldControl(pause=False))
        target = {name: 0 for name in ('base_yaw_joint', 'shoulder_joint', 'elbow_joint', 'wrist_pitch_joint')}
        target.update(self.gripper(0))
        self.stop_roll()
        self.move('Возврат позиционных суставов в вертикальную позу, захват открыт.', target)

    def demo(self):
        self.wait_ready()
        self.service('/control', WorldControl(pause=False))
        report = {'result': 'running', 'source': 'Gazebo joint-state feedback',
                  'hardware_connection': 'none',
                  'started_at': datetime.now(timezone.utc).isoformat(),
                  'model_sha256': hashlib.sha256(
                      (ROOT / 'export/robot_arm_freecad/model.sdf').read_bytes()).hexdigest(),
                  'phases': self.results,
                  'limits_status': 'approximate command ranges; not measured mechanical stops',
                  'settle_requirement': 'error < 1 degree (fingers 0.6 mm), speed < 0.03 rad/s (fingers 2 mm/s), for 0.3 s'}
        report_path = ROOT / 'export/motion_test.json'
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        try:
            self.home()
            self.move('Основание: 0° → 90°.', {'base_yaw_joint': math.radians(90)})
            self.move('Основание: 90° → 0°.', {'base_yaw_joint': 0})
            for name, title in [('shoulder_joint', 'Плечо'), ('elbow_joint', 'Локоть'),
                                 ('wrist_pitch_joint', 'Наклон кисти')]:
                home=self.config[name]['home']
                sign=self.config[name].get('servo_direction_sign',1)
                for offset in (20, -20, 0):
                    self.move(f'{title}: абсолютный угол сервопривода {home + sign*offset}°.',
                              {name: math.radians(offset)})
            print('Поворот кисти: +0.6 рад/с и −0.6 рад/с, ход по обратной связи.', flush=True)
            self.roll_cycle()
            self.move('Захват: закрытие на 90° по сервоприводу (расчётный ход).', self.gripper(90))
            self.move('Захват: открытие.', self.gripper(0))
            combined = {'base_yaw_joint': math.radians(45), 'shoulder_joint': math.radians(15),
                        'elbow_joint': math.radians(-20), 'wrist_pitch_joint': math.radians(15)}
            combined.update(self.gripper(60))
            self.move('Совместное плавное движение суставов.', combined)
            self.home()
            report['result'] = 'passed'
            report['finished_at'] = datetime.now(timezone.utc).isoformat()
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            print('ГОТОВО: все суставы двигались, измерения сохранены; кисть остановлена.', flush=True)
        except BaseException as error:
            report.update(result='failed', error=str(error),
                          finished_at=datetime.now(timezone.utc).isoformat())
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            raise
        finally:
            self.stop_roll()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['reload', 'demo', 'status', 'home', 'stop', 'move', 'roll-test'])
    parser.add_argument('axis', nargs='?', choices=['base', 'shoulder', 'elbow', 'wrist_pitch', 'gripper'])
    parser.add_argument('angle', nargs='?', type=float)
    args = parser.parse_args()
    arm = Arm()
    try:
        if args.action == 'reload':
            arm.reload()
            arm.wait_ready()
            print('Получены состояния всех восьми механических суставов.', flush=True)
        elif args.action == 'demo':
            arm.demo()
        elif args.action == 'home':
            arm.wait_ready()
            arm.home()
        elif args.action == 'roll-test':
            arm.service('/control', WorldControl(pause=False))
            arm.roll_cycle()
        elif args.action == 'move':
            if args.axis is None or args.angle is None:
                parser.error('move requires an axis and an absolute servo angle in degrees')
            joint_name = {'base': 'base_yaw_joint', 'shoulder': 'shoulder_joint', 'elbow': 'elbow_joint',
                          'wrist_pitch': 'wrist_pitch_joint', 'gripper': 'gripper_joint'}[args.axis]
            definitions = json.loads((ROOT / 'freecad/joint_setup.json').read_text())['joints']
            config = next(j for j in definitions if j['name'] == joint_name)
            if not 0 <= args.angle <= config['servo_max']:
                parser.error('Angle outside configured servo range')
            value=math.radians(args.angle-config['home'])*config.get('servo_direction_sign',1)
            lower=config.get('lower',math.radians(-config['home']))
            upper=config.get('upper',math.radians(config['servo_max']-config['home']))
            if args.axis!='gripper' and not lower-1e-9 <= value <= upper+1e-9:
                parser.error('Angle outside the configured mechanical prototype range')
            target = arm.gripper(args.angle) if args.axis == 'gripper' else {joint_name:value}
            arm.wait_ready()
            arm.service('/control', WorldControl(pause=False))
            arm.move(f'{args.axis}: абсолютный угол {args.angle}°.', target)
        elif args.action == 'stop':
            arm.stop_roll()
            arm.wait_ready()
            with arm.lock:
                targets = {name: state['position'] for name, state in arm.states.items() if name != 'wrist_roll_joint'}
            arm.targets(targets)
        else:
            arm.wait_ready()
            with arm.lock:
                print(json.dumps(arm.states, indent=2))
    finally:
        arm.close()


if __name__ == '__main__':
    main()
