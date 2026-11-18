"""Preliminary ESKD-layout reference drawings from extracted FreeCAD HLR geometry.

One editable SVG per sheet and one combined, vector PDF. No invented tolerances,
material, approval signatures or servo mounting nominal dimensions.
"""
from pathlib import Path
import json
import math
from html import escape
import textwrap
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'drawings'
PDF=OUT/'output/pdf'
SVG=OUT/'svg'
PDF.mkdir(parents=True,exist_ok=True)
SVG.mkdir(parents=True,exist_ok=True)
FONT=ROOT.parents[1]/'tools/freecad/squashfs-root/usr/share/Mod/TechDraw/Resources/fonts/osifont-lgpl3fe.ttf'
pdfmetrics.registerFont(TTFont('Drawing',str(FONT)))
NAMES={
 'AXIS1_-_hornArm':'Рычаг плеча ведущий',
 'AXIS1_-_pivotArm':'Рычаг плеча опорный',
 'AXIS1_-_servoEnclosure_-_bottom':'Корпус привода плеча нижний',
 'AXIS1_-_servoEnclosure_-_top':'Корпус привода плеча верхний',
 'AXIS2_-_servoEnclosure_-_bottom':'Корпус приводов локтя нижний',
 'AXIS2_-_servoEnclosure_-_top':'Корпус приводов локтя верхний',
 'AXIS3_-_hornArm':'Рычаг кисти ведущий',
 'AXIS3_-_pivotArm':'Рычаг кисти опорный',
 'BASE_-_base':'Основание манипулятора',
 'BASE_-_platform':'Платформа поворотная',
 'BASE_-_servo_-_stand':'Кронштейн привода основания',
 'BASE_-_servo_-_stand_-_wire':'Кронштейн с выводом кабеля',
 'BASE_-_support':'Кольцо опорное основания',
 'BASE_-_support_-_spacer':'Проставка стойки основания',
 'BASE_-_support_-_stand':'Стойка основания',
 'GRIPPER_-_gear_-_rack':'Рейка зубчатая захвата',
 'GRIPPER_-_gear_-_servo':'Шестерня привода захвата',
 'GRIPPER_-_jaw':'Губка захвата',
 'GRIPPER_-_plate_-_back':'Пластина захвата задняя',
 'GRIPPER_-_plate_-_front':'Пластина захвата передняя',
 'GRIPPER_-_servoEnclosure_-_bottom':'Корпус привода захвата нижний',
 'GRIPPER_-_servoEnclosure_-_top':'Корпус привода захвата верхний',
 'GRIPPER_-_spacer_-_jaw':'Проставка губки захвата',
 'GRIPPER_-_wristHornAttachment':'Адаптер захвата к качалке',
 'WRIST_-_base':'Плита крепления кисти',
 'WRIST_-_servoEnclosure_-_bottom':'Корпус поворота кисти нижний',
 'WRIST_-_servoEnclosure_-_top':'Корпус поворота кисти верхний'}

def number(value):
    if abs(value)<.005:value=0
    return ('%.2f'%value).rstrip('0').rstrip('.').replace('.',',')

