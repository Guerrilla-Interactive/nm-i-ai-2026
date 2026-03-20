#!/bin/bash
cd "$(dirname "$0")"
set -a
source .env
set +a
cd app
pip install -r requirements.txt 2>/dev/null
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
