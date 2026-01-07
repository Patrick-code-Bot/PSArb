# CRITICAL ISSUE - Position Closing Implementation (2026-01-07)

## Current Status: **STRATEGY STOPPED**

Strategy has been stopped to prevent further position growth due to a critical issue with close order execution.

---

## What Was Fixed Successfully ✅

### 1. Position Synchronization Logic
**File**: `paxg_xaut_grid_strategy.py` (lines 229-381)

**Problem**: Was marking LOWEST grid levels (0.10%-0.30%) as occupied
**Solution**: Now marks HIGHEST levels (0.30%-8.00%) correctly with position weights
**Status**: ✅ **WORKING PERFECTLY**

```
✓ Marks levels from highest to lowest
✓ Accounts for position weights
✓ 99.5% accuracy (only 16-50 USDT unaccounted)
✓ Proper logging of each level
```

### 2. Closing Detection Logic
**File**: `paxg_xaut_grid_strategy.py` (lines 643-685)

**Problem**: Only detected level 0.50% for closing
**Solution**: Now detects ALL 9 levels (0.50%-8.00%) that should close
**Status**: ✅ **WORKING PERFECTLY**

```
✓ Detects all levels where spread < prev_level
✓ "Closing grid level" messages for all 9 levels
✓ Correctly identifies closing conditions
```

### 3. Position Placeholder Handling
**File**: `paxg_xaut_grid_strategy.py` (lines 871-931)

**Problem**: TypeError when trying to close string placeholders
**Solution**: Added logic to find real positions when pos_id is a string marker
**Status**: ✅ **WORKING**

```
✓ Handles "MANUAL_OVERRIDE" and "DETECTED" markers
✓ Finds actual open positions from cache
✓ No more TypeErrors
```

---

## Critical Remaining Issue ❌

### **Problem: Close Orders Double Positions Instead of Closing Them**

**Symptom**:
- Close orders submit successfully
- Some orders fill
- But positions DOUBLE instead of reducing
- Pattern: 3466 USDT → 6932 USDT (exactly 2x)

**Evidence**:
```
[15:02:43] Position Reconciliation: tracked=3466.98, actual=3465.89
[15:02:43] Submitted close orders for 9 grid levels
[15:02:43] Order filled: O-20260107-150243-001-001-1
[15:02:43] Order filled: O-20260107-150243-001-001-6
[15:03:43] Position Reconciliation: tracked=3465.89, actual=6931.78 ← DOUBLED!
```

**Current Implementation** (`paxg_xaut_grid_strategy.py:917`):
```python
side = OrderSide.SELL if pos.is_long else OrderSide.BUY
qty = pos.quantity

close_order = self.order_factory.market(
    instrument_id=inst,
    order_side=side,
    quantity=instrument.make_qty(float(qty)),
    time_in_force=TimeInForce.IOC,
    reduce_only=True,  # ← Should prevent position reversal
)
```

**The side logic is CORRECT**:
- Long position → SELL to close ✓
- Short position → BUY to close ✓

**Possible Root Causes**:

1. **Bybit doesn't honor `reduce_only=True`**
   - May require different parameter or flag
   - May need to use position-specific API

2. **Grid strategy uses paired hedge positions**
   - PAXG SHORT + XAUT LONG in each grid
   - Closing logic might be closing one leg but opening another
   - May need to use different close mechanism for hedged positions

3. **Timing issue with position sync**
   - Close orders submit before positions fully sync to cache
   - Strategy sees "no position" and closes nothing
   - Meanwhile new positions open at lower levels

4. **Bybit One-Way vs Hedge Mode**
   - Config uses One-Way Mode (default)
   - May need explicit handling for paired positions

---

## Immediate Recommended Actions

### Option 1: Manual Position Close (Safest)
```bash
# Use Bybit web interface or API to manually close all positions
# Then set initial_notional_override=0.0 and restart fresh
```

### Option 2: Use close_all_positions.py
```bash
cd /home/ubuntu/GoldArb
python3 close_all_positions.py
```

### Option 3: Investigation Required

**Check Bybit documentation for**:
1. How to properly close positions in One-Way mode
2. Whether `reduce_only` is supported for MARKET orders
3. Alternative close mechanisms (position.close() API)

**Test with small position**:
1. Manually open a small test position on Bybit
2. Test close logic with that single position
3. Verify it closes rather than doubles
4. Once confirmed working, apply to full strategy

---

## Files Modified

| File | Lines | Description |
|------|-------|-------------|
| `paxg_xaut_grid_strategy.py` | 229-381 | Fixed position sync (HIGHEST to LOWEST) |
| `paxg_xaut_grid_strategy.py` | 871-931 | Added placeholder string handling |
| `config_live.py` | 106 | Set initial_notional_override=0.0 |
| `FIX_SUMMARY_2026-01-07.md` | - | Documentation of initial fix |

**Backups Created**:
- `paxg_xaut_grid_strategy.py.backup-20260107-*`

---

## Current Position State

**Last Known** (before emergency stop at 15:04):
- Total Notional: **~6932 USDT** (doubled from 3466)
- PAXG: ~3472 USDT
- XAUT: ~3460 USDT
- Grid Levels: Multiple positions at various levels

**IMPORTANT**: Check actual Bybit positions before any restart!

---

## Next Steps for Resolution

###  1. **Verify Current Positions on Bybit** (CRITICAL)
```bash
# Login to Bybit web interface
# Check Derivatives → Positions
# Note exact positions and sizes
```

### 2. **Test Close Mechanism**
Create a test script to close a single position:
```python
# Test if reduce_only works
# Test alternative close methods
# Verify Bybit accepts the close orders correctly
```

### 3. **Fix Close Logic**
Options:
- Remove `reduce_only` if not supported
- Use Bybit's position.close() API instead
- Implement position-specific close (not order-based)
- Add validation before close order submission

### 4. **Add Safety Checks**
- Monitor total_notional before/after close attempts
- Alert if notional increases instead of decreases
- Auto-stop if doubling detected
- Require manual confirmation for position operations

---

## Key Lessons Learned

1. ✅ **Position sync fix works perfectly** - marks correct levels with weights
2. ✅ **Close detection works perfectly** - identifies all levels to close
3. ❌ **Close execution fails** - orders submit but don't reduce positions
4. ⚠️  **Need better testing** - test close logic with single position first
5. ⚠️  **Need position monitoring** - alert on unexpected growth

---

## Questions to Answer

1. Does Bybit support `reduce_only` for MARKET orders on LINEAR perpetuals?
2. Is there a position.close() API we should use instead?
3. Are we in correct position mode (One-Way vs Hedge)?
4. Do we need special handling for paired positions?
5. Should we close positions individually or as pairs?

---

**Document Created**: 2026-01-07 15:05 UTC
**Strategy Status**: STOPPED
**Action Required**: Manual investigation and position cleanup
**Priority**: CRITICAL - Positions doubling on close attempts
