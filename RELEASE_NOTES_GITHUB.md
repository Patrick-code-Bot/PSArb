# 🎉 PAXG-XAUT Grid Strategy v1.0.0

> **First Stable Release** - Market-neutral spread arbitrage for Bybit perpetual swaps

## Overview

Automated grid-based spread arbitrage strategy between PAXG (Pax Gold) and XAUT (Tether Gold) perpetual contracts on Bybit, built with NautilusTrader framework.

## ✨ Features

### Core Strategy
- ✅ **Market-Neutral Design** - Hedged positions minimize directional risk
- ✅ **Grid-Based Trading** - 8 configurable spread levels (0.10% - 1.00%)
- ✅ **Automated Execution** - Fully autonomous trading
- ✅ **Maker Orders** - Post-only limits for optimal fees
- ✅ **Real-Time Monitoring** - Continuous spread tracking

### Risk Management
- ✅ **Position Limits** - Max $40K notional (configurable)
- ✅ **Extreme Spread Stop** - Auto-close at 1.5%
- ✅ **Auto-Rebalancing** - Maintains hedge ratio
- ✅ **Position Reconciliation** - Syncs with exchange
- ✅ **Comprehensive Logging** - JSON structured logs

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/Patrick-code-Bot/PSArb.git
cd PSArb

# Quick setup
./setup.sh

# Configure credentials
cp .env.example .env
# Edit .env with your Bybit API keys

# Run live trading
python run_live.py
```

## 📋 Requirements

- Python 3.10+
- NautilusTrader 1.200.0+
- Bybit account with API access
- Minimum $10,000 USDT recommended

## 📦 Installation

```bash
pip install -r requirements.txt
```

## ⚙️ Default Configuration

```python
Grid Levels: [0.10%, 0.20%, 0.30%, 0.40%, 0.50%, 0.60%, 0.80%, 1.00%]
Notional per Level: $2,000 USDT
Max Total Notional: $40,000 USDT
Target Leverage: 10x
Spread Stop: 1.5%
```

## 📊 Strategy Logic

**Spread Calculation:**
```
spread = (PAXG_mid - XAUT_mid) / XAUT_mid
```

**Grid Opening:**
- `spread > level`: Short PAXG + Long XAUT
- `spread < -level`: Long PAXG + Short XAUT

**Grid Closing:**
- `|spread| < previous_level`: Close and realize profit

## 🧪 Testing First!

**Recommended workflow:**
1. Test on Bybit testnet (24+ hours)
2. Start with 10-20% of target size
3. Monitor closely for 24-48 hours
4. Scale up gradually

```bash
# Enable testnet in .env
BYBIT_TESTNET=true
```

## 📚 Documentation

- **[README.md](README.md)** - Complete setup guide
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical details
- **[RELEASE_NOTES_v1.0.0.md](RELEASE_NOTES_v1.0.0.md)** - Full release notes

## 🛡️ Safety Features

1. Max notional cap
2. Extreme spread protection
3. Position reconciliation
4. Graceful shutdown
5. Order rejection handling

## ⚠️ Risk Warning

**Trading cryptocurrencies involves substantial risk of loss.**

- Only trade with funds you can afford to lose
- This is NOT financial advice
- Authors are not responsible for losses
- Use at your own risk

## 🔧 Support

- **Issues**: [GitHub Issues](https://github.com/Patrick-code-Bot/PSArb/issues)
- **NautilusTrader**: [Documentation](https://nautilustrader.io/docs)
- **Community**: [Discord](https://discord.gg/AUNMNnNDwP)

## 📈 What's Next?

**Planned for v1.1.0:**
- Dynamic position sizing
- Advanced rebalancing
- Telegram notifications
- Enhanced metrics

## 🙏 Built With

- [NautilusTrader](https://nautilustrader.io) - Trading framework
- [Bybit](https://www.bybit.com) - Exchange
- [Claude Code](https://claude.com/claude-code) - AI development

---

**Happy Trading! 🚀** Remember to start small and test thoroughly.

*Generated with Claude Code | December 2024*
