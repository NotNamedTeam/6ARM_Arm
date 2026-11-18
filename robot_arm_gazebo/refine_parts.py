"""Merge coplanar STL-derived faces without changing part geometry."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import Part

report_file = ROOT / 'freecad/build_report.json'
report = json.loads(report_file.read_text())
counts = {}
for path in sorted((ROOT / 'freecad/parts').glob('*.FCStd')):
    doc = App.openDocument(str(path))
    model = doc.getObject('Model')
    old_shape = model.Shape
    new_shape = old_shape.removeSplitter()
    error = abs(new_shape.Volume - old_shape.Volume)
    if not new_shape.isValid() or error > max(1e-4, abs(old_shape.Volume) * 1e-8):
        raise RuntimeError('Refine changed or invalidated solid: ' + path.name)
    counts[path.stem] = {'faces_before': len(old_shape.Faces), 'faces_after': len(new_shape.Faces)}
    model.Shape = new_shape
    model.Representation = 'Refined faceted solid from STL; no parametric design history'
    doc.recompute()
    doc.save()
    print(path.stem, counts[path.stem], flush=True)
    App.closeDocument(doc.Name)
for entry in report['parts']:
    entry.update(counts[Path(entry['file']).stem])
report['refine_volume_verified'] = True
report_file.write_text(json.dumps(report, indent=2))
