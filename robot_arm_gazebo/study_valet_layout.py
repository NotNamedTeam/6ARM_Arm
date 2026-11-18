"""MG996R envelope study, dimensions in mm. Does not change the robot assembly."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import Part
V=App.Vector
# Source mount coordinates: shaft (-10,9.92,0), body extends towards -X.
body=Part.makeBox(40.7,19.7,36.6,V(-40.75,.07,-39.55))
# Flange height 26.8 mm from bottom is an approximate interpretation;
# retain it as a configurable envelope, not a manufacturing nominal.
ears=Part.makeBox(54,20,2.6,V(-47.4,-.08,-14.05))
flange=ears.cut(body)
servo=body.fuse(ears).fuse(Part.makeCylinder(6.0,5.45,V(-10,9.92,-2.95)))
result=[]
for pitch in (60.5125,62,64,66,68,70,72,74,76,80,85):
    p=App.Placement(V(-pitch-20,0,-40.8),App.Rotation(V(0,1,0),180))
    other=servo.copy();other.Placement=p.multiply(other.Placement)
    obody=body.copy();obody.Placement=p.multiply(obody.Placement)
    oflange=flange.copy();oflange.Placement=p.multiply(oflange.Placement)
    row={'axis_pitch_mm':pitch, 'body_body_overlap_mm3':body.common(obody).Volume,
         'ear_body_overlap_mm3':flange.common(obody).Volume+oflange.common(body).Volume,
         'total_overlap_mm3':servo.common(other).Volume}
    result.append(row)
    print(row,flush=True)
angled=[]
old_axis=V(-10,9.92,0)
for angle in (0,15,20,25,30,35,40,45,60,90):
    rotation=App.Rotation(V(0,0,1),angle).multiply(App.Rotation(V(0,1,0),180))
    target=V(-70.5125,9.92,-40.8)
    p=App.Placement(target-rotation.multVec(old_axis),rotation)
    other=servo.copy();other.Placement=p.multiply(other.Placement)
    row={'pitch_mm':60.5125,'case_angle_deg':angle,'overlap_mm3':servo.common(other).Volume,
         'clearance_mm':servo.distToShape(other)[0]}
    angled.append(row)
    print('angled',row,flush=True)
both_angled=[]
for angle in (15,20,22,25,28,30):
    r1=App.Rotation(V(0,0,1),angle)
    p1=App.Placement(old_axis-r1.multVec(old_axis),r1)
    a=servo.copy();a.Placement=p1.multiply(a.Placement)
    r2=r1.multiply(App.Rotation(V(0,1,0),180))
    p2=App.Placement(V(-70.5125,9.92,-40.8)-r2.multVec(old_axis),r2)
    b=servo.copy();b.Placement=p2.multiply(b.Placement)
    row={'pitch_mm':60.5125,'both_case_angle_deg':angle,
         'overlap_mm3':a.common(b).Volume,'clearance_mm':a.distToShape(b)[0]}
    both_angled.append(row);print('both angled',row,flush=True)
(ROOT/'freecad/mg996r_valet_layout_study.json').write_text(json.dumps({
    'case_dimensions_mm':[40.7,19.7,36.6], 'overall_height_mm':42.9,
    'flange_envelope_mm':[54,20,2.6], 'flange_z':[-14.05,-11.45],
    'status':'conservative simplified envelope; flange details and horn require physical check',
    'source':'https://towerpro.com.tw/product/mg996R/', 'results':result,
    'angled_original_pitch':angled,'both_angled':both_angled},indent=2))
