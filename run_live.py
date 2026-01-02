#!/usr/bin/env python
"""
Live trading entry point for PAXG-XAUT Grid Strategy on Bybit

This script initializes and runs the live trading node with the PAXG-XAUT grid strategy.

Usage:
    python run_live.py

Environment Variables Required:
    BYBIT_API_KEY - Your Bybit API key
    BYBIT_API_SECRET - Your Bybit API secret

Optional Environment Variables:
    BYBIT_TESTNET - Set to 'true' to use testnet (default: false)
"""

import asyncio
import os
import signal
import sys
from pathlib import Path
from datetime import datetime, timedelta

from nautilus_trader.adapters.bybit.factories import (
    BybitLiveDataClientFactory,
    BybitLiveExecClientFactory,
)
from nautilus_trader.live.node import TradingNode

from config_live import create_live_config
from paxg_xaut_grid_strategy import PaxgXautGridStrategy


# Global reference to the trading node for signal handling
trading_node = None


def cleanup_old_logs(log_dir: str = "logs", max_total_size_mb: int = 100, max_files: int = 10):
    """
    Clean up old log files to prevent unlimited growth.

    NautilusTrader creates a new log file series on each restart with timestamps.
    This function removes old log files to keep total size and file count under limits.

    Args:
        log_dir: Directory containing log files
        max_total_size_mb: Maximum total size in MB (default: 100MB)
        max_files: Maximum number of log files to keep (default: 10)
    """
    log_path = Path(log_dir)

    if not log_path.exists():
        print(f"[Cleanup] Log directory '{log_dir}' does not exist, skipping cleanup")
        return

    # Get all .json log files
    log_files = sorted(log_path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not log_files:
        print("[Cleanup] No log files found")
        return

    # Calculate total size
    total_size = sum(f.stat().st_size for f in log_files)
    total_size_mb = total_size / (1024 * 1024)
    file_count = len(log_files)

    print(f"[Cleanup] Found {file_count} log files, total size: {total_size_mb:.2f}MB")

    # Determine which files to delete
    files_to_delete = []

    # Keep newest files up to max_files
    if file_count > max_files:
        files_to_delete.extend(log_files[max_files:])
        print(f"[Cleanup] Will delete {len(log_files[max_files:])} old files (keeping {max_files} newest)")

    # If total size exceeds limit, delete oldest files until under limit
    if total_size_mb > max_total_size_mb:
        kept_files = log_files[:max_files]
        kept_size = sum(f.stat().st_size for f in kept_files) / (1024 * 1024)

        if kept_size > max_total_size_mb:
            # Even after keeping max_files, still over limit - delete more
            current_size = 0
            files_to_keep = []

            for f in log_files:
                file_size = f.stat().st_size / (1024 * 1024)
                if current_size + file_size <= max_total_size_mb:
                    files_to_keep.append(f)
                    current_size += file_size
                else:
                    if f not in files_to_delete:
                        files_to_delete.append(f)

            print(f"[Cleanup] Will delete {len(files_to_delete)} files to reduce size below {max_total_size_mb}MB")

    # Delete files
    deleted_count = 0
    deleted_size = 0

    for f in files_to_delete:
        try:
            file_size = f.stat().st_size
            f.unlink()
            deleted_count += 1
            deleted_size += file_size
            print(f"[Cleanup] Deleted: {f.name} ({file_size / (1024 * 1024):.2f}MB)")
        except Exception as e:
            print(f"[Cleanup] Failed to delete {f.name}: {e}")

    if deleted_count > 0:
        deleted_size_mb = deleted_size / (1024 * 1024)
        remaining_files = file_count - deleted_count
        remaining_size = total_size - deleted_size
        remaining_size_mb = remaining_size / (1024 * 1024)

        print(f"[Cleanup] ✓ Deleted {deleted_count} files ({deleted_size_mb:.2f}MB)")
        print(f"[Cleanup] ✓ Remaining: {remaining_files} files ({remaining_size_mb:.2f}MB)")
    else:
        print("[Cleanup] ✓ No cleanup needed")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    print("\n" + "=" * 80)
    print("Shutdown signal received. Stopping trading node...")
    print("=" * 80)
    if trading_node:
        asyncio.create_task(trading_node.stop())
    sys.exit(0)


async def main():
    """Main entry point for live trading."""
    global trading_node

    print("=" * 80)
    print("PAXG-XAUT Grid Strategy - Live Trading")
    print("=" * 80)

    # Check required environment variables
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")

    if not api_key or not api_secret:
        print("\n❌ ERROR: Missing required environment variables")
        print("Please set the following environment variables:")
        print("  - BYBIT_API_KEY")
        print("  - BYBIT_API_SECRET")
        print("\nYou can set them in a .env file or export them:")
        print("  export BYBIT_API_KEY='your_api_key'")
        print("  export BYBIT_API_SECRET='your_api_secret'")
        print("=" * 80)
        sys.exit(1)

    # Check if using testnet
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    if testnet:
        print("\n⚠️  WARNING: Running in TESTNET mode")
    else:
        print("\n✅ Running in LIVE mode")

    print("=" * 80)

    try:
        # Clean up old log files BEFORE starting
        print("\n[0/5] Cleaning up old log files...")
        cleanup_old_logs(log_dir="logs", max_total_size_mb=50, max_files=10)

        # Create configuration
        print("\n[1/5] Loading configuration...")
        config = create_live_config()

        # Create trading node
        print("[2/5] Building trading node...")
        trading_node = TradingNode(config=config)

        # Add client factories
        print("[3/5] Registering Bybit adapters...")
        trading_node.add_data_client_factory("BYBIT", BybitLiveDataClientFactory)
        trading_node.add_exec_client_factory("BYBIT", BybitLiveExecClientFactory)

        # Build the node
        print("[4/5] Initializing trading node...")
        trading_node.build()

        # Start the node
        print("[5/5] Starting trading node...")
        print("\n" + "=" * 80)
        print("🚀 Trading node started successfully!")
        print("=" * 80)
        print("\nStrategy: PAXG-XAUT Grid Arbitrage")
        print(f"Venue: Bybit {'(Testnet)' if testnet else '(Live)'}")
        print("Instruments:")
        print("  - PAXGUSDT-LINEAR")
        print("  - XAUTUSDT-LINEAR")
        print("\nPress Ctrl+C to stop the trading node...")
        print("=" * 80 + "\n")

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start the node (this will block until stopped)
        await trading_node.run_async()

    except KeyboardInterrupt:
        print("\n" + "=" * 80)
        print("Keyboard interrupt received. Shutting down...")
        print("=" * 80)
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if trading_node:
            print("\nStopping trading node...")
            await trading_node.stop_async()
            print("✅ Trading node stopped successfully")
            print("=" * 80)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
