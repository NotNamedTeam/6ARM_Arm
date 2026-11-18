"""CAD clearance checks for the opposed-shaft prototype, not a strength approval."""
from pathlib import Path
import sys,json,math,hashlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import Part,Mesh,AssemblyApp
V=App.Vector
DEST=ROOT/'variants/mg996r_valet_v1'
doc=App.openDocument(str(DEST/'freecad/RobotArm_Assembly.FCStd'))
objects={}; groups={}
for obj in doc.Objects:
    if obj.TypeId!='App::Link':continue
    shape=obj.Shape.copy()
    parent=obj.getParentGeoFeatureGroup()
    placement=App.Placement()
    group=parent.Name
    while parent is not None:
        placement=parent.Placement.multiply(placement)
        parent=parent.getParentGeoFeatureGroup()
    shape.Placement=placement.multiply(shape.Placement)
    objects[obj.Name]=(obj,shape)
    groups.setdefault(group,[]).append((obj,shape))

def bounds(shape):
    b=shape.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def compare(a,b):
    ab,bb=a.BoundBox,b.BoundBox
    aa=[ab.XMin,ab.YMin,ab.ZMin];az=[ab.XMax,ab.YMax,ab.ZMax]
    ba=[bb.XMin,bb.YMin,bb.ZMin];bz=[bb.XMax,bb.YMax,bb.ZMax]
    lower=math.sqrt(sum(max(ba[i]-az[i],aa[i]-bz[i],0)**2 for i in range(3)))
    if lower>1e-6 and lower<.5:
        return {'overlap_mm3':0,'clearance_mm':a.distToShape(b)[0],'distance_method':'exact BRep after close AABB'}
    if lower>1e-6:
        return {'overlap_mm3':0,'clearance_mm':lower,'distance_method':'AABB conservative lower bound'}
    volume=a.common(b).Volume
    # Keep exact minimum distances, including intended face-to-face contact.
    return {'overlap_mm3':volume,'clearance_mm':0 if volume>.001 else a.distToShape(b)[0],
            'distance_method':'exact BRep'}

fixed=groups['forearm']
moving=[pair for group in ('wrist_pitch','gripper_body','gripper_rotor','jaw_left','jaw_right')
        for pair in groups[group]]
new_cheeks=[pair for pair in moving if pair[0].SourceSTL in
            ('AXIS3_-_hornArm.stl','AXIS3_-_pivotArm.stl','WRIST_-_base.stl')]
pitch=doc.getObject('wrist_pitch_joint').OriginMM
result={'status':'running','source_fcstd':doc.FileName,
        'source_sha256':hashlib.sha256(Path(doc.FileName).read_bytes()).hexdigest(),'hardware_connection':'none',
        'scope':'CAD hard geometry only; servo/flange/connector assumptions unverified',
        'neutral':{},'wrist_pitch_sweep':[],'stl_checks':[]}
axes=[]
for obj,_shape in fixed:
    if not obj.SourceSTL.startswith('MG996R'):continue
    origin=obj.LinkPlacement.multVec(V(-10,9.92,0))
    direction=obj.LinkPlacement.Rotation.multVec(V(0,0,1))
    axes.append({'name':obj.Name,'origin_mm':list(origin),'outward':list(direction)})
delta=V(*axes[1]['origin_mm'])-V(*axes[0]['origin_mm'])
n=V(*axes[0]['outward'])
result['servo_axes']={'axes':axes,'opposed_direction_dot':n.dot(V(*axes[1]['outward'])),
                      'perpendicular_spacing_mm':delta.cross(n).Length}
assert abs(result['servo_axes']['perpendicular_spacing_mm']-60.5125)<1e-6
assert result['servo_axes']['opposed_direction_dot']<-.999999
for obj,shape in fixed:
    if not obj.SourceSTL.startswith('MG996R'):continue
    for case,cshape in fixed:
        if case.SourceSTL.startswith('MG996R'):continue
        key=obj.Name+' / '+case.Name
        result['neutral'][key]=compare(shape,cshape)
        print('Servo/case',key,result['neutral'][key],flush=True)
for angle in range(-30,31,5):
    checks=[]
    for obj,shape in moving:
        rotated=shape.copy();rotated.rotate(pitch,V(1,0,0),angle)
        for other,obstacle in fixed:
            measurement=compare(rotated,obstacle)
            checks.append({'moving':obj.Label,'fixed':other.Label,**measurement})
    row={'angle_deg':angle,'checks':checks,
         'maximum_overlap_mm3':max(c['overlap_mm3'] for c in checks),
         'minimum_clearance_mm':min(c['clearance_mm'] for c in checks)}
    result['wrist_pitch_sweep'].append(row)
    print('Pitch',angle,'max overlap',row['maximum_overlap_mm3'],'min clearance',row['minimum_clearance_mm'],flush=True)
for path in sorted((DEST/'print_stl').glob('*.stl')):
    mesh=Mesh.Mesh(str(path))
    result['stl_checks'].append({'file':path.name,'facets':mesh.CountFacets,
                                 'solid':mesh.isSolid()})
result['part_bounds']={obj.Label:bounds(shape) for obj,shape in objects.values()
                       if obj.SourceSTL.startswith(('AXIS2','AXIS3','MG996R','WRIST_-_base'))}
result['status']='checked; review interference results before motion or printing'
(DEST/'clearance_report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print('CAD clearance report saved.',flush=True)
