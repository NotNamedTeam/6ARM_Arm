"""Separate FreeCAD prototype: opposed MG996R shafts, original 60.5125 mm pitch.

Servo envelope/flange details and factory horn interfaces need physical checking.
This script only writes its own variant folder; original FCStd files are unchanged.
"""
from pathlib import Path
import sys,json,math,shutil,hashlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
sys.path.insert(0,str(ROOT))
import FreeCAD as App
import Part,Mesh,AssemblyApp
import setup_joints,export_from_freecad
V=App.Vector;R=App.Rotation;P=App.Placement
DEST=ROOT/'variants/mg996r_valet_v1'
PARTS=DEST/'freecad/parts'
PRINT=DEST/'print_stl'
PARTS.mkdir(parents=True,exist_ok=True);PRINT.mkdir(parents=True,exist_ok=True)
PITCH=60.5125;ANGLE=25.;GAP=1.5;CHEEK=6.5;WALL=3.;PLATE=3.
OLD_AXIS=V(-10,9.92,0)
RA=R(V(0,0,1),ANGLE)
RB=RA.multiply(R(V(0,1,0),180))
PA=P(OLD_AXIS-RA.multVec(OLD_AXIS),RA)
TARGET=V(-PITCH-10,9.92,-40.8)
PB=P(TARGET-RB.multVec(OLD_AXIS),RB)
original_files=[ROOT/'freecad/RobotArm_Assembly.FCStd',*sorted((ROOT/'freecad/parts').glob('*.FCStd'))]
original_hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in original_files}
for f in (ROOT/'freecad/parts').glob('*.FCStd'):
    if not (PARTS/f.name).exists():shutil.copy2(f,PARTS/f.name)
report=json.loads((ROOT/'freecad/build_report.json').read_text())
report['variant']='MG996R opposed shafts / both cases tilted 25 deg'
report['axis_heights_mm']['wrist_roll']+=PLATE-2
(DEST/'freecad/build_report.json').write_text(json.dumps(report,indent=2))

def placed(shape,placement):
    result=shape.copy();result.Placement=placement.multiply(result.Placement);return result

def clean(shape,name,single=True):
    shape=shape.removeSplitter()
    if not shape.isValid() or shape.Volume<=0 or (single and len(shape.Solids)!=1):
        raise RuntimeError('%s invalid: valid=%s solids=%d volume=%g'%(name,shape.isValid(),len(shape.Solids),shape.Volume))
    return shape

def convex(points):
    points=sorted(set(points))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[];upper=[]
    for p in points:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]

body=Part.makeBox(40.7,19.7,36.6,V(-40.75,.07,-39.55))
ears=Part.makeBox(54,20,2.6,V(-47.4,-.08,-14.05))
servo=clean(body.fuse(ears).fuse(Part.makeCylinder(6,3.45,V(-10,9.92,-2.95))).fuse(
    Part.makeCylinder(3,2.85,V(-10,9.92,.5))),'servo')
# Body clearances 0.3 mm per side, flange capture 0.3 mm per face.
void=Part.makeBox(41.3,20.3,37.2,V(-41.05,-.23,-39.85)).fuse(
    Part.makeBox(54.6,20.6,3.2,V(-47.7,-.38,-14.35))).fuse(
    Part.makeCylinder(10,12,V(-10,9.92,-3.5)))
sa,sb=placed(servo,PA),placed(servo,PB)
clearance=sa.distToShape(sb)[0]
if sa.common(sb).Volume>.01 or clearance<4:
    raise RuntimeError('Servo envelopes intersect or have insufficient spacing')
foot=[]
for placement in (PA,PB):
    for x,y in ((-50.7,-3.38),(9.9,-3.38),(9.9,23.22),(-50.7,23.22)):
        p=placement.multVec(V(x,y,0));foot.append((p.x,p.y))
hull=convex(foot)
wire=Part.makePolygon([V(x,y,-43.85) for x,y in hull]+[V(*hull[0],-43.85)])
outer=Part.Face(wire).extrude(V(0,0,46.9))
negative=placed(void,PA).fuse(placed(void,PB))
# Open-to-parting-plane cable channels: cables can be laid in before closing;
# a terminated three-pin plug does not need to pass through a small round hole.
port_a=Part.makeBox(6,59,15.61,V(-45.5,-45,-36))
port_b=Part.makeBox(6,59,15.61,V(-45.5,6,-36))
negative=negative.fuse(placed(port_a,PA)).fuse(placed(port_b,PB))
housing=clean(outer.cut(negative),'housing')
# Select four closure bolts in solid material outside both servo envelopes.
cx=sum(x for x,y in hull)/len(hull);cy=sum(y for x,y in hull)/len(hull)
candidates=[]
for i,(x,y) in enumerate(hull):
    nx,ny=hull[(i+1)%len(hull)]
    candidates.extend([(x,y),((x+nx)/2,(y+ny)/2)])
