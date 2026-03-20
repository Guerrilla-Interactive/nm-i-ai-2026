#!/bin/bash
# Run the Tripletex agent locally and expose via ngrok
# This lets us submit to the competition immediately while setting up GCP

echo "Starting local Tripletex agent on port 8080..."
cd "$(dirname "$0")/app"
pip install -r requirements.txt 2>/dev/null

# Start uvicorn in background
uvicorn main:app --host 0.0.0.0 --port 8080 &
UVICORN_PID=$!
sleep 2

# Expose via ngrok (must be installed: brew install ngrok)
echo "Exposing port 8080 via ngrok..."
echo "Register the HTTPS URL at app.ainm.no as your endpoint"
ngrok http 8080

kill $UVICORN_PID 2>/dev/null
