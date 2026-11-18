"""Build a separate FreeCAD/Gazebo prototype of the carton labeler.

The existing MG996R elbow/wrist-pitch variant is the starting point.  Its
originals remain untouched.  Dimensions here are a layout, not print release.
"""
from pathlib import Path
import argparse
import json
import math
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'tools/freecad/squashfs-root/usr/lib'))
sys.path.insert(0, str(ROOT))
import FreeCAD as App
import Part
import AssemblyApp
import export_from_freecad

V, R, P = App.Vector, App.Rotation, App.Placement
parser = argparse.ArgumentParser()
parser.add_argument('--mg90s-roll', action='store_true', help='Use the original small wrist-roll enclosure')
args = parser.parse_args()
SOURCE = ROOT / 'variants/mg996r_valet_v1'
DEST = ROOT / ('variants/labeler_mg90s_n20_v2' if args.mg90s_roll
               else 'variants/labeler_mg996r_n20_v1')
PARTS = DEST / 'freecad/parts'
PARTS.mkdir(parents=True, exist_ok=True)
for source in (SOURCE / 'freecad/parts').glob('*.FCStd'):
    target = PARTS / source.name
    if not target.exists():
        shutil.copy2(source, target)


def save_part(name, shape, note):
    if shape.isNull() or not shape.isValid() or shape.Volume <= 0:
        raise RuntimeError('Invalid new CAD part: ' + name)
    doc = App.newDocument('Labeler_' + name)
    part = doc.addObject('Part::Feature', 'Model')
    part.Label = name
    part.Shape = shape.removeSplitter()
    part.addProperty('App::PropertyString', 'DesignNote')
    part.DesignNote = note
    doc.recompute()
    doc.saveAs(str(PARTS / (name + '.FCStd')))
    return doc, part


# The v1 option replaces the small wrist rotation cradle by an MG996R-size split cradle.
# Its shaft is shifted 10 mm in X so the full 66 mm case sits over the
# existing 62.9 mm wrist plate.  Four original outer holes remain accessible.
if not args.mg90s_roll:
    ref_doc = App.openDocument(str(PARTS / 'MG996R_reference.FCStd'))
    servo = ref_doc.getObject('Model')
    servo_pose = P(V(20, -9.92, 46.85), R())
    servo_shape = servo.Shape.copy()
    servo_shape.Placement = servo_pose.multiply(servo_shape.Placement)
    outer = Part.makeBox(66, 38, 46.9, V(-33, -19, 3))
    body_void = Part.makeBox(41.3, 20.3, 37.2, V(-41.05, -.23, -39.85))
    flange_void = Part.makeBox(54.6, 20.6, 3.2, V(-47.7, -.38, -14.35))
    shaft_void = Part.makeCylinder(8, 8, V(-10, 9.92, -3.5))
    void = body_void.fuse(flange_void).fuse(shaft_void)
    void.Placement = servo_pose.multiply(void.Placement)
    housing = outer.cut(void)
    for x in (-28.2, 28.2):
        for y in (-15, 15):
            housing = housing.cut(Part.makeCylinder(1.7, 47.2, V(x, y, 2.9)))
    rear = housing.common(Part.makeBox(80, 19, 48, V(-40, -19, 2.9)))
    front = housing.common(Part.makeBox(80, 19, 48, V(-40, 0, 2.9)))
    rear_doc, rear_part = save_part('WristMG996R_Rear', rear, 'Split case; four M3 mounting bores; fit is nominal')
    front_doc, front_part = save_part('WristMG996R_Front', front, 'Split case; servo flange and cable clearance require physical fit')

# Create an editable FreeCAD head document from the latest nip/peel concept.
# Replace the bare SM300 and its large clamps with an encoded 210:1 N20.
head = App.openDocument(str(ROOT / 'label_applicator/LabelApplicator_v5_SM300.FCStd'))
head_document_name = ('LabelApplicator_N20_40RPM.FCStd' if args.mg90s_roll
                      else 'LabelApplicator_N20_Encoder.FCStd')
head.saveAs(str(PARTS / head_document_name))
remove = {'SM300Body', 'SM300Shaft', 'MotorCoupling', 'MotorTerminals',
          'MotorSaddle', 'MotorClamp', 'MotorBase', 'MotorSupport',
          'WristAdapter', 'AdapterSpacer'}
for obj in list(head.Objects):
    if any(obj.Name == n or obj.Name.startswith(n + '0') for n in remove):
        head.removeObject(obj.Name)
