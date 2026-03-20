"""Quick YOLOv8n training — runs detached, CPU-safe."""
from ultralytics import YOLO
import shutil
from pathlib import Path
import json

print("=" * 60)
print("Starting YOLOv8n quick training (CPU, 30 epochs)")
print("=" * 60)

model = YOLO('yolov8n.pt')
results = model.train(
    data='norgesgruppen.yaml',
    epochs=30,
    imgsz=640,
    batch=16,
    device='cpu',
    amp=False,
    patience=15,
    lr0=0.01,
    mosaic=1.0,
    close_mosaic=5,
    mixup=0.1,
    project='runs',
    name='quick_n_cpu',
    exist_ok=True,
    workers=0,
    save_period=5,
    plots=True,
    verbose=True,
)

print('\n' + '=' * 60)
print('TRAINING COMPLETE')
print('=' * 60)
try:
    d = results.results_dict
    print(f"mAP50:     {d.get('metrics/mAP50(B)', 'N/A')}")
    print(f"mAP50-95:  {d.get('metrics/mAP50-95(B)', 'N/A')}")
    print(f"Precision: {d.get('metrics/precision(B)', 'N/A')}")
    print(f"Recall:    {d.get('metrics/recall(B)', 'N/A')}")
except Exception as e:
    print(f"Metrics error: {e}")

# Export to ONNX
print('\nExporting to ONNX...')
best_path = 'runs/quick_n_cpu/weights/best.pt'
best_model = YOLO(best_path)
export_path = best_model.export(format='onnx', imgsz=640, simplify=True)
print(f'ONNX exported: {export_path}')

# Copy to submission
sub = Path('submission')
sub.mkdir(exist_ok=True)
shutil.copy2(str(export_path), str(sub / 'best.onnx'))
print(f'Copied to submission/best.onnx')
print('\nDONE — ready to package and submit!')
