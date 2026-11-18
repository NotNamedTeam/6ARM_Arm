"""Read-only inspection for the MG996R prototype interface."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import Part
result={}
for name in ['AXIS1_-_hornArm','AXIS1_-_pivotArm','AXIS1_-_servoEnclosure_-_bottom',
             'AXIS1_-_servoEnclosure_-_top','AXIS3_-_hornArm','AXIS3_-_pivotArm','WRIST_-_base']:
    d=App.openDocument(str(ROOT/'freecad/parts'/(name+'.FCStd')))
    shape=d.getObject('Model').Shape;b=shape.BoundBox
    data={'bounds':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax], 'faces':[]}
    for f in sorted(shape.Faces,key=lambda f:-f.Area)[:8]:
        n=f.normalAt(0,0)
        wires=[]
        for w in f.Wires:
            if w.isSame(f.OuterWire):continue
            q=w.BoundBox
            wires.append([q.XMin,q.YMin,q.ZMin,q.XMax,q.YMax,q.ZMax])
        data['faces'].append({'area':f.Area,'normal':list(n),'inner_wires':wires})
    result[name]=data
    print(name,'bbox',data['bounds'],flush=True)
    if name=='WRIST_-_base':print(json.dumps(data,indent=2),flush=True)
    App.closeDocument(d.Name)
(ROOT/'freecad/mg996r_interface_inspection.json').write_text(json.dumps(result,indent=2))
