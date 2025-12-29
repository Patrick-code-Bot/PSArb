"""
Live trading configuration for PAXG-XAUT Grid Strategy on Bybit
"""

from decimal import Decimal
from pathlib import Path

from nautilus_trader.adapters.bybit.config import BybitDataClientConfig, BybitExecClientConfig
from nautilus_trader.adapters.bybit.common.enums import BybitPositionMode
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
        # 8 levels with fine 0.05% spacing to capture current 0.37%-0.39% spread
        # Levels 0.30%-0.35% will immediately trade at current market conditions
        grid_levels=[
            0.0010,  # 0.10% - First level
            0.0015,  # 0.15% - Second level
            0.0020,  # 0.20% - Third level
            0.0025,  # 0.25% - Fourth level
            0.0030,  # 0.30% - Fifth level (captures current spread!)
            0.0035,  # 0.35% - Sixth level (captures current spread!)
            0.0040,  # 0.40% - Seventh level (near current spread)
            0.0050,  # 0.50% - Eighth level
        ],

        # Risk management - Adjusted for available balance with existing positions
        # $300 per side = $600 total per grid
        # 8 grids max = $4800 notional = $480 margin at 10x
        # Works with existing ~$600 margin in use, total ~$1080 margin needed
        base_notional_per_level=300.0,   # USDT per side (each leg)
        max_total_notional=6000.0,       # Maximum total exposure allows flexibility
        target_leverage=10.0,            # Target leverage (set on Bybit exchange)

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
        # Position mode for linear perpetuals - MERGED_SINGLE is Bybit's One-Way Mode
        # This must match your Bybit account settings
        position_mode=BybitPositionMode.MERGED_SINGLE,
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
