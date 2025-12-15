"""
PAXG-XAUT Grid Spread Arbitrage Strategy (NautilusTrader, Bybit single-venue)

逻辑概要：
- 在 Bybit 上订阅 PAXG/USDT-LINEAR 与 XAUT/USDT-LINEAR 两个合约
- 实时计算价差 spread = (PAXG - XAUT) / XAUT
- 使用预设的网格 levels（例如 [0.001, 0.002, ...]）
- 当 spread 超过某一档 level：高卖贵的、低买便宜的（成对开仓）
- 当 spread 回落到上一个 level 以下：平掉该档位的对冲仓位
- 所有下单尽量用挂单（maker），以降低手续费
- 杠杆建议在 Bybit 侧设置为约 10x，本策略通过 max_total_notional 控制整体风险敞口
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple, Any

from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.orders import LimitOrder


# ==========================
# 配置 Config
# ==========================

class PaxgXautGridConfig(StrategyConfig, frozen=True):
    # 交易标的（请用你实际环境里的 InstrumentId 字符串）
    # 例如："PAXGUSDT-LINEAR.BYBIT" 和 "XAUTUSDT-LINEAR.BYBIT"
    paxg_instrument_id: str = "PAXGUSDT-LINEAR.BYBIT"
    xaut_instrument_id: str = "XAUTUSDT-LINEAR.BYBIT"

    # 网格档位（价差：相对 XAUT 的百分比）
    # 例如 0.001 = 0.10%，0.01 = 1%
    grid_levels: List[float] = field(
        default_factory=lambda: [0.0010, 0.0020, 0.0030, 0.0040,
                                 0.0050, 0.0060, 0.0080, 0.0100]
    )

    # 每档网格对应的名义价值（USDT），真实下单数量 = notional / price
    base_notional_per_level: float = 100.0

    # 最大总名义风险（两条腿合计）
    # 如果你打算 10x 杠杆，可以设置为：账户权益的 5~8 倍（视风险偏好）
    max_total_notional: float = 1000.0

    # 目标杠杆（仅用于日志与风险思路说明；实际杠杆通过 Bybit 账户/仓位配置控制）
    target_leverage: float = 10.0

    # 是否启用“增强区”（更高档位）——你可以以后接参数调整风险
    enable_high_levels: bool = True

    # maker 挂单相对中间价偏移（bps = 万分之一）
    maker_offset_bps: float = 2.0  # 0.02%

    # 挂单超时秒数（没成交就撤单重挂）
    order_timeout_sec: float = 5.0

    # rebalance 阈值：两腿名义不平衡多少 bps 时，自动微调
    rebalance_threshold_bps: float = 20.0  # 0.20%

    # 极端价差风控：超过该值（例如 1.5%）全平并暂停策略
    extreme_spread_stop: float = 0.015  # 1.5%

    # 是否在启动时自动订阅行情
    auto_subscribe: bool = True


# ==========================
# 内部数据结构
# ==========================

@dataclass
class GridPositionState:
    level: float
    paxg_pos_id: Optional[Any] = None  # PositionId type
    xaut_pos_id: Optional[Any] = None  # PositionId type
    # 可以扩展记录：建仓价、建仓时间等


# ==========================
# 策略主体
# ==========================

class PaxgXautGridStrategy(Strategy):
    def __init__(self, config: PaxgXautGridConfig) -> None:
        super().__init__(config)

        # Instruments
        self.paxg_id = InstrumentId.from_str(config.paxg_instrument_id)
        self.xaut_id = InstrumentId.from_str(config.xaut_instrument_id)

        self.paxg = None
        self.xaut = None

        # 最新报价
        self.paxg_bid: Optional[float] = None
        self.paxg_ask: Optional[float] = None
        self.xaut_bid: Optional[float] = None
        self.xaut_ask: Optional[float] = None

        # 网格状态：level -> GridPositionState
        self.grid_state: Dict[float, GridPositionState] = {}

        # 在途订单追踪：order_id -> (level, leg)
        # leg: "PAXG_LONG", "PAXG_SHORT", "XAUT_LONG", "XAUT_SHORT"
        self.working_orders: Dict[Any, tuple[float, str]] = {}  # OrderId type

        # 累计名义风险
        self.total_notional: float = 0.0

    # ========== 生命周期 ==========
    def on_start(self) -> None:
        self.log.info(
            f"PaxgXautGridStrategy starting on Bybit, target_leverage={self.config.target_leverage}x, "
            f"max_total_notional={self.config.max_total_notional}."
        )

        # 获取 instrument
        self.paxg = self.cache.instrument(self.paxg_id)
        self.xaut = self.cache.instrument(self.xaut_id)

        if self.paxg is None or self.xaut is None:
            raise RuntimeError(
                f"Instruments not found in cache. Check instruments config: "
                f"paxg={self.paxg_id}, xaut={self.xaut_id}"
            )

        # 初始化网格状态
        for level in self.config.grid_levels:
            self.grid_state[level] = GridPositionState(level=level)

        if self.config.auto_subscribe:
            self.subscribe_instrument(self.paxg_id)
            self.subscribe_instrument(self.xaut_id)

        self.log.info(
            f"Subscribed PAXG={self.paxg_id} XAUT={self.xaut_id}, "
            f"grid_levels={self.config.grid_levels}"
        )

    def on_stop(self) -> None:
        self.log.info("PaxgXautGridStrategy stopping, cancelling working orders and closing positions...")
        # 撤销所有挂单
        for order_id in list(self.working_orders.keys()):
            self.cancel_order(order_id)
        # 可以按需选择是否强平所有持仓
        # self.flatten_all()

    # ========== 行情处理 ==========
    def on_quote_tick(self, tick: QuoteTick) -> None:
        # 更新最新报价
        if tick.instrument_id == self.paxg_id:
            self.paxg_bid = float(tick.bid_price)
            self.paxg_ask = float(tick.ask_price)
        elif tick.instrument_id == self.xaut_id:
            self.xaut_bid = float(tick.bid_price)
            self.xaut_ask = float(tick.ask_price)

        if not self._has_valid_quotes():
            return

        spread = self._calc_spread()
        if spread is None:
            return

        # 极端风控
        if abs(spread) > self.config.extreme_spread_stop:
            self.log.warning(f"Extreme spread detected {spread:.4%}, closing all and pausing.")
            self._close_all_grids()
            # 这里可以选择 disable 策略 / raise 等
            return

        # 网格开仓 / 平仓逻辑
        self._process_grids(spread)

        # 持仓 rebalance
        self._rebalance_if_needed()

        # 检查挂单是否超时（可根据你需求补充完整实现）
        self._check_order_timeouts()

    # ========== 订单回报 ==========
    def on_order_accepted(self, event) -> None:
        self.log.debug(f"Order accepted: {event.client_order_id}")

    def on_order_rejected(self, event) -> None:
        self.log.warning(f"Order rejected: {event.client_order_id}, reason: {event.reason}")
        self.working_orders.pop(event.client_order_id, None)

    def on_order_canceled(self, event) -> None:
        self.log.debug(f"Order canceled: {event.client_order_id}")
        self.working_orders.pop(event.client_order_id, None)

    def on_order_filled(self, event) -> None:
        self.log.info(f"Order filled: {event.client_order_id}")
        level, leg = self.working_orders.pop(event.client_order_id, (None, None))

        if level is None:
            return

        # 更新持仓状态
        pos = self.cache.position_for_order(event.client_order_id)
        state = self.grid_state.get(level)

        if state is None:
            return

        if leg == "PAXG_LONG":
            state.paxg_pos_id = pos.id if pos is not None else None
        elif leg == "PAXG_SHORT":
            state.paxg_pos_id = pos.id if pos is not None else None
        elif leg == "XAUT_LONG":
            state.xaut_pos_id = pos.id if pos is not None else None
        elif leg == "XAUT_SHORT":
            state.xaut_pos_id = pos.id if pos is not None else None

    # ========== 网格逻辑 ==========
    def _process_grids(self, spread: float) -> None:
        """
        spread = (PAXG - XAUT) / XAUT
        > 0 : PAXG 贵，做空 PAXG & 做多 XAUT
        < 0 : XAUT 贵，做空 XAUT & 做多 PAXG
        """
        abs_spread = abs(spread)

        # 1) 先处理“平仓条件”：spread 回到前一档以内 -> 平该档位
        levels_sorted = sorted(self.config.grid_levels)
        for i, level in enumerate(levels_sorted):
            state = self.grid_state[level]
            if not self._grid_has_position(state):
                continue

            prev_level = 0.0 if i == 0 else levels_sorted[i - 1]
            if abs_spread < prev_level:
                self.log.info(f"Closing grid level={level}, spread={spread:.4%}")
                self._close_grid(level, state)

        # 2) 再处理“开仓条件”：spread 超过某档且该档没有持仓 -> 开新对冲
        for i, level in enumerate(levels_sorted):
            state = self.grid_state[level]
            if self._grid_has_position(state):
                continue

            if abs_spread > level:
                # 检查总风险
                notional = self.config.base_notional_per_level
                if self.total_notional + 2 * notional > self.config.max_total_notional:
                    self.log.warning("Max total notional reached, skip new grid.")
                    continue

                self.log.info(f"Opening grid level={level}, spread={spread:.4%}")
                self._open_grid(level, spread)

    def _grid_has_position(self, state: GridPositionState) -> bool:
        return (state.paxg_pos_id is not None) or (state.xaut_pos_id is not None)

    # ========== Grid 开仓 / 平仓 ==========
    def _open_grid(self, level: float, spread: float) -> None:
        """
        spread > 0: PAXG 贵 → 空 PAXG，多 XAUT
        spread < 0: XAUT 贵 → 空 XAUT，多 PAXG
        """
        paxg_price = self._mid_price(self.paxg_bid, self.paxg_ask)
        xaut_price = self._mid_price(self.xaut_bid, self.xaut_ask)

        if paxg_price is None or xaut_price is None:
            return

        notional = self.config.base_notional_per_level

        paxg_qty = notional / paxg_price
        xaut_qty = notional / xaut_price

        if spread > 0:
            # 空 PAXG，多 XAUT
            paxg_side = OrderSide.SELL
            xaut_side = OrderSide.BUY
            paxg_leg_tag = "PAXG_SHORT"
            xaut_leg_tag = "XAUT_LONG"
        else:
            # 空 XAUT，多 PAXG
            paxg_side = OrderSide.BUY
            xaut_side = OrderSide.SELL
            paxg_leg_tag = "PAXG_LONG"
            xaut_leg_tag = "XAUT_SHORT"

        # maker price = mid ± offset
        paxg_price_limit = self._maker_price(self.paxg_bid, self.paxg_ask, paxg_side)
        xaut_price_limit = self._maker_price(self.xaut_bid, self.xaut_ask, xaut_side)

        # 创建订单
        paxg_order = self.order_factory.limit(
            instrument_id=self.paxg_id,
            order_side=paxg_side,
            quantity=self.paxg.make_qty(paxg_qty),
            price=self.paxg.make_price(paxg_price_limit),
            time_in_force=TimeInForce.GTC,
        )

        xaut_order = self.order_factory.limit(
            instrument_id=self.xaut_id,
            order_side=xaut_side,
            quantity=self.xaut.make_qty(xaut_qty),
            price=self.xaut.make_price(xaut_price_limit),
            time_in_force=TimeInForce.GTC,
        )

        # 提交订单
        self.submit_order(paxg_order)
        self.submit_order(xaut_order)

        # 记录在途订单
        self.working_orders[paxg_order.client_order_id] = (level, paxg_leg_tag)
        self.working_orders[xaut_order.client_order_id] = (level, xaut_leg_tag)

        # 更新总名义风险（两腿）
        self.total_notional += 2 * notional

    def _close_grid(self, level: float, state: GridPositionState) -> None:
        # 平掉这一档的两条腿
        if state.paxg_pos_id is not None:
            self._close_position(state.paxg_pos_id)
            state.paxg_pos_id = None

        if state.xaut_pos_id is not None:
            self._close_position(state.xaut_pos_id)
            state.xaut_pos_id = None

        self.total_notional = max(0.0, self.total_notional - 2 * self.config.base_notional_per_level)

    def _close_all_grids(self) -> None:
        for level, state in self.grid_state.items():
            self._close_grid(level, state)

    def _close_position(self, pos_id: Any) -> None:  # PositionId type
        pos = self.cache.position(pos_id)
        if pos is None:
            return

        inst = pos.instrument_id
        instrument = self.cache.instrument(inst)
        if instrument is None:
            return

        side = OrderSide.SELL if pos.is_long else OrderSide.BUY
        qty = pos.quantity

        bid, ask = self._get_bid_ask(inst)
        price = self._maker_price(bid, ask, side)

        close_order = self.order_factory.limit(
            instrument_id=inst,
            order_side=side,
            quantity=instrument.make_qty(float(qty)),
            price=instrument.make_price(price),
            time_in_force=TimeInForce.GTC,
        )
        self.submit_order(close_order)

    # ========== Rebalance ==========
    def _rebalance_if_needed(self) -> None:
        """
        这里可以做一个简单的 rebalance：
        - 计算当前所有 PAXG 名义 vs XAUT 名义
        - 差值超过 threshold 时，通过微小挂单校正
        """
        paxg_notional = 0.0
        xaut_notional = 0.0

        for pos in self.cache.positions():
            if pos.instrument_id == self.paxg_id:
                paxg_notional += pos.quantity * self._mid_price(self.paxg_bid, self.paxg_ask)
            elif pos.instrument_id == self.xaut_id:
                xaut_notional += pos.quantity * self._mid_price(self.xaut_bid, self.xaut_ask)

        if paxg_notional == 0 and xaut_notional == 0:
            return

        delta = paxg_notional - xaut_notional
        base = max(abs(paxg_notional), abs(xaut_notional), 1.0)

        imbalance = abs(delta) / base
        if imbalance < self.config.rebalance_threshold_bps / 10_000.0:
            return

        self.log.info(
            f"Rebalancing, paxg_notional={paxg_notional:.2f}, "
            f"xaut_notional={xaut_notional:.2f}, imbalance={imbalance:.4%}"
        )

        # 简单方式：用市价或近似 limit 做一个微小反向单
        # 后续可以根据实际需求做精细实现
        pass

    # ========== 行情辅助函数 ==========
    def _has_valid_quotes(self) -> bool:
        return all([
            self.paxg_bid is not None,
            self.paxg_ask is not None,
            self.xaut_bid is not None,
            self.xaut_ask is not None,
        ])

    def _calc_spread(self) -> Optional[float]:
        # 用中间价来算
        paxg_mid = self._mid_price(self.paxg_bid, self.paxg_ask)
        xaut_mid = self._mid_price(self.xaut_bid, self.xaut_ask)
        if paxg_mid is None or xaut_mid is None:
            return None
        return (paxg_mid - xaut_mid) / xaut_mid

    @staticmethod
    def _mid_price(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2.0

    def _maker_price(self, bid: float, ask: float, side: OrderSide) -> float:
        """
        maker_offset_bps > 0:
        - 买单：略低于 ask
        - 卖单：略高于 bid
        """
        mid = (bid + ask) / 2.0
        offset = self.config.maker_offset_bps / 10_000.0 * mid

        if side == OrderSide.BUY:
            return min(ask, mid - offset)
        else:
            return max(bid, mid + offset)

    def _get_bid_ask(self, inst: InstrumentId) -> Tuple[Optional[float], Optional[float]]:
        if inst == self.paxg_id:
            return self.paxg_bid, self.paxg_ask
        else:
            return self.xaut_bid, self.xaut_ask

    # ========== 挂单超时检查 ==========
    def _check_order_timeouts(self) -> None:
        """
        如果你在 Nautilus 有现成的 “GoodTillTime / IOC” 机制，
        可以直接用 TIF 替代手动超时逻辑。
        这里给一个骨架：你可以结合 self.cache.orders / self.clock.now 去实现：
        - 为 working_orders 多记录一个 timestamp
        - 超时就 cancel_order(order_id)
        """
        pass


# ==========================
# 工厂函数（方便在 YAML/JSON 中引用）
# ==========================

def create_strategy(config: PaxgXautGridConfig) -> PaxgXautGridStrategy:
    return PaxgXautGridStrategy(config=config)