bolts=[]
# Grid search also considers the solid triangular webs created by the opposed
# layout. A 4.9 mm guard radius leaves >=1.65 mm around a 6.5 mm nut pocket.
bounds=outer.BoundBox
for ix in range(math.ceil(bounds.XMin+5),math.floor(bounds.XMax-4),3):
    for iy in range(math.ceil(bounds.YMin+5),math.floor(bounds.YMax-4),3):
        candidates.append((ix,iy))
for x,y in candidates:
    length=math.hypot(cx-x,cy-y)
    x+=(cx-x)*4/length;y+=(cy-y)*4/length
    guard=Part.makeCylinder(4.9,46.9,V(x,y,-43.85))
    if abs(outer.common(guard).Volume-guard.Volume)>.1:continue
    if negative.common(guard).Volume>.01:continue
    if any(math.hypot(x-a,y-b)<12 for a,b in bolts):continue
    bolts.append((x,y))
    if len(bolts)==4:break
if len(bolts)<4:raise RuntimeError('Not enough closure-bolt positions: '+str(bolts))
for x,y in bolts:
    housing=housing.cut(Part.makeCylinder(1.7,48,V(x,y,-44)))
# Captive-nut pockets at rear cover, front screw seats are flush counterbores.
for x,y in bolts:
    pts=[V(x+3.25*math.cos(k*math.pi/3),y+3.25*math.sin(k*math.pi/3),-43.86) for k in range(6)]
    housing=housing.cut(Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,2.7)))
    housing=housing.cut(Part.makeCylinder(3.1,2.0,V(x,y,1.06)))
# Passive-pivot insert boss at the new servo's non-output face.
boss=Part.makeCylinder(5,.6,V(TARGET.x,TARGET.y,3.05))
housing=housing.fuse(boss).cut(Part.makeCylinder(2.1,3.2,V(TARGET.x,TARGET.y,.45)))
housing=clean(housing,'finished housing')
front=clean(housing.common(Part.makeBox(300,200,24.2,V(-150,-100,-20.4))),'front cover')
rear=clean(housing.common(Part.makeBox(300,200,23.45,V(-150,-100,-43.85))),'rear cover')

def original_shape(stem):
    doc=App.openDocument(str(ROOT/'freecad/parts'/(stem+'.FCStd')))
    shape=doc.getObject('Model').Shape.copy();App.closeDocument(doc.Name);return shape

small_horn=original_shape('AXIS3_-_hornArm')
large_horn=original_shape('AXIS1_-_hornArm')
cap=large_horn.common(Part.makeBox(4,40,40,V(0,-80,-20)))
cap.translate(V(0,60,0))
cap_void=Part.makeCylinder(19.5,4,V(),V(1,0,0)).cut(cap)
horn=clean(small_horn.fuse(Part.makeCylinder(20,4,V(),V(1,0,0))).cut(cap_void),'MG996R horn cheek')
horn=horn.fuse(placed(horn,P(V(CHEEK-4,0,0),R())))
horn=horn.fuse(Part.makeBox(CHEEK,8,40,V(0,-30,-20)))
for z in (-15,15):horn=horn.cut(Part.makeCylinder(1.75,8.2,V(CHEEK/2,-30.1,z),V(0,1,0)))
horn=clean(horn,'reinforced horn cheek')
support=original_shape('AXIS3_-_pivotArm')
support=support.fuse(Part.makeCylinder(20,4,V(0,30,0),V(1,0,0)))
support=support.fuse(placed(support,P(V(CHEEK-4,0,0),R())))
support=support.fuse(Part.makeBox(CHEEK,8,40,V(0,0,-20)))
for z in (-15,15):support=support.cut(Part.makeCylinder(1.75,8.2,V(CHEEK/2,-.1,z),V(0,1,0)))
support=clean(support.cut(Part.makeCylinder(3.1,CHEEK,V(0,30,0),V(1,0,0))),'sleeve-bearing cheek')
inside=23.45+GAP
center=inside+CHEEK/2
plate=Part.makeBox(2*(inside+CHEEK),PLATE,40,V(-inside-CHEEK,0,-20))
for x,z in ((-center,-15),(-center,15),(center,-15),(center,15),(-7.5,0),(7.5,0)):
    plate=plate.cut(Part.makeCylinder(1.75,PLATE,V(x,0,z),V(0,1,0)))
