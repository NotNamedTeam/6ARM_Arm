#!/usr/bin/env bash
set -euo pipefail
variant_root="$(cd -- "$(dirname -- "$0")" && pwd)"
unset PYTHONHOME PYTHONPATH LD_LIBRARY_PATH QT_QPA_PLATFORM_PLUGIN_PATH QT_PLUGIN_PATH
unset QT_QPA_PLATFORM PREFIX PATH_TO_FREECAD_LIBDIR
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_DISTRO ROS_VERSION
set +u
source /opt/ros/lyrical/setup.bash
set -u
export GZ_SIM_RESOURCE_PATH="$variant_root/export${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_PARTITION=robot_arm_labeler_mg996r_n20
export GZ_IP=127.0.0.1
exec flock -n "$variant_root/export/gazebo.lock" gz sim "$variant_root/export/preview.sdf" \
  --gui-config "$variant_root/export/gui.config" "$@"
