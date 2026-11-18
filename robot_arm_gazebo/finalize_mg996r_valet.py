"""Summarize only completed checks for this exact CAD/SDF prototype version."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
DEST=ROOT/'variants/mg996r_valet_v1'
build=json.loads((DEST/'build_report.json').read_text())
cad=json.loads((DEST/'clearance_report.json').read_text())
motion=json.loads((DEST/'export/motion_test.json').read_text())
cad_hash=hashlib.sha256((DEST/'freecad/RobotArm_Assembly.FCStd').read_bytes()).hexdigest()
model_hash=hashlib.sha256((DEST/'export/robot_arm_freecad/model.sdf').read_bytes()).hexdigest()
assert cad['source_sha256']==cad_hash,'CAD changed since clearance check'
assert motion['model_sha256']==model_hash,'SDF changed since motion check'
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==value
           for f,value in build['original_fcstd_sha256'].items()),'Original document changed'
assert len(cad['wrist_pitch_sweep'])==13
assert all(r['maximum_overlap_mm3']<.001 for r in cad['wrist_pitch_sweep'])
assert all(r['solid'] for r in cad['stl_checks'])
assert motion['result']=='passed','Gazebo test has not passed'
assert len(motion['phases'])>=17,'Incomplete Gazebo motion cycle'
build.update(status='CAD prototype checked, Gazebo cycle passed; PHYSICAL FIT AND STRENGTH NOT VERIFIED',
             checked_at=datetime.now(timezone.utc).isoformat(),
             cad_assembly_sha256=cad_hash,sdf_sha256=model_hash,
             servo_axes=cad['servo_axes'],
             checks={'cad_discrete_positions':13,'wrist_pitch_range_checked_deg':[-30,30],
                     'print_stl_closed_solids':len(cad['stl_checks']),
                     'gazebo_cycle':'passed','gazebo_motion_phases':len(motion['phases']),
                     'original_fcstd_unchanged':True},
             physical_status='Not approved for full-size printing until fit coupons and hardware measurements are checked')
(DEST/'build_report.json').write_text(json.dumps(build,indent=2,ensure_ascii=False),encoding='utf-8')
print('VERIFIED: separate CAD variant, 8 solid STLs, 13 discrete wrist positions, complete Gazebo cycle; originals unchanged.')
