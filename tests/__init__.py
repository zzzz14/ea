"""
Test package for MT5 Trading Bot.
Contains unit tests and integration tests for all components.
"""

import logging
from datetime import datetime

# Setup test configuration
TEST_CONFIG = {
    'current_time': datetime.strptime("2025-03-12 00:17:56", "%Y-%m-%d %H:%M:%S"),
    'login': 'zzzz14',
    'test_symbols': ['EURUSD', 'GBPUSD', 'USDJPY'],
    'timeframe': 'M5'
}

# Setup test logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(name)s] - [%(levelname)s] - %(message)s'
)