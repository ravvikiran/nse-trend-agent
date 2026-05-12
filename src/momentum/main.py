"""
QuantGridIndia — Main Entry Point

Wires all pipeline components together and runs the scan scheduler.
Supports standalone execution via:
    python -m src.momentum.main
    python src/momentum/main.py

CLI flags:
    --mock      Use MockDataProvider instead of KiteDataProvider (for testing)
    --config    Path to config JSON file (default: config/momentum_scanner.json)
    --log-level Console log level (default: INFO)
    --log-file  Path to log file (default: logs/momentum_scanner.log)

Requirements: 13.1, 17.1, 18.1
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure project root is on sys.path for both execution modes
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env file if present (for local development; Railway uses dashboard env vars)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")
except ImportError:
    pass  # python-dotenv not required in production

from src.momentum.alert_formatter import AlertFormatter
from src.momentum.config_manager import ConfigManager
from src.momentum.data_provider import DataProvider
from src.momentum.deduplicator import Deduplicator
from src.momentum.final_ranker import FinalRanker
from src.momentum.market_breadth_filter import MarketBreadthFilter
from src.momentum.models import ScannerConfig
from src.momentum.scan_logger import ScanLogger
from src.momentum.scan_scheduler import ScanScheduler
from src.momentum.scanner import MomentumScanner
from src.momentum.sector_analyzer import SectorAnalyzer
from src.momentum.stage1_trend_filter import Stage1TrendFilter
from src.momentum.stage2_relative_strength import Stage2RelativeStrength
from src.momentum.stage3_entry_trigger import Stage3EntryTrigger
from src.momentum.trade_levels import TradeLevelCalculator
from src.momentum.universe_manager import UniverseManager

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="QuantGridIndia — rule-based intraday momentum detection"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Use MockDataProvider for testing (no broker API required)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to scanner config JSON (default: config/momentum_scanner.json)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Console log level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="logs/momentum_scanner.log",
        help="Path to log file (default: logs/momentum_scanner.log)",
    )
    return parser.parse_args()


def setup_logging(log_level: str, log_file: str) -> None:
    """Configure logging with console (INFO+) and file (DEBUG) handlers.

    Args:
        log_level: Console log level string (e.g., 'INFO', 'DEBUG').
        log_file: Path to the log file for DEBUG-level output.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Console handler at the specified level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler at DEBUG level
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def create_data_provider(use_mock: bool, config: ScannerConfig) -> DataProvider:
    """Create the appropriate DataProvider based on CLI flag or environment.

    Priority order:
      1. --mock flag → MockDataProvider
      2. Default → YahooFinanceProvider (free, no API key needed)

    Args:
        use_mock: If True, use MockDataProvider regardless of environment.
        config: Scanner configuration (used for batch_size).

    Returns:
        A concrete DataProvider instance.
    """
    if use_mock:
        from src.momentum.providers.mock_provider import MockDataProvider

        logger.info("Using MockDataProvider (--mock flag)")
        return MockDataProvider(seed=42)

    # Default: Yahoo Finance (free, no credentials needed)
    from src.momentum.providers.yahoo_provider import YahooFinanceProvider

    logger.info("Using YahooFinanceProvider (free, no API key required)")
    return YahooFinanceProvider(batch_size=config.batch_size)


def build_scanner(config: ScannerConfig, data_provider: DataProvider) -> MomentumScanner:
    """Instantiate all pipeline components and wire them into MomentumScanner.

    Args:
        config: Validated scanner configuration.
        data_provider: The data provider to use for market data.

    Returns:
        Fully wired MomentumScanner instance.
    """
    # Pipeline stages
    stage1_filter = Stage1TrendFilter(config)
    stage2_rs = Stage2RelativeStrength(config)
    stage3_trigger = Stage3EntryTrigger(config)

    # Support components
    final_ranker = FinalRanker(config)
    deduplicator = Deduplicator(config)

    # Telegram integration
    from src.momentum.telegram_service import TelegramService
    telegram = TelegramService()
    alert_formatter = AlertFormatter(alert_service=telegram)

    market_breadth_filter = MarketBreadthFilter(config)
    sector_analyzer = SectorAnalyzer(config)
    trade_level_calculator = TradeLevelCalculator(config)
    scan_logger = ScanLogger()
    universe_manager = UniverseManager(config)

    # Load the stock universe on startup
    universe_manager.load_universe()

    scanner = MomentumScanner(
        data_provider=data_provider,
        stage1_filter=stage1_filter,
        stage2_rs=stage2_rs,
        stage3_trigger=stage3_trigger,
        final_ranker=final_ranker,
        deduplicator=deduplicator,
        alert_formatter=alert_formatter,
        market_breadth_filter=market_breadth_filter,
        sector_analyzer=sector_analyzer,
        trade_level_calculator=trade_level_calculator,
        scan_logger=scan_logger,
        universe_manager=universe_manager,
        config=config,
    )

    return scanner


async def run_scanner(args: argparse.Namespace) -> None:
    """Main async entry point: load config, build components, run scheduler.

    Args:
        args: Parsed CLI arguments.
    """
    # Step 1: Load configuration
    config_manager = ConfigManager(config_path=args.config)
    config = config_manager.load()
    logger.info("Configuration loaded (scan_interval=%ds)", config.scan_interval_seconds)

    # Step 2: Create data provider
    data_provider = create_data_provider(use_mock=args.mock, config=config)

    # Step 3: Connect to data provider
    connected = await data_provider.connect()
    if not connected:
        logger.error("Failed to connect to data provider. Exiting.")
        return

    # Step 4: Build the scanner pipeline
    scanner = build_scanner(config, data_provider)

    # Step 5: Create scheduler with scan callback
    scheduler = ScanScheduler(
        config=config,
        scan_callback=scanner.run_cycle,
    )

    # Step 6: Register graceful shutdown handlers
    loop = asyncio.get_running_loop()

    def _shutdown_handler() -> None:
        logger.info("Shutdown signal received. Stopping scheduler...")
        scheduler.stop()

    # Register for SIGINT (Ctrl+C) and SIGTERM
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler; use signal.signal fallback
            signal.signal(sig, lambda s, f: _shutdown_handler())

    # Step 7: Run the scheduler
    logger.info("QuantGridIndia started. Press Ctrl+C to stop.")
    try:
        await scheduler.run()
    finally:
        # Clean up data provider connection
        await data_provider.disconnect()
        logger.info("QuantGridIndia stopped.")


def main() -> None:
    """CLI entry point: parse args, setup logging, run async loop."""
    args = parse_args()
    setup_logging(log_level=args.log_level, log_file=args.log_file)

    logger.info("=" * 60)
    logger.info("QuantGridIndia — Starting")
    logger.info("=" * 60)

    try:
        asyncio.run(run_scanner(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.critical("Unhandled exception: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