plate=clean(plate,'wide wrist plate')
parts={
 'AXIS2_-_servoEnclosure_-_bottom':(rear,'Обойма MG996R задняя'),
 'AXIS2_-_servoEnclosure_-_top':(front,'Обойма MG996R передняя'),
 'AXIS3_-_hornArm':(horn,'Щека MG996R под штатную качалку'),
 'AXIS3_-_pivotArm':(support,'Щека опорная под втулку 6×3,2×8'),
 'WRIST_-_base':(plate,'Плита кисти расширенная 62,9×40×3')}
part_stats=[]
def save_part(stem,shape,label,hardware=False):
    doc=App.newDocument('MG996R_'+stem.replace('-','_'))
    doc.Label=label
    obj=doc.addObject('Part::Feature','Model');obj.Label=label;obj.Shape=shape
    obj.addProperty('App::PropertyString','Representation');obj.Representation='Generated FreeCAD prototype; fit not physically verified'
    obj.addProperty('App::PropertyString','SourceSTL');obj.SourceSTL=stem+'.stl'
    obj.addProperty('App::PropertyString','Attribution');obj.Attribution='Original interface: BasementMaker / Thingiverse 4604664 / CC Attribution'
    for prop,value in [('CaseAngleDeg',ANGLE),('AxisPitchMM',PITCH),('CaseClearanceMM',.3)]:
        obj.addProperty('App::PropertyFloat',prop,'Prototype');setattr(obj,prop,value)
    if App.GuiUp:obj.ViewObject.ShapeColor=(.95,.55,.15)
    doc.recompute();doc.saveAs(str(PARTS/(stem+'.FCStd')))
    if not hardware:
        Mesh.Mesh(shape.tessellate(.08)).write(str(PRINT/(stem+'.stl')))
        shape.exportStep(str(PRINT/(stem+'.step')))
    part_stats.append({'stem':stem,'label':label,'valid':shape.isValid(),'solids':len(shape.Solids),'volume_mm3':shape.Volume})
    App.closeDocument(doc.Name)
for stem,(shape,label) in parts.items():
    save_part(stem,shape,label);print('New part:',stem,flush=True)
save_part('MG996R_reference',servo,'MG996R - габаритная модель, НЕ ПЕЧАТАТЬ',True)
frame=Part.makeBox(60.6,29.7,3,V(-50.7,-4.93,0)).cut(
    Part.makeBox(41.3,20.3,3.2,V(-41.05,-.23,-.1)))
save_part('FIT_body_frame',clean(frame,'fit body frame'),'Пробник корпуса MG996R 41,3×20,3')
save_part('FIT_horn_pattern',clean(cap,'fit horn pattern'),'Пробник посадки штатной качалки')
bearing_fit=Part.makeBox(36,16,CHEEK)
for x,radius in ((6,3),(18,3.1),(30,3.2)):
    bearing_fit=bearing_fit.cut(Part.makeCylinder(radius,CHEEK+.2,V(x,8,-.1)))
save_part('FIT_bushing_6_0_6_2_6_4',clean(bearing_fit,'fit bushing gauge'),'Пробник втулки: отверстия 6,0 / 6,2 / 6,4')

doc=App.openDocument(str(ROOT/'freecad/RobotArm_Assembly.FCStd'))
doc.saveAs(str(DEST/'freecad/RobotArm_Assembly.FCStd'))
sources={}
for stem in {o.SourceSTL[:-4] for o in doc.Objects if o.TypeId=='App::Link'}:
    pd=App.openDocument(str(PARTS/(stem+'.FCStd')));sources[stem]=pd.getObject('Model')
forearm_placement=None
for obj in doc.Objects:
    if obj.TypeId!='App::Link':continue
    stem=obj.SourceSTL[:-4];obj.setLink(sources[stem])
    if stem=='AXIS2_-_servoEnclosure_-_bottom':forearm_placement=obj.LinkPlacement
    if stem=='AXIS3_-_hornArm':
        # The servo output now faces the opposite axial side.
        obj.LinkPlacement=P(V(-inside-CHEEK,0,report['axis_heights_mm']['wrist_pitch']),R(V(1,0,0),-90))
    elif stem=='AXIS3_-_pivotArm':
        # Source local Y=30 is the pivot, local Y=0 the wrist-plate end.
        rot=R(V(0,0,1),180)
        yup=P(V(inside+CHEEK,report['axis_heights_mm']['wrist_pitch']+30,0),rot)
        obj.LinkPlacement=P(V(),R(V(1,0,0),90)).multiply(yup)
    if stem.startswith('WRIST_-_servoEnclosure') or obj.getParentGeoFeatureGroup().Name in ('gripper_body','jaw_left','jaw_right','gripper_rotor'):
        p=obj.LinkPlacement;p.Base.z+=PLATE-2;obj.LinkPlacement=p
    if stem in parts:obj.Label=parts[stem][1]