class Sheet:
    def __init__(self,doc,key):
        self.doc=doc; self.key=key; self.svg=[]
    def line(self,x1,y1,x2,y2,width=.25,dash=None):
        c=self.doc
        c.setLineWidth(width*mm)
        c.setDash([v*mm for v in dash] if dash else [])
        c.line(x1*mm,(297-y1)*mm,x2*mm,(297-y2)*mm)
        dash_attr=' stroke-dasharray="%s"'%','.join(map(str,dash)) if dash else ''
        self.svg.append(f'<path d="M{x1:.4f},{y1:.4f} L{x2:.4f},{y2:.4f}" fill="none" stroke="black" stroke-width="{width}"{dash_attr}/>')
    def poly(self,points,width=.25,dash=None,fill=False):
        if len(points)<2:return
        c=self.doc; c.setLineWidth(width*mm);c.setDash([v*mm for v in dash] if dash else [])
        p=c.beginPath();p.moveTo(points[0][0]*mm,(297-points[0][1])*mm)
        for x,y in points[1:]:p.lineTo(x*mm,(297-y)*mm)
        if fill:p.close()
        c.drawPath(p,stroke=1,fill=int(fill))
        coords=' '.join(f'{x:.4f},{y:.4f}' for x,y in points)
        da=' stroke-dasharray="%s"'%','.join(map(str,dash)) if dash else ''
        self.svg.append(f'<polyline points="{coords}" fill="{"black" if fill else "none"}" stroke="black" stroke-width="{width}"{da}/>')
    def text(self,x,y,value,size=3.5,align='left',rotate=0):
        value=str(value); c=self.doc;c.saveState();c.translate(x*mm,(297-y)*mm);c.rotate(-rotate)
        c.setFont('Drawing',size*mm)
        if align=='center':c.drawCentredString(0,0,value)
        elif align=='right':c.drawRightString(0,0,value)
        else:c.drawString(0,0,value)
        c.restoreState()
        anchor={'left':'start','center':'middle','right':'end'}[align]
        tr=f' transform="rotate({rotate},{x},{y})"' if rotate else ''
        self.svg.append(f'<text x="{x}" y="{y}" font-family="osifont" font-size="{size}" text-anchor="{anchor}"{tr}>{escape(value)}</text>')
    def rect(self,x,y,w,h,width=.5):
        self.poly([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],width)
    def finish(self):
        head='<svg xmlns="http://www.w3.org/2000/svg" xmlns:freecad="https://www.freecad.org/wiki/index.php?title=Svg_Namespace" width="420mm" height="297mm" viewBox="0 0 420 297">'
        (SVG/(self.key+'.svg')).write_text(head+'\n'+'\n'.join(self.svg)+'\n</svg>',encoding='utf-8')
        self.doc.showPage()

    def triangle(self,points):
        c=self.doc;c.setFillColorRGB(1,1,1)
        p=c.beginPath();p.moveTo(points[0][0]*mm,(297-points[0][1])*mm)
        for x,y in points[1:]:p.lineTo(x*mm,(297-y)*mm)
        p.close();c.drawPath(p,stroke=0,fill=1);c.setFillColorRGB(0,0,0)
        self.svg.append('<polygon points="'+' '.join('%.4f,%.4f'%tuple(p) for p in points)+'" fill="white" stroke="none"/>')

def frame(s,code,name,scale='1:1',sheet=1,total=1):
    s.rect(20,5,395,287,.5)
    s.rect(230,237,185,55,.5)
    for x in (247,270,285,295):s.line(x,237,x,292,.5)
    s.line(237,237,237,262,.5)
    for y in (242,247,252,257,267,272,277,282,287):s.line(230,y,295,y,.25)
    s.line(230,262,295,262,.5)
    s.line(295,252,415,252,.5);s.line(295,277,415,277,.5)
    s.line(365,252,365,292,.5)
    for y in (257,272):s.line(365,y,415,y,.5)
    for x in (380,397):s.line(x,252,x,272,.5)
    for x in (370,375):s.line(x,257,x,272,.25)
    s.line(385,272,385,277,.5)
    for x,label in ((233.5,'Изм.'),(242,'Лист'),(258.5,'№ докум.'),(277.5,'Подп.'),(290,'Дата')):
        s.text(x,261,label,2.5,'center')
    for y,label in ((266,'Разраб.'),(271,'Пров.'),(276,'Т.контр.'),(286,'Н.контр.'),(291,'Утв.')):
        s.text(231,y,label,2.5)
    s.text(355,247,code,5,'center')
    lines=textwrap.wrap(name,24)
    for i,line in enumerate(lines[:3]):s.text(330,260+i*5,line,3.5,'center')
    s.text(330,284,'Материал не задан',3,'center')
    s.text(330,289,'Уточнить перед изготовлением',2.5,'center')
    for x,label in ((372.5,'Лит.'),(388.5,'Масса'),(406,'Масштаб')):s.text(x,256,label,2.5,'center')
    s.text(388.5,266,'-',3.5,'center');s.text(406,266,scale,3.5,'center')
    s.text(367,276,'Лист',2.5);s.text(380,276,sheet,2.5,'center')
    s.text(387,276,'Листов',2.5);s.text(406,276,total,2.5,'center')
    s.text(390,284,'Робот-манипулятор',3,'center')
    s.text(390,289,'Предварительный',3,'center')
    s.rect(20,5,70,14,.5);s.text(55,14,code,4,'center',180)
    s.text(410,296,'Формат А3',2.5,'right')

