#!/bin/sh
# Use Railway's PORT if available, otherwise default to 5000
PORT=${PORT:-5000}
echo "Starting Clara Backend on port $PORT"
exec python main.py --host 0.0.0.0 --port $PORT