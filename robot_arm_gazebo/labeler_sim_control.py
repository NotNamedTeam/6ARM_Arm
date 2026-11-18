"""Gazebo-only motion check for the labeler arm.  No physical I/O."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import time

from gz.msgs.world_control_pb2 import WorldControl
from gz.msgs.entity_pb2 import Entity
from gz.msgs.entity_factory_pb2 import EntityFactory
from sim_control import Arm, ROOT

SHOULDER_Z_MM=89.6825
UPPER_ARM_MM=60.0
FOREARM_MM=60.5125
ROLL_JOINT_Z_MM=next(j['z'] for j in json.loads((ROOT/'freecad/joint_setup.json').read_text())['joints']
                     if j['name']=='wrist_roll_joint')
WRIST_TO_ROLLER_Z_MM=122.85+(ROLL_JOINT_Z_MM-287.045)
ROLLER_FRONT_Y_MM=39.0
BOX_FRONT_Y_MM=95.0


def roller_tip_mm(joints):
    shoulder=joints['shoulder_joint']
    elbow=joints['elbow_joint']
    pitch=joints['wrist_pitch_joint']
    orientation=shoulder+elbow+pitch
    return {
        'y': -UPPER_ARM_MM*math.sin(shoulder)
             -FOREARM_MM*math.sin(shoulder+elbow)
             -WRIST_TO_ROLLER_Z_MM*math.sin(orientation)
             +ROLLER_FRONT_Y_MM*math.cos(orientation),
        'z': SHOULDER_Z_MM+UPPER_ARM_MM*math.cos(shoulder)
             +FOREARM_MM*math.cos(shoulder+elbow)
             +WRIST_TO_ROLLER_Z_MM*math.cos(orientation)
             +ROLLER_FRONT_Y_MM*math.sin(orientation),
    }


def measured_tip(robot):
    with robot.lock:
        joints={k:robot.states[k]['position'] for k in
                ('shoulder_joint','elbow_joint','wrist_pitch_joint')}
    return roller_tip_mm(joints)


def wait_precise(robot, targets, tolerance_deg=.35, timeout=30):
    """Wait for the simulated arm to finish correcting its position."""
    deadline=time.monotonic()+timeout
    stable_since=None
    while time.monotonic()<deadline:
        with robot.lock:
            snapshot={name:dict(robot.states[name]) for name in targets}
        precise=all(abs(snapshot[name]['position']-angle)<math.radians(tolerance_deg)
                    and abs(snapshot[name]['velocity'])<.015
                    for name,angle in targets.items())
        if precise:
            stable_since=stable_since or time.monotonic()
            if time.monotonic()-stable_since>=.3:
                return
        else:
            stable_since=None
        time.sleep(.05)
    raise RuntimeError('Simulated arm did not settle to %.2f degrees' % tolerance_deg)


def vertical_head_ik(y_mm,z_mm):
    # Two-link elbow-up solution; the wrist pitch keeps the head upright.
    reach_y=y_mm-ROLLER_FRONT_Y_MM
    reach_z=z_mm-SHOULDER_Z_MM-WRIST_TO_ROLLER_Z_MM
    radius=math.hypot(reach_y,reach_z)
    if not abs(UPPER_ARM_MM-FOREARM_MM)<radius<UPPER_ARM_MM+FOREARM_MM:
        raise ValueError('Requested box pose is outside planar arm reach')
    cos_elbow=(radius*radius-UPPER_ARM_MM**2-FOREARM_MM**2)/(2*UPPER_ARM_MM*FOREARM_MM)
    elbow=math.acos(max(-1,min(1,cos_elbow)))
    bearing=math.atan2(reach_y,reach_z)
    bend=math.atan2(FOREARM_MM*math.sin(elbow),UPPER_ARM_MM+FOREARM_MM*math.cos(elbow))
    shoulder=-(bearing+bend)
    pitch=-shoulder-elbow
    if not -math.radians(25)<=pitch<=math.radians(25):
        raise ValueError('Wrist pitch exceeds nominal +/-25 degree CAD range')
    return {'shoulder_joint':shoulder,'elbow_joint':elbow,'wrist_pitch_joint':pitch}


def feed_label(robot):
    with robot.lock:
        start={k:robot.states[k]['position'] for k in ('feed_joint','pinch_joint')}
    target_rad=22/5.0
    deadline=time.monotonic()+12
    robot.publish('feed_joint',1.8,velocity=True)
    robot.publish('pinch_joint',1.8,velocity=True)
    try:
        while time.monotonic()<deadline:
            with robot.lock:
                positions={k:robot.states[k]['position'] for k in start}
            if positions['feed_joint']-start['feed_joint']>=target_rad:
                break
            time.sleep(.04)
        else:
            raise RuntimeError('Feed roller did not complete one nominal label pitch')
    finally:
        robot.publish('feed_joint',0,velocity=True)
        robot.publish('pinch_joint',0,velocity=True)
    time.sleep(.4)
    with robot.lock:
        end={k:robot.states[k]['position'] for k in start}
    delta={k:end[k]-start[k] for k in start}
    if delta['pinch_joint']<.8*delta['feed_joint']:
        raise RuntimeError('Pinch roller did not rotate with feed roller')
    return {'target_liner_mm':22,'computed_feed_mm':5*delta['feed_joint'],
            'feed_angle_rad':delta['feed_joint'],'pinch_angle_rad':delta['pinch_joint'],
            'note':'Joint feedback only: no flexible liner or adhesion model'}


def application_demo(robot,home):
    report={'result':'running','hardware_connection':'none',
            'started_at':datetime.now(timezone.utc).isoformat(),
            'model_sha256':hashlib.sha256((ROOT/'export/robot_arm_freecad/model.sdf').read_bytes()).hexdigest(),
            'box_front_y_mm':BOX_FRONT_Y_MM,
            'positions_mm':{'home':measured_tip(robot)},
            'joint_phases':robot.results,
            'contact_model':'visual alignment only; carton and label have no collision or adhesive physics'}
    path=ROOT/'export/application_motion_test.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    try:
        try:
            robot.service('/remove/blocking',Entity(name='applied_label',type=Entity.MODEL))
        except RuntimeError:
            pass
        print('Выдать наклейку из рулона на расстоянии от коробки.',flush=True)
        report['feed']=feed_label(robot)
        top_z=(SHOULDER_Z_MM+UPPER_ARM_MM*math.cos(math.radians(35))
               +FOREARM_MM*math.cos(math.radians(20))+WRIST_TO_ROLLER_Z_MM)
        bottom_z=top_z-20
        approach=vertical_head_ik(BOX_FRONT_Y_MM-10,top_z)
        contact=vertical_head_ik(BOX_FRONT_Y_MM,top_z)
        bottom=vertical_head_ik(BOX_FRONT_Y_MM,bottom_z)
        print('Подвести ролик к удалённой стенке коробки.',flush=True)
        robot.move('Подвод с номинальным зазором 10 мм',approach)
        report['positions_mm']['approach']=measured_tip(robot)
        if not 2<=BOX_FRONT_Y_MM-report['positions_mm']['approach']['y']<=15:
            raise RuntimeError('Head did not stop at a safe approach distance')
        robot.move('Прижать верхний край этикетки',contact)
        wait_precise(robot,contact)
        report['positions_mm']['contact']=measured_tip(robot)
        if abs(report['positions_mm']['contact']['y']-BOX_FRONT_Y_MM)>2:
            raise RuntimeError('Head did not align with the reference box wall')
        print('Прижим и непрерывный ход вниз на 20 мм.',flush=True)
        duration=4.5
        start=time.monotonic()
        while True:
            fraction=min((time.monotonic()-start)/duration,1)
            blend=fraction*fraction*(3-2*fraction)
            targets=vertical_head_ik(BOX_FRONT_Y_MM,top_z-20*blend)
            for name,angle in targets.items():
                robot.publish(name,angle)
            if fraction>=1:
                break
            time.sleep(.04)
        robot.targets(bottom)
        robot.settle(bottom,timeout=20)
        wait_precise(robot,bottom)
        report['positions_mm']['after_downstroke']=measured_tip(robot)
        if report['positions_mm']['contact']['z']-report['positions_mm']['after_downstroke']['z']<18:
            raise RuntimeError('Downward stroke was less than 18 mm by kinematic estimate')
        if abs(report['positions_mm']['after_downstroke']['y']-BOX_FRONT_Y_MM)>2:
            raise RuntimeError('Head left the reference wall during downward stroke')
        print('Отвести ролик от коробки.',flush=True)
        robot.move('Отвод ролика',{'wrist_pitch_joint':bottom['wrist_pitch_joint']+math.radians(10)})
        report['positions_mm']['retreated']=measured_tip(robot)
        if report['positions_mm']['retreated']['y']>=report['positions_mm']['after_downstroke']['y']-10:
            raise RuntimeError('Head did not withdraw from the box')
        factory=EntityFactory(sdf_filename=str(ROOT/'export/applied_label.sdf'),
                              name='applied_label',allow_renaming=False)
        robot.service('/create/blocking',factory)
        print('На коробке показана условно приклеенная этикетка 20×20 мм.',flush=True)
        robot.move('Возврат к исходной позиции',home)
        wait_precise(robot,home)
        report['positions_mm']['returned_home']=measured_tip(robot)
        report['result']='passed'
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print('Клеющее движение пройдено:',path,flush=True)
    except BaseException as error:
        report['result']='failed'
        report['error']=str(error)
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        try:
            robot.move('Безопасный возврат после ошибки симуляции',home)
        except Exception as return_error:
            report['return_error']=str(return_error)
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        raise


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['demo','apply-demo','status','home','stop','reload'])
    args = parser.parse_args()
    robot = Arm()
    try:
        robot.wait_ready(timeout=20)
        if args.action == 'reload':
            robot.reload()
            robot.wait_ready(timeout=20)
            return
        robot.service('/control',WorldControl(pause=False))
        if args.action == 'status':
            with robot.lock:
                print(json.dumps(robot.states,indent=2))
            return
        if args.action == 'stop':
            robot.publish('feed_joint',0,velocity=True)
            robot.publish('pinch_joint',0,velocity=True)
            with robot.lock:
                targets={k:v['position'] for k,v in robot.states.items()
                         if k not in ('feed_joint','pinch_joint')}
            robot.targets(targets)
            return
        home={k:0 for k in ('base_yaw_joint','shoulder_joint','elbow_joint',
                            'wrist_pitch_joint','wrist_roll_joint')}
        robot.publish('feed_joint',0,velocity=True)
        robot.publish('pinch_joint',0,velocity=True)
        robot.move('Вертикальная опорная поза',home)
        if args.action == 'home':
            return
        if args.action == 'apply-demo':
            wait_precise(robot,home)
            application_demo(robot,home)
            return
        report={'result':'running','hardware_connection':'none',
                'started_at':datetime.now(timezone.utc).isoformat(),
                'model_sha256':hashlib.sha256((ROOT/'export/robot_arm_freecad/model.sdf').read_bytes()).hexdigest(),
                'phases':robot.results,'feed':None}
        path=ROOT/'export/labeler_motion_test.json'
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        try:
            for joint,offset in [('base_yaw_joint',30),('shoulder_joint',12),
                                 ('elbow_joint',-12),('wrist_pitch_joint',12),
                                 ('wrist_roll_joint',20)]:
                robot.move(joint+' → смещение', {joint:math.radians(offset)})
                robot.move(joint+' → 0', {joint:0})
            print('Протяжка: 22 мм по расчётному диаметру 10 мм.',flush=True)
            report['feed']=feed_label(robot)
            robot.move('Совместное движение к коробке',{
                'base_yaw_joint':math.radians(10),'shoulder_joint':math.radians(8),
                'elbow_joint':math.radians(-8),'wrist_pitch_joint':math.radians(8)})
            robot.move('Вертикальная поза после цикла',home)
            report['result']='passed'
            report['finished_at']=datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
            print('Проверка движения пройдена; модель и измерения:',path,flush=True)
        except BaseException as error:
            report['result']='failed'
            report['error']=str(error)
            report['finished_at']=datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
            raise
    finally:
        try:
            robot.publish('feed_joint',0,velocity=True)
            robot.publish('pinch_joint',0,velocity=True)
        finally:
            robot.close()


if __name__=='__main__':
    run()
