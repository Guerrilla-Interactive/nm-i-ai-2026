# ONNX Model Search Results

**Date:** 2026-03-21

## Result: FOUND in main repo

All three ONNX models exist in the **main repo** submission directory, but are missing from the worktree (likely gitignored/untracked binary files not carried over to worktrees).

### ONNX Files Location

| File | Path | Size |
|------|------|------|
| best_x.onnx | `/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/submission/best_x.onnx` | 219 MB |
| best.onnx | `/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/submission/best.onnx` | 100 MB |
| best_s.onnx | `/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/submission/best_s.onnx` | 43 MB |
| **Total** | | **362 MB** |

**362 MB total — under the 420 MB limit.**

### Model Origins (PyTorch source weights)

| ONNX Model | Likely Source .pt | .pt Size | Training Run |
|------------|-------------------|----------|-------------|
| best_x.onnx (219MB) | yolox_local/train2/weights/best.pt | 131 MB | YOLO11x @ 1280px |
| best.onnx (100MB) | runs/medium_m_640/weights/best.pt | 50 MB | YOLOv8m @ 640px |
| best_s.onnx (43MB) | runs/improved_s_640/weights/best.pt | 22 MB | YOLOv8s @ 640px |

### Why They're Missing from Worktree

ONNX and .pt files are not tracked in git (no git LFS configured, no .gitignore found but files are untracked). Git worktrees only share tracked files, so untracked binary files in the main repo don't appear in worktree checkouts.

### Action Required

To complete the submission from the worktree, copy the ONNX files:
```bash
cp /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/submission/best_x.onnx \
   /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/submission/best.onnx \
   /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/submission/best_s.onnx \
   /tmp/doey/nm-i-ai-2026/worktrees/team-3/norgesgruppen/submission/
```

Or package directly from the main repo:
```bash
cd /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen && python package_submission.py
```
