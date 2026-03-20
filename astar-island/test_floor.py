#!/usr/bin/env python3
"""Test if API accepts predictions with values < 0.005"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from client import AstarClient

ROUND_ID = "f1dac9a9-5cf1-49a9-8f17-d6cb5d5ba5cb"

token = os.environ.get("ASTAR_TOKEN", "")
if not token:
    print("Set ASTAR_TOKEN"); sys.exit(1)

client = AstarClient(token)
rnd = client.get_round(ROUND_ID)

# Build a test prediction with floor=0.001
from resubmit_simple import predict_from_initial
pred = predict_from_initial(rnd.initial_states[0].grid, floor=0.001)
print(f"Min value: {pred.min():.6f}")
print(f"Trying submit seed 0 with floor=0.001...")
try:
    result = client.submit(ROUND_ID, 0, pred.tolist())
    print(f"Result: {result}")
except Exception as e:
    print(f"ERROR: {e}")
