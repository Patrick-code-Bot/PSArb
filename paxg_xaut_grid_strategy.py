"""
PAXG-XAUT Grid Spread Arbitrage Strategy (NautilusTrader, Bybit single-venue)

逻辑概要：
- 在 Bybit 上订阅 PAXG/USDT-LINEAR 与 XAUT/USDT-LINEAR 两个合约
- 实时计算价差 spread = (PAXG - XAUT) / XAUT
- 使用预设的网格 levels（例如 [0.001, 0.002, ...]）
- 当 spread 超过某一档 level：高卖贵的、低买便宜的（成对开仓）
  * 开仓使用市价单（market orders）确保快速成交，建立对冲仓位
- 当 spread 回落到上一个 level 以下：平掉该档位的对冲仓位
  * 平仓使用限价单（limit orders）以更好的价格捕获利润
- 杠杆建议在 Bybit 侧设置为约 10x，本策略通过 max_total_notional 控制整体风险敞口
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple, Any

from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderSide, TimeInForce, OrderType
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.orders import LimitOrder, MarketOrder


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


@dataclass
class PairedOrderTracker:
    """Track paired PAXG+XAUT orders to detect partial fills"""
    level: float
    paxg_order_id: Any
    xaut_order_id: Any
    paxg_filled: bool = False
    xaut_filled: bool = False
    submit_time: int = 0  # timestamp in nanoseconds
    paxg_leg: str = ""  # "PAXG_LONG" or "PAXG_SHORT"
    xaut_leg: str = ""  # "XAUT_LONG" or "XAUT_SHORT"


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

        # 配对订单追踪：用于检测不平衡成交
        # Key: 使用唯一标识符 (submit_time + level) 来追踪每对订单
        self.paired_orders: Dict[int, PairedOrderTracker] = {}

        # 累计名义风险（仅计算实际成交的持仓）
        self.total_notional: float = 0.0
        # 待确认名义风险（已提交但未成交的订单）
        self.pending_notional: float = 0.0

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
            # Subscribe to quote ticks for both instruments
            self.subscribe_quote_ticks(instrument_id=self.paxg_id)
            self.subscribe_quote_ticks(instrument_id=self.xaut_id)
            self.log.info(
                f"Subscribed to quote ticks: PAXG={self.paxg_id}, XAUT={self.xaut_id}"
            )

        self.log.info(
            f"Strategy initialized with grid_levels={self.config.grid_levels}"
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

        # 检查是否是配对订单中的一个被拒绝
        # 如果是，需要检查另一侧是否已成交，如果成交了需要平仓
        self._handle_order_failure(event.client_order_id, "rejected")

    def on_order_canceled(self, event) -> None:
        self.log.debug(f"Order canceled: {event.client_order_id}")
        self.working_orders.pop(event.client_order_id, None)

    def _handle_order_failure(self, order_id: Any, reason: str) -> None:
        """处理订单失败（拒绝/超时）时的配对订单清理"""
        notional = self.config.base_notional_per_level

        for submit_time, tracker in list(self.paired_orders.items()):
            if tracker.paxg_order_id == order_id:
                self.log.warning(f"PAXG order {reason} for level={tracker.level}")
                # 如果 XAUT 已经成交，需要平掉
                if tracker.xaut_filled:
                    self.log.warning(f"XAUT already filled, closing XAUT position for level={tracker.level}")
                    state = self.grid_state.get(tracker.level)
                    if state and state.xaut_pos_id:
                        self._close_position(state.xaut_pos_id)
                        state.xaut_pos_id = None
                else:
                    # XAUT 还没成交，取消它
                    self._safe_cancel_order(tracker.xaut_order_id)
                # 清理pending_notional
                self.pending_notional = max(0.0, self.pending_notional - 2 * notional)
                self.log.info(f"Order failure cleanup, pending_notional={self.pending_notional:.2f}")
                del self.paired_orders[submit_time]
                break
            elif tracker.xaut_order_id == order_id:
                self.log.warning(f"XAUT order {reason} for level={tracker.level}")
                # 如果 PAXG 已经成交，需要平掉
                if tracker.paxg_filled:
                    self.log.warning(f"PAXG already filled, closing PAXG position for level={tracker.level}")
                    state = self.grid_state.get(tracker.level)
                    if state and state.paxg_pos_id:
                        self._close_position(state.paxg_pos_id)
                        state.paxg_pos_id = None
                else:
                    # PAXG 还没成交，取消它
                    self._safe_cancel_order(tracker.paxg_order_id)
                # 清理pending_notional
                self.pending_notional = max(0.0, self.pending_notional - 2 * notional)
                self.log.info(f"Order failure cleanup, pending_notional={self.pending_notional:.2f}")
                del self.paired_orders[submit_time]
                break

    def on_order_filled(self, event) -> None:
        self.log.info(f"Order filled: {event.client_order_id}")
        level, leg = self.working_orders.pop(event.client_order_id, (None, None))

        if level is None:
            return

        # 更新配对订单追踪器，检查是否两边都成交了
        both_filled = False
        tracker_submit_time = None  # Track which tracker to potentially remove
        notional = self.config.base_notional_per_level

        for submit_time, tracker in self.paired_orders.items():
            if tracker.paxg_order_id == event.client_order_id:
                tracker.paxg_filled = True
                tracker_submit_time = submit_time
                self.log.debug(f"PAXG order filled for level={tracker.level}")
                # 检查是否两边都成交
                if tracker.xaut_filled:
                    both_filled = True
                    # 从待确认转移到已确认
                    self.pending_notional = max(0.0, self.pending_notional - 2 * notional)
                    self.total_notional += 2 * notional
                    self.log.info(
                        f"Both orders filled for level={tracker.level}, "
                        f"moved {2*notional:.2f} from pending to total. "
                        f"Total={self.total_notional:.2f}, Pending={self.pending_notional:.2f}"
                    )
                break
            elif tracker.xaut_order_id == event.client_order_id:
                tracker.xaut_filled = True
                tracker_submit_time = submit_time
                self.log.debug(f"XAUT order filled for level={tracker.level}")
                # 检查是否两边都成交
                if tracker.paxg_filled:
                    both_filled = True
                    # 从待确认转移到已确认
                    self.pending_notional = max(0.0, self.pending_notional - 2 * notional)
                    self.total_notional += 2 * notional
                    self.log.info(
                        f"Both orders filled for level={tracker.level}, "
                        f"moved {2*notional:.2f} from pending to total. "
                        f"Total={self.total_notional:.2f}, Pending={self.pending_notional:.2f}"
                    )
                break

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

        # Clean up tracker immediately when both orders filled AND positions are set
        # This prevents the race condition while ensuring positions are tracked
        if both_filled and tracker_submit_time is not None:
            if state.paxg_pos_id is not None and state.xaut_pos_id is not None:
                del self.paired_orders[tracker_submit_time]
                self.log.debug(
                    f"Removed tracker for level={level} after both fills confirmed "
                    f"and positions set (PAXG={state.paxg_pos_id}, XAUT={state.xaut_pos_id})"
                )

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

        # 2) 再处理"开仓条件"：spread 超过某档且该档没有持仓/待处理订单 -> 开新对冲
        for i, level in enumerate(levels_sorted):
            state = self.grid_state[level]
            # 检查是否已有持仓
            if self._grid_has_position(state):
                continue

            # 检查是否已有pending订单 - 防止重复提交
            if self._grid_has_pending_orders(level):
                continue

            if abs_spread > level:
                # 检查总风险（包括已成交和待成交的订单）
                notional = self.config.base_notional_per_level
                total_exposure = self.total_notional + self.pending_notional + 2 * notional
                if total_exposure > self.config.max_total_notional:
                    self.log.warning(
                        f"Max total notional reached (total={self.total_notional:.2f}, "
                        f"pending={self.pending_notional:.2f}, would_add={2*notional:.2f}), skip new grid."
                    )
                    continue

                self.log.info(f"Opening grid level={level}, spread={spread:.4%}")
                self._open_grid(level, spread)

    def _grid_has_position(self, state: GridPositionState) -> bool:
        return (state.paxg_pos_id is not None) or (state.xaut_pos_id is not None)

    def _grid_has_pending_orders(self, level: float) -> bool:
        """Check if there are pending or recently-filled orders for the specified grid level.
        
        Returns True if ANY tracker exists for this level, regardless of fill status.
        This prevents race conditions where both orders fill but position IDs haven't
        been updated yet in grid_state, which could cause duplicate grid openings.
        """
        for tracker in self.paired_orders.values():
            if tracker.level == level:
                return True  # Any tracker for this level = don't open new grid
        return False

    # ========== Grid 开仓 / 平仓 ==========
    def _open_grid(self, level: float, spread: float) -> None:
        """
        spread > 0: PAXG 贵 → 空 PAXG，多 XAUT
        spread < 0: XAUT 贵 → 空 XAUT，多 PAXG

        使用市价单快速建立对冲仓位，确保两腿同时成交
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

        # 使用市价单确保立即成交，建立对冲仓位
        paxg_order = self.order_factory.market(
            instrument_id=self.paxg_id,
            order_side=paxg_side,
            quantity=self.paxg.make_qty(paxg_qty),
        )

        xaut_order = self.order_factory.market(
            instrument_id=self.xaut_id,
            order_side=xaut_side,
            quantity=self.xaut.make_qty(xaut_qty),
        )

        # 提交订单
        self.submit_order(paxg_order)
        self.submit_order(xaut_order)

        self.log.info(
            f"Submitted MARKET orders for grid level={level}: "
            f"{paxg_leg_tag} qty={paxg_qty:.6f}, {xaut_leg_tag} qty={xaut_qty:.6f}"
        )

        # 记录在途订单
        self.working_orders[paxg_order.client_order_id] = (level, paxg_leg_tag)
        self.working_orders[xaut_order.client_order_id] = (level, xaut_leg_tag)

        # 创建配对订单追踪器
        submit_time = self.clock.timestamp_ns()
        tracker = PairedOrderTracker(
            level=level,
            paxg_order_id=paxg_order.client_order_id,
            xaut_order_id=xaut_order.client_order_id,
            submit_time=submit_time,
            paxg_leg=paxg_leg_tag,
            xaut_leg=xaut_leg_tag,
        )
        self.paired_orders[submit_time] = tracker
        self.log.debug(f"Created paired order tracker for level={level}, submit_time={submit_time}")

        # 更新待确认名义风险（两腿）- 等待订单成交后再计入total_notional
        self.pending_notional += 2 * notional
        self.log.debug(f"Added {2*notional:.2f} to pending_notional, now pending={self.pending_notional:.2f}")

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
        """
        使用限价单平仓，以更好的价格捕获利润
        Close positions with limit orders to capture profit at favorable maker prices
        """
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
        检查配对订单是否出现部分成交：
        - 开仓使用市价单，通常会立即成交，超时主要作为安全机制
        - 如果一侧成交但另一侧超时未成交，则取消未成交订单并平掉已成交的仓位
        - 防止累积单边持仓风险
        """
        if not self.paired_orders:
            return

        current_time = self.clock.timestamp_ns()
        timeout_ns = int(self.config.order_timeout_sec * 1_000_000_000)

        for submit_time, tracker in list(self.paired_orders.items()):
            elapsed_time = current_time - tracker.submit_time

            # 检查是否超时
            if elapsed_time < timeout_ns:
                continue

            # 检查是否两边都成交了
            if tracker.paxg_filled and tracker.xaut_filled:
                # 两边都成交，正常情况，清理追踪器
                del self.paired_orders[submit_time]
                self.log.debug(f"Both orders filled for level={tracker.level}, removing tracker")
                continue

            # 检查是否只有一侧成交（不平衡成交）
            notional = self.config.base_notional_per_level

            if tracker.paxg_filled and not tracker.xaut_filled:
                self.log.warning(
                    f"IMBALANCED FILL DETECTED: PAXG filled but XAUT not filled for level={tracker.level}. "
                    f"Canceling XAUT order and closing PAXG position to prevent directional exposure."
                )
                # 取消未成交的 XAUT 订单
                self._safe_cancel_order(tracker.xaut_order_id)
                # 平掉已成交的 PAXG 仓位
                state = self.grid_state.get(tracker.level)
                if state and state.paxg_pos_id:
                    self._close_position(state.paxg_pos_id)
                    state.paxg_pos_id = None
                # PAXG成交了，但配对失败，需要从pending中扣除全部（因为XAUT没成交，不会进入total）
                # 注意：PAXG成交时已经在on_order_filled中等待配对，这里只需要清理pending
                self.pending_notional = max(0.0, self.pending_notional - 2 * notional)
                self.log.info(f"Cleaned up imbalanced pair, pending_notional={self.pending_notional:.2f}")
                # 清理追踪器
                del self.paired_orders[submit_time]

            elif tracker.xaut_filled and not tracker.paxg_filled:
                self.log.warning(
                    f"IMBALANCED FILL DETECTED: XAUT filled but PAXG not filled for level={tracker.level}. "
                    f"Canceling PAXG order and closing XAUT position to prevent directional exposure."
                )
                # 取消未成交的 PAXG 订单
                self._safe_cancel_order(tracker.paxg_order_id)
                # 平掉已成交的 XAUT 仓位
                state = self.grid_state.get(tracker.level)
                if state and state.xaut_pos_id:
                    self._close_position(state.xaut_pos_id)
                    state.xaut_pos_id = None
                # XAUT成交了，但配对失败，需要从pending中扣除全部
                self.pending_notional = max(0.0, self.pending_notional - 2 * notional)
                self.log.info(f"Cleaned up imbalanced pair, pending_notional={self.pending_notional:.2f}")
                # 清理追踪器
                del self.paired_orders[submit_time]

            elif not tracker.paxg_filled and not tracker.xaut_filled:
                # 两边都没成交，只是超时了，取消两个订单并清理pending
                self.log.info(f"Both orders timed out for level={tracker.level}, canceling both")
                self._safe_cancel_order(tracker.paxg_order_id)
                self._safe_cancel_order(tracker.xaut_order_id)
                # 从pending中扣除
                self.pending_notional = max(0.0, self.pending_notional - 2 * notional)
                self.log.debug(f"Removed {2*notional:.2f} from pending_notional, now pending={self.pending_notional:.2f}")
                del self.paired_orders[submit_time]

    def _safe_cancel_order(self, order_id: Any) -> None:
        """安全地取消订单（检查订单状态）"""
        try:
            order = self.cache.order(order_id)
            if order and order.is_open:
                self.cancel_order(order)
                self.log.debug(f"Canceled order: {order_id}")
        except Exception as e:
            self.log.error(f"Error canceling order {order_id}: {e}")


# ==========================
# 工厂函数（方便在 YAML/JSON 中引用）
# ==========================

def create_strategy(config: PaxgXautGridConfig) -> PaxgXautGridStrategy:
    return PaxgXautGridStrategy(config=config)