#!/bin/bash
# =============================================================================
# RunPod Setup Guide — NorgesGruppen Object Detection
# =============================================================================
# How to upload data to a RunPod pod and download results.
#
# RunPod provides SSH access via: ssh root@<POD_IP> -p <PORT> -i ~/.ssh/id_ed25519
# Find your pod's SSH command in the RunPod dashboard under "Connect".
# =============================================================================

set -euo pipefail

# --- Configuration (edit these) ---
POD_SSH=""          # e.g., "root@123.45.67.89" or from RunPod dashboard
POD_PORT="22"       # RunPod SSH port (check dashboard, often 22 or a high port)
SSH_KEY=""          # e.g., "~/.ssh/id_ed25519" (leave empty if using password)

# Local paths
LOCAL_REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_NORGESGRUPPEN="${LOCAL_REPO}/norgesgruppen"
LOCAL_DATA="${LOCAL_NORGESGRUPPEN}/data"

# Remote paths
REMOTE_WORKSPACE="/workspace"
REMOTE_REPO="${REMOTE_WORKSPACE}/nm-i-ai-2026"
REMOTE_DATA="${REMOTE_WORKSPACE}/data"

# Build SSH/SCP options
SSH_OPTS="-p ${POD_PORT}"
if [ -n "${SSH_KEY}" ]; then
    SSH_OPTS="${SSH_OPTS} -i ${SSH_KEY}"
fi

usage() {
    cat <<'USAGE'
Usage: ./runpod_setup.sh <command>

Commands:
  upload-all     Upload repo code + dataset to the pod
  upload-code    Upload only the repo code (no data)
  upload-data    Upload only the dataset
  download       Download trained model (best.onnx) from pod
  status         Check training status on the pod
  help           Show detailed manual setup instructions

Before running, edit POD_SSH and POD_PORT at the top of this script,
or set them as environment variables:
  POD_SSH="root@1.2.3.4" POD_PORT=22 ./runpod_setup.sh upload-all
USAGE
}

check_pod_ssh() {
    if [ -z "${POD_SSH}" ]; then
        echo "ERROR: POD_SSH is not set."
        echo ""
        echo "Set it at the top of this script or via environment variable:"
        echo "  POD_SSH=\"root@<POD_IP>\" POD_PORT=<PORT> ./runpod_setup.sh <command>"
        echo ""
        echo "Find your SSH details in the RunPod dashboard → your pod → Connect"
        exit 1
    fi
}

cmd_upload_code() {
    check_pod_ssh
    echo "Uploading repo code to ${POD_SSH}:${REMOTE_REPO}/ ..."
    ssh ${SSH_OPTS} "${POD_SSH}" "mkdir -p ${REMOTE_REPO}"

    rsync -avz --progress \
        -e "ssh ${SSH_OPTS}" \
        --exclude 'data/' \
        --exclude 'runs/' \
        --exclude '__pycache__/' \
        --exclude '.venv/' \
        --exclude '*.onnx' \
        --exclude '*.pt' \
        --exclude 'submission/' \
        --exclude 'submission.zip' \
        "${LOCAL_REPO}/" "${POD_SSH}:${REMOTE_REPO}/"

    echo "Code uploaded."
}

cmd_upload_data() {
    check_pod_ssh

    if [ ! -d "${LOCAL_DATA}" ]; then
        echo "ERROR: Local data directory not found: ${LOCAL_DATA}"
        echo "Expected: ${LOCAL_DATA}/annotations.json and ${LOCAL_DATA}/images/"
        exit 1
    fi

    echo "Uploading dataset to ${POD_SSH}:${REMOTE_DATA}/ ..."
    ssh ${SSH_OPTS} "${POD_SSH}" "mkdir -p ${REMOTE_DATA}"

    rsync -avz --progress \
        -e "ssh ${SSH_OPTS}" \
        --exclude 'images/train/' \
        --exclude 'images/val/' \
        --exclude 'labels/' \
        "${LOCAL_DATA}/" "${POD_SSH}:${REMOTE_DATA}/"

    echo "Dataset uploaded."
}

cmd_upload_all() {
    cmd_upload_code
    echo ""
    cmd_upload_data
    echo ""
    echo "============================================================"
    echo "All files uploaded. Now SSH into the pod and run:"
    echo "  ssh ${SSH_OPTS} ${POD_SSH}"
    echo "  cd ${REMOTE_REPO}/norgesgruppen"
    echo "  chmod +x runpod_train.sh && ./runpod_train.sh"
    echo "============================================================"
}

