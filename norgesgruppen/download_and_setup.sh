#!/bin/bash
# Download and setup NorgesGruppen training data
#
# MANUAL STEP REQUIRED: Download these from https://app.ainm.no/submit/norgesgruppen-data
# (requires Google login):
#   1. NM_NGD_coco_dataset.zip (~864 MB)
#   2. NM_NGD_product_images.zip (~60 MB)
#
# Place them in this directory, then run this script.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$DIR/data"

echo "=== NorgesGruppen Data Setup ==="

# Check for ZIP files
COCO_ZIP=""
PRODUCT_ZIP=""

for f in "$DIR"/NM_NGD_coco_dataset*.zip "$HOME/Downloads/NM_NGD_coco_dataset"*.zip; do
    [ -f "$f" ] && COCO_ZIP="$f" && break
done

for f in "$DIR"/NM_NGD_product_images*.zip "$HOME/Downloads/NM_NGD_product_images"*.zip; do
    [ -f "$f" ] && PRODUCT_ZIP="$f" && break
done

if [ -z "$COCO_ZIP" ]; then
    echo "ERROR: NM_NGD_coco_dataset.zip not found!"
    echo "Download from: https://app.ainm.no/submit/norgesgruppen-data"
    echo "Place in: $DIR/ or ~/Downloads/"
    exit 1
fi

echo "Found COCO dataset: $COCO_ZIP"

# Extract COCO dataset
echo "Extracting COCO dataset..."
mkdir -p "$DATA_DIR"
unzip -o "$COCO_ZIP" -d "$DATA_DIR"

# Move files into expected structure if needed
if [ -d "$DATA_DIR/images" ] && [ -f "$DATA_DIR/annotations.json" ]; then
    echo "Dataset structure looks correct."
elif [ -d "$DATA_DIR/NM_NGD_coco_dataset" ]; then
    echo "Moving from subdirectory..."
    mv "$DATA_DIR/NM_NGD_coco_dataset"/* "$DATA_DIR/" 2>/dev/null || true
    rmdir "$DATA_DIR/NM_NGD_coco_dataset" 2>/dev/null || true
fi

# Find annotations.json wherever it ended up
ANN=$(find "$DATA_DIR" -name "annotations.json" -maxdepth 3 | head -1)
if [ -z "$ANN" ]; then
    echo "WARNING: annotations.json not found after extraction!"
    echo "Contents of $DATA_DIR:"
    ls -la "$DATA_DIR"
else
    echo "Found annotations: $ANN"
    # Move to expected location if not already there
    if [ "$ANN" != "$DATA_DIR/annotations.json" ]; then
        cp "$ANN" "$DATA_DIR/annotations.json"
        echo "Copied to $DATA_DIR/annotations.json"
    fi
fi

# Extract product images if available
if [ -n "$PRODUCT_ZIP" ]; then
    echo "Extracting product images..."
    mkdir -p "$DATA_DIR/product_images"
    unzip -o "$PRODUCT_ZIP" -d "$DATA_DIR/product_images"
    echo "Product images extracted."
else
    echo "WARNING: NM_NGD_product_images.zip not found (optional, ~60MB)"
fi

# Count files
echo ""
echo "=== Dataset Contents ==="
echo "Images: $(find "$DATA_DIR" -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' | wc -l | tr -d ' ')"
echo "Annotations: $([ -f "$DATA_DIR/annotations.json" ] && python3 -c "import json; d=json.load(open('$DATA_DIR/annotations.json')); print(len(d['annotations']))" || echo 'N/A')"
echo ""

# Run analysis
echo "=== Running Analysis ==="
python3 "$DIR/analyze_data.py"

echo ""
echo "=== Creating Train/Val Split ==="
python3 "$DIR/split_dataset.py"

echo ""
echo "=== DONE ==="
echo "Dataset ready at: $DATA_DIR"
echo "YAML config at: $DIR/norgesgruppen.yaml"
echo "Analysis at: $DIR/DATA-ANALYSIS.md"
