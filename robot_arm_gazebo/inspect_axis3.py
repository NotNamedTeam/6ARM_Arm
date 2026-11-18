"""Read-only geometry inspection of the original FreeCAD servo mounts."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import Part


def bounds(shape):
    b = shape.BoundBox
    return {'min': [b.XMin, b.YMin, b.ZMin], 'max': [b.XMax, b.YMax, b.ZMax],
            'size': [b.XLength, b.YLength, b.ZLength]}


report = {}
for stem in ('AXIS1_-_servoEnclosure_-_bottom', 'AXIS2_-_servoEnclosure_-_bottom',
             'AXIS2_-_servoEnclosure_-_top', 'AXIS3_-_hornArm',
             'AXIS3_-_pivotArm', 'WRIST_-_base'):
    doc = App.openDocument(str(ROOT / 'freecad/parts' / (stem + '.FCStd')))
    shape = doc.getObject('Model').Shape
    planes = []
    for face in shape.Faces:
        if face.Area < 12:
            continue
        n = face.normalAt(0, 0)
        if max(abs(n.x), abs(n.y), abs(n.z)) < .99999:
            continue
        c = face.CenterOfMass
        planes.append({'area': face.Area, 'normal': list(n), 'center': list(c),
                       'bounds': bounds(face)})
    report[stem] = {'bounds': bounds(shape), 'volume_mm3': shape.Volume,
                    'planes': sorted(planes, key=lambda f: -f['area'])}
    print(stem, json.dumps(report[stem]['bounds']), flush=True)
    App.closeDocument(doc.Name)
path = ROOT / 'freecad/axis3_original_inspection.json'
path.write_text(json.dumps(report, indent=2))
print('Inspection saved: ' + str(path), flush=True)