drive = head.getObject('Drive')
drive.Label = ('04 N20 40 об/мин, 5 В, без подтверждённого энкодера'
               if args.mg90s_roll else '04 N20 210:1, 6 В, энкодер 12 CPR')
frame = head.getObject('Frame')

def add_head(name, label, shape, group, color):
    if not shape.isValid() or shape.Volume <= 0:
        raise RuntimeError('Invalid head body ' + name)
    obj = head.addObject('Part::Feature', name)
    obj.Label = label
    obj.Shape = shape.removeSplitter()
    group.addObject(obj)
    if App.GuiUp:
        obj.ViewObject.ShapeColor = color
    return obj

# The old shaft ended at x=19.5; the N20 D shaft runs 19.5..28.5 mm.
fy, fz = [float(v) for v in json.loads(
    (ROOT / 'label_applicator/concept_report_v5.json').read_text())['nip_centres_yz_mm']['drive']]
steel = (.62, .68, .74)
blue = (.25, .47, .70)
add_head('N20Gearbox', ('N20 40 об/мин — редуктор 10×12, ось Ø2,8' if args.mg90s_roll
                        else 'N20 210:1 — редуктор 10×12, ось Ø3'),
         Part.makeBox(9, 10, 12, V(28.5, fy-5, fz-6)), drive, (.80,.64,.25))
motor_body_length = 26 if args.mg90s_roll else 32
motor_shell_length = motor_body_length-9
add_head(('N20Motor40' if args.mg90s_roll else 'N20MotorEncoder'),
         ('N20 5 В/40 об/мин — условный габарит 10×12×26 без вала'
          if args.mg90s_roll else 'N20 с энкодером — габарит 10×12×32 без вала'),
         Part.makeBox(motor_shell_length, 10, 12, V(37.5, fy-5, fz-6)), drive, steel)
shaft_radius = 1.4 if args.mg90s_roll else 1.5
shaft_start = 18.5 if args.mg90s_roll else 19.5
shaft_length = 10 if args.mg90s_roll else 9
shaft = Part.makeCylinder(shaft_radius, shaft_length, V(shaft_start,fy,fz), V(1,0,0))
shaft = shaft.cut(Part.makeBox(shaft_length+.2, 3, 2,
                              V(shaft_start-.1,fy+shaft_radius-.45,fz-1)))
add_head('N20Dshaft', ('Выходной D-вал Ø2,8×10 (уточнить)' if args.mg90s_roll
                       else 'Выходной D-вал Ø3×9'), shaft, drive, steel)
coupling = Part.makeCylinder(3.5, 8, V(16.5,fy,fz), V(1,0,0))
coupling = coupling.cut(Part.makeCylinder(1.6,8.2,V(16.4,fy,fz),V(1,0,0)))
add_head('ShaftCoupling', 'Муфта осей Ø3, фиксация пока условная', coupling, drive, (.95,.43,.12))
mount = Part.makeBox((39 if args.mg90s_roll else 45), 17, 3, V(16,fy-8.5,fz-10))
mount = mount.fuse(Part.makeBox(3,17,12,V(16,fy-8.5,fz-10)))
for y in (fy-7.4,fy+5.3):
    mount = mount.fuse(Part.makeBox((26 if args.mg90s_roll else 25),2.1,14,V(28.5,y,fz-7)))
mount = mount.fuse(Part.makeBox(3,14.8,2,V(33,fy-7.4,fz+7)))
add_head('N20Mount', ('Лоток N20 26 мм; посадка по фактическому мотору не проверена'
                       if args.mg90s_roll else 'Лоток и скоба N20; задние 7 мм открыты для энкодера'),
         mount, frame, blue)
head_mount_width = 28 if args.mg90s_roll else 40
head_mount = Part.makeBox(head_mount_width, head_mount_width, 3,
                          V(-head_mount_width/2,-head_mount_width/2,-27))
head_mount = head_mount.cut(Part.makeCylinder(4,3.2,V(0,0,-27.1)))
for x in ((-5,5) if args.mg90s_roll else (-7,7)):
    for y in ((-9,9) if args.mg90s_roll else (-12,12)):
        head_mount = head_mount.cut(Part.makeCylinder(1.65,3.2,V(x,y,-27.1)))
