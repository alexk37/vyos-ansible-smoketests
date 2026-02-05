#!/usr/bin/env bash
set -euo pipefail

# Ensure user-local bin is available
export PATH="$HOME/.local/bin:$PATH"

# Upgrade pip
python3 -m pip install --upgrade pip --break-system-packages

# Install Ansible and dependencies
python3 -m pip install --user \
    ansible-core==2.18.2 \
    ansible-pylibssh \
    --break-system-packages

# Install VyOS Ansible collection
ansible-galaxy collection install \
    git+https://github.com/vyos/vyos.vyos.git,main

