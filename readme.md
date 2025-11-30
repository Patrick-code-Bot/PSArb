# PAXG–XAUT Grid Spread Arbitrage (Bybit / NautilusTrader)

## 1. 策略概述

本策略在 **同一 CEX（Bybit）** 上，对两个黄金锚定永续合约：

- `PAXGUSDT-PERP`
- `XAUTUSDT-PERP`

进行 **价差网格套利（spread grid arbitrage）**。

核心逻辑：

- 实时计算两者的中间价：
  - `paxg_mid = (paxg_bid + paxg_ask) / 2`
  - `xaut_mid = (xaut_bid + xaut_ask) / 2`
- 计算价差：
  - `spread = (paxg_mid - xaut_mid) / xaut_mid`
- 使用一组固定网格档位，例如：
  - `[0.10%, 0.20%, 0.30%, 0.40%, 0.50%, 0.60%, 0.80%, 1.00%]`
- 当 `|spread|` 超过某一档时：
  - 贵的一腿做空，便宜的一腿做多（对冲开仓）  
  - 例如 `spread > 0` → PAXG 贵 → 空 PAXG，多 XAUT
- 当 `|spread|` 回落到上一档以下时：
  - 平掉对应档位的双腿仓位，锁定价差回归收益
- 所有订单尽量使用 **maker 限价挂单**，降低手续费。

该策略是 **非方向性 / 市场中性**，覆盖的是 **PAXG 与 XAUT 的价差回归收益**，适合在整体黄金长期趋势不确定的条件下持续运行。

---

## 2. 杠杆与资金配置

策略配置中有两个关键参数：

- `base_notional_per_level`: 单档网格名义价值（USDT），例如 `2_000`
- `max_total_notional`: 所有网格档位合计的最大名义价值，例如 `40_000`

Bybit 账户端建议：

- 保证金模式：逐仓 / 组合保证金均可，根据个人偏好决定
- 杠杆建议：**约 10x**（在 Bybit 界面或 API 中设置）
- `max_total_notional` 建议不超过：  
  `账户实际权益 × 5 ~ 8`（留足保证金缓冲），例如：
  - 账户权益 = 10,000 USDT
  - 目标 10x 杠杆 → 名义可以 100,000  
  - 实务中为了安全，可将 `max_total_notional` 设为 50,000–80,000

策略自身 **不会**直接控制 Bybit 杠杆倍数，只通过 **名义值上限 + 网格规模** 来间接控制风险。

---

## 3. 网格设计

默认网格档位：

```python
grid_levels = [0.0010, 0.0020, 0.0030,
               0.0040, 0.0050, 0.0060,
               0.0080, 0.0100]   # 即 0.10% ~ 1.00%