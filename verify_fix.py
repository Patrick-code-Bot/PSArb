#!/usr/bin/env python3
"""
Verification script to confirm the position sync fix is working correctly
"""
import json
import sys
import os
from datetime import datetime
import glob

def find_latest_log():
    """Find the most recent log file"""
    log_files = glob.glob("/home/ubuntu/GoldArb/logs/paxg_xaut_grid_*.json")
    if not log_files:
        return None
    # Sort by modification time, most recent first
    log_files.sort(key=os.path.getmtime, reverse=True)
    return log_files[0]

def check_startup_sync(log_file):
    """Check if startup sync happened correctly"""
    print("\n" + "=" * 80)
    print("CHECKING STARTUP SYNC")
    print("=" * 80)

    found_sync = False
    marked_levels = []

    with open(log_file, 'r') as f:
        for line in f:
            try:
                log = json.loads(line)
                msg = log.get('message', '')

                # Look for startup sync message
                if 'STARTUP SYNC' in msg:
                    found_sync = True
                    print(f"\n✓ Found startup sync message:")
                    print(f"  {msg}")

                # Look for marked grid levels
                if 'Marked grid level' in msg and 'occupied' in msg:
                    # Extract level from message
                    if 'level=' in msg:
                        level_str = msg.split('level=')[1].split()[0]
                        try:
                            level = float(level_str)
                            marked_levels.append(level)
                        except:
                            pass
                    print(f"  {msg}")

            except:
                continue

    if not found_sync:
        print("\n❌ STARTUP SYNC NOT FOUND - strategy may not have restarted yet")
        return False, []

    print(f"\n✓ Marked {len(marked_levels)} grid levels: {[f'{l*100:.2f}%' for l in sorted(marked_levels)]}")
    return True, marked_levels

def check_closing_activity(log_file):
    """Check if closing logic is being executed"""
    print("\n" + "=" * 80)
    print("CHECKING CLOSING ACTIVITY")
    print("=" * 80)

    closing_messages = []
    close_orders = []

    with open(log_file, 'r') as f:
        for line in f:
            try:
                log = json.loads(line)
                msg = log.get('message', '')
                timestamp = log.get('timestamp', '')

                # Look for closing grid messages
                if 'Closing grid' in msg:
                    closing_messages.append((timestamp, msg))

                # Look for close order submissions
                if 'Submitted close order' in msg or 'close order filled' in msg.lower():
                    close_orders.append((timestamp, msg))

            except:
                continue

    if closing_messages:
        print(f"\n✓ Found {len(closing_messages)} closing grid messages:")
        for ts, msg in closing_messages[-10:]:  # Show last 10
            print(f"  [{ts}] {msg}")
    else:
        print("\n⚠️  No 'Closing grid' messages found yet")
        print("   (This is expected if spread hasn't crossed closing threshold)")

    if close_orders:
        print(f"\n✓ Found {len(close_orders)} close order messages:")
        for ts, msg in close_orders[-10:]:  # Show last 10
            print(f"  [{ts}] {msg}")
    else:
        print("\n⚠️  No close order messages found yet")

    return len(closing_messages) > 0, len(close_orders) > 0

def check_process_grids_execution(log_file):
    """Check if _process_grids is being called"""
    print("\n" + "=" * 80)
    print("CHECKING GRID PROCESSING")
    print("=" * 80)

    # Count recent quote updates (last 100 lines)
    quote_count = 0
    recent_lines = []

    with open(log_file, 'r') as f:
        lines = f.readlines()
        recent_lines = lines[-100:]  # Last 100 lines

    for line in recent_lines:
        try:
            log = json.loads(line)
            msg = log.get('message', '')

            # Grid processing happens on every quote tick (looking for related messages)
            if 'Max total notional reached' in msg or 'Opening grid' in msg or 'Closing grid' in msg:
                quote_count += 1

        except:
            continue

    if quote_count > 0:
        print(f"✓ Grid processing is active ({quote_count} relevant messages in last 100 log lines)")
    else:
        print("⚠️  No grid processing activity detected in recent logs")

    return quote_count > 0

def main():
    print("=" * 80)
    print("GOLD ARBITRAGE STRATEGY - FIX VERIFICATION")
    print("=" * 80)
    print(f"Verification time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Find latest log file
    log_file = find_latest_log()
    if not log_file:
        print("\n❌ ERROR: No log files found in /home/ubuntu/GoldArb/logs/")
        return 1

    print(f"\nAnalyzing log file: {os.path.basename(log_file)}")
    print(f"File size: {os.path.getsize(log_file) / 1024:.2f} KB")
    print(f"Last modified: {datetime.fromtimestamp(os.path.getmtime(log_file)).strftime('%Y-%m-%d %H:%M:%S')}")

    # Check 1: Startup sync
    sync_ok, marked_levels = check_startup_sync(log_file)

    # Check 2: Closing activity
    closing_ok, orders_ok = check_closing_activity(log_file)

    # Check 3: Grid processing
    processing_ok = check_process_grids_execution(log_file)

    # Final summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    if sync_ok and len(marked_levels) > 0:
        print("✓ Startup sync executed correctly")
        print(f"  - Marked {len(marked_levels)} grid levels as occupied")
        print(f"  - Levels: {[f'{l*100:.2f}%' for l in sorted(marked_levels)]}")
    else:
        print("❌ Startup sync issue detected or not executed yet")

    if processing_ok:
        print("✓ Grid processing is active")
    else:
        print("⚠️  Grid processing may not be active")

    if closing_ok or orders_ok:
        print("✓ Closing logic is being executed")
    else:
        print("⚠️  No closing activity detected yet (may be expected if spread is stable)")
        print("   Run 'python3 check_spread.py' to see current spread and expected actions")

    print("\n" + "=" * 80)
    print("EXPECTED BEHAVIOR:")
    print("=" * 80)
    print("1. Positions should be marked at HIGHER spread levels (0.30%-8.00%)")
    print("2. Current spread (~0.38%) means positions at 0.50%+ should close")
    print("3. When spread drops below a grid level's 'prev_level', that position closes")
    print("\nRun 'python3 check_spread.py' to see current market conditions")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    sys.exit(main())
