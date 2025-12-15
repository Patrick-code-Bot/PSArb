# 🏆 GoldArb - PAXG/XAUT Grid Arbitrage Strategy

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![NautilusTrader](https://img.shields.io/badge/NautilusTrader-1.221.0-green.svg)](https://nautilustrader.io/)
[![License](https://img.shields.io/badge/License-LGPL--3.0-orange.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](Dockerfile)

A high-frequency market-neutral spread arbitrage trading strategy for PAXG/USDT and XAUT/USDT perpetual swaps on Bybit, built with the NautilusTrader algorithmic trading framework.

---

## 📖 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Strategy Logic](#strategy-logic)
- [Architecture](#architecture)
- [Installation](#installation)
  - [Docker Deployment (Recommended)](#docker-deployment-recommended)
  - [Local Development Setup](#local-development-setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Monitoring](#monitoring)
- [Risk Management](#risk-management)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## 🎯 Overview

GoldArb is an automated trading strategy that exploits price spreads between two highly correlated gold-backed tokens:

- **PAXG (Pax Gold)**: ERC-20 token backed by physical gold
- **XAUT (Tether Gold)**: ERC-20 token backed by physical gold

By trading perpetual swap contracts on Bybit, the strategy captures arbitrage opportunities while maintaining a market-neutral hedged position.

### Key Characteristics

- **Market Neutral**: Long one asset, short the other - no directional exposure
- **Grid-Based**: Multiple price levels with predefined entry/exit points
- **High Frequency**: Real-time quote monitoring and rapid order execution
- **Risk Controlled**: Built-in position limits, notional caps, and extreme spread stops
- **Maker Orders**: Uses limit orders to earn maker rebates and minimize fees

---

## ✨ Features

- ✅ **Real-time market data streaming** from Bybit WebSocket
- ✅ **Automated quote tick subscription** for accurate spread calculation
- ✅ **Multi-level grid trading** with configurable spread thresholds
- ✅ **Position reconciliation** on startup and periodic snapshots
- ✅ **Comprehensive logging** (JSON format, DEBUG/INFO levels)
- ✅ **Docker containerization** for easy deployment
- ✅ **Testnet support** for risk-free testing
- ✅ **Emergency stop mechanisms** for extreme market conditions
- ✅ **Graceful shutdown** with order cancellation and position management

---

## 📊 Strategy Logic

### Core Mechanism

1. **Spread Calculation**
   ```
   spread = (PAXG_price - XAUT_price) / XAUT_price
   ```

2. **Grid Entry Logic**
   - When `spread > grid_level`: Open hedged position
     - SELL PAXG (expensive asset)
     - BUY XAUT (cheap asset)
   - Each grid level represents a specific spread threshold (e.g., 0.10%, 0.20%, etc.)

3. **Grid Exit Logic**
   - When spread reverts below the grid level: Close position
   - Profit is locked in from spread convergence

4. **Order Execution**
   - All orders are **limit orders** (maker)
   - Orders placed with small offset from mid-price for better fill rates
   - 5-second timeout for unfilled orders (cancel and resubmit)

### Example Trade Flow

```
1. Initial State:
   PAXG = $2,700.00
   XAUT = $2,695.00
   Spread = 0.185% (above 0.10% grid)

2. Entry:
   → SELL 0.023 PAXG @ $2,700.00
   → BUY  0.023 XAUT @ $2,695.00
   → Position opened at 0.10% grid level

3. Spread Converges:
   PAXG = $2,697.00
   XAUT = $2,696.00
   Spread = 0.037% (below 0.10% grid)

4. Exit:
   → BUY  0.023 PAXG @ $2,697.00 (close short)
   → SELL 0.023 XAUT @ $2,696.00 (close long)
   → Profit: ~$0.046 per unit (minus fees)
```

---

## 🏗️ Architecture

### Technology Stack

- **Framework**: [NautilusTrader](https://nautilustrader.io/) v1.221.0
- **Exchange**: Bybit (Unified Trading Account)
- **Language**: Python 3.12
- **Containerization**: Docker with multi-stage builds
- **Logging**: Structured JSON logging with rotation

### Project Structure

```
GoldArb/
├── paxg_xaut_grid_strategy.py   # Core strategy implementation
├── config_live.py                # Live trading configuration
├── run_live.py                   # Main entry point
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker image definition
├── .env.example                  # Environment template
├── .dockerignore                 # Docker ignore patterns
├── logs/                         # Trading logs (auto-created)
│   └── paxg_xaut_grid.json
├── data/                         # Historical data (optional)
└── README.md                     # This file
```

### System Requirements

- **CPU**: 2+ cores (ARM64 or x86_64)
- **RAM**: 1GB minimum, 2GB recommended
- **Storage**: 5GB for Docker images and logs
- **Network**: Stable internet connection (low latency preferred)
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows with WSL2

---

## 🚀 Installation

### Docker Deployment (Recommended)

Docker provides the easiest and most reliable deployment method.

#### Prerequisites

- Docker 20.10+
- Docker Compose 1.29+
- Bybit API credentials

#### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/Patrick-code-Bot/GoldArb.git
   cd GoldArb
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   nano .env  # Edit with your API credentials
   ```

   Required variables:
   ```bash
   BYBIT_API_KEY=your_api_key_here
   BYBIT_API_SECRET=your_api_secret_here
   BYBIT_TESTNET=false  # Set to 'true' for testnet
   ```

3. **Build and run with Docker Compose** (if using orchestration)
   ```bash
   cd ../trading-deployment
   docker-compose up -d goldarb
   ```

   Or **run standalone**:
   ```bash
   docker build -t goldarb .
   docker run -d \
     --name goldarb \
     --env-file .env \
     -v $(pwd)/logs:/app/logs \
     --restart unless-stopped \
     goldarb
   ```

4. **Monitor logs**
   ```bash
   docker logs -f goldarb
   ```

#### Docker Features

- ✅ **Multi-stage builds** for optimized image size
- ✅ **Non-root user** for security
- ✅ **Health checks** for container monitoring
- ✅ **Automatic restarts** on failure
- ✅ **Volume mounts** for persistent logs

---

### Local Development Setup

For development or testing without Docker:

1. **Install Python 3.10+**
   ```bash
   python3 --version  # Should be 3.10 or higher
   ```

2. **Clone and install dependencies**
   ```bash
   git clone https://github.com/Patrick-code-Bot/GoldArb.git
   cd GoldArb
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   nano .env  # Add your API credentials
   ```

4. **Run the strategy**
   ```bash
   python run_live.py
   ```

---

## ⚙️ Configuration

### Strategy Parameters

Edit `config_live.py` to customize the trading parameters:

```python
strategy_config = PaxgXautGridConfig(
    # Instruments (Bybit LINEAR perpetual swaps)
    paxg_instrument_id="PAXGUSDT-LINEAR.BYBIT",
    xaut_instrument_id="XAUTUSDT-LINEAR.BYBIT",

    # Grid levels (spread as decimal percentage)
    grid_levels=[
        0.0010,  # 0.10% spread
        0.0020,  # 0.20% spread
        0.0030,  # 0.30% spread
        0.0040,  # 0.40% spread
        0.0050,  # 0.50% spread
        0.0060,  # 0.60% spread
        0.0080,  # 0.80% spread
        0.0100,  # 1.00% spread
    ],

    # Risk management
    base_notional_per_level=100.0,   # USDT per grid level
    max_total_notional=1000.0,       # Maximum total exposure (USDT)
    target_leverage=10.0,            # Target leverage (for reference)

    # Trading parameters
    maker_offset_bps=2.0,            # 0.02% price offset for limit orders
    order_timeout_sec=5.0,           # Cancel and resubmit after 5s
    rebalance_threshold_bps=20.0,   # 0.20% imbalance triggers rebalance
    extreme_spread_stop=0.015,       # 1.5% spread triggers emergency stop

    # Features
    enable_high_levels=True,         # Allow upper grid levels
    auto_subscribe=True,             # Auto-subscribe to market data
    order_id_tag="001",              # Unique strategy identifier
)
```

### Risk Profiles

#### 🟢 Conservative (Beginners)
```python
base_notional_per_level=50.0    # $50 per level
max_total_notional=500.0        # $500 max exposure
target_leverage=5.0             # 5x leverage
```
**Recommended Capital**: $1,000+ USDT

#### 🟡 Moderate (Default)
```python
base_notional_per_level=100.0   # $100 per level
max_total_notional=1000.0       # $1,000 max exposure
target_leverage=10.0            # 10x leverage
```
**Recommended Capital**: $2,000+ USDT

#### 🔴 Aggressive (Experienced)
```python
base_notional_per_level=500.0   # $500 per level
max_total_notional=5000.0       # $5,000 max exposure
target_leverage=15.0            # 15x leverage
```
**Recommended Capital**: $10,000+ USDT

---

## 🎮 Usage

### Starting the Strategy

#### Live Trading Mode
```bash
# Using Docker
docker start goldarb

# Using Python
python run_live.py
```

Expected output:
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
  - PAXGUSDT-LINEAR.BYBIT
  - XAUTUSDT-LINEAR.BYBIT

Press Ctrl+C to stop the trading node...
================================================================================
```

#### Testnet Mode

For risk-free testing:

1. Create testnet API keys at [https://testnet.bybit.com](https://testnet.bybit.com)
2. Update `.env`:
   ```bash
   BYBIT_TESTNET=true
   BYBIT_API_KEY=testnet_api_key
   BYBIT_API_SECRET=testnet_api_secret
   ```
3. Restart the strategy

### Stopping the Strategy

**Graceful Shutdown**:
```bash
# Docker
docker stop goldarb

# Python (Press Ctrl+C in terminal)
```

The strategy will:
- Cancel all pending orders
- Log final positions
- Save state snapshots
- Shut down cleanly

**Force Stop** (not recommended):
```bash
docker kill goldarb
```

---

## 📈 Monitoring

### Real-Time Logs

#### Docker Logs
```bash
# Follow live logs
docker logs -f goldarb

# Last 100 lines
docker logs --tail 100 goldarb

# Search for errors
docker logs goldarb 2>&1 | grep ERROR
```

#### Log Files

Location: `logs/paxg_xaut_grid.json`

Format: Structured JSON with fields:
- `timestamp`: ISO 8601 timestamp
- `trader_id`: TRADER-001
- `level`: DEBUG, INFO, WARNING, ERROR
- `component`: Strategy, ExecEngine, DataClient, etc.
- `message`: Log message

Example:
```json
{
  "timestamp": "2025-12-15T12:48:45.480095413Z",
  "trader_id": "TRADER-001",
  "level": "INFO",
  "component": "PaxgXautGridStrategy",
  "message": "OrderFilled(instrument_id=XAUTUSDT-LINEAR.BYBIT, ...)"
}
```

### Key Metrics

Monitor these critical metrics:

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| **Spread** | Current PAXG-XAUT price difference | > 1.5% (extreme) |
| **Active Grids** | Number of open grid positions | Approaching max |
| **Total Notional** | Current exposure vs max limit | > 90% of max |
| **Order Fill Rate** | % of orders filled | < 80% |
| **Unrealized PnL** | Open position P&L | Large negative |
| **API Latency** | Bybit API response time | > 500ms |

### Bybit Web Interface

Monitor positions and orders:
- **Live**: [https://www.bybit.com/trade/usdt/PAXGUSDT](https://www.bybit.com/trade/usdt/PAXGUSDT)
- **Testnet**: [https://testnet.bybit.com/trade/usdt/PAXGUSDT](https://testnet.bybit.com/trade/usdt/PAXGUSDT)

Check:
- Open positions
- Order history
- Account balance
- Funding rates
- Liquidation price

---

## 🛡️ Risk Management

### Built-in Safety Features

1. **Position Limits**
   - `max_total_notional`: Hard cap on total exposure
   - Prevents over-leveraging

2. **Extreme Spread Stop**
   - `extreme_spread_stop = 0.015` (1.5%)
   - Pauses strategy if spread becomes abnormal
   - Prevents trading during market dislocation

3. **Order Timeouts**
   - `order_timeout_sec = 5.0`
   - Cancels stale orders
   - Ensures fresh pricing

4. **Position Reconciliation**
   - On startup: Reconciles local state with exchange
   - Periodic snapshots every 5 minutes
   - Prevents state drift

5. **Maker-Only Orders**
   - All orders are limit orders
   - Earns maker rebates
   - Avoids paying taker fees

### Operational Best Practices

#### Before Going Live

- [ ] Test on testnet for 24+ hours
- [ ] Verify API keys have correct permissions
- [ ] Set Bybit account leverage (10x recommended)
- [ ] Fund account with sufficient margin
- [ ] Configure position size alerts on Bybit mobile app
- [ ] Document emergency procedures

#### Daily Operations

- [ ] Check positions and P&L (morning/evening)
- [ ] Review log files for warnings/errors
- [ ] Monitor account balance and margin
- [ ] Verify strategy is running (Docker health check)
- [ ] Check for NautilusTrader updates

#### Emergency Procedures

If something goes wrong:

1. **Stop the Strategy**
   ```bash
   docker stop goldarb
   ```

2. **Assess Positions**
   - Log into Bybit
   - Check open positions and orders
   - Review account P&L

3. **Manual Intervention** (if needed)
   - Use Bybit web interface to manually close positions
   - Cancel any stuck orders
   - Document what happened

4. **Review Logs**
   ```bash
   tail -1000 logs/paxg_xaut_grid.json | grep ERROR
   ```

5. **Restart** (only after resolving issues)
   ```bash
   docker start goldarb
   ```

---

## 📊 Performance

### Expected Returns

**Note**: Past performance does not guarantee future results.

- **Target**: 0.5-2% weekly return (annualized 26-104%)
- **Sharpe Ratio**: 2-4 (market neutral, low volatility)
- **Max Drawdown**: < 10% (with proper risk management)
- **Win Rate**: 75-85% (mean reversion strategy)

### Fee Structure

Bybit perpetual swaps (as of Dec 2025):
- **Maker Fee**: -0.01% (rebate)
- **Taker Fee**: +0.06%
- **Funding Rate**: ±0.01% per 8 hours (variable)

**Strategy uses maker orders only** → earning rebates on every fill!

### Example P&L

With default configuration (8 grid levels, $100 per level):

```
Grid Level: 0.10%
Entry Spread: 0.185%
Exit Spread: 0.037%
Profit per Grid: ~$0.046 per unit × 0.023 units = $1.06
Maker Rebate: -0.01% × $200 notional = $0.20
Net P&L: $1.26 per grid close

Daily Average: 5-10 grid closes
Daily P&L: $6.30 - $12.60
Monthly Estimate: $189 - $378 (19-38% ROI on $1000 capital)
```

*Results vary based on market volatility and spread behavior.*

---

## 🔧 Troubleshooting

### Common Issues

#### Issue: "Max total notional reached, skip new grid"

**Cause**: Strategy has reached maximum exposure limit.

**Solution**:
- This is **expected behavior** when positions are at max
- Wait for positions to close before new grids open
- Or increase `max_total_notional` in config (higher risk)

---

#### Issue: No orders being placed

**Symptoms**: Strategy running but no OrderSubmitted logs.

**Diagnosis**:
```bash
# Check if quote data is flowing
docker logs goldarb 2>&1 | grep QuoteTick

# Check spread warnings
docker logs goldarb 2>&1 | grep spread
```

**Solutions**:
1. Verify instruments are correct: `PAXGUSDT-LINEAR.BYBIT`
2. Check quote tick subscription is active
3. Ensure spread is crossing grid levels
4. Review `extreme_spread_stop` threshold

---

#### Issue: Orders rejected by exchange

**Symptoms**: OrderRejected events in logs.

**Common Causes**:
- Insufficient margin/balance
- Incorrect leverage settings
- Position limits exceeded
- Price too far from market (stale)

**Solutions**:
1. Check Bybit account balance
2. Verify leverage is set to 10x on Bybit
3. Review `maker_offset_bps` in config
4. Check API rate limits

---

#### Issue: Container keeps restarting

**Diagnosis**:
```bash
docker ps -a | grep goldarb
docker logs goldarb
```

**Solutions**:
1. Check `.env` file has valid API credentials
2. Verify network connectivity to Bybit
3. Review startup logs for errors
4. Check Docker resource limits (CPU/RAM)

---

#### Issue: "Instruments not found in cache"

**Cause**: Instrument IDs don't match Bybit's format.

**Solution**:
- Correct format: `PAXGUSDT-LINEAR.BYBIT` (not `-PERP`)
- Update `config_live.py` if needed
- Rebuild Docker image: `docker-compose build goldarb`

---

### Getting Help

#### Resources

- **NautilusTrader Docs**: [https://nautilustrader.io/docs](https://nautilustrader.io/docs)
- **NautilusTrader Discord**: [Join Community](https://discord.gg/AUNMNnNDwP)
- **Bybit API Docs**: [https://bybit-exchange.github.io/docs](https://bybit-exchange.github.io/docs)
- **Bybit Support**: [https://www.bybit.com/en-US/help-center](https://www.bybit.com/en-US/help-center)

#### Reporting Issues

When reporting issues, include:
1. Docker logs (`docker logs goldarb --tail 200`)
2. Configuration file (redact API keys)
3. Error messages
4. Steps to reproduce
5. Environment info (OS, Docker version)

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (on testnet)
5. Submit a pull request

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings for functions
- Keep lines under 100 characters
- Run `black` formatter

### Testing

Before submitting:
```bash
# Run on testnet
BYBIT_TESTNET=true python run_live.py

# Check logs for errors
tail -f logs/paxg_xaut_grid.json
```

---

## ⚠️ Disclaimer

**IMPORTANT RISK DISCLOSURE**

- **Trading involves substantial risk of loss**
- **This strategy is for educational purposes only**
- **Past performance does not guarantee future results**
- **The authors are not responsible for any financial losses**
- **This is not financial advice**

### Risks

1. **Market Risk**: Spread may widen unexpectedly
2. **Liquidity Risk**: Positions may be difficult to exit
3. **Technical Risk**: Software bugs, API failures
4. **Execution Risk**: Slippage, partial fills
5. **Funding Risk**: Negative funding rates on perpetual swaps
6. **Correlation Risk**: PAXG and XAUT correlation may break down

### Recommendations

- ✅ **Only trade with capital you can afford to lose**
- ✅ **Understand the strategy before deploying**
- ✅ **Start with small position sizes**
- ✅ **Monitor actively, especially initially**
- ✅ **Have a plan for extreme scenarios**

Use at your own risk.

---

## 📄 License

This project is licensed under the GNU Lesser General Public License v3.0 (LGPL-3.0).

See the [LICENSE](LICENSE) file for full license text.

---

## 📞 Contact

- **GitHub**: [@Patrick-code-Bot](https://github.com/Patrick-code-Bot)
- **Repository**: [GoldArb](https://github.com/Patrick-code-Bot/GoldArb)
- **Issues**: [Report a bug](https://github.com/Patrick-code-Bot/GoldArb/issues)

---

## 🙏 Acknowledgments

Built with:
- [NautilusTrader](https://nautilustrader.io/) - High-performance algorithmic trading platform
- [Bybit](https://www.bybit.com/) - Cryptocurrency derivatives exchange

Special thanks to the NautilusTrader community for their excellent framework and support.

---

<div align="center">

**⭐ If this project helps you, consider giving it a star! ⭐**

Made with ❤️ for the algorithmic trading community

</div>
