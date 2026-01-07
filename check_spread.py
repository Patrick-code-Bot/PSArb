#!/usr/bin/env python3
"""
Quick script to check current PAXG/XAUT spread on Bybit
"""
import os
import requests
import sys

def get_ticker(symbol):
    """Get ticker info from Bybit"""
    url = "https://api.bybit.com/v5/market/tickers"
    params = {
        "category": "linear",
        "symbol": symbol
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("retCode") == 0 and data.get("result", {}).get("list"):
            ticker = data["result"]["list"][0]
            return {
                "symbol": ticker.get("symbol"),
                "bid": float(ticker.get("bid1Price", 0)),
                "ask": float(ticker.get("ask1Price", 0)),
                "last": float(ticker.get("lastPrice", 0)),
            }
        else:
            print(f"Error getting ticker for {symbol}: {data.get('retMsg')}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"Exception getting ticker for {symbol}: {e}", file=sys.stderr)
        return None

def main():
    print("Fetching PAXG and XAUT ticker data from Bybit...\n")

    paxg = get_ticker("PAXGUSDT")
    xaut = get_ticker("XAUTUSDT")

    if not paxg or not xaut:
        print("Failed to fetch ticker data", file=sys.stderr)
        return 1

    print(f"PAXG: Bid={paxg['bid']:.2f}, Ask={paxg['ask']:.2f}, Last={paxg['last']:.2f}")
    print(f"XAUT: Bid={xaut['bid']:.2f}, Ask={xaut['ask']:.2f}, Last={xaut['last']:.2f}")
    print()

    # Calculate mid prices
    paxg_mid = (paxg['bid'] + paxg['ask']) / 2
    xaut_mid = (xaut['bid'] + xaut['ask']) / 2

    # Calculate spread
    spread = (paxg_mid - xaut_mid) / xaut_mid
    abs_spread = abs(spread)

    print(f"PAXG Mid: {paxg_mid:.2f}")
    print(f"XAUT Mid: {xaut_mid:.2f}")
    print(f"Spread: {spread:.6f} ({spread * 100:.4f}%)")
    print(f"Abs Spread: {abs_spread:.6f} ({abs_spread * 100:.4f}%)")
    print()

    # Check against grid levels
    grid_levels = [0.0010, 0.0015, 0.0020, 0.0025, 0.0030, 0.0040, 0.0050, 0.0060, 0.0080, 0.0100, 0.0150, 0.0200, 0.0300, 0.0500, 0.0800]

    print("Grid Level Analysis:")
    print("-" * 60)
    for i, level in enumerate(grid_levels):
        prev_level = 0.0 if i == 0 else grid_levels[i - 1]
        should_open = abs_spread > level
        should_close = abs_spread < prev_level

        status = ""
        if should_open:
            status = "SHOULD OPEN"
        elif should_close:
            status = "SHOULD CLOSE (if position exists)"
        else:
            status = "No action"

        print(f"Level {level*100:5.2f}% (prev={prev_level*100:5.2f}%): {status}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
