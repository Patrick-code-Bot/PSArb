#!/usr/bin/env python3
"""
Script to close all open positions on Bybit
"""
import os
import sys
import time
import hmac
import hashlib
import requests
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
TESTNET = os.getenv("BYBIT_TESTNET", "false").lower() == "true"

BASE_URL = "https://api-testnet.bybit.com" if TESTNET else "https://api.bybit.com"


def generate_signature(timestamp, api_key, recv_window, param_str):
    """Generate signature for Bybit V5 API"""
    sign_str = f"{timestamp}{api_key}{recv_window}{param_str}"
    return hmac.new(
        API_SECRET.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def get_positions():
    """Get all open positions"""
    endpoint = "/v5/position/list"
    url = BASE_URL + endpoint

    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    param_str = "category=linear&settleCoin=USDT"

    signature = generate_signature(timestamp, API_KEY, recv_window, param_str)

    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
    }

    response = requests.get(url, headers=headers, params={"category": "linear", "settleCoin": "USDT"})

    if response.status_code != 200:
        print(f"Error getting positions: {response.text}")
        return []

    data = response.json()
    print(f"DEBUG: API Response: {data}")  # Debug output

    if data.get("retCode") != 0:
        print(f"API Error: {data.get('retMsg')}")
        return []

    positions = data.get("result", {}).get("list", [])
    print(f"DEBUG: Found {len(positions)} total positions (including zero-size)")

    # Filter only positions with non-zero size
    non_zero = [p for p in positions if float(p.get("size", 0)) != 0]
    print(f"DEBUG: {len(non_zero)} non-zero positions")
    return non_zero


def close_position(symbol, side, size):
    """Close a position using market order"""
    import json

    endpoint = "/v5/order/create"
    url = BASE_URL + endpoint

    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    # Determine order side (opposite of position side)
    order_side = "Sell" if side == "Buy" else "Buy"

    params = {
        "category": "linear",
        "symbol": symbol,
        "side": order_side,
        "orderType": "Market",
        "qty": str(size),
        "reduceOnly": True,  # Important: only close position, don't open new one
        "timeInForce": "IOC",
    }

    # For POST requests with JSON body
    param_str = json.dumps(params, separators=(',', ':'))
    signature = generate_signature(timestamp, API_KEY, recv_window, param_str)

    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=params)

    if response.status_code != 200:
        print(f"Error closing position: {response.text}")
        return False

    data = response.json()
    if data.get("retCode") != 0:
        print(f"API Error closing {symbol}: {data.get('retMsg')}")
        return False

    print(f"✓ Successfully closed {symbol} position ({order_side} {size})")
    return True


def main():
    print("=" * 60)
    print("Bybit Position Closer")
    print("=" * 60)

    if not API_KEY or not API_SECRET:
        print("ERROR: BYBIT_API_KEY and BYBIT_API_SECRET must be set")
        sys.exit(1)

    print(f"Using {'TESTNET' if TESTNET else 'MAINNET'}")
    print()

    # Get all positions
    print("Fetching open positions...")
    positions = get_positions()

    if not positions:
        print("No open positions found.")
        return

    print(f"\nFound {len(positions)} open position(s):\n")

    for pos in positions:
        symbol = pos.get("symbol")
        side = pos.get("side")
        size = pos.get("size")
        entry_price = pos.get("avgPrice")
        unrealized_pnl = pos.get("unrealisedPnl")

        print(f"  {symbol}:")
        print(f"    Side: {side}")
        print(f"    Size: {size}")
        print(f"    Entry Price: {entry_price}")
        print(f"    Unrealized PnL: {unrealized_pnl} USDT")
        print()

    # Ask for confirmation
    response = input("Do you want to close ALL positions? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        return

    print("\nClosing positions...\n")

    success_count = 0
    for pos in positions:
        symbol = pos.get("symbol")
        side = pos.get("side")
        size = pos.get("size")

        if close_position(symbol, side, size):
            success_count += 1
            time.sleep(0.5)  # Rate limiting

    print()
    print("=" * 60)
    print(f"Closed {success_count}/{len(positions)} positions")
    print("=" * 60)

    # Verify all positions are closed
    time.sleep(2)
    print("\nVerifying positions are closed...")
    remaining = get_positions()
    if remaining:
        print(f"WARNING: {len(remaining)} position(s) still open:")
        for pos in remaining:
            print(f"  - {pos.get('symbol')}: {pos.get('size')}")
    else:
        print("✓ All positions successfully closed!")


if __name__ == "__main__":
    main()
