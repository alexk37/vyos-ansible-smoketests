#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./vyos-ansible-install.sh
#     → installs the default VyOS Ansible collection (upstream, main branch)
#
#   ./vyos-ansible-install.sh <repo-url> [ref]
#     → installs VyOS Ansible collection from a custom Git repository and branch/tag
#     → example:
#         ./vyos-ansible-install.sh https://github.com/myfork/vyos.vyos.git dev

# Ensure ~/.local/bin is on PATH
export PATH="$HOME/.local/bin:$PATH"

# Default repo (plain URL, no git+)
DEFAULT_COLLECTION_REPO="https://github.com/vyos/vyos.vyos.git"
DEFAULT_COLLECTION_REF="main"

# Optional argument: repo URL (plain)
COLLECTION_REPO="${1:-$DEFAULT_COLLECTION_REPO}"
COLLECTION_REF="${2:-$DEFAULT_COLLECTION_REF}"

COLLECTION_URL="git+${COLLECTION_REPO},${COLLECTION_REF}"

echo "Using VyOS Ansible collection:"
echo "  Repo : $COLLECTION_REPO"
echo "  Ref  : $COLLECTION_REF"
echo

# Upgrade pip
python3 -m pip install --upgrade pip --break-system-packages

# Install Ansible and dependencies
python3 -m pip install --user \
    ansible-core==2.18.2 \
    ansible-pylibssh \
    --break-system-packages

# Install VyOS Ansible collection
ansible-galaxy collection install "$COLLECTION_URL"

# If ansible is not on PATH
echo
echo "⚠️  ansible is installed but it may not be on PATH"
echo 'Run: export PATH="$HOME/.local/bin:$PATH"'
echo
