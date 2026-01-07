#!/bin/bash
# ExaSignal - Smart Scheduler Daemon
# Runs the news monitoring with smart polling based on market hours

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate virtual environment if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check for required env vars
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  GROQ_API_KEY not set. Loading from .env..."
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
fi

echo "🚀 Starting ExaSignal Smart Scheduler..."
echo "   Market Hours (UTC): 13:00 - 02:00"
echo "   Polling: 5min (market) / 30min (off-hours)"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

# Run scheduler
python -m src.core.scheduler
