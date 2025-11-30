# PAXG-XAUT Grid Strategy - Comprehensive Code Explanation

## Table of Contents
1. [Overview](#overview)
2. [Configuration Structure](#configuration-structure)
3. [Strategy Initialization](#strategy-initialization)
4. [Lifecycle Methods](#lifecycle-methods)
5. [Market Data Processing](#market-data-processing)
6. [Grid Logic Deep Dive](#grid-logic-deep-dive)
7. [Order Management](#order-management)
8. [Position Management](#position-management)
9. [Helper Functions](#helper-functions)
10. [Execution Flow Diagram](#execution-flow-diagram)

---

## Overview

**Strategy Type**: Market-Neutral Spread Arbitrage
**Framework**: NautilusTrader
**Venue**: Bybit (Perpetual Swaps)
**Instruments**: PAXGUSDT-PERP, XAUTUSDT-PERP

### Core Concept

```
spread = (PAXG_mid_price - XAUT_mid_price) / XAUT_mid_price

When spread > threshold:
  - If spread > 0: PAXG is expensive → Short PAXG, Long XAUT
  - If spread < 0: XAUT is expensive → Long PAXG, Short XAUT

When spread reverts < threshold:
  - Close positions and realize profit
```

---

## Configuration Structure

### Lines 31-72: `PaxgXautGridConfig` Class

```python
@dataclass
class PaxgXautGridConfig(StrategyConfig):
```

**Purpose**: Defines all strategy parameters in a type-safe dataclass.

#### Key Parameters Explained:

**1. Instrument IDs (Lines 35-36)**
```python
paxg_instrument_id: str = "PAXGUSDT-PERP.BYBIT"
xaut_instrument_id: str = "XAUTUSDT-PERP.BYBIT"
```
- Specifies which contracts to trade
- Format: `{SYMBOL}-PERP.{VENUE}`

**2. Grid Levels (Lines 40-43)**
```python
grid_levels: List[float] = [0.0010, 0.0020, 0.0030, ...]
```
- Spread thresholds that trigger trades
- `0.0010` = 0.10% spread
- `0.0100` = 1.00% spread
- **Example**: If spread reaches 0.30%, grid at 0.0030 activates

**3. Position Sizing (Lines 46-50)**
```python
base_notional_per_level: float = 2_000.0  # $2,000 USDT per grid
max_total_notional: float = 40_000.0      # Max $40,000 total exposure
```
- **base_notional_per_level**: How much USDT to risk per grid level
- **max_total_notional**: Total risk cap (prevents over-exposure)
- **Calculation**: With 8 grid levels × $2,000 × 2 legs = $32,000 max

**4. Risk Controls (Lines 59-68)**
```python
maker_offset_bps: float = 2.0           # 0.02% price improvement
extreme_spread_stop: float = 0.015      # Emergency stop at 1.5%
rebalance_threshold_bps: float = 20.0   # Hedge ratio tolerance
```

---

## Strategy Initialization

### Lines 90-117: `__init__` Method

```python
def __init__(self, config: PaxgXautGridConfig) -> None:
    super().__init__(config)  # Initialize NautilusTrader base class
```

**Step-by-Step Initialization**:

**1. Store Configuration (Line 94)**
```python
self.config: PaxgXautGridConfig = config
```

**2. Create Instrument IDs (Lines 97-98)**
```python
self.paxg_id = InstrumentId.from_str(config.paxg_instrument_id)
self.xaut_id = InstrumentId.from_str(config.xaut_instrument_id)
```
- Converts strings to NautilusTrader InstrumentId objects
- Used for all subsequent instrument references

**3. Initialize Quote Storage (Lines 104-107)**
```python
self.paxg_bid: Optional[float] = None
self.paxg_ask: Optional[float] = None
self.xaut_bid: Optional[float] = None
self.xaut_ask: Optional[float] = None
```
- Stores latest bid/ask prices for spread calculation
- `None` until first quote received

**4. Grid State Tracking (Line 110)**
```python
self.grid_state: Dict[float, GridPositionState] = {}
```
- Maps each grid level to its position state
- Example: `{0.0010: GridPositionState(paxg_pos_id=123, xaut_pos_id=456)}`

**5. Working Orders (Line 114)**
```python
self.working_orders: Dict[OrderId, tuple[float, str]] = {}
```
- Tracks pending orders: `{order_id: (grid_level, leg_type)}`
- Example: `{order_123: (0.0030, "PAXG_SHORT")}`

**6. Notional Tracking (Line 117)**
```python
self.total_notional: float = 0.0
```
- Cumulative exposure across all open grids
- Updated on open/close

---

## Lifecycle Methods

### Lines 120-148: `on_start` Method

**Execution Flow**:

**1. Log Startup (Lines 121-124)**
```python
self.log.info(f"PaxgXautGridStrategy starting...")
```

**2. Fetch Instruments from Cache (Lines 127-128)**
```python
self.paxg = self.cache.instrument(self.paxg_id)
self.xaut = self.cache.instrument(self.xaut_id)
```
- Retrieves instrument metadata (tick size, lot size, etc.)
- **Critical**: Needed for `make_qty()` and `make_price()` conversions

**3. Validate Instruments (Lines 130-134)**
```python
if self.paxg is None or self.xaut is None:
    raise RuntimeError("Instruments not found in cache...")
```
- Ensures instruments exist before trading
- Prevents runtime errors

**4. Initialize Grid States (Lines 137-138)**
```python
for level in self.config.grid_levels:
    self.grid_state[level] = GridPositionState(level=level)
```
- Creates empty state for each grid level
- Example result:
```python
{
    0.0010: GridPositionState(level=0.0010, paxg_pos_id=None, xaut_pos_id=None),
    0.0020: GridPositionState(level=0.0020, paxg_pos_id=None, xaut_pos_id=None),
    ...
}
```

**5. Subscribe to Market Data (Lines 140-142)**
```python
if self.config.auto_subscribe:
    self.subscribe_instrument(self.paxg_id)
    self.subscribe_instrument(self.xaut_id)
```
- Starts receiving `QuoteTick` events via WebSocket
- Triggers `on_quote_tick()` handler

### Lines 149-155: `on_stop` Method

**Shutdown Procedure**:

```python
def on_stop(self) -> None:
    # Cancel all pending orders
    for order_id in list(self.working_orders.keys()):
        self.cancel_order(order_id)
```

**Why This Matters**:
- Prevents orphaned orders on Bybit
- Ensures clean shutdown
- Optional: Could also close all positions (currently commented out)

---

## Market Data Processing

### Lines 158-188: `on_quote_tick` Method

**This is the HEART of the strategy** - called every time a new quote arrives.

**Step 1: Update Quote Storage (Lines 160-165)**
```python
if tick.instrument_id == self.paxg_id:
    self.paxg_bid = float(tick.bid_price)
    self.paxg_ask = float(tick.ask_price)
elif tick.instrument_id == self.xaut_id:
    self.xaut_bid = float(tick.bid_price)
    self.xaut_ask = float(tick.ask_price)
```

**Example**:
```
PAXG quote arrives: bid=$2750.50, ask=$2750.60
→ self.paxg_bid = 2750.50
→ self.paxg_ask = 2750.60

XAUT quote arrives: bid=$2748.20, ask=$2748.30
→ self.xaut_bid = 2748.20
→ self.xaut_ask = 2748.30
```

**Step 2: Validate Quotes (Lines 167-168)**
```python
if not self._has_valid_quotes():
    return
```
- Ensures all 4 prices (PAXG bid/ask, XAUT bid/ask) exist
- Early return if any price missing

**Step 3: Calculate Spread (Lines 170-172)**
```python
spread = self._calc_spread()  # Calls helper function
if spread is None:
    return
```

**Calculation** (from lines 412-418):
```python
paxg_mid = (self.paxg_bid + self.paxg_ask) / 2.0
xaut_mid = (self.xaut_bid + self.xaut_ask) / 2.0
spread = (paxg_mid - xaut_mid) / xaut_mid
```

**Example Calculation**:
```
PAXG mid = (2750.50 + 2750.60) / 2 = 2750.55
XAUT mid = (2748.20 + 2748.30) / 2 = 2748.25

spread = (2750.55 - 2748.25) / 2748.25 = 0.000837 (0.084%)
```

**Step 4: Extreme Spread Protection (Lines 174-179)**
```python
if abs(spread) > self.config.extreme_spread_stop:  # 1.5% default
    self.log.warning(f"Extreme spread detected {spread:.4%}")
    self._close_all_grids()
    return
```

**Why This Exists**:
- Market disruption (exchange issues, oracle failure)
- Protects against abnormal conditions
- Emergency shutdown mechanism

**Step 5: Process Grid Logic (Line 182)**
```python
self._process_grids(spread)
```
**This is where trading decisions happen** - detailed below.

**Step 6: Rebalance Check (Line 185)**
```python
self._rebalance_if_needed()
```
- Ensures hedge ratio stays balanced
- Currently a placeholder (line 401: `pass`)

**Step 7: Order Timeout Check (Line 188)**
```python
self._check_order_timeouts()
```
- Cancels stale orders
- Currently a placeholder (line 455: `pass`)

---

## Grid Logic Deep Dive

### Lines 226-260: `_process_grids` Method

**This method implements the core grid strategy logic.**

#### Part 1: Close Grids (Lines 234-244)

**Logic**: "If spread has reverted below previous grid level, close that grid."

```python
levels_sorted = sorted(self.config.grid_levels)  # [0.001, 0.002, 0.003, ...]

for i, level in enumerate(levels_sorted):
    state = self.grid_state[level]

    # Skip if no position at this level
    if not self._grid_has_position(state):
        continue

    # Calculate previous level (0 for first level)
    prev_level = 0.0 if i == 0 else levels_sorted[i - 1]

    # If spread dropped below previous level, close this grid
    if abs_spread < prev_level:
        self.log.info(f"Closing grid level={level}, spread={spread:.4%}")
        self._close_grid(level, state)
```

**Example Scenario**:

```
Grid Levels: [0.001, 0.002, 0.003]
Current spread: 0.0025 (0.25%)

Active grids:
- Level 0.001 (0.10%): Has position ✓
- Level 0.002 (0.20%): Has position ✓
- Level 0.003 (0.30%): No position

Closing check:
- Level 0.001: prev_level=0, abs(0.0025) > 0 → Keep open
- Level 0.002: prev_level=0.001, abs(0.0025) > 0.001 → Keep open
- Level 0.003: No position, skip

If spread drops to 0.0008 (0.08%):
- Level 0.001: abs(0.0008) < 0 (prev_level) → FALSE, keep open
- Level 0.002: abs(0.0008) < 0.001 → TRUE → CLOSE! ✓

Result: Grid at 0.002 closes, profit realized
```

#### Part 2: Open New Grids (Lines 246-260)

**Logic**: "If spread exceeds a grid level and that grid is empty, open new hedged position."

```python
for i, level in enumerate(levels_sorted):
    state = self.grid_state[level]

    # Skip if already have position at this level
    if self._grid_has_position(state):
        continue

    # Check if spread exceeds this level
    if abs_spread > level:
        # Risk check: Don't exceed max notional
        notional = self.config.base_notional_per_level
        if self.total_notional + 2 * notional > self.config.max_total_notional:
            self.log.warning("Max total notional reached, skip new grid.")
            continue

        # Open new grid
        self.log.info(f"Opening grid level={level}, spread={spread:.4%}")
        self._open_grid(level, spread)
```

**Example Scenario**:

```
Grid Levels: [0.001, 0.002, 0.003]
Current spread: 0.0032 (0.32%)
Max notional: $40,000
Current total: $8,000

Opening check:
- Level 0.001 (0.10%): 0.0032 > 0.001 → TRUE
  - Has position? Check state
  - If no position: Open grid ($2k × 2 = $4k)
  - New total: $8k + $4k = $12k < $40k ✓

- Level 0.002 (0.20%): 0.0032 > 0.002 → TRUE
  - Has position? Check state
  - If no position: Open grid ($2k × 2 = $4k)
  - New total: $12k + $4k = $16k < $40k ✓

- Level 0.003 (0.30%): 0.0032 > 0.003 → TRUE
  - Has position? Check state
  - If no position: Open grid ($2k × 2 = $4k)
  - New total: $16k + $4k = $20k < $40k ✓

Result: All three grids opened with hedged positions
```

### Lines 266-325: `_open_grid` Method

**This creates and submits the paired hedge orders.**

**Step 1: Calculate Mid Prices (Lines 271-275)**
```python
paxg_price = self._mid_price(self.paxg_bid, self.paxg_ask)
xaut_price = self._mid_price(self.xaut_bid, self.xaut_ask)
```

**Step 2: Calculate Order Quantities (Lines 277-280)**
```python
notional = self.config.base_notional_per_level  # $2,000

paxg_qty = notional / paxg_price
xaut_qty = notional / xaut_price
```

**Example**:
```
notional = $2,000
paxg_price = $2750.55
xaut_price = $2748.25

paxg_qty = 2000 / 2750.55 = 0.727 contracts
xaut_qty = 2000 / 2748.25 = 0.728 contracts
```

**Step 3: Determine Order Sides (Lines 282-293)**
```python
if spread > 0:
    # PAXG is expensive → Short PAXG, Long XAUT
    paxg_side = OrderSide.SELL
    xaut_side = OrderSide.BUY
    paxg_leg_tag = "PAXG_SHORT"
    xaut_leg_tag = "XAUT_LONG"
else:
    # XAUT is expensive → Long PAXG, Short XAUT
    paxg_side = OrderSide.BUY
    xaut_side = OrderSide.SELL
    paxg_leg_tag = "PAXG_LONG"
    xaut_leg_tag = "XAUT_SHORT"
```

**Visual Representation**:
```
Spread = +0.32% (PAXG expensive)
┌────────────────────────────────────┐
│ PAXG @ $2750.55 (expensive)        │
│ Action: SELL (Short)               │
│ Qty: 0.727 contracts              │
└────────────────────────────────────┘
         ↓ (Hedge)
┌────────────────────────────────────┐
│ XAUT @ $2748.25 (cheap)           │
│ Action: BUY (Long)                 │
│ Qty: 0.728 contracts              │
└────────────────────────────────────┘

Result: Market-neutral position
If PAXG/XAUT spread narrows → Profit!
```

**Step 4: Calculate Maker Prices (Lines 296-297)**
```python
paxg_price_limit = self._maker_price(self.paxg_bid, self.paxg_ask, paxg_side)
xaut_price_limit = self._maker_price(self.xaut_bid, self.xaut_ask, xaut_side)
```

**Maker Price Logic** (Lines 426-438):
```python
mid = (bid + ask) / 2.0
offset = self.config.maker_offset_bps / 10_000.0 * mid  # 0.02% default

if side == OrderSide.BUY:
    return min(ask, mid - offset)  # Buy below mid
else:
    return max(bid, mid + offset)  # Sell above mid
```

**Example**:
```
PAXG: bid=$2750.50, ask=$2750.60, side=SELL
mid = 2750.55
offset = 2.0 / 10000 × 2750.55 = 0.55
price = max(2750.50, 2750.55 + 0.55) = 2751.10

XAUT: bid=$2748.20, ask=$2748.30, side=BUY
mid = 2748.25
offset = 2.0 / 10000 × 2748.25 = 0.55
price = min(2748.30, 2748.25 - 0.55) = 2747.70
```

**Why Maker Pricing**:
- Gets rebates instead of paying taker fees
- Example: Bybit maker rebate = -0.01%, taker fee = +0.06%
- Saves 0.07% on each trade!

**Step 5: Create Limit Orders (Lines 300-314)**
```python
paxg_order = self.order_factory.limit(
    instrument_id=self.paxg_id,
    order_side=paxg_side,
    quantity=self.paxg.make_qty(paxg_qty),  # Converts to proper precision
    price=self.paxg.make_price(paxg_price_limit),
    time_in_force=TimeInForce.GTC,  # Good Till Cancel
)
```

**Key Detail**: `make_qty()` and `make_price()`
- Converts floats to exchange-specific precision
- Example: PAXG might require 0.001 lot size → rounds 0.727 to 0.727

**Step 6: Submit Orders (Lines 317-318)**
```python
self.submit_order(paxg_order)
self.submit_order(xaut_order)
```
- Sends orders to NautilusTrader execution engine
- Engine routes to Bybit execution client
- Orders hit Bybit API

**Step 7: Track Working Orders (Lines 321-322)**
```python
self.working_orders[paxg_order.client_order_id] = (level, paxg_leg_tag)
self.working_orders[xaut_order.client_order_id] = (level, xaut_leg_tag)
```

**Example**:
```python
{
    "O-20241201-001": (0.0030, "PAXG_SHORT"),
    "O-20241201-002": (0.0030, "XAUT_LONG")
}
```

**Step 8: Update Total Notional (Line 325)**
```python
self.total_notional += 2 * notional  # $2k × 2 = $4k
```

---

## Order Management

### Lines 190-223: Order Event Handlers

**Event Flow**:
```
Order Submitted
    ↓
OrderAccepted (Line 191)
    ↓
OrderFilled (Line 202)
```

#### `on_order_filled` Deep Dive (Lines 202-223)

**Step 1: Retrieve Order Info (Line 204)**
```python
level, leg = self.working_orders.pop(event.client_order_id, (None, None))
```
- Removes order from tracking
- Gets grid level and leg type

**Step 2: Get Position (Line 210)**
```python
pos = self.cache.position_for_order(event.client_order_id)
```
- NautilusTrader automatically creates positions
- Returns Position object or None

**Step 3: Update Grid State (Lines 216-223)**
```python
if leg == "PAXG_LONG":
    state.paxg_pos_id = pos.id if pos is not None else None
elif leg == "PAXG_SHORT":
    state.paxg_pos_id = pos.id if pos is not None else None
# ... same for XAUT
```

**Example State Update**:
```python
# Before fill
grid_state[0.0030] = GridPositionState(
    level=0.0030,
    paxg_pos_id=None,
    xaut_pos_id=None
)

# After PAXG SHORT fills
grid_state[0.0030] = GridPositionState(
    level=0.0030,
    paxg_pos_id="POS-123",  # ← Updated
    xaut_pos_id=None
)

# After XAUT LONG fills
grid_state[0.0030] = GridPositionState(
    level=0.0030,
    paxg_pos_id="POS-123",
    xaut_pos_id="POS-124"  # ← Updated
)
```

---

## Position Management

### Lines 327-366: Closing Positions

#### `_close_grid` (Lines 327-337)

**Purpose**: Close both legs of a grid level.

```python
def _close_grid(self, level: float, state: GridPositionState) -> None:
    # Close PAXG leg
    if state.paxg_pos_id is not None:
        self._close_position(state.paxg_pos_id)
        state.paxg_pos_id = None

    # Close XAUT leg
    if state.xaut_pos_id is not None:
        self._close_position(state.xaut_pos_id)
        state.xaut_pos_id = None

    # Reduce total notional
    self.total_notional = max(0.0, self.total_notional - 2 * self.config.base_notional_per_level)
```

**Example**:
```
Before close:
total_notional = $20,000

Grid 0.0030 closes ($2k × 2 = $4k)
total_notional = max(0, 20000 - 4000) = $16,000
```

#### `_close_position` (Lines 343-366)

**Step-by-Step**:

**1. Get Position from Cache (Lines 344-346)**
```python
pos = self.cache.position(pos_id)
if pos is None:
    return
```

**2. Determine Close Direction (Lines 353-354)**
```python
side = OrderSide.SELL if pos.is_long else OrderSide.BUY
qty = pos.quantity
```

**Logic**:
```
Long position → SELL to close
Short position → BUY to close
```

**3. Get Current Quotes (Lines 356-357)**
```python
bid, ask = self._get_bid_ask(inst)
price = self._maker_price(bid, ask, side)
```
- Uses current market prices
- Applies maker offset for rebates

**4. Create Close Order (Lines 359-365)**
```python
close_order = self.order_factory.limit(
    instrument_id=inst,
    order_side=side,
    quantity=instrument.make_qty(float(qty)),
    price=instrument.make_price(price),
    time_in_force=TimeInForce.GTC,
)
```

**5. Submit (Line 366)**
```python
self.submit_order(close_order)
```

---

## Helper Functions

### Spread Calculation (Lines 412-418)

```python
def _calc_spread(self) -> Optional[float]:
    paxg_mid = self._mid_price(self.paxg_bid, self.paxg_ask)
    xaut_mid = self._mid_price(self.xaut_bid, self.xaut_ask)
    if paxg_mid is None or xaut_mid is None:
        return None
    return (paxg_mid - xaut_mid) / xaut_mid
```

**Formula**:
```
spread = (PAXG_mid - XAUT_mid) / XAUT_mid

Positive spread: PAXG expensive relative to XAUT
Negative spread: XAUT expensive relative to PAXG
```

### Mid Price (Lines 420-424)

```python
@staticmethod
def _mid_price(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2.0
```

**Why Mid Price**:
- Fair value between bid/ask
- Reduces noise from spread fluctuations
- Standard practice for spread calculations

---

## Execution Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    STRATEGY STARTS                           │
│                     (on_start)                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. Fetch instruments from cache                             │
│ 2. Initialize grid states (all empty)                       │
│ 3. Subscribe to PAXG & XAUT quotes                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              WAITING FOR QUOTES...                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           QUOTE TICK ARRIVES (on_quote_tick)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
         ┌──────────────────┴──────────────────┐
         ↓                                      ↓
┌─────────────────┐                  ┌─────────────────┐
│  PAXG Quote?    │                  │  XAUT Quote?    │
│  Update bid/ask │                  │  Update bid/ask │
└─────────────────┘                  └─────────────────┘
         ↓                                      ↓
         └──────────────────┬──────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│             Have all 4 prices?                               │
│       (PAXG bid/ask, XAUT bid/ask)                          │
└─────────────────────────────────────────────────────────────┘
                            ↓ YES
┌─────────────────────────────────────────────────────────────┐
│          CALCULATE SPREAD                                    │
│  spread = (PAXG_mid - XAUT_mid) / XAUT_mid                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│        Extreme spread check                                  │
│     |spread| > 1.5%?                                        │
└─────────────────────────────────────────────────────────────┘
         ↓ NO                               ↓ YES
         │                         ┌─────────────────┐
         │                         │  Close all      │
         │                         │  grids & stop   │
         │                         └─────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│              PROCESS GRIDS                                   │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Check for grids to CLOSE                           │
│  For each level with position:                              │
│    If |spread| < previous_level:                            │
│      → Close both legs                                       │
│      → Update total_notional                                 │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Check for grids to OPEN                            │
│  For each level without position:                           │
│    If |spread| > level:                                     │
│      → Check max_total_notional                             │
│      → Open new hedged position                              │
│      → Update total_notional                                 │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│         OPENING NEW GRID (if triggered)                      │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│  1. Calculate quantities (notional / price)                  │
│  2. Determine sides (Short expensive, Long cheap)           │
│  3. Calculate maker prices (mid ± offset)                   │
│  4. Create limit orders                                      │
│  5. Submit both orders                                       │
│  6. Track in working_orders                                  │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│              ORDERS SENT TO BYBIT                            │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│         ORDER FILLS (on_order_filled)                        │
│  1. Get order from working_orders                           │
│  2. Fetch position from cache                                │
│  3. Update grid_state with position_id                      │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│        WAIT FOR NEXT QUOTE TICK...                          │
│              (Loop continues)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Complete Example Scenario

Let's walk through a complete trading scenario:

### Initial State
```
Grid Levels: [0.001, 0.002, 0.003]
All grids: Empty
Total notional: $0
```

### Quote 1: Spread = 0.0005 (0.05%)
```
PAXG: $2750.50 / $2750.60
XAUT: $2749.10 / $2749.20

spread = (2750.55 - 2749.15) / 2749.15 = 0.00051 (0.051%)

Check grids:
- 0.001: 0.00051 < 0.001 → No action
- 0.002: 0.00051 < 0.002 → No action
- 0.003: 0.00051 < 0.003 → No action

Result: No trades
```

### Quote 2: Spread = 0.0025 (0.25%)
```
PAXG: $2756.30 / $2756.40
XAUT: $2749.50 / $2749.60

spread = (2756.35 - 2749.55) / 2749.55 = 0.00247 (0.247%)

Check grids:
- 0.001: 0.00247 > 0.001 AND no position → OPEN ✓
- 0.002: 0.00247 > 0.002 AND no position → OPEN ✓
- 0.003: 0.00247 < 0.003 → No action

Opening grid 0.001:
  PAXG: SELL 0.726 @ $2756.90 (maker price)
  XAUT: BUY 0.728 @ $2749.00 (maker price)

Opening grid 0.002:
  PAXG: SELL 0.726 @ $2756.90 (maker price)
  XAUT: BUY 0.728 @ $2749.00 (maker price)

Total notional: $8,000 ($2k × 2 grids × 2 legs)
```

### Quote 3: Spread = 0.0012 (0.12%)
```
PAXG: $2752.80 / $2752.90
XAUT: $2749.50 / $2749.60

spread = (2752.85 - 2749.55) / 2749.55 = 0.0012 (0.12%)

Check grids to close:
- 0.001: prev_level=0, |0.0012| > 0 → Keep
- 0.002: prev_level=0.001, |0.0012| > 0.001 → Keep

Check grids to open:
- 0.001: Already has position → Skip
- 0.002: Already has position → Skip
- 0.003: 0.0012 < 0.003 → No action

Result: Hold positions
```

### Quote 4: Spread = 0.0008 (0.08%)
```
PAXG: $2751.20 / $2751.30
XAUT: $2749.00 / $2749.10

spread = (2751.25 - 2749.05) / 2749.05 = 0.0008 (0.08%)

Check grids to close:
- 0.001: prev_level=0, |0.0008| > 0 → Keep
- 0.002: prev_level=0.001, |0.0008| < 0.001 → CLOSE ✓

Closing grid 0.002:
  PAXG: BUY 0.726 @ $2751.20 (close short)
  XAUT: SELL 0.728 @ $2749.10 (close long)

Profit calculation:
  PAXG: Sold @ $2756.90, Bought @ $2751.20 = +$5.70 × 0.726 = +$4.14
  XAUT: Bought @ $2749.00, Sold @ $2749.10 = +$0.10 × 0.728 = +$0.07
  Total: ~$4.21 (before fees)

Total notional: $4,000 (only grid 0.001 remains)
```

---

## Key Takeaways

### Strategy Strengths
1. ✅ **Market Neutral**: No directional exposure to gold prices
2. ✅ **Systematic**: Rule-based, no discretion
3. ✅ **Scalable**: Can add more grid levels
4. ✅ **Fee Efficient**: Uses maker orders

### Current Limitations
1. ⚠️ **No Dynamic Sizing**: Fixed $2k per level
2. ⚠️ **Rebalancing Incomplete**: Placeholder only
3. ⚠️ **Order Timeout**: Not implemented
4. ⚠️ **No Historical Data**: Starts from scratch

### Risk Considerations
1. 🛡️ **Spread Divergence**: If spread widens beyond extreme_stop
2. 🛡️ **Liquidity**: Needs sufficient depth on both instruments
3. 🛡️ **Correlation Break**: PAXG/XAUT must stay correlated
4. 🛡️ **Exchange Risk**: Bybit outages or issues

---

*Last updated: December 1, 2024*
