#!/usr/bin/env bash
set -euo pipefail
variant_root="$(cd -- "$(dirname -- "$0")" && pwd)"
unset PYTHONHOME PYTHONPATH LD_LIBRARY_PATH ROS_DISTRO
set +u
source /opt/ros/lyrical/setup.bash
set -u
export GZ_PARTITION=robot_arm_mg996r_valet
export GZ_IP=127.0.0.1
export ROBOT_ARM_ROOT="$variant_root"
exec python3 "$variant_root/../../sim_control.py" "$@"
