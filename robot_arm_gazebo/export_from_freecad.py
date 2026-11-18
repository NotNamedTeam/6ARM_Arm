"""Export the geometry of the active linked FreeCAD assembly to Gazebo.

No source STL is copied to the output: each mesh is tessellated from the
current FreeCAD solid and placed using the assembly's current placements.
"""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
import FreeCAD as App
import Mesh

ROOT = Path(__file__).resolve().parent
EXPORT = ROOT / 'export'
MODEL = EXPORT / 'robot_arm_freecad'
COLORS = {'base': '.65 .69 .74 1', 'turntable': '.82 .32 .23 1',
          'upper_arm': '.90 .48 .26 1', 'forearm': '.28 .47 .72 1',
          'wrist_pitch': '.31 .65 .62 1', 'gripper_body': '.49 .55 .76 1',
          'jaw_left': '.85 .64 .27 1', 'jaw_right': '.85 .64 .27 1'}


def save_xml(root, path):
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(str(path), encoding='utf-8', xml_declaration=True)


def export(doc=None, project_root=None):
    export_dir = Path(project_root) / 'export' if project_root else EXPORT
    model_dir = export_dir / 'robot_arm_freecad'
    doc = doc or App.ActiveDocument
    if doc is None or doc.getObject('Assembly') is None:
        raise RuntimeError('Open RobotArm_Assembly.FCStd before export')
    doc.recompute()
    mesh_dir = model_dir / 'meshes'
    mesh_dir.mkdir(parents=True, exist_ok=True)
    components = []
    sdf = ET.Element('sdf', version='1.10')
    model = ET.SubElement(sdf, 'model', name='robot_arm_freecad')
    articulated = any(hasattr(o, 'ExportJointType') for o in doc.Objects)
    ET.SubElement(model, 'static').text = 'false' if articulated else 'true'
    ET.SubElement(model, 'self_collide').text = 'false'
    for group in doc.Objects:
        if not hasattr(group, 'ExportGroup'):
            continue
        name = group.ExportGroup
        combined = Mesh.Mesh()
        hardware_meshes = []
        volume_mm3 = 0.0
        for instance in group.Group:
            if instance.TypeId != 'App::Link':
                continue
            if not hasattr(instance, 'Shape') or instance.Shape.isNull():
                raise RuntimeError('Missing FreeCAD solid for ' + instance.Label)
            # App::Link.Shape already includes the link/source placement.
            # Its containing App::Part/Assembly placements are separate.
            mesh = Mesh.Mesh(instance.Shape.tessellate(0.1))
            parent = instance.getParentGeoFeatureGroup()
            parent_placement = App.Placement()
            while parent is not None:
                parent_placement = parent.Placement.multiply(parent_placement)
                parent = parent.getParentGeoFeatureGroup()
            mesh.transform(parent_placement.toMatrix())
            hardware_proxy = getattr(instance, 'IsHardwareProxy', False)
            if not hardware_proxy:
                volume_mm3 += abs(instance.Shape.Volume)
            if articulated:
                frame = getattr(group, 'ExportFrameOriginMM', App.Vector())
                shift = App.Matrix()
                shift.move(-frame)
                mesh.transform(shift)
            scale = App.Matrix()
            scale.scale(.001, .001, .001)
            mesh.transform(scale)
            if hardware_proxy:
                hardware_meshes.append((instance.Name, mesh))
            else:
                combined.addMesh(mesh)
            components.append(instance.Label)
        if combined.CountFacets == 0:
            continue
        mesh_filename = name + ('_articulated.stl' if articulated else '.stl')
        combined.write(str(mesh_dir / mesh_filename))
        link = ET.SubElement(model, 'link', name=name)
        if articulated:
            frame = group.ExportFrameOriginMM
            ET.SubElement(link, 'pose').text = f'{frame.x*.001} {frame.y*.001} {frame.z*.001} 0 0 0'
            add_link_physics(link, combined, volume_mm3 * 600e-9 + group.EstimatedHardwareMassKg)
        visual = ET.SubElement(link, 'visual', name=name + '_visual')
        geometry = ET.SubElement(visual, 'geometry')
        mesh = ET.SubElement(geometry, 'mesh')
        ET.SubElement(mesh, 'uri').text = 'model://robot_arm_freecad/meshes/' + mesh_filename
        material = ET.SubElement(visual, 'material')
        ET.SubElement(material, 'ambient').text = COLORS.get(name, '.7 .7 .7 1')
        ET.SubElement(material, 'diffuse').text = COLORS.get(name, '.7 .7 .7 1')
        for hardware_name, hardware_mesh in hardware_meshes:
            hardware_file = name + '_' + hardware_name + '.stl'
            hardware_mesh.write(str(mesh_dir / hardware_file))
            hv = ET.SubElement(link, 'visual', name=hardware_name + '_visual')
            hm = ET.SubElement(ET.SubElement(hv, 'geometry'), 'mesh')
            ET.SubElement(hm, 'uri').text = 'model://robot_arm_freecad/meshes/' + hardware_file
            material = ET.SubElement(hv, 'material')
            ET.SubElement(material, 'ambient').text = '.12 .13 .15 1'
            ET.SubElement(material, 'diffuse').text = '.12 .13 .15 1'
    if len(components) == 0:
        raise RuntimeError('The assembly contains no exportable instances')
    if articulated:
        add_joints_and_controllers(model, doc)
    save_xml(sdf, model_dir / 'model.sdf')
    config = ET.Element('model')
    ET.SubElement(config, 'name').text = 'Robot arm / FreeCAD assembly'
    ET.SubElement(config, 'version').text = '0.1'
    ET.SubElement(config, 'sdf', version='1.10').text = 'model.sdf'
    author = ET.SubElement(config, 'author')
    ET.SubElement(author, 'name').text = 'Original parts: BasementMaker'
    ET.SubElement(config, 'description').text = 'CC Attribution. Exported from FreeCAD; approximate joint limits and inertias; fit and dynamics require calibration.'
    save_xml(config, model_dir / 'model.config')

    world_sdf = ET.Element('sdf', version='1.10')
    world = ET.SubElement(world_sdf, 'world', name='freecad_robot_arm')
    physics = ET.SubElement(world, 'physics', name='robot_physics', type='ignored')
    ET.SubElement(physics, 'max_step_size').text = '.0005'
    ET.SubElement(physics, 'real_time_factor').text = '1'
    ET.SubElement(world, 'plugin', filename='gz-sim-physics-system', name='gz::sim::systems::Physics')
    ET.SubElement(world, 'plugin', filename='gz-sim-user-commands-system', name='gz::sim::systems::UserCommands')
    ET.SubElement(world, 'plugin', filename='gz-sim-scene-broadcaster-system', name='gz::sim::systems::SceneBroadcaster')
    scene = ET.SubElement(world, 'scene')
    ET.SubElement(scene, 'ambient').text = '.65 .65 .65 1'
    ET.SubElement(scene, 'background').text = '.93 .94 .96 1'
    light = ET.SubElement(world, 'light', name='sun', type='directional')
    ET.SubElement(light, 'pose').text = '0 0 3 0 0 0'
    ET.SubElement(light, 'diffuse').text = '.85 .85 .85 1'
    ET.SubElement(light, 'direction').text = '-.5 -.3 -1'
    include = ET.SubElement(world, 'include')
    ET.SubElement(include, 'uri').text = 'model://robot_arm_freecad'
    ground = ET.SubElement(world, 'model', name='ground')
    ET.SubElement(ground, 'static').text = 'true'
    link = ET.SubElement(ground, 'link', name='ground')
    for tag in ('visual', 'collision'):
        item = ET.SubElement(link, tag, name='ground_' + tag)
        plane = ET.SubElement(ET.SubElement(item, 'geometry'), 'plane')
        ET.SubElement(plane, 'normal').text = '0 0 1'
        ET.SubElement(plane, 'size').text = '2 2'
        if tag == 'visual':
            material = ET.SubElement(item, 'material')
            ET.SubElement(material, 'ambient').text = '.76 .78 .8 1'
            ET.SubElement(material, 'diffuse').text = '.76 .78 .8 1'
    save_xml(world_sdf, export_dir / 'preview.sdf')
    gui_template = Path('/opt/ros/lyrical/opt/gz_sim_vendor/share/gz/gz-sim/gui/gui.config')
    if gui_template.exists():
        gui = gui_template.read_text()
        gui = gui.replace('name="quick_start" show_again="true"', 'name="quick_start" show_again="false"')
        gui = gui.replace('<camera_pose>-6 0 6 0 0.5 0</camera_pose>',
                          '<camera_pose>0.4 -0.5 0.38 0 0.32 2.246</camera_pose>')
        (export_dir / 'gui.config').write_text(gui)
    (export_dir / 'export_report.json').write_text(json.dumps({
        'source_fcstd': doc.FileName,
        'instances': len(components),
        'components': components,
        'representation': 'articulated assembly' if articulated else 'static visual assembly',
        'mesh_source': 'current FreeCAD solids and assembly placements',
        'units': 'metres',
    }, indent=2), encoding='utf-8')
    App.Console.PrintMessage('Exported %d FreeCAD instances to %s\n' % (len(components), model_dir))
    return export_dir / 'preview.sdf'