def arrow(s,x,y,dx,dy):
    s.poly([(x,y),(x+dx*3-dy*.5,y+dy*3+dx*.5),(x+dx*3+dy*.5,y+dy*3-dx*.5)],.18,fill=True)

def hdim(s,x1,x2,ybase,y,value):
    s.line(x1,ybase+1,x1,y+2,.18);s.line(x2,ybase+1,x2,y+2,.18)
    if x2-x1<10:
        s.line(x1-5,y,x2+5,y,.18);arrow(s,x1,y,-1,0);arrow(s,x2,y,1,0)
    else:
        s.line(x1,y,x2,y,.18);arrow(s,x1,y,1,0);arrow(s,x2,y,-1,0)
    s.text((x1+x2)/2,y-1.4,value,3.5,'center')

def vdim(s,y1,y2,xbase,x,value):
    s.line(xbase-1,y1,x-2,y1,.18);s.line(xbase-1,y2,x-2,y2,.18)
    s.line(x,y1,x,y2,.18);arrow(s,x,y1,0,1);arrow(s,x,y2,0,-1)
    s.text(x-1.4,(y1+y2)/2,value,3.5,'center',-90)

def draw_view(s,data,box,scale,hidden=False):
    points=[p for path in data['visible'] for p in path]
    if not points:return None
    lo=[min(p[i] for p in points) for i in range(2)]
    hi=[max(p[i] for p in points) for i in range(2)]
    cx=box[0]+box[2]/2-scale*(lo[0]+hi[0])/2
    cy=box[1]+box[3]/2+scale*(lo[1]+hi[1])/2
    def pt(p):return [cx+scale*p[0],cy-scale*p[1]]
    if hidden:
        for path in data['hidden']:s.poly([pt(p) for p in path],.15,[2,1])
    for path in data['visible']:s.poly([pt(p) for p in path],.25)
    return pt,[cx+scale*lo[0],cy-scale*hi[1],cx+scale*hi[0],cy-scale*lo[1]]

def feature_table(s,features,x=298,y=38,width=110):
    s.text(x,y-5,'Отверстия и замкнутые проёмы*',3.5)
    widths=[10,12,19,19,50]; xs=[x]
    for w in widths:xs.append(xs[-1]+w)
    labels=['Поз.','Норм.','u','v','Размер / тип']
    for i,label in enumerate(labels):s.text(xs[i]+1,y+5,label,2.5)
    s.rect(x,y,width,8+len(features)*7,.25)
    for xx in xs[1:-1]:s.line(xx,y,xx,y+8+len(features)*7,.18)
    s.line(x,y+8,x+width,y+8,.25)
    for row,f in enumerate(features):
        yy=y+8+row*7
        size=('⌀'+number(f['diameter'])) if f['type']=='circle' else ('×'.join(number(v) for v in f['size']))
        if f['type']=='contour':size+=' контур'
        vals=[f['id'],'XYZ'[f['normal_axis']],number(f['center'][0]),number(f['center'][1]),size]
        for i,value in enumerate(vals):s.text(xs[i]+1,yy+4.7,value,2.5)
        s.line(x,yy+7,x+width,yy+7,.18)