if forearm_placement is None:raise RuntimeError('Forearm placement not found')
refdoc=App.openDocument(str(PARTS/'MG996R_reference.FCStd'))
for index,local in enumerate((PA,PB),1):
    obj=doc.addObject('App::Link','MG996R_Envelope_%d'%index)
    obj.setLink(refdoc.getObject('Model'));doc.getObject('forearm').addObject(obj)
    obj.LinkPlacement=forearm_placement.multiply(local)
    obj.addProperty('App::PropertyString','SourceSTL');obj.SourceSTL='MG996R_reference.stl'
    obj.addProperty('App::PropertyBool','IsHardwareProxy');obj.IsHardwareProxy=True
    obj.Label='MG996R %d - габарит, вал %s'%(index,'справа' if index==1 else 'слева')
doc.Label='Манипулятор MG996R валетом - прототип v1'
doc.getObject('Assembly').AssemblyStatus='Prototype: opposed MG996R shafts; original pitch; hardware fit requires measurement'
doc.recompute();doc.save()
setup_joints.configure(doc,DEST)
joint=doc.getObject('wrist_pitch_joint')
joint.ServoHomeDeg=90;joint.ServoMaxDeg=159
joint.LowerLimitSI=math.radians(-25);joint.UpperLimitSI=math.radians(25)
joint.EffortLimitSI=.65;joint.SpeedLimitSI=.45
joint.LimitStatus='Prototype CAD envelope range +/-25 deg; actual MG996R travel and mechanical zero uncalibrated'
joint.addProperty('App::PropertyInteger','ServoDirectionSign','Prototype');joint.ServoDirectionSign=-1
doc.getObject('forearm').EstimatedHardwareMassKg=.124
grip=doc.getObject('gripper_joint')
if not hasattr(grip,'PositionIGain'):
    grip.addProperty('App::PropertyFloat','PositionIGain','Gazebo controller (prototype)')
grip.PositionIGain=.008
if not hasattr(grip,'PositionIMax'):
    grip.addProperty('App::PropertyFloat','PositionIMax','Gazebo controller (prototype)')
grip.PositionIMax=.0002
doc.recompute();doc.save()
config=json.loads((DEST/'freecad/joint_setup.json').read_text())
for j in config['joints']:
    if j['name']=='wrist_pitch_joint':j.update(home=90,servo_max=159,lower=-math.radians(25),upper=math.radians(25),effort=.65,speed=.45,servo_direction_sign=-1)
(DEST/'freecad/joint_setup.json').write_text(json.dumps(config,indent=2))
export_from_freecad.export(doc,DEST)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in original_hashes.items()),'An original document changed'
result={'status':'prototype built; motion/collision test pending','axis_pitch_mm':PITCH,'case_angle_deg':ANGLE,
 'servo_envelope_clearance_mm':clearance,'fork_width_mm':2*(inside+CHEEK),'wrist_plate_thickness_mm':PLATE,
 'original_fcstd_sha256':original_hashes,'parts':part_stats,'closure_bolts_xy_mm':bolts,
 'unverified':['actual MG996R flange dimensions','factory horn fit','printed tolerances','insert and sleeve bearing installation','strength and payload'],
 'servo_reference_nominal_mm':[40.7,19.7,42.9],
 'servo_reference_assumptions':'Body height 36.6 mm; flange 54x20x2.6 and shaft details are provisional; verify on owned units',
 'replacement_parts':list(parts),
 'fit_coupons':['FIT_body_frame','FIT_horn_pattern','FIT_bushing_6_0_6_2_6_4'],
 'hardware_changes':['2x MG996R 55 g within forearm','4x M3 closure bolts and nuts, length to measure','1x sleeve OD6 ID3.2 length8 mm, M3 pivot bolt, short M3 insert length 3 mm; fit to measure'],
 'hardware_connection':'none'}
(DEST/'build_report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print('BUILT',str(DEST),json.dumps({'servo_clearance_mm':clearance,'parts':len(parts)}),flush=True)
