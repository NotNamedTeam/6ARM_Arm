#!/usr/bin/env bash
set -euo pipefail
robot_root="$(cd -- "$(dirname -- "$0")" && pwd)"
unset PYTHONHOME PYTHONPATH LD_LIBRARY_PATH ROS_DISTRO
set +u
source /opt/ros/lyrical/setup.bash
set -u
export GZ_SIM_RESOURCE_PATH="$robot_root/export${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_PARTITION=robot_arm_freecad
export GZ_IP=127.0.0.1
exec python3 "$robot_root/sim_control.py" "$@"