def part_pages(c,d):
    dims=d['bounds']['size']; name=NAMES[d['stem']]
    scale=next(k for k in (4,2,1,.5,.2,.1) if dims[0]*k<=140 and dims[1]*k<=80 and dims[2]*k<=65)
    scale_label={4:'4:1',2:'2:1',1:'1:1',.5:'1:2',.2:'1:5',.1:'1:10'}[scale]
    fs=d['features']; chunk=23
    for f in fs:
        if f['type']=='rectangle':
            lo=[min(p[i] for p in f['outline']) for i in range(2)]
            hi=[max(p[i] for p in f['outline']) for i in range(2)]
            if not all(all(min(abs(p[i]-lo[i]),abs(p[i]-hi[i]))<.005 for i in range(2)) for p in f['outline']):
                f['type']='contour'
    total=1+max(1,math.ceil(len(fs)/chunk))
    s=Sheet(c,d['designation'].replace('.','_'))
    frame(s,d['designation'],name,scale_label,1,total)
    s.text(100,15,name,5)
    s.text(25,27,'ПРЕДВАРИТЕЛЬНО. Все размеры со знаком * - для справок, по модели FreeCAD.',3)
    front=draw_view(s,d['views']['front'],[43,45,145,80],scale)
    top=draw_view(s,d['views']['top'],[43,165,145,40],scale)
    left=draw_view(s,d['views']['left'],[210,45,65,80],scale)
    iso_points=[p for path in d['views']['iso']['visible'] for p in path]
    iw=max(p[0] for p in iso_points)-min(p[0] for p in iso_points)
    ih=max(p[1] for p in iso_points)-min(p[1] for p in iso_points)
    iso_scale=next(k for k in (scale,.5,.2,.1) if k*iw<=75 and k*ih<=45)
    draw_view(s,d['views']['iso'],[205,160,75,45],iso_scale,False)
    iso_label='Аксонометрия'
    if iso_scale!=scale:
        iso_label+=' ('+{4:'4:1',2:'2:1',1:'1:1',.5:'1:2',.2:'1:5',.1:'1:10'}[iso_scale]+')'
    for x,y,t in ((115,39,'Главный вид'),(115,159,'Вид сверху'),(243,39,'Вид слева'),(243,154,iso_label)):
        s.text(x,y,t,3,'center')
    pt,b=front
    hdim(s,b[0],b[2],b[3],b[3]+10,number(dims[0])+'*')
    vdim(s,b[1],b[3],b[0],b[0]-10,number(dims[1])+'*')
    _,bside=left
    hdim(s,bside[0],bside[2],bside[3],bside[3]+10,number(dims[2])+'*')
    # Label the measured opening features without replacing contours by circles.
    maps={2:(front,lambda f:f['center']),1:(top,lambda f:[f['center'][0],-f['center'][1]]),0:(left,lambda f:f['center'])}
    occupied=[]
    for f in fs:
        mapped,coord=maps[f['normal_axis']]
        center=coord(f)
        if f['normal_axis']==0:center=[center[1],center[0]]
        p=mapped[0](center)
        s.line(p[0]-1.5,p[1],p[0]+1.5,p[1],.15)
        s.line(p[0],p[1]-1.5,p[0],p[1]+1.5,.15)
        # Dense patterns remain fully tabulated; labels must stay legible.
        if any(abs(p[0]-q[0])<8 and abs(p[1]-q[1])<5 for q in occupied):continue
        occupied.append(p)
        s.text(p[0]+2,p[1]-2,f['id'],2.5)
    feature_table(s,fs[:chunk])
    s.text(298,211,'u, v: координаты центра проёма.',2.5)
    s.text(298,216,'Норм. Z: u=X, v=Y; Y: u=X, v=Z;',2.5)
    s.text(298,221,'Норм. X: u=Y, v=Z. Базы: min X,Y,Z.',2.5)
    s.text(25,220,'Локальные X,Y,Z на листе соответствуют исходным осям: '+', '.join(d['orientation']),3)
    s.text(25,226,'Исходный файл: '+d['stem']+'.FCStd',2.5)
    notes=['1. Размеры сняты с гранёного тела; округление до 0,01 мм не задаёт точность.',
           '2. Допуски, посадки, шероховатость и материал не назначены.',
           '3. Невидимые линии опущены; сложные профили - по исходной 3D-модели.',
           '4. Радиусы, фаски и глубины отверстий требуют конструкторской проверки.',
           '5. Контрольные подписи отсутствуют. Для изготовления требуется доработка.',
           '6. Печатать 100%, без подгонки к странице. Размеры в миллиметрах.']
    for i,note in enumerate(notes):s.text(25,244+7*i,note,3)
    s.finish()
    for page_index,offset in enumerate(range(0,max(1,len(fs)),chunk),2):
        a=Sheet(c,d['designation'].replace('.','_')+'_sheet_%d'%page_index)
        frame(a,d['designation'],name,'-',page_index,total)
        a.text(100,15,'Таблица дополнительных проёмов: '+name,5)
        feature_table(a,fs[offset:offset+chunk],40,38)
        a.text(170,42,'Положение плоскостей границ проёмов*',3.5)
        for i,f in enumerate(fs[offset:offset+chunk]):
            a.text(170,52+i*7,f['id']+': '+', '.join(number(v) for v in f['levels']),3)
        if offset+chunk>=len(fs):
            level_top=38+8+len(fs[offset:offset+chunk])*7+12
            for axis,levels in enumerate(d['plane_levels']):
                xx=40+axis*120
                a.text(xx,level_top,'Плоские грани: '+ 'XYZ'[axis]+'*',3)
                values=', '.join(number(v) for v in levels)
                for row,line in enumerate(textwrap.wrap(values,60)):
                    a.text(xx,level_top+6+row*4,line,2.5)
        a.text(25,245,'Плоскости - координаты плоских граней, а не назначение глубины сверления.',3)
        a.text(25,254,'Контуры проёмов и полный объём детали сохранены в STEP и JSON рядом с чертежами.',3)
        a.finish()

