#!/usr/bin/env bash
# Local clone paths — short names mirror long repo folder names.
# Usage (from any shell):
#   export CODE_HOME="${CODE_HOME:-$HOME/code}"   # optional; defaults to ~/code
#   source /path/to/10xProductivity/tool_connections/repo_paths.sh
#
# If you keep CODE_HOME in .env, run from 10xProductivity root:
#   set -a && source .env && set +a && source tool_connections/repo_paths.sh

_root="${CODE_HOME:-$HOME/code}"
export REPO_10XPRODUCTIVITY="$_root/10xProductivity"
export REPO_10X="$REPO_10XPRODUCTIVITY"
export REPO_EDDG_RDA="$_root/EDDG-RDA"
export REPO_EDDG="$REPO_EDDG_RDA"
export REPO_COLLABORATION_STATION="$_root/collaboration-station"
export REPO_COLLAB="$REPO_COLLABORATION_STATION"
unset _root
