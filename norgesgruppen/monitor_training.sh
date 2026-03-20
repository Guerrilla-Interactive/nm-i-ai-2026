#!/usr/bin/env bash
# monitor_training.sh — Periodically check training progress and auto-export best model
set -euo pipefail

RESULTS_CSV="/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/runs/improved_s_640/results.csv"
BEST_PT="/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/runs/improved_s_640/weights/best.pt"
SUBMISSION_DIR="/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/submission"
STATE_FILE="/tmp/doey/nm-i-ai-2026/monitor_state.txt"
VENV_ACTIVATE="/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/.venv/bin/activate"
TRAIN_PID=$(cat /tmp/doey/nm-i-ai-2026/train_v2_pid.txt 2>/dev/null || echo 0)
CHECK_INTERVAL=60

mkdir -p /tmp/doey/nm-i-ai-2026
mkdir -p "$SUBMISSION_DIR"

# Load previous best mAP50 from state file, or default to 0
if [[ -f "$STATE_FILE" ]]; then
    LAST_EXPORTED_MAP50=$(cat "$STATE_FILE")
else
    LAST_EXPORTED_MAP50="0"
fi

do_export() {
    local map50="$1"
    local map50_95="$2"
    local reason="$3"
    local ts
    ts=$(date '+%Y%m%d_%H%M%S')

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] EXPORT ($reason): mAP50=$map50 mAP50-95=$map50_95"

    # Timestamped backup of best.pt
    cp "$BEST_PT" "${SUBMISSION_DIR}/best_${ts}.pt"

    # Export to ONNX
    source "$VENV_ACTIVATE"
    python -c "from ultralytics import YOLO; m = YOLO('$BEST_PT'); m.export(format='onnx', imgsz=640, simplify=True)"
    deactivate 2>/dev/null || true

    # Find the exported ONNX (it appears next to best.pt)
    local onnx_path="${BEST_PT%.pt}.onnx"
    if [[ -f "$onnx_path" ]]; then
        cp "$onnx_path" "${SUBMISSION_DIR}/best.onnx"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Copied ONNX to ${SUBMISSION_DIR}/best.onnx"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: ONNX file not found at $onnx_path"
    fi

    # Update state
    echo "$map50" > "$STATE_FILE"
    LAST_EXPORTED_MAP50="$map50"
}

while true; do
    # Check if results CSV exists
    if [[ ! -f "$RESULTS_CSV" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for results.csv..."
        sleep "$CHECK_INTERVAL"
        continue
    fi

    # Parse latest line (skip header, get last row)
    latest=$(tail -1 "$RESULTS_CSV")
    epoch=$(echo "$latest" | awk -F',' '{gsub(/^ +| +$/, "", $1); print $1}')
    map50=$(echo "$latest" | awk -F',' '{gsub(/^ +| +$/, "", $8); print $8}')
    map50_95=$(echo "$latest" | awk -F',' '{gsub(/^ +| +$/, "", $9); print $9}')

    # Check if training is still alive
    process_alive=true
    if ! kill -0 "$TRAIN_PID" 2>/dev/null; then
        process_alive=false
    fi

    # Status line
    if $process_alive; then
        status="TRAINING"
    else
        status="FINISHED"
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Epoch: $epoch | mAP50: $map50 | mAP50-95: $map50_95 | Status: $status"

    # Check for improvement (>10% over last exported value)
    if [[ -n "$map50" && "$map50" != "0" ]]; then
        improved=$(awk "BEGIN { threshold = $LAST_EXPORTED_MAP50 * 1.1; print ($map50 > threshold) ? 1 : 0 }")
        # Also export if we've never exported (LAST_EXPORTED_MAP50 == 0)
        never_exported=0
        if [[ "$LAST_EXPORTED_MAP50" == "0" ]]; then
            never_exported=1
        fi

        if [[ "$improved" == "1" || "$never_exported" == "1" ]]; then
            do_export "$map50" "$map50_95" "improvement"
        fi
    fi

    # If training is dead, do final export and exit
    if ! $process_alive; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Training process (PID $TRAIN_PID) is no longer running."
        do_export "$map50" "$map50_95" "final"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Final export complete. Monitor exiting."
        exit 0
    fi

    sleep "$CHECK_INTERVAL"
done
