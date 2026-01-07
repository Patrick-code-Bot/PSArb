#!/usr/bin/env python3
"""
Diagnostic script to understand which grid levels are marked as occupied
"""
import sys

# Based on the config and logs
total_notional = 3432.39
base_notional_per_level = 88.5
grid_levels = [0.0010, 0.0015, 0.0020, 0.0025, 0.0030, 0.0040, 0.0050, 0.0060, 0.0080, 0.0100, 0.0150, 0.0200, 0.0300, 0.0500, 0.0800]
position_weights = {
    0.0010: 0.4, 0.0015: 0.5, 0.0020: 0.6, 0.0025: 0.7, 0.0030: 0.8,
    0.0040: 1.0, 0.0050: 1.0, 0.0060: 1.0, 0.0080: 1.2, 0.0100: 1.5,
    0.0150: 1.8, 0.0200: 2.0, 0.0300: 2.5, 0.0500: 3.0, 0.0800: 3.5
}

# Current spread (from check_spread.py)
current_spread = 0.003755  # 0.3755%

print("=" * 80)
print("GOLD ARBITRAGE STRATEGY - POSITION DIAGNOSTIC")
print("=" * 80)
print(f"\nCurrent Spread: {current_spread:.6f} ({current_spread * 100:.4f}%)")
print(f"Total Notional: {total_notional:.2f} USDT")
print()

# Bug in sync: marks FIRST N levels (line 328-340 of strategy)
notional_per_grid = 2 * base_notional_per_level  # Assumes weight=1.0
estimated_grids = int(total_notional / notional_per_grid)

print("INCORRECT SYNC LOGIC (Current Implementation):")
print("-" * 80)
print(f"Notional per grid (base, weight=1.0): {notional_per_grid:.2f}")
print(f"Estimated grids: {estimated_grids}")
print(f"Marks first {estimated_grids} levels as occupied:")
levels_sorted = sorted(grid_levels)
for i, level in enumerate(levels_sorted):
    if i < estimated_grids:
        prev_level = 0.0 if i == 0 else levels_sorted[i - 1]
        should_close = current_spread < prev_level
        print(f"  Level {level*100:5.2f}% - MARKED AS OCCUPIED (prev={prev_level*100:.2f}%, should_close={should_close})")
    else:
        break
print()

print("REALITY (Positions opened at HIGH spreads):")
print("-" * 80)
print("Likely open at HIGHER levels (estimated from total notional with weights):")
# Reverse calculation with weights
levels_reverse = sorted(grid_levels, reverse=True)
remaining = total_notional
actual_open = []
for level in levels_reverse:
    weight = position_weights.get(level, 1.0)
    notional = 2 * base_notional_per_level * weight
    if remaining >= notional:
        remaining -= notional
        actual_open.append(level)
    if remaining < 50:
        break

for level in sorted(actual_open):
    i = grid_levels.index(level)
    prev_level = 0.0 if i == 0 else grid_levels[i - 1]
    should_close = current_spread < prev_level
    print(f"  Level {level*100:5.2f}% - ACTUALLY OPEN (prev={prev_level*100:.2f}%, should_close={should_close})")

print()
print("=" * 80)
print("ROOT CAUSE IDENTIFIED:")
print("=" * 80)
print("❌ Bug: Startup sync marks LOWEST grid levels as occupied (0.10%, 0.15%, ...)")
print("✅ Reality: Positions were opened at HIGHEST spreads (0.80%, 1.00%, 2.00%, ...)")
print("⚠️  Result: Closing logic checks wrong levels, positions never close!")
print()

print("PROOF:")
print("-" * 80)
positions_that_should_close = [l for l in actual_open if l > 0.0040]  # Levels > 0.40%
print(f"Positions at levels > 0.40% should close (spread={current_spread*100:.2f}% < 0.40%):")
for level in sorted(positions_that_should_close):
    i = grid_levels.index(level)
    prev_level = grid_levels[i - 1] if i > 0 else 0.0
    print(f"  Level {level*100:5.2f}% (prev={prev_level*100:.2f}%): {current_spread*100:.4f}% < {prev_level*100:.2f}% = {current_spread < prev_level}")

print()
print("But these positions are NOT tracked in grid_state at the correct levels!")
print("Instead, grid_state has positions at levels 0.10%-0.30% (wrong!)")
print()
