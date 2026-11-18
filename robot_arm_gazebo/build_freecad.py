"""Create separate native part documents and a linked FreeCAD assembly.

Run with the downloaded FreeCAD Python runtime, not system Python.
The assembly placement of the wrist and servo brackets is a draft fit.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT.parents[1] / 'tools/freecad'
sys.path.insert(0, str(APP_ROOT / 'squashfs-root/usr/lib'))
import FreeCAD as App
import Part
import Mesh
import AssemblyApp

DEST = ROOT / 'freecad'
PARTS = DEST / 'parts'
PARTS.mkdir(parents=True, exist_ok=True)
V = App.Vector
R = App.Rotation
P = App.Placement
IDENTITY = R()
Y_UP_TO_Z_UP = P(V(), R(V(1, 0, 0), 90))


def plc(x=0, y=0, z=0, rotation=None):
    return P(V(x, y, z), rotation or IDENTITY)


def rotation_matrix(rows):
    matrix = App.Matrix()
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            setattr(matrix, 'A%d%d' % (i + 1, j + 1), value)
    return R(matrix)


def create_part(path, index, reuse=False):
    filename = PARTS / (path.stem + '.FCStd')
    if reuse and filename.exists():
        doc = App.openDocument(str(filename))
        return doc.getObject('Model'), doc.getObject('SourceMesh'), filename
    doc = App.newDocument('Part_%02d' % index)
    doc.Label = path.stem
    imported = doc.addObject('Mesh::Feature', 'SourceMesh')
    imported.Label = 'Original STL / mm'
    imported.Mesh = Mesh.Mesh(str(path))
    shell = Part.Shape()
    shell.makeShapeFromMesh(imported.Mesh.Topology, 0.01)
    if not shell.isClosed():
        raise RuntimeError('STL does not form a closed shell: ' + path.name)
    solid = Part.makeSolid(shell)
    if not solid.isValid():
        raise RuntimeError('Invalid solid: ' + path.name)
    model = doc.addObject('Part::Feature', 'Model')
    model.Label = path.stem
    model.Shape = solid
    model.addProperty('App::PropertyString', 'SourceSTL', 'Source')
    model.SourceSTL = path.name
    model.addProperty('App::PropertyString', 'Attribution', 'Source')
    model.Attribution = 'BasementMaker / Thingiverse 4604664 / CC Attribution'
    model.addProperty('App::PropertyString', 'Representation', 'Source')
    model.Representation = 'Faceted solid converted in FreeCAD; no parametric design history'
    if App.GuiUp:
        imported.Visibility = False
        model.ViewObject.ShapeColor = (0.78, 0.83, 0.88)
        model.ViewObject.DisplayMode = 'Flat Lines'
    doc.recompute()
    doc.saveAs(str(filename))
    return model, imported, filename


def build():
    sources = {}
    report = {'freecad_version': '.'.join(App.Version()[:3]),
              'source': 'BasementMaker / Thingiverse 4604664 / CC Attribution',
              'units': 'mm', 'parts': [], 'assembly_status': 'draft_fit',
              'unverified': ['wrist attachment fit', 'base servo bracket positions',
                             'hardware clearance', 'servo models and joint limits'],
              'instances': []}
    for index, path in enumerate(sorted((ROOT / 'meshes').glob('*.stl')), 1):
        name = path.stem
        model, imported, filename = create_part(path, index, '--reuse-parts' in sys.argv)
        sources[name] = model
        report['parts'].append({'file': str(filename.relative_to(ROOT)),
                                'facets': imported.Mesh.CountFacets,
                                'valid_solid': True,
                                'volume_mm3': model.Shape.Volume})
        print('Saved %02d/27: %s' % (index, filename.name), flush=True)

    doc = App.newDocument('RobotArm_Assembly')
    doc.Label = 'Robot arm / draft assembly'
    root = doc.addObject('Assembly::AssemblyObject', 'Assembly')
    root.Type = 'Assembly'
    root.Label = 'Robot arm / linked parts'
    root.addProperty('App::PropertyString', 'AssemblyStatus', 'Review')
    root.AssemblyStatus = 'Draft geometry; wrist and servo bracket fit require review'
    root.addProperty('App::PropertyString', 'SourceAttribution', 'Source')
    root.SourceAttribution = report['source']
    root.addProperty('App::PropertyString', 'SimulationStatus', 'Review')
    root.SimulationStatus = 'Static geometry export; dynamics and joint limits are not configured'
    root.newObject('Assembly::JointGroup', 'Joints')
    groups = {}
    colors = {'base': (0.65, .69, .74), 'turntable': (.82, .32, .23),
              'upper_arm': (.90, .48, .26), 'forearm': (.28, .47, .72),
              'wrist_pitch': (.31, .65, .62), 'gripper_body': (.49, .55, .76),
              'jaw_left': (.85, .64, .27), 'jaw_right': (.85, .64, .27)}
    for name in colors:
        group = doc.addObject('App::Part', name)
        group.Label = name.replace('_', ' ')
        group.addProperty('App::PropertyString', 'ExportGroup', 'Gazebo')
        group.ExportGroup = name
        root.addObject(group)
        groups[name] = group
    # External App::Link references need a saved owner document to be relative.
    doc.saveAs(str(DEST / 'RobotArm_Assembly.FCStd'))

    def add(source_name, group_name, placement, suffix=''):
        source = sources[source_name]
        obj = doc.addObject('App::Link', 'Instance_%02d' % (len(report['instances']) + 1))
        obj.setLink(source)
        obj.Label = source_name + (' / ' + suffix if suffix else '')
        groups[group_name].addObject(obj)
        obj.LinkPlacement = Y_UP_TO_Z_UP.multiply(placement)
        obj.addProperty('App::PropertyString', 'SourceSTL', 'Source')
        obj.SourceSTL = source_name + '.stl'
        if App.GuiUp:
            obj.ViewObject.ShapeColor = colors[group_name]
        report['instances'].append({'name': obj.Name, 'part': source_name,
                                     'group': group_name, 'suffix': suffix})
        return obj

    # The source meshes use Y as the upward axis. Apply one final rotation
    # to every placement to obtain the Z-up frame used by Gazebo.
    add('BASE_-_base', 'base', plc())
    for i in range(4):
        radial = plc(rotation=R(V(0, 1, 0), i * 90))
        add('BASE_-_support_-_stand', 'base', radial.multiply(plc(0, 0, 44.5)), str(i + 1))
        add('BASE_-_support_-_spacer', 'base', radial.multiply(plc(-7.5, 47, 44.5)), str(i + 1))
    add('BASE_-_support', 'base', plc(0, 45, 0), 'lower ring')
    add('BASE_-_support', 'base', plc(0, 51.4, 0), 'upper ring')
    add('BASE_-_servo_-_stand', 'base', plc(-27, 45, 0, R(V(0, 0, 1), -90)))
    add('BASE_-_servo_-_stand_-_wire', 'base', plc(27, 45, 0, R(V(0, 0, 1), -90)))

    platform_top = 51.2
    shoulder = platform_top + 38.4825
    elbow = shoulder + 60.0
    wrist_pitch = elbow + 60.5125
    wrist_plate = wrist_pitch + 30.0
    wrist_roll = wrist_plate + 2.0 + 32.65 + 3.0
    report['axis_heights_mm'] = {'base_yaw': 47.2, 'shoulder': shoulder,
                                'elbow': elbow, 'wrist_pitch': wrist_pitch,
                                'wrist_roll': wrist_roll}
    add('BASE_-_platform', 'turntable', plc(0, 47.2, 0, R(V(0, 1, 0), 90)))
    shoulder_rotation = rotation_matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0)))
    shoulder_fit = plc(20.4, shoulder + 10, -9.92, shoulder_rotation)
    for half in ('bottom', 'top'):
        add('AXIS1_-_servoEnclosure_-_' + half, 'turntable', shoulder_fit)
    flip_z = R(V(0, 0, 1), 180)
    add('AXIS1_-_hornArm', 'upper_arm', plc(27.45, shoulder, 0, flip_z))
    add('AXIS1_-_pivotArm', 'upper_arm', plc(-23.45, shoulder, 0, flip_z))
    forearm_rotation = rotation_matrix(((0, 0, 1), (-1, 0, 0), (0, -1, 0)))
    forearm_fit = plc(20.4, elbow - 10, 9.92, forearm_rotation)
    for half in ('bottom', 'top'):
        add('AXIS2_-_servoEnclosure_-_' + half, 'forearm', forearm_fit)
    add('AXIS3_-_hornArm', 'wrist_pitch', plc(20.45, wrist_pitch, 0, flip_z))
    add('AXIS3_-_pivotArm', 'wrist_pitch', plc(-16.2, wrist_pitch + 30, 0, flip_z))
    add('WRIST_-_base', 'wrist_pitch', plc(0, wrist_plate, 0))
    wrist_fit = plc(-7.9026, wrist_plate + 2 + 15.6854, 14.0646, R(V(1, 0, 0), -90))
    for half in ('bottom', 'top'):
        add('WRIST_-_servoEnclosure_-_' + half, 'wrist_pitch', wrist_fit)

    gripper_fit = plc(0, wrist_roll + 39, -8.675, flip_z)
    add('GRIPPER_-_wristHornAttachment', 'gripper_body', gripper_fit.multiply(plc(0, 35, 8.675)))
    for half in ('bottom', 'top'):
        add('GRIPPER_-_servoEnclosure_-_' + half, 'gripper_body', gripper_fit)
    back_frame = gripper_fit.multiply(plc(0, 7.49, 8.675, R(V(1, 0, 0), 180)))
    add('GRIPPER_-_plate_-_back', 'gripper_body', back_frame)
    add('GRIPPER_-_plate_-_front', 'gripper_body', back_frame.multiply(plc(0, 6.2, 0)))
    add('GRIPPER_-_gear_-_servo', 'gripper_body', back_frame.multiply(plc(0, 2.1, 0)))
    flip_y = R(V(0, 1, 0), 180)
    add('GRIPPER_-_gear_-_rack', 'jaw_left', back_frame.multiply(plc(0, 2.1, 12.75)))
    add('GRIPPER_-_spacer_-_jaw', 'jaw_left', back_frame.multiply(plc(0, 8.2, 14.625)))
    add('GRIPPER_-_jaw', 'jaw_left', back_frame.multiply(plc(.75, 10.6, 12.75, flip_y)))
    add('GRIPPER_-_gear_-_rack', 'jaw_right', back_frame.multiply(plc(0, 2.1, -12.75, flip_y)))
    add('GRIPPER_-_spacer_-_jaw', 'jaw_right', back_frame.multiply(plc(0, 8.2, -14.625, flip_y)))
    add('GRIPPER_-_jaw', 'jaw_right', back_frame.multiply(plc(-.75, 10.6, -12.75)))

    doc.recompute()
    assembly_file = DEST / 'RobotArm_Assembly.FCStd'
    doc.saveAs(str(assembly_file))
    report['assembly'] = str(assembly_file.relative_to(ROOT))
    (DEST / 'build_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Saved linked assembly: %s (%d instances)' % (assembly_file, len(report['instances'])), flush=True)
    return doc


if __name__ == '__main__':
    build()
