"""Save the generated vector sheets as a separate native FreeCAD TechDraw book.

Sheets are embedded SVG reference snapshots, not associative dimension objects.
Original part and assembly FCStd files remain untouched by this script.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import TechDraw
OUT=ROOT/'drawings'
doc=App.newDocument('RobotArm_Reference_Drawings')
doc.Label='Манипулятор - предварительные чертежи'
info=doc.addObject('App::FeaturePython','DrawingStatus')
info.addProperty('App::PropertyString','Status')
info.Status='Reference SVG snapshots; non-associative. Regenerate after changing part geometry.'
info.addProperty('App::PropertyString','SourceAssembly')
info.SourceAssembly=str(ROOT/'freecad/RobotArm_Assembly.FCStd')
for index,path in enumerate(sorted((OUT/'svg').glob('*.svg')),1):
    page=doc.addObject('TechDraw::DrawPage','Sheet_%03d'%index)
    page.Label='%02d - %s'%(index,path.stem)
    template=doc.addObject('TechDraw::DrawSVGTemplate','Template_%03d'%index)
    template.Template=str(path)
    page.Template=template
    print('FreeCAD sheet',index,path.stem,flush=True)
doc.recompute()
doc.saveAs(str(OUT/'RobotArm_Drawings.FCStd'))
print('Saved separate TechDraw reference book.',flush=True)