head_mount_servo = 'MG90S' if args.mg90s_roll else 'MG996R'
add_head(head_mount_servo+'HeadMount','Площадка лепилки под качалку '+head_mount_servo+' — узор условный',head_mount,frame,blue)
if args.mg90s_roll:
    adapter = Part.makeCylinder(4.5, 6, V(0,0,-34))
    adapter = adapter.fuse(Part.makeCylinder(7, 1, V(0,0,-28)))
    adapter = adapter.fuse(Part.makeCylinder(3.9, 3, V(0,0,-27)))
    add_head('MG90SOutputAdapter',
             'Переходник от вала MG90S к площадке лепилки; шлицы и крепёж условные',
             adapter,frame,blue)
add_head('HeadMountRib','Связь площадки с корпусом лепилки',
         Part.makeBox(25.2,12,6,V(-12.6,-20,-24)),frame,blue)
params = head.getObject('ConceptParameters')
params.Status = ('N20 5 В / 40 об/мин. Макет; вал, ток и момент по товару не подтверждены.'
                 if args.mg90s_roll else 'N20 210:1 с энкодером. Макет; фактическая протяжка и посадка головки не испытаны.')
params.MotorData = ('Номинально 5 В, 40 об/мин; заявлен диапазон 3–6 В, 10×12×26 мм, вал Ø2,8×10 мм; проверить экземпляр.'
                    if args.mg90s_roll else 'Pololu 5143: 6 В, корпус 10×12×32 мм + выходной D-вал Ø3×9 мм, 11 г; энкодер 12 CPR.')
params.ElectricalPlan = ('6 В через драйвер двигателя с ШИМ и отдельной ветвью питания; общий GND; энкодер не подтверждён.'
                         if args.mg90s_roll else '6 В через драйвер двигателя; энкодер к входам ESP32 по напряжению платы энкодера; общий GND.')
for old in ('MotorDiameter','MotorBodyLength','MotorShaftProjection',
            'MotorShaftDiameterAssumed','RewindDiameter'):
    if old in params.PropertiesList:
        params.removeProperty(old)
for name,value in [('MotorWidth',10),('MotorHeight',12),('MotorBodyLength',motor_body_length),
                   ('MotorOutputShaftDiameter',2*shaft_radius),('MotorOutputShaftLength',shaft_length)]:
    params.addProperty('App::PropertyLength',name,'Motor N20')
    setattr(params,name,value)
if not args.mg90s_roll:
    params.addProperty('App::PropertyInteger','EncoderCPR','Motor N20')
    params.EncoderCPR = 12
head.recompute()
head.save()

# Make an independent linked arm document and redirect all inherited links to
# copied FreeCAD part files.  The old jaw and its three motion joints are gone.
arm = App.openDocument(str(SOURCE / 'freecad/RobotArm_Assembly.FCStd'))
arm.saveAs(str(DEST / 'freecad/RobotArm_Assembly.FCStd'))
sources = {}
for link in [o for o in arm.Objects if o.TypeId == 'App::Link']:
    stem = link.SourceSTL[:-4]
    if stem not in sources:
        d = App.openDocument(str(PARTS / (stem + '.FCStd')))
        sources[stem] = d.getObject('Model')
    link.setLink(sources[stem])
for name in ('gripper_joint','finger_left_joint','finger_right_joint'):
    arm.removeObject(name)
for group_name in ('gripper_body','gripper_rotor','jaw_left','jaw_right'):
    group = arm.getObject(group_name)
    for obj in list(group.Group):
        arm.removeObject(obj.Name)
    arm.removeObject(group_name)
for obj in list(arm.Objects):
    if not args.mg90s_roll and obj.TypeId == 'App::Link' and obj.SourceSTL.startswith('WRIST_-_servoEnclosure'):
        arm.removeObject(obj.Name)

plate_z = 240.195
case_axis_z = 278.845 if args.mg90s_roll else plate_z + 46.85
head_origin_z = case_axis_z + 31
assembly = arm.getObject('Assembly')

def new_group(name, label, origin, mass):
    group = arm.addObject('App::Part', name)
    group.Label = label
    group.addProperty('App::PropertyString', 'ExportGroup', 'Gazebo')
    group.ExportGroup = name
    group.addProperty('App::PropertyVector', 'ExportFrameOriginMM', 'Gazebo')
    group.ExportFrameOriginMM = origin
    group.addProperty('App::PropertyFloat', 'EstimatedHardwareMassKg', 'Gazebo')
    group.EstimatedHardwareMassKg = mass
    assembly.addObject(group)
    return group

