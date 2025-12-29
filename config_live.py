"""
Live trading configuration for PAXG-XAUT Grid Strategy on Bybit
"""

from decimal import Decimal
from pathlib import Path

from nautilus_trader.adapters.bybit.config import BybitDataClientConfig, BybitExecClientConfig
from nautilus_trader.adapters.bybit.factories import BybitLiveDataClientFactory, BybitLiveExecClientFactory
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
        # Optimized for $2500 capital with 10x leverage
        # 8 levels with 0.5% spacing to match PAXG-XAUT volatility
        # Higher levels (3.0%-4.0%) capture current stable spread at 0.37%-0.39%
        grid_levels=[
            0.0050,  # 0.50% - First level
            0.0100,  # 1.00% - Second level
            0.0150,  # 1.50% - Third level
            0.0200,  # 2.00% - Fourth level
            0.0250,  # 2.50% - Fifth level
            0.0300,  # 3.00% - Sixth level (captures current market)
            0.0350,  # 3.50% - Seventh level
            0.0400,  # 4.00% - Eighth level
        ],

        # Risk management - Optimized for $2500 USDT capital
        # $600 per side = $1200 total per grid
        # 8 grids max = $9600 notional = $960 margin at 10x (38% utilization)
        # Leaves $1540 margin (62%) as safety buffer
        base_notional_per_level=600.0,   # USDT per side (each leg)
        max_total_notional=12000.0,      # Maximum total exposure allows 10 grids with buffer
        target_leverage=10.0,            # Target leverage (set on Bybit exchange)

        # Trading parameters
        maker_offset_bps=2.0,            # 0.02% offset from mid price
        order_timeout_sec=5.0,           # Order timeout in seconds
        rebalance_threshold_bps=20.0,   # 0.20% rebalance threshold
        extreme_spread_stop=0.050,       # 5.0% extreme spread stop (above highest grid at 4.0%)

        # Features
        enable_high_levels=True,
        auto_subscribe=True,

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
        testnet=False,  # Set to True for testnet
    )

    # Logging configuration
    logging_config = LoggingConfig(
        log_level="INFO",
        log_level_file="DEBUG",
        log_directory="logs",
        log_file_name="paxg_xaut_grid",
        log_file_format="json",
        log_colors=True,
        bypass_logging=False,
        log_file_max_size=10_485_760,  # 10MB in bytes (10 * 1024 * 1024)
        log_file_max_backup_count=3,   # Keep 3 backup files (total: 40MB max)
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
