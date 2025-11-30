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

from nautilus_trader.adapters.bybit.factories import (
    BybitLiveDataClientFactory,
    BybitLiveExecClientFactory,
)
from nautilus_trader.live.node import TradingNode

from config_live import create_live_config
from paxg_xaut_grid_strategy import PaxgXautGridStrategy


# Global reference to the trading node for signal handling
trading_node = None


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
        print("  - PAXGUSDT-PERP")
        print("  - XAUTUSDT-PERP")
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