def link_part(name, part, group, pose, proxy=False):
    obj = arm.addObject('App::Link', name)
    obj.setLink(part)
    obj.Label = part.Label
    group.addObject(obj)
    obj.LinkPlacement = pose
    obj.addProperty('App::PropertyString','SourceSTL','Source')
    obj.SourceSTL = name + '.stl'
    if proxy:
        obj.addProperty('App::PropertyBool','IsHardwareProxy','Gazebo')
        obj.IsHardwareProxy = True
    return obj

wrist = arm.getObject('wrist_pitch')
wrist.EstimatedHardwareMassKg = .025 if args.mg90s_roll else .07
pitch_joint = arm.getObject('wrist_pitch_joint')
for name,value in [('PositionPGain',2.5),('PositionIGain',.10),
                   ('PositionDGain',.04),('PositionIMax',.08)]:
    if not hasattr(pitch_joint,name):
        pitch_joint.addProperty('App::PropertyFloat',name,'Gazebo controller')
    setattr(pitch_joint,name,value)
case_pose = P(V(0,0,plate_z),R())
if not args.mg90s_roll:
    link_part('WristMG996R_Rear',rear_part,wrist,case_pose)
    link_part('WristMG996R_Front',front_part,wrist,case_pose)
    link_part('WristMG996R_Envelope',servo,wrist,case_pose.multiply(servo_pose),True)

applicator = new_group('applicator',
                       ('Лепилка 20 мм / N20 5 В 40 об/мин' if args.mg90s_roll
                        else 'Лепилка 20 мм / N20 с энкодером'),
                       V(10,0,case_axis_z),.045)
feed_group = new_group('feed_roller','Ведущий ролик протяжки',V(10,fy,fz+head_origin_z),.006)
pinch_report = json.loads((ROOT / 'label_applicator/concept_report_v5.json').read_text())
iy, iz = [float(v) for v in pinch_report['nip_centres_yz_mm']['idler']]
pinch_group = new_group('pinch_roller','Встречный ролик с шестернёй',V(10,iy,iz+head_origin_z),.005)
feed_names = {'FeedCore','FeedRubber','FeedShaft','FeedGear'}
pinch_names = {'PinchRoller','PinchAxle','PinchGear'}
head_pose = P(V(10,0,head_origin_z),R())
head_parts=[]
for obj in head.Objects:
    if not obj.isDerivedFrom('Part::Feature'):
        continue
    if obj in head.getObject('Reference').Group:
        continue
    group = feed_group if obj.Name in feed_names else pinch_group if obj.Name in pinch_names else applicator
    link_part('Head_'+obj.Name,obj,group,head_pose)
    head_parts.append(obj.Name)

joint = arm.getObject('wrist_roll_joint')
joint.ChildBody = 'applicator'
joint.OriginMM = V(10,0,case_axis_z)
joint.Continuous = False
joint.LowerLimitSI = -math.radians(60)
joint.UpperLimitSI = math.radians(60)
joint.EffortLimitSI = .12 if args.mg90s_roll else .5
joint.SpeedLimitSI = .8 if args.mg90s_roll else .5
joint.ServoHomeDeg = 90
joint.ServoMaxDeg = 180
joint.LimitStatus = head_mount_servo+' positional wrist: provisional +/-60 deg; not continuous rotation'
for name,value in [('PositionPGain',1.2),('PositionIGain',.01),
                   ('PositionDGain',.035),('PositionIMax',.02)]:
    if not hasattr(joint,name):
        joint.addProperty('App::PropertyFloat',name,'Gazebo controller')
    setattr(joint,name,value)

def add_rotary(name, child, origin, sign):
    j = arm.addObject('App::FeaturePython', name)
    j.Label = name
    props = [('App::PropertyString','ExportJointType','revolute'),
             ('App::PropertyString','ParentBody','applicator'),
             ('App::PropertyString','ChildBody',child),
             ('App::PropertyVector','OriginMM',origin),
             ('App::PropertyVector','AxisVector',V(sign,0,0)),
             ('App::PropertyFloat','LowerLimitSI',-1e16),
             ('App::PropertyFloat','UpperLimitSI',1e16),
             ('App::PropertyFloat','EffortLimitSI',.03),
             ('App::PropertyFloat','SpeedLimitSI',10.5),
             ('App::PropertyBool','Continuous',True)]
    for typ,key,value in props:
        j.addProperty(typ,key,'Gazebo')
        setattr(j,key,value)
    arm.getObject('Joints').addObject(j)

