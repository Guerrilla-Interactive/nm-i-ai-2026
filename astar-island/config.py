import os

API_BASE = "https://api.ainm.no/astar-island"
TOKEN = os.environ.get("ASTAR_TOKEN", "")
# Also check ~/.astar-token file as fallback
if not TOKEN:
    token_file = os.path.expanduser("~/.astar-token")
    if os.path.exists(token_file):
        TOKEN = open(token_file).read().strip()

GRID_SIZE = 40
VIEWPORT_MAX = 15
NUM_SEEDS = 5
NUM_CLASSES = 6
QUERIES_PER_ROUND = 50
QUERIES_PER_SEED = 10

# Terrain code mapping: simulation codes → submission class indices
SIM_TO_CLASS = {10: 0, 11: 0, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
CLASS_NAMES = {0: "Empty/Ocean/Plains", 1: "Settlement", 2: "Port", 3: "Ruin", 4: "Forest", 5: "Mountain"}

# Rate limits
SIMULATE_DELAY = 0.22  # seconds between simulate calls (5 req/s limit)
SUBMIT_DELAY = 0.55    # seconds between submit calls (2 req/s limit)
