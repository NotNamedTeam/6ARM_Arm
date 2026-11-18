from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import Part
import TechDraw
doc = App.openDocument(str(ROOT / 'freecad/parts/AXIS3_-_pivotArm.FCStd'))
shape = doc.getObject('Model').Shape
print('projectEx doc:', TechDraw.projectEx.__doc__, flush=True)
print('projectToSVG doc:', TechDraw.projectToSVG.__doc__, flush=True)
projected = TechDraw.projectEx(shape, App.Vector(1, 0, 0))
print('Returned', type(projected), len(projected), flush=True)
for i, group in enumerate(projected):
    print('Group', i, type(group), len(group.Edges) if hasattr(group,'Edges') else len(group), flush=True)
print('sample face wires', flush=True)
for f in sorted(shape.Faces, key=lambda f:-f.Area)[:4]:
    print(f.Area, list(f.normalAt(0,0)), 'wires', len(f.Wires), [len(w.Vertexes) for w in f.Wires], flush=True)
print(TechDraw.projectToSVG(shape, App.Vector(1,0,0))[:1500], flush=True)
App.closeDocument(doc.Name)
