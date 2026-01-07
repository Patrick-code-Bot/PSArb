# Gold Arbitrage Strategy - Critical Fix Applied (2026-01-07)

## Issue Summary

**Problem**: Positions were not closing after the initial grid was established, despite spread conditions meeting the closing criteria.

**Root Cause**: The position synchronization logic (`_sync_existing_positions()`) had a critical bug that marked the **WRONG grid levels** as occupied on strategy restart.

## Technical Details

### The Bug

1. **What it did wrong**:
   - Marked the **FIRST N** (lowest) grid levels as occupied (0.10%, 0.15%, 0.20%, ...)
   - Did NOT account for position weights when calculating which levels were filled
   - Used incorrect notional calculation (assumed weight=1.0 for all levels)

2. **Reality**:
   - Positions were opened at **HIGH spread levels** (0.30%, 0.50%, 1.00%, 2.00%, 3.00%, 5.00%, 8.00%)
   - Each level has different position weights affecting notional size
   - Total notional: 3432.39 USDT across ~11 grid levels

3. **Why closing didn't work**:
   - Closing logic checks: `if not self._grid_has_position(state): continue`
   - Since wrong levels were marked, the ACTUAL positions were never tracked
   - Result: All closing conditions were skipped, positions stayed open indefinitely

### The Fix

**File Modified**: `paxg_xaut_grid_strategy.py`
- Lines 229-381: Completely rewrote `_sync_existing_positions()` method

**Changes**:
1. ✅ Iterate from **HIGHEST to LOWEST** levels (reverse order)
2. ✅ Account for **position weights** when calculating notional per level
3. ✅ Use **80% threshold** for matching (handles slight price variations)
4. ✅ Provide detailed logging of which levels are marked and remaining notional
5. ✅ Link actual PositionId objects when available from cache

**Config Modified**: `config_live.py`
- Line 106: Set `initial_notional_override=3432.39` (from logs showing total_notional)

## Current Market Situation (as of verification)

```
Current Spread: 0.3755% (PAXG: $4463.75, XAUT: $4447.05)
Total Notional: 3432.39 USDT
Estimated Positions: ~11 grid levels
```

**Expected Behavior After Fix**:
- Positions at levels 0.50% and above **SHOULD CLOSE** (spread 0.38% < their prev_level)
- This includes: 0.50%, 0.60%, 0.80%, 1.00%, 1.50%, 2.00%, 3.00%, 5.00%, 8.00%
- Only positions at 0.30% and 0.40% should remain open

## How to Apply the Fix

### Step 1: Review the Changes (Optional)
```bash
cd /home/ubuntu/GoldArb

# Check backup was created
ls -lh paxg_xaut_grid_strategy.py.backup-*

# Compare changes if desired
diff paxg_xaut_grid_strategy.py.backup-* paxg_xaut_grid_strategy.py | head -100
```

### Step 2: Verify Current State
```bash
# Check current spread and expected actions
python3 check_spread.py

# Diagnose position mapping issue
python3 diagnose_positions.py
```

### Step 3: Restart Strategy with Fix
```bash
# Use the automated restart script (RECOMMENDED)
./restart_strategy.sh

# OR manual restart:
# 1. Find PID: ps aux | grep run_live.py
# 2. Stop: kill -TERM <PID>
# 3. Wait for clean shutdown (watch logs)
# 4. Start: nohup python3 run_live.py > logs/run_live.out 2>&1 &
```

### Step 4: Verify Fix is Working
```bash
# Run comprehensive verification
python3 verify_fix.py

# Monitor logs in real-time
tail -f logs/paxg_xaut_grid_*.json | grep -E "STARTUP SYNC|Marked grid level|Closing grid"

# Check for close orders
grep -i "closing grid\|close order\|fully closed" logs/paxg_xaut_grid_*.json | tail -20
```

## Expected Results After Restart

### 1. Startup Sync Log Messages

You should see:
```
⚠️ STARTUP SYNC (MANUAL): initial_notional_override=3432.39.
Marked 11 grid level(s) as occupied: ['0.30%', '0.40%', '0.50%', '0.60%', '0.80%', '1.00%', '1.50%', '2.00%', '3.00%', '5.00%', '8.00%'].
```

Each marked level will show:
```
Marked grid level=0.0050 (0.50%) as occupied (notional=177.00, remaining=XXX.XX)
```

### 2. Position Closing Activity

Within minutes of restart (if spread remains ~0.38%):
```
Closing grid level=0.0050, spread=0.003755
Submitted close orders for grid level=0.0050: PAXG=..., XAUT=...
✓ Grid level 0.005 fully closed. Reduced notional by 177.00. Total=3255.39
```

