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
        # Example: 0.001 = 0.10%, 0.01 = 1%
        # Reduced to 5 levels to match available balance
        grid_levels=[
            0.0010,  # 0.10%
            0.0020,  # 0.20%
            0.0030,  # 0.30%
            0.0040,  # 0.40%
            0.0050,  # 0.50%
        ],

        # Risk management
        # Reduced to 50 USDT per level for better balance safety
        # 5 levels × 2 legs × 50 = 500 USDT notional, ~50 USDT margin at 10x
        base_notional_per_level=50.0,   # USDT per grid level
        max_total_notional=500.0,       # Maximum total exposure (USDT)
        target_leverage=10.0,             # Target leverage (informational)

        # Trading parameters
        maker_offset_bps=2.0,             # 0.02% offset from mid price
        order_timeout_sec=5.0,            # Order timeout in seconds
        rebalance_threshold_bps=20.0,    # 0.20% rebalance threshold
        extreme_spread_stop=0.015,        # 1.5% extreme spread stop

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
