# PAXG-XAUT Grid Strategy - Live Trading Setup Guide

## Overview

This is a grid spread arbitrage strategy for PAXG/USDT-PERP and XAUT/USDT-PERP on Bybit, implemented using the NautilusTrader framework.

### Strategy Logic

- **Market**: Bybit perpetual swaps (PAXGUSDT-PERP and XAUTUSDT-PERP)
- **Type**: Market-neutral spread arbitrage
- **Mechanism**:
  - Calculates real-time price spread: `spread = (PAXG - XAUT) / XAUT`
  - Uses predefined grid levels (e.g., 0.10%, 0.20%, 0.30%, etc.)
  - When spread exceeds a grid level: Opens hedged positions (sell expensive, buy cheap)
  - When spread reverts below previous level: Closes the corresponding grid position
  - All orders use limit orders (maker) to minimize fees

## Directory Structure

```
PSArb/
├── paxg_xaut_grid_strategy.py   # Strategy implementation
├── config_live.py                # Live trading configuration
├── run_live.py                   # Main entry point for live trading
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
├── readme.md                     # Strategy documentation
└── logs/                         # Trading logs (auto-created)
```

## Prerequisites

### 1. System Requirements

- Python 3.10 or higher (3.12 recommended)
- pip package manager
- Git (optional, for version control)

### 2. Bybit Account Setup

