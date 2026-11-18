"""Store the robot joint graph and approximate servo limits in the FCStd assembly."""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import AssemblyApp


def configure(doc, project_root=None):
    project_root = Path(project_root) if project_root else ROOT
    heights = json.loads((project_root / 'freecad/build_report.json').read_text())['axis_heights_mm']
    # The pinion is a separate rotating link; the two racks are driven by the
    # same logical gripper command in the Gazebo-only control program.
    rotor = doc.getObject('gripper_rotor')
    if rotor is None:
        rotor = doc.addObject('App::Part', 'gripper_rotor')
        rotor.addProperty('App::PropertyString', 'ExportGroup', 'Gazebo')
        rotor.ExportGroup = 'gripper_rotor'
        rotor.Label = 'gripper pinion / servo'
        doc.getObject('Assembly').addObject(rotor)
        body = doc.getObject('gripper_body')
        for instance in list(body.Group):
            if getattr(instance, 'SourceSTL', '') == 'GRIPPER_-_gear_-_servo.stl':
                body.removeObject(instance)
                rotor.addObject(instance)

    finger_height = heights['wrist_roll'] + 31.51
    definitions = [
        dict(name='base_yaw_joint', parent='base', child='turntable', z=heights['base_yaw'],
             axis=[0, 0, 1], gpio=16, home=0, servo_max=270, speed=.65, effort=1.5, control_mode='force_pid'),
        dict(name='shoulder_joint', parent='turntable', child='upper_arm', z=heights['shoulder'],
             axis=[1, 0, 0], gpio=17, home=82, servo_max=180, speed=.45, effort=1.2),
        dict(name='elbow_joint', parent='upper_arm', child='forearm', z=heights['elbow'],
             axis=[1, 0, 0], gpio=5, home=75, servo_max=180, speed=.50, effort=1.2),
        dict(name='wrist_pitch_joint', parent='forearm', child='wrist_pitch', z=heights['wrist_pitch'],
             axis=[1, 0, 0], gpio=18, home=30, servo_max=180, speed=.55, effort=.20),
        dict(name='wrist_roll_joint', parent='wrist_pitch', child='gripper_body', z=heights['wrist_roll'],
             axis=[0, 0, 1], gpio=19, home=90, servo_max=180, speed=.8, effort=.20, continuous=True),
        dict(name='gripper_joint', parent='gripper_body', child='gripper_rotor', z=finger_height,
             axis=[0, 0, 1], gpio=21, home=0, servo_max=math.degrees(.017 / .0085),
             speed=.6, effort=.15, note='Estimated pinion pitch radius 8.5 mm; maximum rack travel 17 mm'),
        dict(name='finger_left_joint', parent='gripper_body', child='jaw_left', z=finger_height,
             axis=[-1, 0, 0], gpio=-1, home=0, servo_max=0, speed=.010, effort=8,
             kind='prismatic', lower=0, upper=.017),
        dict(name='finger_right_joint', parent='gripper_body', child='jaw_right', z=finger_height,
             axis=[1, 0, 0], gpio=-1, home=0, servo_max=0, speed=.010, effort=8,
             kind='prismatic', lower=0, upper=.017),
    ]
    joints = doc.getObject('Joints')
    for data in definitions:
        name = data['name']
        joint = doc.getObject(name) or joints.newObject('App::FeaturePython', name)
        kind = data.get('kind', 'revolute')
        continuous = data.get('continuous', False)
        lower = data.get('lower', -1e16 if continuous else math.radians(-data['home']))
        upper = data.get('upper', 1e16 if continuous else math.radians(data['servo_max'] - data['home']))
        props = [
            ('App::PropertyString', 'ExportJointType', kind),
            ('App::PropertyString', 'ParentBody', data['parent']),
            ('App::PropertyString', 'ChildBody', data['child']),
            ('App::PropertyVector', 'OriginMM', App.Vector(0, 0, data['z'])),
            ('App::PropertyVector', 'AxisVector', App.Vector(*data['axis'])),
            ('App::PropertyFloat', 'LowerLimitSI', lower),
            ('App::PropertyFloat', 'UpperLimitSI', upper),
            ('App::PropertyFloat', 'SpeedLimitSI', data['speed']),
            ('App::PropertyFloat', 'EffortLimitSI', data['effort']),
            ('App::PropertyBool', 'Continuous', continuous),
            ('App::PropertyInteger', 'GPIO', data['gpio']),
            ('App::PropertyFloat', 'ServoHomeDeg', data['home']),
            ('App::PropertyFloat', 'ServoMinDeg', 0),
            ('App::PropertyFloat', 'ServoMaxDeg', data['servo_max']),
            ('App::PropertyString', 'LimitStatus', data.get('note', 'Approximate command limits, not measured mechanical stops')),
            ('App::PropertyString', 'ControlMode', data.get('control_mode', 'force_pid')),
        ]
        for type_name, prop, value in props:
            if not hasattr(joint, prop):
                joint.addProperty(type_name, prop, 'Gazebo joint')
            setattr(joint, prop, value)
        joint.Label = name + (' / continuous velocity' if continuous else '')

    for group in [o for o in doc.Objects if hasattr(o, 'ExportGroup')]:
        child_joint = next((j for j in definitions if j['child'] == group.ExportGroup), None)
        origin = App.Vector(0, 0, child_joint['z']) if child_joint else App.Vector()
        if not hasattr(group, 'ExportFrameOriginMM'):
            group.addProperty('App::PropertyVector', 'ExportFrameOriginMM', 'Gazebo')
        group.ExportFrameOriginMM = origin
        if not hasattr(group, 'EstimatedHardwareMassKg'):
            group.addProperty('App::PropertyFloat', 'EstimatedHardwareMassKg', 'Gazebo')
        group.EstimatedHardwareMassKg = {'base': .075, 'turntable': .065, 'forearm': .078,
                                         'wrist_pitch': .013, 'gripper_body': .009}.get(group.ExportGroup, .002)

    root = doc.getObject('Assembly')
    root.SimulationStatus = 'Articulated Gazebo model; approximate limits and inertias; force PID servos with smooth targets'
    doc.recompute()
    doc.save()
    summary = {'source_fcstd': doc.FileName, 'joints': definitions,
               'pinion_radius_m': .0085, 'finger_travel_m': .017,
               'effective_print_density_kg_m3': 600,
               'status': 'approximate; mechanical stops, masses and servo directions not calibrated',
               'hardware_connection': 'none; Gazebo Transport only'}
    (project_root / 'freecad/joint_setup.json').write_text(json.dumps(summary, indent=2))
    return doc


if __name__ == '__main__':
    doc = App.openDocument(str(ROOT / 'freecad/RobotArm_Assembly.FCStd'))
    configure(doc)
    sys.path.insert(0, str(ROOT))
    import export_from_freecad
    export_from_freecad.export(doc)
