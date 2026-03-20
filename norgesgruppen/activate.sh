#!/bin/bash
source /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/.venv/bin/activate
echo "Activated nm-ai venv ($(python --version))"
echo "PyTorch: $(python -c 'import torch; print(torch.__version__)')"
echo "MPS: $(python -c 'import torch; print(torch.backends.mps.is_available())')"