1. **Create a Bybit Account**
   - Register at [https://www.bybit.com](https://www.bybit.com)
   - Complete KYC verification if required

2. **Generate API Keys**
   - Go to [API Management](https://www.bybit.com/app/user/api-management)
   - Create a new API key with the following permissions:
     - ✅ Read-Write (for trading)
     - ✅ Contract (for perpetual swaps)
   - **Important**: Save your API key and secret securely
   - Configure IP whitelist for additional security (recommended)

3. **Set Account Leverage**
   - Go to Bybit trading interface
   - Navigate to PAXGUSDT-PERP contract
   - Set leverage to **10x** (or your preferred level)
   - Repeat for XAUTUSDT-PERP contract
   - **Note**: The strategy uses `max_total_notional` to control risk exposure

4. **Fund Your Account**
   - Deposit USDT to your Derivatives account
   - Recommended: Start with at least $10,000 USDT for the default configuration
   - Ensure sufficient balance for the configured `max_total_notional`

## Installation

### Step 1: Install NautilusTrader

```bash
# Install NautilusTrader with Bybit support
pip install -U nautilus_trader

# Or install all dependencies from requirements.txt
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your Bybit API credentials:
```bash
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=false  # Set to 'true' for testnet
```

3. Load environment variables (or the script will read from .env):
```bash
export $(cat .env | xargs)
```

### Step 3: Verify Configuration

Run the configuration verification:
```bash
python config_live.py
```

Expected output:
```
================================================================================
PAXG-XAUT Grid Strategy - Live Trading Configuration
================================================================================
Trader ID: TRADER-001
Data Clients: ['BYBIT']
Exec Clients: ['BYBIT']
Strategies: 1
================================================================================
```

## Configuration

### Strategy Parameters

Edit `config_live.py` to customize the strategy:

```python
strategy_config = PaxgXautGridConfig(
    # Grid levels (price spread as percentage)
    grid_levels=[
        0.0010,  # 0.10%
        0.0020,  # 0.20%
        0.0030,  # 0.30%
        # ... add more levels as needed
    ],

    # Risk management
    base_notional_per_level=2000.0,  # USDT per grid level
    max_total_notional=40000.0,      # Maximum total exposure
    target_leverage=10.0,             # Target leverage (informational)

    # Trading parameters
    maker_offset_bps=2.0,             # 0.02% offset from mid price
    order_timeout_sec=5.0,            # Order timeout
    rebalance_threshold_bps=20.0,    # Rebalance threshold
    extreme_spread_stop=0.015,        # 1.5% extreme spread stop
)
```

### Risk Management Guidelines

**Conservative (Recommended for beginners)**:
```python
base_notional_per_level=1000.0   # $1,000 per level
max_total_notional=20000.0       # $20,000 max exposure
target_leverage=5.0              # 5x leverage
```

**Moderate**:
```python
base_notional_per_level=2000.0   # $2,000 per level
max_total_notional=40000.0       # $40,000 max exposure
target_leverage=10.0             # 10x leverage
```

**Aggressive**:
```python
base_notional_per_level=5000.0   # $5,000 per level
max_total_notional=100000.0      # $100,000 max exposure
target_leverage=15.0             # 15x leverage
```

## Running the Strategy

### Live Trading

```bash
python run_live.py
```

Expected startup output:
```
================================================================================
PAXG-XAUT Grid Strategy - Live Trading
================================================================================
✅ Running in LIVE mode
================================================================================

[1/5] Loading configuration...
[2/5] Building trading node...
[3/5] Registering Bybit adapters...
[4/5] Initializing trading node...
[5/5] Starting trading node...

================================================================================
🚀 Trading node started successfully!
================================================================================

Strategy: PAXG-XAUT Grid Arbitrage
Venue: Bybit (Live)
Instruments:
  - PAXGUSDT-PERP
  - XAUTUSDT-PERP

Press Ctrl+C to stop the trading node...
================================================================================
```

### Testnet Mode

For testing without real funds:

1. Create testnet API keys at [https://testnet.bybit.com](https://testnet.bybit.com)
2. Update `.env`:
```bash
BYBIT_TESTNET=true
BYBIT_API_KEY=your_testnet_api_key
BYBIT_API_SECRET=your_testnet_api_secret
```
3. Run the strategy:
```bash
python run_live.py
```

## Monitoring

### Log Files

Logs are saved in the `logs/` directory:
- **Location**: `logs/paxg_xaut_grid_*.log`
- **Format**: JSON (structured logging)
- **Levels**: DEBUG (file), INFO (console)

### Key Metrics to Monitor

1. **Spread**: Current PAXG-XAUT price spread
2. **Active Grids**: Number of open grid positions
3. **Total Notional**: Current exposure vs. max limit
4. **Realized PnL**: Profit/loss from closed positions
5. **Unrealized PnL**: Current open position P&L

### Bybit Web Interface

Monitor your positions and orders at:
- **Live**: [https://www.bybit.com/trade/usdt](https://www.bybit.com/trade/usdt)
- **Testnet**: [https://testnet.bybit.com/trade/usdt](https://testnet.bybit.com/trade/usdt)

## Stopping the Strategy

To gracefully stop the trading node:

1. Press `Ctrl+C` in the terminal
2. The strategy will:
   - Cancel all working orders
   - Optionally close positions (if configured)
   - Save state and shut down cleanly

## Troubleshooting

### Issue: "Missing required environment variables"

**Solution**: Ensure `.env` file exists and contains valid API credentials.

```bash
# Check if .env exists
ls -la .env

# Verify environment variables are set
echo $BYBIT_API_KEY
echo $BYBIT_API_SECRET
```

### Issue: "ModuleNotFoundError: No module named 'nautilus_trader'"

**Solution**: Install NautilusTrader:
```bash
pip install -U nautilus_trader
```

### Issue: "Instruments not found in cache"

**Solution**:
- Verify instrument IDs are correct for Bybit
- Check network connectivity
- Ensure API keys have correct permissions

### Issue: Orders getting rejected

**Common causes**:
- Insufficient margin/balance
- Incorrect leverage settings
- Position limits exceeded
- API rate limits

**Solution**:
- Check Bybit account balance
- Verify leverage is set correctly (10x recommended)
- Review `max_total_notional` in configuration
- Check Bybit API status

## Safety Recommendations

### Before Going Live

1. ✅ **Test on Testnet**: Run the strategy on testnet for at least 24 hours
2. ✅ **Start Small**: Use conservative position sizes initially
3. ✅ **Monitor Closely**: Watch the first few hours of live trading
4. ✅ **Set Alerts**: Configure Bybit mobile app for position/order alerts
5. ✅ **Risk Limits**: Ensure `max_total_notional` aligns with your risk tolerance

### Operational Best Practices

1. **Daily Monitoring**: Check positions and P&L at least once daily
2. **Log Review**: Regularly review log files for errors or warnings
3. **Balance Checks**: Ensure sufficient margin is maintained
4. **Extreme Events**: Be prepared to manually intervene during extreme market conditions
5. **Updates**: Keep NautilusTrader and dependencies updated

### Emergency Procedures

**If something goes wrong:**

1. **Stop the Strategy**: Press `Ctrl+C`
2. **Check Positions**: Review open positions on Bybit
3. **Manual Control**: Use Bybit web interface to manually close positions if needed
4. **Review Logs**: Check log files for error messages
5. **Seek Help**: Contact NautilusTrader community or Bybit support

## Support and Resources

### NautilusTrader
- **Documentation**: [https://nautilustrader.io/docs](https://nautilustrader.io/docs)
- **GitHub**: [https://github.com/nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader)
- **Discord**: [NautilusTrader Community](https://discord.gg/AUNMNnNDwP)

### Bybit
- **API Documentation**: [https://bybit-exchange.github.io/docs](https://bybit-exchange.github.io/docs)
- **Support**: [https://www.bybit.com/en-US/help-center](https://www.bybit.com/en-US/help-center)

## Disclaimer

**⚠️ IMPORTANT RISK DISCLOSURE**

Trading cryptocurrencies and derivatives involves substantial risk of loss. This strategy is provided for educational purposes only. Past performance does not guarantee future results.

- **Do not trade with funds you cannot afford to lose**
- **Understand the risks before deploying real capital**
- **The authors are not responsible for any financial losses**
- **This is not financial advice**

Use at your own risk.

## License

See the license header in the strategy source files for licensing information.
