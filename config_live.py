"""
Live trading configuration for PAXG-XAUT Grid Strategy on Bybit
"""

from decimal import Decimal
from pathlib import Path

from nautilus_trader.adapters.bybit.config import BybitDataClientConfig, BybitExecClientConfig
from nautilus_trader.adapters.bybit.factories import BybitLiveDataClientFactory, BybitLiveExecClientFactory
from nautilus_trader.core.nautilus_pyo3 import BybitProductType
from nautilus_trader.config import (
    InstrumentProviderConfig,
    LiveExecEngineConfig,
    LoggingConfig,
    TradingNodeConfig,
)
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.trading.config import ImportableStrategyConfig

from paxg_xaut_grid_strategy import PaxgXautGridConfig


def create_live_config() -> TradingNodeConfig:
    """
    Create live trading configuration for PAXG-XAUT grid strategy.

    Returns
    -------
    TradingNodeConfig
        The configured trading node for live trading.
    """

    # Strategy configuration
    strategy_config = PaxgXautGridConfig(
        # Instrument IDs (Bybit perpetual swaps)
        paxg_instrument_id="PAXGUSDT-LINEAR.BYBIT",
        xaut_instrument_id="XAUTUSDT-LINEAR.BYBIT",

        # Grid levels (price spread as percentage of XAUT price)
        # Optimized for $2500 capital with 10x leverage and 30% safety reserve
        # 15 levels: 5 low (0.1%-0.3%), 4 mid (0.4%-0.8%), 3 high (1.0%-2.0%), 3 extreme (3%-8%)
        # Available capital: 1750 USDT (70%), Safety reserve: 750 USDT (30%)
        grid_levels=[
            0.0010,  # 0.10% - Low tier 1
            0.0015,  # 0.15% - Low tier 2
            0.0020,  # 0.20% - Low tier 3
            0.0025,  # 0.25% - Low tier 4
            0.0030,  # 0.30% - Low tier 5
            0.0040,  # 0.40% - Mid tier 1
            0.0050,  # 0.50% - Mid tier 2
            0.0060,  # 0.60% - Mid tier 3
            0.0080,  # 0.80% - Mid tier 4
            0.0100,  # 1.00% - High tier 1
            0.0150,  # 1.50% - High tier 2
            0.0200,  # 2.00% - High tier 3
            0.0300,  # 3.00% - Extreme tier 1
            0.0500,  # 5.00% - Extreme tier 2
            0.0800,  # 8.00% - Extreme tier 3
        ],

        # Risk management - $2500 capital, 10x leverage, 30% safety reserve
        # Base unit: 88.5 USDT per side (adjustable by position weights)
        # Max total: 3500 USDT (2x available capital for flexibility)
        base_notional_per_level=88.5,    # USDT per side (base unit, scaled by weights)
        max_total_notional=3500.0,       # Maximum total exposure (2x available capital)
        target_leverage=10.0,            # Target leverage (set on Bybit exchange)

        # Position weights for different grid levels (multiplier for base_notional_per_level)
        # Lower spreads = smaller positions, higher spreads = larger positions
        position_weights={
            0.0010: 0.4,  # 35.4 USDT per side → 70.8 USDT total per grid
            0.0015: 0.5,  # 44.3 USDT per side → 88.6 USDT total per grid
            0.0020: 0.6,  # 53.1 USDT per side → 106.2 USDT total per grid
            0.0025: 0.7,  # 62.0 USDT per side → 124.0 USDT total per grid
            0.0030: 0.8,  # 70.8 USDT per side → 141.6 USDT total per grid
            0.0040: 1.0,  # 88.5 USDT per side → 177.0 USDT total per grid
            0.0050: 1.0,  # 88.5 USDT per side → 177.0 USDT total per grid
            0.0060: 1.0,  # 88.5 USDT per side → 177.0 USDT total per grid
            0.0080: 1.2,  # 106.2 USDT per side → 212.4 USDT total per grid
            0.0100: 1.5,  # 132.8 USDT per side → 265.6 USDT total per grid
            0.0150: 1.8,  # 159.3 USDT per side → 318.6 USDT total per grid
            0.0200: 2.0,  # 177.0 USDT per side → 354.0 USDT total per grid
            0.0300: 2.5,  # 221.3 USDT per side → 442.6 USDT total per grid
            0.0500: 3.0,  # 265.5 USDT per side → 531.0 USDT total per grid
            0.0800: 3.5,  # 309.8 USDT per side → 619.6 USDT total per grid
        },

        # Trading parameters
        maker_offset_bps=1.0,            # 0.01% offset from mid price (tighter for fine grids)
        order_timeout_sec=5.0,           # Order timeout in seconds
        rebalance_threshold_bps=10.0,   # 0.10% rebalance threshold (matches grid spacing)
        extreme_spread_stop=0.010,       # 1.0% extreme spread stop (above highest grid at 0.5%)

        # Features
        enable_high_levels=True,
        auto_subscribe=True,

        # Startup settings
        startup_delay_sec=10.0,  # Wait 10s for NautilusTrader position reconciliation

        # IMPORTANT: Set this when restarting with existing positions!
        # Bybit doesn't report external positions to NautilusTrader.
        # Check Bybit position page and set to actual exposure.
        # Set to 0.0 when starting fresh with no positions.
        # UPDATED: Set to 0.0 - no existing positions after multiple restarts (2026-01-07 15:01)
        initial_notional_override=0.0,

        # Strategy identification (required for multiple strategy instances)
        order_id_tag="001",
    )

    # Wrap strategy config in ImportableStrategyConfig
    importable_config = ImportableStrategyConfig(
        strategy_path="paxg_xaut_grid_strategy:PaxgXautGridStrategy",
        config_path="paxg_xaut_grid_strategy:PaxgXautGridConfig",
        config=strategy_config.dict(),
    )

    # Bybit data client configuration
    bybit_data_config = BybitDataClientConfig(
        api_key=None,  # Will use BYBIT_API_KEY env var
        api_secret=None,  # Will use BYBIT_API_SECRET env var
        base_url_http=None,  # Uses default Bybit endpoint
        instrument_provider=InstrumentProviderConfig(
            load_all=True,
            load_ids=None,
        ),
        testnet=False,  # Set to True for testnet
    )

    # Bybit execution client configuration
    bybit_exec_config = BybitExecClientConfig(
        api_key=None,  # Will use BYBIT_API_KEY env var
        api_secret=None,  # Will use BYBIT_API_SECRET env var
        base_url_http=None,  # Uses default Bybit endpoint
        instrument_provider=InstrumentProviderConfig(
            load_all=True,
            load_ids=None,
        ),
        product_types=[BybitProductType.LINEAR],  # Trading linear perpetuals (PAXG/XAUT)
        testnet=False,  # Set to True for testnet
        # Using One-Way Mode (default) - position mode must be set on Bybit exchange to match
    )

    # Logging configuration
    # NOTE: NautilusTrader automatically adds timestamps to log filenames on each restart.
    # This prevents overwriting but means old files accumulate.
    # Use the cleanup_old_logs() function in run_live.py to remove old files on startup.
    logging_config = LoggingConfig(
        log_level="INFO",
        log_level_file="INFO",  # Changed from DEBUG to INFO to reduce log size
        log_directory="logs",
        log_file_name="paxg_xaut_grid",
        log_file_format="json",
        log_colors=True,
        bypass_logging=False,
        log_file_max_size=10_485_760,  # 10MB per file (rotation within single series)
        log_file_max_backup_count=3,   # Keep 3 backup files per series (applies to current series only)
    )

    # Execution engine configuration
    exec_engine_config = LiveExecEngineConfig(
        reconciliation=True,  # Enable position reconciliation
        reconciliation_lookback_mins=1440,  # 24 hours
        snapshot_orders=True,
        snapshot_positions=True,
        snapshot_positions_interval_secs=300.0,  # 5 minutes
    )

    # Trading node configuration
    config = TradingNodeConfig(
        trader_id=TraderId("TRADER-001"),
        logging=logging_config,
        exec_engine=exec_engine_config,

        # Data clients
        data_clients={
            "BYBIT": bybit_data_config,
        },

        # Execution clients
        exec_clients={
            "BYBIT": bybit_exec_config,
        },

        # Strategy configurations
        strategies=[importable_config],

        # Timeout settings
        timeout_connection=30.0,
        timeout_reconciliation=10.0,
        timeout_portfolio=10.0,
        timeout_disconnection=10.0,
    )

    return config


if __name__ == "__main__":
    # Print configuration for verification
    config = create_live_config()
    print("=" * 80)
    print("PAXG-XAUT Grid Strategy - Live Trading Configuration")
    print("=" * 80)
    print(f"Trader ID: {config.trader_id}")
    print(f"Data Clients: {list(config.data_clients.keys())}")
    print(f"Exec Clients: {list(config.exec_clients.keys())}")
    print(f"Strategies: {len(config.strategies)}")
    print("=" * 80)
