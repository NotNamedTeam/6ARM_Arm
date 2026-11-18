"""Simplified drawing triangles from the saved FreeCAD assembly, not raw STL."""
from pathlib import Path
import sys,json,math
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import AssemblyApp
doc=App.openDocument(str(ROOT/'freecad/RobotArm_Assembly.FCStd'))
parts=[]; all_points=[]
for obj in doc.Objects:
    if obj.TypeId!='App::Link':continue
    shape=obj.Shape.copy()
    parent=obj.getParentGeoFeatureGroup()
    placement=App.Placement()
    while parent is not None:
        placement=parent.Placement.multiply(placement)
        parent=parent.getParentGeoFeatureGroup()
    shape.Placement=placement.multiply(shape.Placement)
    vertices,triangles=shape.tessellate(.12)
    points=[list(p) for p in vertices]
    # Tessellation may duplicate a vertex across faces; merge by position.
    unique={}; canonical=[]; remap=[]
    for p in points:
        key=tuple(round(v,5) for v in p)
        if key not in unique:
            unique[key]=len(canonical);canonical.append(p)
        remap.append(unique[key])
    tris=[[remap[i] for i in t] for t in triangles]
    normals=[]; edges={}
    for index,t in enumerate(tris):
        p,q,r=[App.Vector(*canonical[i]) for i in t]
        n=(q-p).cross(r-p)
        n.normalize();normals.append(list(n))
        for a,b in zip(t,t[1:]+t[:1]):edges.setdefault(tuple(sorted([a,b])),[]).append(index)
    parts.append({'instance':obj.Name,'stem':obj.SourceSTL[:-4],
                  'center':list(shape.BoundBox.Center),'vertices':canonical,
                  'triangles':tris,'normals':normals,
                  'edges':[[list(k),v] for k,v in edges.items()]})
    all_points+=canonical
result={'parts':parts,'bounds':{'min':[min(p[i] for p in all_points) for i in range(3)],
                              'max':[max(p[i] for p in all_points) for i in range(3)]}}
(ROOT/'drawings/geometry/assembly.json').write_text(json.dumps(result),encoding='utf-8')
print('Assembly drawing geometry: %d instances, %d triangles.'%(len(parts),sum(len(p['triangles']) for p in parts)),flush=True)