cmd_download() {
    check_pod_ssh
    RUN_NAME="runpod_yolov8l_1280"
    REMOTE_ONNX="${REMOTE_REPO}/norgesgruppen/runs/${RUN_NAME}/weights/best.onnx"
    REMOTE_PT="${REMOTE_REPO}/norgesgruppen/runs/${RUN_NAME}/weights/best.pt"
    LOCAL_DST="${LOCAL_NORGESGRUPPEN}"

    echo "Downloading trained model from pod..."

    # Download best.onnx
    echo "  Fetching best.onnx..."
    scp ${SSH_OPTS} "${POD_SSH}:${REMOTE_ONNX}" "${LOCAL_DST}/best.onnx" 2>/dev/null && \
        echo "  Saved: ${LOCAL_DST}/best.onnx" || \
        echo "  WARNING: best.onnx not found on pod (training may still be running)"

    # Also download best.pt as backup
    echo "  Fetching best.pt..."
    scp ${SSH_OPTS} "${POD_SSH}:${REMOTE_PT}" "${LOCAL_DST}/best.pt" 2>/dev/null && \
        echo "  Saved: ${LOCAL_DST}/best.pt" || \
        echo "  WARNING: best.pt not found on pod"

    # Download training results CSV
    REMOTE_CSV="${REMOTE_REPO}/norgesgruppen/runs/${RUN_NAME}/results.csv"
    scp ${SSH_OPTS} "${POD_SSH}:${REMOTE_CSV}" "${LOCAL_DST}/results.csv" 2>/dev/null && \
        echo "  Saved: ${LOCAL_DST}/results.csv" || true

    echo ""
    echo "Done. To package the submission:"
    echo "  cd ${LOCAL_NORGESGRUPPEN}"
    echo "  python export_onnx.py --weights best.pt --imgsz 1280 --simplify  # if re-exporting"
    echo "  python package_submission.py"
}

cmd_status() {
    check_pod_ssh
    RUN_NAME="runpod_yolov8l_1280"
    echo "Checking training status on pod..."
    echo ""

    # Check if training process is running
    ssh ${SSH_OPTS} "${POD_SSH}" "
        echo '--- GPU Status ---'
        nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv 2>/dev/null || echo 'nvidia-smi not available'
        echo ''

        echo '--- Training Process ---'
        ps aux | grep -E 'python|yolo' | grep -v grep || echo 'No training process found'
        echo ''

        RESULTS='${REMOTE_REPO}/norgesgruppen/runs/${RUN_NAME}/results.csv'
        if [ -f \"\${RESULTS}\" ]; then
            EPOCHS=\$(wc -l < \"\${RESULTS}\")
            echo \"--- Progress: \$((EPOCHS - 1))/200 epochs ---\"
            echo 'Last 3 epochs:'
            tail -3 \"\${RESULTS}\" | column -t -s,
        else
            echo '--- No results.csv found (training may not have started) ---'
        fi

        echo ''
        BEST='${REMOTE_REPO}/norgesgruppen/runs/${RUN_NAME}/weights/best.pt'
        if [ -f \"\${BEST}\" ]; then
            SIZE=\$(du -h \"\${BEST}\" | cut -f1)
            echo \"best.pt exists (\${SIZE})\"
        else
            echo 'best.pt not yet created'
        fi
    "
}

cmd_help() {
    cat <<'HELP'
=============================================================================
  MANUAL SETUP INSTRUCTIONS — RunPod GPU Training
=============================================================================

1. CREATE A RUNPOD POD
   - Go to https://www.runpod.io/
   - Choose a GPU pod (recommended: RTX 4090, A100, or L40S)
   - Use the PyTorch template (comes with CUDA + Python)
   - Note the SSH connection details from the dashboard

2. UPLOAD DATA TO THE POD

   # Upload the repo
   rsync -avz --exclude 'data/' --exclude 'runs/' --exclude '.venv/' \
     /path/to/nm-i-ai-2026/ root@<POD_IP>:/workspace/nm-i-ai-2026/

   # Upload the dataset
   rsync -avz /path/to/norgesgruppen/data/ root@<POD_IP>:/workspace/data/

   Expected structure on pod:
     /workspace/data/annotations.json
     /workspace/data/images/*.jpg
     /workspace/nm-i-ai-2026/norgesgruppen/  (repo code)

3. RUN TRAINING

   ssh root@<POD_IP>
   cd /workspace/nm-i-ai-2026/norgesgruppen
   chmod +x runpod_train.sh

   # Run in tmux so it survives disconnection
   tmux new -s train
   ./runpod_train.sh
   # Detach: Ctrl+B, then D
   # Reattach: tmux attach -t train

4. MONITOR TRAINING

   # From the pod:
   tail -f runs/runpod_yolov8l_1280/results.csv
   nvidia-smi -l 5

5. DOWNLOAD RESULTS

   # From your local machine:
   scp root@<POD_IP>:/workspace/nm-i-ai-2026/norgesgruppen/runs/runpod_yolov8l_1280/weights/best.onnx .
   scp root@<POD_IP>:/workspace/nm-i-ai-2026/norgesgruppen/runs/runpod_yolov8l_1280/weights/best.pt .

6. PACKAGE SUBMISSION (locally)

   cp best.onnx norgesgruppen/submission/
   cd norgesgruppen && python package_submission.py

=============================================================================
HELP
}

# --- Main ---
COMMAND="${1:-}"

case "${COMMAND}" in
    upload-all)   cmd_upload_all ;;
    upload-code)  cmd_upload_code ;;
    upload-data)  cmd_upload_data ;;
    download)     cmd_download ;;
    status)       cmd_status ;;
    help)         cmd_help ;;
    *)            usage ;;
esac
