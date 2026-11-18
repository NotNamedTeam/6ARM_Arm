"""Variant-only pinion controller; preserve all original files and CAD geometry."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
sys.path.insert(0,str(ROOT))
import FreeCAD as App
import AssemblyApp
import export_from_freecad
DEST=ROOT/'variants/mg996r_valet_v1'
doc=App.openDocument(str(DEST/'freecad/RobotArm_Assembly.FCStd'))
grip=doc.getObject('gripper_joint')
if not hasattr(grip,'PositionIGain'):
    grip.addProperty('App::PropertyFloat','PositionIGain','Gazebo controller (prototype)')
grip.PositionIGain=.008
if not hasattr(grip,'PositionIMax'):
    grip.addProperty('App::PropertyFloat','PositionIMax','Gazebo controller (prototype)')
grip.PositionIMax=.0002
doc.recompute();doc.save()
export_from_freecad.export(doc,DEST)
print('MG996R variant only: pinion Ki=0.008, integral clamp=0.0002 Nm. CAD solids unchanged.',flush=True)
