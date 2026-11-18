#!/usr/bin/env bash
set -euo pipefail
robot_root="$(cd -- "$(dirname -- "$0")" && pwd)"
# Remove the portable FreeCAD Python/Qt environment before starting Gazebo.
unset PYTHONHOME PYTHONPATH LD_LIBRARY_PATH QT_QPA_PLATFORM_PLUGIN_PATH QT_PLUGIN_PATH
unset QT_QPA_PLATFORM PREFIX PATH_TO_FREECAD_LIBDIR
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_DISTRO ROS_VERSION
set +u
source /opt/ros/lyrical/setup.bash
set -u
export GZ_SIM_RESOURCE_PATH="$robot_root/export${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_PARTITION=robot_arm_freecad
export GZ_IP=127.0.0.1
exec flock -n "$robot_root/export/gazebo.lock" gz sim "$robot_root/export/preview.sdf" \
  --gui-config "$robot_root/export/gui.config" "$@"