add_rotary('feed_joint','feed_roller',feed_group.ExportFrameOriginMM,1)
add_rotary('pinch_joint','pinch_roller',pinch_group.ExportFrameOriginMM,-1)
arm.Label = 'Робот этикетировщик / '+head_mount_servo+' осевой поворот / N20'
assembly.AssemblyStatus = ('MG996R on elbow and wrist pitch; '+head_mount_servo+
                           (' wrist roll; 5V 40rpm N20 label head; interfaces provisional'
                            if args.mg90s_roll else ' wrist roll; N20 encoder label head; interfaces provisional'))
arm.recompute()
arm.save()

config = json.loads((SOURCE / 'freecad/joint_setup.json').read_text())
config['source_fcstd'] = str(DEST / 'freecad/RobotArm_Assembly.FCStd')
config['joints'] = [j for j in config['joints'] if j['name'] not in
                    ('gripper_joint','finger_left_joint','finger_right_joint')]
for j in config['joints']:
    if j['name'] == 'wrist_roll_joint':
        j.update(child='applicator',z=case_axis_z,home=90,servo_max=180,
                 continuous=False,lower=-math.radians(60),upper=math.radians(60),
                 effort=(.12 if args.mg90s_roll else .5),
                 speed=(.8 if args.mg90s_roll else .5),
                 origin_xyz_mm=[10,0,case_axis_z])
config['joints'] += [
    {'name':'feed_joint','parent':'applicator','child':'feed_roller','origin_xyz_mm':[10,fy,fz+head_origin_z],
     'axis':[1,0,0],'continuous':True,'effort':.03,'speed':10.5},
    {'name':'pinch_joint','parent':'applicator','child':'pinch_roller','origin_xyz_mm':[10,iy,iz+head_origin_z],
     'axis':[-1,0,0],'continuous':True,'effort':.03,'speed':10.5}]
