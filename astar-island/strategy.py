"""Query strategy: 9-tile full coverage + 1 spare center query."""

# 3x3 tiling with 15x15 viewports covering the full 40x40 grid
# Offsets: [0, 13, 25] → viewports [0-14], [13-27], [25-39]
TILE_OFFSETS = [0, 13, 25]

TILE_POSITIONS = [
    (row, col) for row in TILE_OFFSETS for col in TILE_OFFSETS
]

# Priority order: center first, then edges, then corners
QUERY_ORDER = [
    (13, 13),  # center
    (0, 13),   # top-center
    (13, 0),   # mid-left
    (13, 25),  # mid-right
    (25, 13),  # bottom-center
    (0, 0),    # top-left
    (0, 25),   # top-right
    (25, 0),   # bottom-left
    (25, 25),  # bottom-right
]


def get_query_plan(seed_index: int) -> list[dict]:
    """Return list of 10 query dicts for a seed.

    Keys match what solver.py expects: x, y, w, h, label.
    """
    queries = []
    labels = ["center", "top-center", "mid-left", "mid-right", "bottom-center",
              "top-left", "top-right", "bottom-left", "bottom-right"]
    for i, (row, col) in enumerate(QUERY_ORDER):
        queries.append({
            "seed_index": seed_index,
            "x": col,
            "y": row,
            "w": 15,
            "h": 15,
            # Also include viewport_* keys for backwards compat with test script
            "viewport_x": col,
            "viewport_y": row,
            "viewport_w": 15,
            "viewport_h": 15,
            "label": labels[i],
        })
    # 10th query: repeat center for stochastic sampling
    queries.append({
        "seed_index": seed_index,
        "x": 13,
        "y": 13,
        "w": 15,
        "h": 15,
        "viewport_x": 13,
        "viewport_y": 13,
        "viewport_w": 15,
        "viewport_h": 15,
        "label": "center-repeat",
    })
    return queries
