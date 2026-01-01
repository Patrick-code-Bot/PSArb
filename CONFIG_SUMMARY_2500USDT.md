# PAXG-XAUT Grid Strategy Configuration Summary
## 2500 USDT Capital with 10x Leverage

### Capital Allocation

| Item | Amount | Percentage |
|------|--------|-----------|
| Total Capital | 2,500 USDT | 100% |
| Available for Trading | 1,750 USDT | 70% |
| Safety Reserve | 750 USDT | 30% |
| Maximum Exposure (10x leverage) | 3,500 USDT | 140% (max_total_notional) |

### 15-Level Grid Configuration

| Level | Spread | Weight | Base Margin/Side | Total Margin/Grid | PAXG Qty @ $2700 | Expected Profit/Trade |
|-------|--------|--------|------------------|-------------------|------------------|---------------------|
| **Low Tier (5 levels)** |
| 1 | 0.10% | 0.4x | 35.4 USDT | 70.8 USDT | 0.131 oz | +0.25 USDT |
| 2 | 0.15% | 0.5x | 44.3 USDT | 88.6 USDT | 0.164 oz | +0.62 USDT |
| 3 | 0.20% | 0.6x | 53.1 USDT | 106.2 USDT | 0.197 oz | +1.12 USDT |
| 4 | 0.25% | 0.7x | 62.0 USDT | 124.0 USDT | 0.230 oz | +1.73 USDT |
| 5 | 0.30% | 0.8x | 70.8 USDT | 141.6 USDT | 0.262 oz | +2.46 USDT |
| **Mid Tier (4 levels)** |
| 6 | 0.40% | 1.0x | 88.5 USDT | 177.0 USDT | 0.328 oz | +4.24 USDT |
| 7 | 0.50% | 1.0x | 88.5 USDT | 177.0 USDT | 0.328 oz | +5.49 USDT |
| 8 | 0.60% | 1.0x | 88.5 USDT | 177.0 USDT | 0.328 oz | +6.72 USDT |
| 9 | 0.80% | 1.2x | 106.2 USDT | 212.4 USDT | 0.393 oz | +10.78 USDT |
| **High Tier (3 levels)** |
| 10 | 1.00% | 1.5x | 132.8 USDT | 265.6 USDT | 0.492 oz | +16.77 USDT |
| 11 | 1.50% | 1.8x | 159.3 USDT | 318.6 USDT | 0.590 oz | +30.24 USDT |
| 12 | 2.00% | 2.0x | 177.0 USDT | 354.0 USDT | 0.656 oz | +45.48 USDT |
| **Extreme Tier (3 levels)** |
| 13 | 3.00% | 2.5x | 221.3 USDT | 442.6 USDT | 0.820 oz | +81.73 USDT |
| 14 | 5.00% | 3.0x | 265.5 USDT | 531.0 USDT | 0.983 oz | +174.58 USDT |
| 15 | 8.00% | 3.5x | 309.8 USDT | 619.6 USDT | 1.147 oz | +325.33 USDT |

### Risk Assessment

| Scenario | Spread | Max Floating Loss | % of Capital | Status |
|----------|--------|-------------------|--------------|--------|
| Normal Fluctuation | 2% | ~350 USDT | 14% | ✅ Safe |
| Large Fluctuation | 5% | ~875 USDT | 35% | ⚠️ Moderate Risk |
| Extreme Condition | 9% | ~1,575 USDT | 63% | 🔴 High Risk (but 750 USDT reserve available) |

### Key Configuration Parameters

```python
# Grid Levels
grid_levels = [
    0.0010, 0.0015, 0.0020, 0.0025, 0.0030,  # Low tier (5 levels)
    0.0040, 0.0050, 0.0060, 0.0080,          # Mid tier (4 levels)
    0.0100, 0.0150, 0.0200,                  # High tier (3 levels)
    0.0300, 0.0500, 0.0800                   # Extreme tier (3 levels)
]

# Risk Management
base_notional_per_level = 88.5  # Base unit USDT per side
max_total_notional = 3500.0     # Maximum total exposure
target_leverage = 10.0          # Set on Bybit exchange

# Position Weights (multiplier for base_notional_per_level)
position_weights = {
    0.0010: 0.4,  0.0015: 0.5,  0.0020: 0.6,
    0.0025: 0.7,  0.0030: 0.8,  0.0040: 1.0,
    0.0050: 1.0,  0.0060: 1.0,  0.0080: 1.2,
    0.0100: 1.5,  0.0150: 1.8,  0.0200: 2.0,
    0.0300: 2.5,  0.0500: 3.0,  0.0800: 3.5
}
```

### Strategy Behavior

1. **Entry (Market Orders)**:
   - When spread exceeds a grid level → Open paired positions immediately
   - PAXG expensive (spread > 0): Short PAXG + Long XAUT
   - XAUT expensive (spread < 0): Short XAUT + Long PAXG
   - Position size = base_notional × weight for that level

2. **Exit (Limit Orders)**:
   - When spread falls below previous level → Close grid at favorable price
   - Uses maker orders to capture better prices

3. **Risk Controls**:
   - Maximum total exposure: 3,500 USDT (protects capital)
   - Safety reserve: 750 USDT (30% kept aside)
   - Extreme spread stop: 1.0% (closes all if exceeded)
   - Paired order tracking: Prevents unbalanced positions

### File Locations

- Configuration: `/home/ubuntu/GoldArb/config_live.py`
- Strategy: `/home/ubuntu/GoldArb/paxg_xaut_grid_strategy.py`
- This Summary: `/home/ubuntu/GoldArb/CONFIG_SUMMARY_2500USDT.md`

### Important Notes

1. **Leverage**: Must be set to 10x on Bybit exchange (not controlled by strategy)
2. **Initial Positions**: Set `initial_notional_override` in config if restarting with existing positions
3. **Position Mode**: Must use hedge mode on Bybit (allows both long and short simultaneously)
4. **API Keys**: Stored in `.env` file (BYBIT_API_KEY, BYBIT_API_SECRET)

### Next Steps

1. Verify leverage is set to 10x on Bybit exchange
2. Ensure sufficient USDT balance (2,500 minimum)
3. Confirm position mode is set to "Hedge Mode"
4. Review and test with small positions first
5. Monitor performance and adjust weights if needed
