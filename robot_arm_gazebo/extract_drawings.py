"""Read FreeCAD solids; extract HLR views and measurable planar opening features.

The faceted source is not reverse engineered into nominal manufacturing geometry.
All values are reference measurements, with the source FCStd left unchanged.
"""
from pathlib import Path
import sys
import json
import math
import hashlib
from collections import Counter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'tools/freecad/squashfs-root/usr/lib'))
import FreeCAD as App
import Part
import TechDraw

OUT = ROOT / 'drawings'
DATA = OUT / 'geometry'
DATA.mkdir(parents=True, exist_ok=True)
V = App.Vector

def bb(shape):
    b = shape.BoundBox
    return {'min': [b.XMin,b.YMin,b.ZMin], 'max': [b.XMax,b.YMax,b.ZMax],
            'size': [b.XLength,b.YLength,b.ZLength]}

def orient(shape):
    sizes = bb(shape)['size']
    order = sorted(range(3), key=lambda i: -sizes[i])
    u, v = order[:2]
    basis = [V(1,0,0),V(0,1,0),V(0,0,1)]
    n = basis[u].cross(basis[v])
    m = App.Matrix()
    for row, vec in enumerate([basis[u],basis[v],n], 1):
        for col, value in enumerate(vec,1):
            setattr(m, 'A%d%d' % (row,col), value)
    result = shape.transformGeometry(m)
    b = bb(result)
    result.translate(V(*[-x for x in b['min']]))
    return result, ['XYZ'[u], 'XYZ'[v], ('-' if min(n)<0 else '+')+'XYZ'[order[2]]]

def view(shape, rotation=None):
    if rotation:
        shape = shape.copy()
        shape.Placement = App.Placement(V(), rotation).multiply(shape.Placement)
    # Exact HLR for every part, no source STL or screenshot used as a drawing.
    groups = TechDraw.projectEx(shape, V(0,0,1))
    def edges(group):
        result=[]
        for edge in group.Edges:
            points=edge.discretize(Deflection=.015)
            if len(points)>=2:
                result.append([[p.x,p.y] for p in points])
        return result
    return {'visible': edges(groups[0]), 'hidden': edges(groups[5])}

def solve3(matrix, rhs):
    a=[list(row)+[value] for row,value in zip(matrix,rhs)]
    for col in range(3):
        pivot=max(range(col,3),key=lambda r:abs(a[r][col]))
        a[col],a[pivot]=a[pivot],a[col]
        if abs(a[col][col])<1e-12:
            raise ValueError('singular')
        divisor=a[col][col]
        a[col]=[x/divisor for x in a[col]]
        for row in range(3):
            if row==col: continue
            factor=a[row][col]
            a[row]=[x-factor*y for x,y in zip(a[row],a[col])]
    return [row[-1] for row in a]

def fit_circle(points):
    if len(points)<10: return None
    # Center the data before the algebraic circle fit.
    mx=sum(p[0] for p in points)/len(points)
    my=sum(p[1] for p in points)/len(points)
    q=[(x-mx,y-my) for x,y in points]
    rows=[(x,y,1) for x,y in q]
    rhs=[-(x*x+y*y) for x,y in q]
    mat=[[sum(r[i]*r[j] for r in rows) for j in range(3)] for i in range(3)]
    vec=[sum(r[i]*b for r,b in zip(rows,rhs)) for i in range(3)]
    try: a,b,c=solve3(mat,vec)
    except ValueError: return None
    cx,cy=-a/2,-b/2
    r2=cx*cx+cy*cy-c
    if r2<=0: return None
    r=math.sqrt(r2)
    error=max(abs(math.hypot(x-cx,y-cy)-r) for x,y in q)
    if error>.025 or r<.3: return None
    return {'center':[cx+mx,cy+my], 'diameter':2*r, 'max_radial_residual':error}

def features(shape):
    collected={}
    levels=[set() for _ in range(3)]
    for f in shape.Faces:
        normal=list(f.normalAt(0,0))
        axis=max(range(3),key=lambda i:abs(normal[i]))
        if abs(normal[axis])<.999999 or f.Area<.5: continue
        level=round(list(f.CenterOfMass)[axis],3)
        levels[axis].add(level)
        axes=[i for i in range(3) if i!=axis]
        for w in f.Wires:
            if w.isSame(f.OuterWire): continue
            points=[list(v.Point) for v in w.Vertexes]
            if len(points)<3: continue
            xy=[[p[i] for i in axes] for p in points]
            lo=[min(p[i] for p in xy) for i in range(2)]
            hi=[max(p[i] for p in xy) for i in range(2)]
            circle=fit_circle(xy)
            rectangle=len(points)==4 and all(
                all(min(abs(p[i]-lo[i]),abs(p[i]-hi[i]))<.005 for i in range(2))
                for p in xy)
            typ='circle' if circle else ('rectangle' if rectangle else 'contour')
            center=circle['center'] if circle else [(a+b)/2 for a,b in zip(lo,hi)]
            size=[b-a for a,b in zip(lo,hi)]
            key=(axis,typ,*(round(x,2) for x in center+size))
            if key not in collected:
                collected[key]={'normal_axis':axis,'coordinate_axes':axes,'type':typ,
                    'center':center,'size':size,'levels':[], 'outline':xy}
                if circle: collected[key].update(circle)
            collected[key]['levels'].append(level)
    ordered=sorted(collected.values(),key=lambda f:(f['normal_axis'],*f['center']))
    for i,f in enumerate(ordered,1):
        f['id']='H%02d'%i
        f['levels']=sorted(set(f['levels']))
    return ordered, [sorted(values) for values in levels]

report=json.loads((ROOT/'freecad/build_report.json').read_text())
counts=Counter(i['part'] for i in report['instances'])
manifest={'source':'FreeCAD BRep converted from BasementMaker STL', 'units':'mm',
          'status':'reference dimensions; preliminary, not released for manufacture',
          'parts':[], 'axes':report['axis_heights_mm']}
for index,path in enumerate(sorted((ROOT/'freecad/parts').glob('*.FCStd')),1):
    print('Projecting %02d/27 %s'%(index,path.stem),flush=True)
    doc=App.openDocument(str(path))
    source=doc.getObject('Model').Shape
    shape,orientation=orient(source)
    fs,levels=features(shape)
    data={'stem':path.stem,'position':index,'designation':'РМ.001.%03d'%index,
        'quantity':counts[path.stem], 'source_fcstd':str(path),
        'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'bounds':bb(shape),'original_bounds':bb(source),'orientation':orientation,
        'volume_mm3':source.Volume,'features':fs,'plane_levels':levels,
        'views':{'front':view(shape), 'top':view(shape,App.Rotation(V(1,0,0),90)),
                 'left':view(shape,App.Rotation(V(0,1,0),90)),
                 'iso':view(shape,App.Rotation(V(1,1,1),V(0,0,1)))}}
    (DATA/(path.stem+'.json')).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    manifest['parts'].append({k:data[k] for k in ('stem','position','designation','quantity','source_fcstd','source_sha256','bounds','orientation')})
    # Native neutral solid geometry, including all original faceted contours.
    source.exportStep(str(DATA/(path.stem+'.step')))
    App.closeDocument(doc.Name)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print('All 27 part views and opening tables extracted.',flush=True)