def add_link_physics(link, mesh, mass):
    bounds = mesh.BoundBox
    x, y, z = max(bounds.XLength, .002), max(bounds.YLength, .002), max(bounds.ZLength, .002)
    center = bounds.Center
    pose = f'{center.x} {center.y} {center.z} 0 0 0'
    inertia = ET.SubElement(link, 'inertial')
    ET.SubElement(inertia, 'pose').text = pose
    ET.SubElement(inertia, 'mass').text = str(max(mass, .003))
    values = {'ixx': mass*(y*y+z*z)/12, 'iyy': mass*(x*x+z*z)/12,
              'izz': mass*(x*x+y*y)/12, 'ixy': 0, 'ixz': 0, 'iyz': 0}
    tensor = ET.SubElement(inertia, 'inertia')
    for key, value in values.items():
        ET.SubElement(tensor, key).text = str(value)
    collision = ET.SubElement(link, 'collision', name=link.attrib['name'] + '_collision')
    ET.SubElement(collision, 'pose').text = pose
    box = ET.SubElement(ET.SubElement(collision, 'geometry'), 'box')
    ET.SubElement(box, 'size').text = f'{x} {y} {z}'


def add_joints_and_controllers(model, doc):
    mount = ET.SubElement(model, 'joint', name='world_mount', type='fixed')
    ET.SubElement(mount, 'parent').text = 'world'
    ET.SubElement(mount, 'child').text = 'base'
    for source in [o for o in doc.Objects if hasattr(o, 'ExportJointType')]:
        joint = ET.SubElement(model, 'joint', name=source.Name, type=source.ExportJointType)
        ET.SubElement(joint, 'parent').text = source.ParentBody
        ET.SubElement(joint, 'child').text = source.ChildBody
        p = source.OriginMM
        ET.SubElement(joint, 'pose', relative_to='__model__').text = f'{p.x*.001} {p.y*.001} {p.z*.001} 0 0 0'
        axis = ET.SubElement(joint, 'axis')
        a = source.AxisVector
        ET.SubElement(axis, 'xyz').text = f'{a.x} {a.y} {a.z}'
        limits = ET.SubElement(axis, 'limit')
        for key, value in [('lower', source.LowerLimitSI), ('upper', source.UpperLimitSI),
                           ('effort', source.EffortLimitSI), ('velocity', source.SpeedLimitSI)]:
            ET.SubElement(limits, key).text = str(value)
        dynamics = ET.SubElement(axis, 'dynamics')
        ET.SubElement(dynamics, 'damping').text = '.0005' if source.ExportJointType == 'revolute' else '.1'
        if source.Continuous:
            control = ET.SubElement(model, 'plugin', filename='gz-sim-joint-controller-system',
                                    name='gz::sim::systems::JointController')
            ET.SubElement(control, 'initial_velocity').text = '0'
        else:
            control = ET.SubElement(model, 'plugin', filename='gz-sim-joint-position-controller-system',
                                    name='gz::sim::systems::JointPositionController')
            force_mode = getattr(source, 'ControlMode', '') == 'force_pid'
            ET.SubElement(control, 'use_velocity_commands').text = 'false' if force_mode else 'true'
            if force_mode:
                gains = {'base_yaw_joint': (4, .05, .02),
                         'shoulder_joint': (20, 2, .012),
                         'elbow_joint': (8, 1, .003),
                         'wrist_pitch_joint': (1.6, .25, .0005),
                         'gripper_joint': (.05, .002, .00002)}
                p, i, d = gains.get(source.Name, (100, 1, .5))
                p = getattr(source, 'PositionPGain', p)
                i = getattr(source, 'PositionIGain', i)
                d = getattr(source, 'PositionDGain', d)
                integral_max = getattr(source, 'PositionIMax', source.EffortLimitSI * .5)
                for tag, value in [('p_gain', p), ('i_gain', i), ('d_gain', d),
                                   ('i_max', integral_max),
                                   ('i_min', -integral_max)]:
                    ET.SubElement(control, tag).text = str(value)
                ET.SubElement(control, 'cmd_max').text = str(source.EffortLimitSI)
                ET.SubElement(control, 'cmd_min').text = str(-source.EffortLimitSI)
            else:
                ET.SubElement(control, 'cmd_max').text = str(source.SpeedLimitSI)
                ET.SubElement(control, 'cmd_min').text = str(-source.SpeedLimitSI)
            ET.SubElement(control, 'initial_position').text = '0'
        ET.SubElement(control, 'joint_name').text = source.Name
    state = ET.SubElement(model, 'plugin', filename='gz-sim-joint-state-publisher-system',
                          name='gz::sim::systems::JointStatePublisher')
    ET.SubElement(state, 'topic').text = '/robot_arm/joint_states'
    for source in [o for o in doc.Objects if hasattr(o, 'ExportJointType')]:
        ET.SubElement(state, 'joint_name').text = source.Name
