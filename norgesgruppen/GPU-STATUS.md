# GPU Status Report — 2026-03-20

## Local Machine
- **Platform:** macOS (Darwin 24.5.0)
- **GPU:** None (no `nvidia-smi` available)
- **Status:** Cannot train locally — CPU-only training is too slow for YOLOv8x/1280px

## GCP Project: nm-i-ai-490723

### Available GPUs in europe-north1

| GPU | Zone | VRAM | Notes |
|-----|------|------|-------|
| NVIDIA B200 | europe-north1-b | 180GB | Overkill, expensive |
| NVIDIA RTX PRO 6000 | europe-north1-a, b | 48GB | Good option, ample VRAM |
| NVIDIA H100 80GB | europe-north1-c | 80GB | Best performance, expensive |
| NVIDIA H100 MEGA 80GB | europe-north1-c | 80GB | Same as above |

### Notable Absences
- No T4 GPUs in europe-north1 (cheapest option not available)
- No A100 GPUs in europe-north1
- No L4 GPUs in europe-north1

### Recommendation
- **Best value:** RTX PRO 6000 (48GB VRAM, europe-north1-a or b) — plenty of VRAM for YOLOv8x @ 1280px with large batch sizes
- **Best performance:** H100 80GB (europe-north1-c) — fastest training but most expensive
- **Fallback:** Use a different region with T4/L4 GPUs if cost is a concern

### Training Time Estimates (YOLOv8x, 1280px, 200 epochs, 248 images)
- RTX PRO 6000: ~1-2 hours
- H100 80GB: ~30-60 minutes
- T4 (if available): ~3-4 hours

## Action Items
1. Use `train_gcp.sh` to spin up a GCE VM with RTX PRO 6000 or H100
2. Run `train_best.py` on the VM
3. Download the resulting ONNX model
4. Optionally run `model_soup.py` to average multiple checkpoints
