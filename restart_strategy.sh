#!/bin/bash
# Script to safely restart the trading strategy

set -e

echo "=========================================="
echo "GOLD ARBITRAGE STRATEGY RESTART"
echo "=========================================="
echo ""

# Find the running process
PID=$(ps aux | grep "python.*run_live.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "No running strategy process found"
    echo "Starting strategy..."
    cd /home/ubuntu/GoldArb
    nohup python3 run_live.py > logs/run_live.out 2>&1 &
    NEW_PID=$!
    echo "Strategy started with PID: $NEW_PID"
    echo "Logs: tail -f logs/run_live.out"
    exit 0
fi

echo "Found running strategy with PID: $PID"
echo ""
echo "This will:"
echo "  1. Send SIGTERM to gracefully stop the strategy"
echo "  2. Wait for clean shutdown (cancels orders, optionally closes positions)"
echo "  3. Start the strategy with the FIXED position sync logic"
echo ""
echo "The fixed logic will:"
echo "  - Properly detect positions at HIGH spread levels (0.30%-8.00%)"
echo "  - Enable closing logic for positions that should close"
echo "  - Current spread is ~0.38%, so positions above 0.40% should close"
echo ""
read -p "Continue with restart? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restart cancelled"
    exit 0
fi

echo ""
echo "Stopping strategy (PID: $PID)..."
kill -TERM $PID

# Wait for process to stop (max 30 seconds)
for i in {1..30}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "Strategy stopped successfully"
        break
    fi
    echo "Waiting for shutdown... ($i/30)"
    sleep 1
done

# Check if still running
if ps -p $PID > /dev/null 2>&1; then
    echo "WARNING: Strategy did not stop gracefully, force killing..."
    kill -9 $PID
    sleep 2
fi

echo ""
echo "Starting strategy with FIXED code..."
cd /home/ubuntu/GoldArb

# Start in background with output redirect
nohup python3 run_live.py > logs/run_live.out 2>&1 &
NEW_PID=$!

echo "Strategy started with PID: $NEW_PID"
echo ""
echo "Monitoring startup (first 20 lines)..."
sleep 3

# Show recent logs
echo "=========================================="
echo "STARTUP LOGS:"
echo "=========================================="
tail -20 logs/run_live.out 2>/dev/null || echo "No output yet, wait a moment..."

echo ""
echo "=========================================="
echo "To monitor logs in real-time:"
echo "  tail -f logs/run_live.out"
echo ""
echo "To check position sync:"
echo "  grep 'STARTUP SYNC\\|Marked grid level\\|Closing grid' logs/*.json | tail -20"
echo ""
echo "To verify spread and expected closes:"
echo "  python3 check_spread.py"
echo "=========================================="
