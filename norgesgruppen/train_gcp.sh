#!/usr/bin/env bash
#
# Launch a GCE VM with GPU for YOLO11x training, run training, download results.
#
# Usage:
#   bash train_gcp.sh                    # RTX PRO 6000, europe-north1-a
#   bash train_gcp.sh --gpu h100         # H100 80GB, europe-north1-c
#   bash train_gcp.sh --dry-run          # Print commands without executing
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Project nm-i-ai-490723

set -euo pipefail

# === Configuration ===
PROJECT="nm-i-ai-490723"
REGION="europe-north1"
VM_NAME="yolo-train-$(date +%Y%m%d-%H%M%S)"
MACHINE_TYPE="n1-standard-8"
BOOT_DISK_SIZE="100GB"
BOOT_IMAGE="projects/ml-images/global/images/family/common-gpu"
GPU_TYPE="nvidia-rtx-pro-6000"
GPU_ZONE="${REGION}-a"
GPU_COUNT=1
DRY_RUN=false
REPO_URL=""  # Set to your repo URL if you want to clone, else we'll SCP files

# === Parse arguments ===
while [[ $# -gt 0 ]]; do
    case $1 in
        --gpu)
            case $2 in
                h100)
                    GPU_TYPE="nvidia-h100-80gb"
                    GPU_ZONE="${REGION}-c"
                    MACHINE_TYPE="a3-highgpu-1g"
                    ;;
                rtx6000|rtx-pro-6000)
                    GPU_TYPE="nvidia-rtx-pro-6000"
                    GPU_ZONE="${REGION}-a"
                    ;;
                *)
                    echo "Unknown GPU type: $2 (use h100 or rtx6000)"
                    exit 1
                    ;;
            esac
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "GCP GPU Training Setup"
echo "============================================"
echo "  Project:  $PROJECT"
echo "  VM:       $VM_NAME"
echo "  Zone:     $GPU_ZONE"
echo "  GPU:      $GPU_TYPE x$GPU_COUNT"
echo "  Machine:  $MACHINE_TYPE"
echo "  Disk:     $BOOT_DISK_SIZE"
echo "============================================"

run_cmd() {
    if $DRY_RUN; then
        echo "[DRY RUN] $*"
    else
        echo "[RUN] $*"
        eval "$@"
    fi
}

# === Step 1: Create VM ===
echo ""
echo ">>> Step 1: Creating VM with GPU..."
run_cmd gcloud compute instances create "$VM_NAME" \
    --project="$PROJECT" \
    --zone="$GPU_ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --accelerator="type=$GPU_TYPE,count=$GPU_COUNT" \
    --boot-disk-size="$BOOT_DISK_SIZE" \
    --image-family="common-gpu" \
    --image-project="ml-images" \
    --maintenance-policy=TERMINATE \
    --metadata="install-nvidia-driver=True"

if ! $DRY_RUN; then
    echo "Waiting 60s for VM to boot and install drivers..."
    sleep 60
fi

# === Step 2: Upload training files ===
echo ""
echo ">>> Step 2: Uploading training files..."
run_cmd gcloud compute scp --zone="$GPU_ZONE" --project="$PROJECT" --recurse \
    "$SCRIPT_DIR/train_best.py" \
    "$SCRIPT_DIR/norgesgruppen.yaml" \
    "$SCRIPT_DIR/data/" \
    "${VM_NAME}:~/training/"

# Upload synthetic data YAML if it exists
if [[ -f "$SCRIPT_DIR/norgesgruppen_with_synthetic.yaml" ]]; then
    run_cmd gcloud compute scp --zone="$GPU_ZONE" --project="$PROJECT" \
        "$SCRIPT_DIR/norgesgruppen_with_synthetic.yaml" \
        "${VM_NAME}:~/training/"
fi

# === Step 3: Install dependencies and run training ===
echo ""
echo ">>> Step 3: Installing deps and starting training..."
TRAIN_SCRIPT='
set -e
cd ~/training

# Install Python deps
pip install --quiet ultralytics opencv-python-headless

# Verify GPU
python -c "import torch; print(f\"GPU: {torch.cuda.get_device_name(0)}, VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB\")"

# Run training
python train_best.py --prepare-submission 2>&1 | tee train.log

echo "=== TRAINING DONE ==="
ls -lh runs/best_x_1280/weights/
'

run_cmd gcloud compute ssh "$VM_NAME" \
    --zone="$GPU_ZONE" \
    --project="$PROJECT" \
    --command="$TRAIN_SCRIPT"

# === Step 4: Download results ===
echo ""
echo ">>> Step 4: Downloading results..."
RESULTS_DIR="$SCRIPT_DIR/runs/best_x_1280"
mkdir -p "$RESULTS_DIR/weights"

run_cmd gcloud compute scp --zone="$GPU_ZONE" --project="$PROJECT" --recurse \
    "${VM_NAME}:~/training/runs/best_x_1280/weights/" \
    "$RESULTS_DIR/weights/"

run_cmd gcloud compute scp --zone="$GPU_ZONE" --project="$PROJECT" \
    "${VM_NAME}:~/training/train.log" \
    "$RESULTS_DIR/train.log"

# === Step 5: Verify ONNX size ===
echo ""
echo ">>> Step 5: Checking ONNX model..."
ONNX_FILE="$RESULTS_DIR/weights/best.onnx"
if [[ -f "$ONNX_FILE" ]]; then
    SIZE_MB=$(du -m "$ONNX_FILE" | cut -f1)
    echo "ONNX model: ${SIZE_MB} MB"
    if [[ $SIZE_MB -gt 420 ]]; then
        echo "WARNING: Exceeds 420MB competition limit!"
    else
        echo "OK: Under 420MB limit"
    fi
else
    echo "WARNING: ONNX file not found at $ONNX_FILE"
fi

# === Step 6: Clean up VM ===
echo ""
echo ">>> Step 6: Cleaning up..."
echo "VM $VM_NAME is still running. To delete it:"
echo "  gcloud compute instances delete $VM_NAME --zone=$GPU_ZONE --project=$PROJECT --quiet"
echo ""
read -p "Delete VM now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    run_cmd gcloud compute instances delete "$VM_NAME" \
        --zone="$GPU_ZONE" \
        --project="$PROJECT" \
        --quiet
    echo "VM deleted."
else
    echo "VM kept running. Remember to delete it when done!"
fi

echo ""
echo "============================================"
echo "Results saved to: $RESULTS_DIR"
echo "============================================"
