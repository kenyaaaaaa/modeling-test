#!/usr/bin/env bash
# Python 3.13 venv with Blender as a module (bpy) and the Mesa libraries that
# Workbench/Eevee need to render without a GPU.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! ldconfig -p | grep -q libEGL.so.1; then
  sudo=""; [ "$(id -u)" -ne 0 ] && sudo="sudo"
  $sudo apt-get update -q
  $sudo apt-get install -y -q libegl1 libegl-mesa0 libgl1-mesa-dri libglx-mesa0 libxkbcommon0 libsm6 libxi6 libxxf86vm1 libxfixes3 libxrender1
fi
"${PYTHON:-python3.13}" -m venv .venv
.venv/bin/pip install -q -r requirements.txt