This should repeat for each level > 0.40% (prev_level threshold).

### 3. Final State

After all closing completes:
- Positions at 0.30% and 0.40% remain open (~318.60 USDT total)
- Positions at 0.50%-8.00% are closed
- Strategy continues monitoring spread for new opportunities

## Monitoring and Validation

### Real-time Monitoring Commands

```bash
# Watch all important events
tail -f logs/paxg_xaut_grid_*.json | jq -r 'select(.message | contains("Closing") or contains("closed") or contains("SYNC")) | "\(.timestamp) [\(.level)] \(.message)"'

# Count closing events
grep -c "Closing grid" logs/paxg_xaut_grid_*.json

# Check current total notional
grep "Position Reconciliation" logs/paxg_xaut_grid_*.json | tail -1

# View position status
grep "total_notional\|Total=" logs/paxg_xaut_grid_*.json | tail -20
```

### Verification Checklist

- [ ] Strategy restarted successfully
- [ ] Startup sync shows 11 grid levels marked (not 19)
- [ ] Marked levels are HIGH spreads (0.30%-8.00%), not low (0.10%-0.30%)
- [ ] "Closing grid" messages appear in logs
- [ ] Close orders are submitted and filled
- [ ] total_notional decreases as positions close
- [ ] Final state matches expected (only 0.30% and 0.40% remain)

## Troubleshooting

### Issue: No "Closing grid" messages appear

**Check 1**: Verify spread is actually below closing threshold
```bash
python3 check_spread.py
```

**Check 2**: Confirm positions were synced correctly
```bash
python3 verify_fix.py
```

**Check 3**: Check for errors in logs
```bash
grep -i "error\|failed\|exception" logs/paxg_xaut_grid_*.json | tail -20
```

### Issue: Positions closing but errors occur

**Check close order status**:
```bash
grep -i "close.*reject\|close.*cancel\|imbalanced close" logs/*.json | tail -20
```

The strategy has retry logic for failed closes, monitor for re-submission.

### Issue: Want to close ALL positions immediately

If you prefer to start fresh:
```bash
# Close all positions manually
python3 close_all_positions.py

# Update config to start fresh
# Edit config_live.py: initial_notional_override=0.0

# Restart strategy
./restart_strategy.sh
```

## Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `paxg_xaut_grid_strategy.py` | Lines 229-381 rewritten | Fixed position sync logic |
| `config_live.py` | Line 106: set to 3432.39 | Enable proper sync on restart |
| `restart_strategy.sh` | Created | Safe restart procedure |
| `verify_fix.py` | Created | Verify fix is working |
| `check_spread.py` | Created | Check current market state |
| `diagnose_positions.py` | Created | Diagnose the bug |

## Backup Files

Original files backed up with timestamp:
- `paxg_xaut_grid_strategy.py.backup-YYYYMMDD-HHMMSS`

## Next Steps

1. **Restart the strategy** using `./restart_strategy.sh`
2. **Monitor for 10-15 minutes** to see closing activity
3. **Verify with** `python3 verify_fix.py`
4. **Check final state** matches expectations (positions at 0.30%, 0.40% remain)

## Long-term Recommendations

1. **After positions close to desired levels**, update `config_live.py`:
   - Set `initial_notional_override` to the new total_notional (from logs)
   - This ensures proper sync on future restarts

2. **Add monitoring alerts** for:
   - Position reconciliation drift > 100 USDT
   - No closing activity when expected
   - Total notional exceeds max_total_notional

3. **Consider implementing** (future enhancement):
   - Real-time position tracking independent of restart sync
   - Grid level tagging in order metadata for exact matching
   - Automated notional override updates

## Questions or Issues?

If the fix doesn't work as expected:

1. Run all diagnostic scripts and save output:
   ```bash
   python3 check_spread.py > diagnostics.txt
   python3 verify_fix.py >> diagnostics.txt
   grep "STARTUP SYNC\|Closing grid\|total_notional" logs/*.json >> diagnostics.txt
   ```

2. Check strategy is using the fixed code:
   ```bash
   grep -n "FIX: Mark grid levels from HIGHEST to LOWEST" paxg_xaut_grid_strategy.py
   # Should show line 249 and 342
   ```

3. Verify config has correct override:
   ```bash
   grep "initial_notional_override" config_live.py
   # Should show: initial_notional_override=3432.39,
   ```

---

**Fix Applied**: 2026-01-07 14:00 UTC
**Status**: Ready for restart
**Expected Result**: Positions at levels 0.50%-8.00% will close when spread < their prev_level
