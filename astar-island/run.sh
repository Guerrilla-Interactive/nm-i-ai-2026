#!/usr/bin/env bash
# Astar Island Solver — run script
# Usage: ./run.sh [options]
#
# Prerequisites:
#   pip install numpy requests
#   Set token: export ASTAR_TOKEN="your-jwt-token"
#   Or:        echo "your-jwt-token" > ~/.astar-token

set -euo pipefail
cd "$(dirname "$0")"

# Check token
if [ -z "${ASTAR_TOKEN:-}" ] && [ ! -f ~/.astar-token ]; then
    echo "ERROR: No auth token found."
    echo "  export ASTAR_TOKEN='your-jwt-from-app.ainm.no'"
    echo "  OR: echo 'your-jwt' > ~/.astar-token"
    exit 1
fi

# Default: solve all seeds on active round
python3 solver.py "$@"