def dot(a,b):return sum(x*y for x,y in zip(a,b))

def assembly_view(s,data,u,v,n,box,scale):
    verts=[p for part in data['parts'] for p in part['vertices']]
    xs=[dot(p,u) for p in verts];ys=[dot(p,v) for p in verts]
    lo=[min(xs),min(ys)];hi=[max(xs),max(ys)]
    cx=box[0]+box[2]/2-scale*(lo[0]+hi[0])/2
    cy=box[1]+box[3]/2+scale*(lo[1]+hi[1])/2
    def pt(p):return [cx+scale*dot(p,u),cy-scale*dot(p,v)]
    all_tris=[]
    for part in data['parts']:
        visible_edges=set()
        for edge,adj in part['edges']:
            if len(adj)!=2:
                visible_edges.add(tuple(edge));continue
            a,b=[part['normals'][i] for i in adj]
            if dot(a,b)<math.cos(math.radians(18)) or dot(a,n)*dot(b,n)<0:
                visible_edges.add(tuple(edge))
        for t,normal in zip(part['triangles'],part['normals']):
            if dot(normal,n)<-1e-7:continue
            points=[part['vertices'][i] for i in t]
            edges=[(a,b) for a,b in zip(t,t[1:]+t[:1]) if tuple(sorted([a,b])) in visible_edges]
            all_tris.append((sum(dot(p,n) for p in points)/3,points,edges,part))
    for _,points,edges,part in sorted(all_tris,key=lambda x:x[0]):
        s.triangle([pt(p) for p in points])
        for a,b in edges:s.poly([pt(part['vertices'][a]),pt(part['vertices'][b])],.25)
    return pt,[cx+scale*lo[0],cy-scale*hi[1],cx+scale*hi[0],cy-scale*lo[1]]

