#!/usr/bin/env bash
set -euo pipefail

# 사용법:
#   bash install_deps.sh
#   또는
#   ./install_deps.sh

python3 -m pip install -U pip wheel setuptools
python3 -m pip install -r requirements.txt
