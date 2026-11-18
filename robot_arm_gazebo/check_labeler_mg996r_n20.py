"""Read-only CAD integrity and nominal clearance checks for labeler variant."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App

V=App.Vector
parser=argparse.ArgumentParser()
parser.add_argument('--mg90s-roll',action='store_true')
args=parser.parse_args()
DEST=ROOT/('variants/labeler_mg90s_n20_v2' if args.mg90s_roll
           else 'variants/labeler_mg996r_n20_v1')
arm=App.openDocument(str(DEST/'freecad/RobotArm_Assembly.FCStd'))
head=App.openDocument(str(DEST/'freecad/parts'/
                          ('LabelApplicator_N20_40RPM.FCStd' if args.mg90s_roll
                           else 'LabelApplicator_N20_Encoder.FCStd')))
links=[o for o in arm.Objects if o.TypeId=='App::Link']
bad_links=[]
for link in links:
    if link.LinkedObject is None or link.Shape.isNull() or not link.Shape.isValid():
        bad_links.append(link.Name)
    elif not Path(link.LinkedObject.Document.FileName).is_relative_to(DEST):
        bad_links.append(link.Name+': outside variant')
heads=[o for o in head.Objects if o.isDerivedFrom('Part::Feature')]
bad_head=[o.Name for o in heads if o.Shape.isNull() or not o.Shape.isValid()]
if args.mg90s_roll:
    rear=next(o.Shape for o in links if o.SourceSTL=='WRIST_-_servoEnclosure_-_bottom.stl')
    front=next(o.Shape for o in links if o.SourceSTL=='WRIST_-_servoEnclosure_-_top.stl')
    mount=arm.getObject('Head_MG90SHeadMount').Shape
else:
    servo=arm.getObject('WristMG996R_Envelope').Shape
    rear=arm.getObject('WristMG996R_Rear').Shape
    front=arm.getObject('WristMG996R_Front').Shape
    mount=arm.getObject('Head_MG996RHeadMount').Shape
motor=head.getObject('N20Motor40' if args.mg90s_roll else 'N20MotorEncoder').Shape
bracket=head.getObject('N20Mount').Shape
report={
  'status':'CAD checked; real fits, strength and flexible web not tested',
  'assembly_links':len(links),'head_features':len(heads),
  'invalid_links':bad_links,'invalid_head_features':bad_head,
  'head_mount_case_clearance_mm':min(mount.distToShape(rear)[0],mount.distToShape(front)[0]),
  'n20_bracket_motor_overlap_mm3':motor.common(bracket).Volume,
  'n20_bracket_motor_clearance_mm':motor.distToShape(bracket)[0],
  'gazebo_joints':[o.Name for o in arm.Objects if hasattr(o,'ExportJointType')],
  'source_paths_self_contained':not bad_links,
}
if args.mg90s_roll:
    report['wrist_roll_housing']='original small wrist enclosure; MG90S body and spline not yet fit-checked'
    report['head_mount_case_overlap_mm3']=mount.common(rear).Volume+mount.common(front).Volume
    adapter=arm.getObject('Head_MG90SOutputAdapter').Shape
    report['adapter_to_housing_gap_mm']=min(adapter.distToShape(rear)[0],adapter.distToShape(front)[0])
    report['adapter_to_head_mount_gap_mm']=adapter.distToShape(mount)[0]
else:
    report['wrist_servo_case_overlap_mm3']=servo.common(rear).Volume+servo.common(front).Volume
    report['wrist_servo_case_clearance_mm']=min(servo.distToShape(rear)[0],servo.distToShape(front)[0])
if (bad_links or bad_head or report.get('wrist_servo_case_overlap_mm3',0)>.01
        or report.get('head_mount_case_overlap_mm3',0)>.01
        or report.get('adapter_to_housing_gap_mm',0)>.1
        or report.get('adapter_to_head_mount_gap_mm',0)>.1
        or report['n20_bracket_motor_overlap_mm3']>.01):
    report['status']='failed'
(DEST/'cad_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if report['status']=='failed':
    raise RuntimeError('CAD check failed')