def assembly_page(c,manifest):
    data=json.loads((OUT/'geometry/assembly.json').read_text())
    s=Sheet(c,'01_assembly')
    frame(s,'РМ.001.000 СБ','Манипулятор. Сборочный чертёж','1:2')
    s.text(100,15,'Манипулятор. Исходная сборка FreeCAD',5)
    front,b=assembly_view(s,data,[1,0,0],[0,0,1],[0,-1,0],[40,35,95,170],.5)
    assembly_view(s,data,[0,1,0],[0,0,1],[1,0,0],[155,35,95,170],.5)
    assembly_view(s,data,[.7071,.7071,0],[-.40825,.40825,.8165],[.57735,-.57735,.57735],[283,40,110,160],.5)
    s.text(86,30,'Главный вид',3,'center');s.text(202,30,'Вид слева',3,'center')
    s.text(338,30,'Аксонометрия',3,'center')
    widths=[hi-lo for lo,hi in zip(data['bounds']['min'],data['bounds']['max'])]
    hdim(s,b[0],b[2],b[3],b[3]+10,number(widths[0])+'*')
    vdim(s,b[1],b[3],b[0],b[0]-10,number(widths[2])+'*')
    # Named joint positions and spacing are source assembly measurements.
    heights=list(manifest['axes'].items())
    for i,(name,z) in enumerate(heights):
        p=front([0,0,z]);s.line(p[0]-10,p[1],p[0]+10,p[1],.15,[5,1,1,1])
        q=[133,p[1]]
        s.poly([p,[q[0]-3,q[1]-1],q],.18);s.text(q[0],q[1],str(i+1),3.5)
    labels=['Поворот основания','Плечо','Локоть','Наклон кисти','Поворот захвата']
    for i,((_,z),label) in enumerate(zip(heights,labels)):
        s.text(285,209+i*5,'%d - %s; Z=%s*'%(i+1,label,number(z)),2.5)
    for i,note in enumerate(['1. * Размеры для справок, миллиметры. Крепёж и сервоприводы условно не показаны.',
                              '2. Изображения упрощённые; расположение кисти и кронштейнов предварительное.',
                              '3. Межосевые расстояния: плечо-локоть 60*; локоть-кисть 60,51*.',
                              '4. Проверить соосность, зазоры и упоры на физической сборке.',
                              '5. Переделка тонкого звена под MG996R в данную редакцию не включена.']):
        s.text(25,245+i*8,note,3)
    s.finish()

def intro(c,manifest):
    s=Sheet(c,'00_catalog')
    frame(s,'РМ.001.000 ВД','Ведомость чертежей','-',1,1)
    s.text(100,15,'Манипулятор: ведомость деталей и листов',5)
    s.text(25,28,'27 наименований, %d печатных деталей. Исходная сборка, без переделки под MG996R.'%sum(p['quantity'] for p in manifest['parts']),3.5)
    x=[25,37,77,223,240,405]
    s.rect(25,36,380,8+27*6.5,.5)
    for xx in x[1:-1]:s.line(xx,36,xx,36+8+27*6.5,.25)
    for xx,label in zip(x,['Поз.','Обозначение','Наименование','Кол.','Исходник FreeCAD']):s.text(xx+1,42,label,3)
    for row,p in enumerate(manifest['parts']):
        y=44+row*6.5
        vals=[str(p['position']),p['designation'],NAMES[p['stem']],str(p['quantity']),p['stem']+'.FCStd']
        for xx,val in zip(x,vals):s.text(xx+1,y+4.5,val,2.5)
        s.line(25,y+6.5,405,y+6.5,.18)
    s.text(25,235,'Это ведомость печатных деталей, а не полная спецификация изделия.',3)
    s.text(25,244,'Крепёж, подшипники, сервоприводы и электрика требуют отдельного учёта.',3)
    s.text(25,253,'Статус: предварительные справочные чертежи. Нормоконтроль не пройден.',3)
    s.text(25,262,'Проекции: FreeCAD TechDraw HLR. Геометрия деталей: BasementMaker, CC BY.',3)
    s.text(25,271,'Оформление: ГОСТ Р 2.104-2023; ГОСТ 2.301, 2.302, 2.303, 2.305, 2.307.',3)
    s.text(25,280,'Дата подготовки: 15.10.2026. Утверждение и выпуск в производство не выполнены.',3)
    s.finish()

def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    c=canvas.Canvas(str(PDF/'RobotArm_drawings_preliminary.pdf'),pagesize=(420*mm,297*mm),pageCompression=1)
    c.setTitle('Манипулятор - предварительные чертежи по геометрии FreeCAD')
    c.setAuthor('Учебный проект; исходная геометрия BasementMaker (CC BY)')
    intro(c,manifest)
    assembly_page(c,manifest)
    for p in manifest['parts']:
        d=json.loads((OUT/'geometry'/(p['stem']+'.json')).read_text())
        part_pages(c,d)
        print('Drawing: '+p['designation']+' '+NAMES[p['stem']],flush=True)
    c.save()
    (OUT/'names_ru.json').write_text(json.dumps(NAMES,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Saved: '+str(PDF/'RobotArm_drawings_preliminary.pdf'),flush=True)

if __name__=='__main__':main()