(DEST / 'freecad/joint_setup.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))

report = {'status':'CAD and Gazebo prototype; physical mounting and label mechanics unverified',
          'source_arm_variant':str(SOURCE),'source_head_v5':str(ROOT/'label_applicator/LabelApplicator_v5_SM300.FCStd'),
          'motor':('N20 5V 40rpm, 3-6V range, no verified encoder'
                   if args.mg90s_roll else 'Pololu 5143 N20 210:1 MP 6V with 12 CPR side connector encoder'),
          'motor_source':('https://ozon.ru/t/hidcPTG'
                          if args.mg90s_roll else 'https://www.pololu.com/product/5143/specs'),
          'head_features':head_parts,
          'axis_heights_mm':{'wrist_plate':plate_z,'wrist_roll':case_axis_z,'head_origin':head_origin_z},
          'servo_replacements':['wrist pitch: inherited two-MG996R valet cradle',
                                ('wrist roll: original small MG90S enclosure and nominal head adapter'
                                 if args.mg90s_roll else 'wrist roll: new split MG996R cradle')],
          'unchanged_strong_joints':['base yaw','shoulder','elbow'],
          'gripper':'removed; applicator replaces it',
          'nominal_feed_mm_per_rev':10*math.pi,
          'nominal_revolutions_per_22mm_pitch':22/(10*math.pi),
          'limitations':[head_mount_servo+' wrist roll limited to +/-60 degrees in Gazebo',
                         'N20 casing, shaft and mount must be checked on purchased unit',
                         'existing wrist-plate bolt pattern is nominal; print fit coupon before parts',
                         'label pitch and feed diameter are assumptions; no label detection',
                         'Gazebo rollers rotate but flexible liner, peeling and adhesive contact are not simulated',
                         'case, head adapter, servo horn, wiring and payload not physically checked',
                         'MG90S torque margin with real applicator and pressing load is not verified']}
(DEST/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
export_from_freecad.export(arm,DEST)
if args.mg90s_roll:
    # The exporter normally gives every rigid link one full bounding box.
    # For the hollow applicator this filled empty space and blocked the
    # arm prematurely. Use a few component-level collision primitives.
    model_path=DEST/'export/robot_arm_freecad/model.sdf'
    model_tree=ET.parse(model_path)
    model=model_tree.getroot().find('model')
    rigid_link=next(link for link in model.findall('link') if link.get('name')=='applicator')
    for collision in list(rigid_link.findall('collision')):
        rigid_link.remove(collision)
    for part_name in ('SupplyRoll','RearCheek','FrontCheek','RearBridge',
                      'BottomBridge','PeelPlate','N20Gearbox','N20Motor40',
                      'N20Mount','MG90SHeadMount','MG90SOutputAdapter'):
        bounds=arm.getObject('Head_'+part_name).Shape.BoundBox
        collision=ET.SubElement(rigid_link,'collision',name=part_name+'_collision')
        cx=(bounds.XMin+bounds.XMax)/2000-.01
        cy=(bounds.YMin+bounds.YMax)/2000
        cz=(bounds.ZMin+bounds.ZMax)/2000-case_axis_z/1000
        ET.SubElement(collision,'pose').text=f'{cx:.6f} {cy:.6f} {cz:.6f} 0 0 0'
        box=ET.SubElement(ET.SubElement(collision,'geometry'),'box')
        ET.SubElement(box,'size').text=(f'{bounds.XLength/1000:.6f} '
                                        f'{bounds.YLength/1000:.6f} '
                                        f'{bounds.ZLength/1000:.6f}')
    bounds=arm.getObject('Head_ApplicationRoller').Shape.BoundBox
    roller_collision=ET.SubElement(rigid_link,'collision',name='application_roller_collision')
    ET.SubElement(roller_collision,'pose').text=(
        f'{(bounds.XMin+bounds.XMax)/2000-.01:.6f} '
        f'{(bounds.YMin+bounds.YMax)/2000:.6f} '
        f'{(bounds.ZMin+bounds.ZMax)/2000-case_axis_z/1000:.6f} '
        f'0 {math.pi/2:.9f} 0')
    cylinder=ET.SubElement(ET.SubElement(roller_collision,'geometry'),'cylinder')
    ET.SubElement(cylinder,'radius').text=f'{bounds.YLength/2000:.6f}'
    ET.SubElement(cylinder,'length').text=f'{bounds.XLength/1000:.6f}'
    ET.indent(model_tree.getroot(),space='  ')
    model_tree.write(model_path,encoding='utf-8',xml_declaration=True)
world_path = DEST / 'export/preview.sdf'
world_tree = ET.parse(world_path)
world = world_tree.getroot().find('world')
if args.mg90s_roll:
    ET.SubElement(world,'plugin',filename='gz-sim-contact-system',
                  name='gz::sim::systems::Contact')
carton = ET.SubElement(world,'model',name='carton_reference')
ET.SubElement(carton,'static').text = 'true'
carton_link = ET.SubElement(carton,'link',name='carton')
ET.SubElement(carton_link,'pose').text = '.01 .17 .32 0 0 0'
for kind in (('visual','collision') if args.mg90s_roll else ('visual',)):
    element = ET.SubElement(carton_link,kind,name='carton_'+kind)
    box = ET.SubElement(ET.SubElement(element,'geometry'),'box')
    ET.SubElement(box,'size').text = '.25 .15 .30'
    if kind=='visual':
        material=ET.SubElement(element,'material')
        ET.SubElement(material,'ambient').text='.65 .48 .31 1'
        ET.SubElement(material,'diffuse').text='.65 .48 .31 1'
if args.mg90s_roll:
    sensor=ET.SubElement(carton_link,'sensor',name='carton_contact_sensor',type='contact')
    ET.SubElement(sensor,'always_on').text='true'
    ET.SubElement(sensor,'update_rate').text='100'
    ET.SubElement(sensor,'topic').text='/carton/contact'
    ET.SubElement(ET.SubElement(sensor,'contact'),'collision').text='carton_collision'
ET.indent(world_tree.getroot(),space='  ')
world_tree.write(world_path,encoding='utf-8',xml_declaration=True)
label_sdf=ET.Element('sdf',version='1.10')
label_model=ET.SubElement(label_sdf,'model',name='applied_label')
ET.SubElement(label_model,'static').text='true'
label_link=ET.SubElement(label_model,'link',name='sticker')
label_center_z_m=(.3085 + (case_axis_z-287.045)/1000)
ET.SubElement(label_link,'pose').text=f'.01 .0946 {label_center_z_m:.4f} 0 0 0'
label_visual=ET.SubElement(label_link,'visual',name='white_20mm_label')
label_box=ET.SubElement(ET.SubElement(label_visual,'geometry'),'box')
ET.SubElement(label_box,'size').text='.02 .0005 .02'
label_material=ET.SubElement(label_visual,'material')
ET.SubElement(label_material,'ambient').text='.98 .97 .88 1'
ET.SubElement(label_material,'diffuse').text='.98 .97 .88 1'
ET.indent(label_sdf,space='  ')
ET.ElementTree(label_sdf).write(DEST/'export/applied_label.sdf',encoding='utf-8',xml_declaration=True)
print('BUILT',DEST,flush=True)
