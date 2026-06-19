#!/usr/bin/env bash
set -e

apt-get update
apt-get install -y ros-${ROS_DISTRO:-humble}-hri-msgs

# Most heavy dependencies are expected to be preinstalled in vulx-mmdet:jp6-cu122.
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
