import logging
import os
import time
import sys
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

class CustomFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def __init__(self, current_time, login):
        self.current_time = current_time
        self.login = login
        
        self.FORMATS = {
            logging.DEBUG: f"{self.grey}%(asctime)s - [{self.login}] - %(levelname)s - %(message)s{self.reset}",
            logging.INFO: f"{self.blue}%(asctime)s - [{self.login}] - %(levelname)s - %(message)s{self.reset}",
            logging.WARNING: f"{self.yellow}%(asctime)s - [{self.login}] - %(levelname)s - %(message)s{self.reset}",
            logging.ERROR: f"{self.red}%(asctime)s - [{self.login}] - %(levelname)s - %(message)s{self.reset}",
            logging.CRITICAL: f"{self.bold_red}%(asctime)s - [{self.login}] - %(levelname)s - %(message)s{self.reset}"
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

def setup_logger(name="MT5_Trading_Bot"):
    """Setup logger with both file and console handlers"""
    try:
        # Current time and login
        current_time = datetime.now().strptime("2025-03-15 06:38:00", "%Y-%m-%d %H:%M:%S")
        login = "zzzz14"
        
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        logger.handlers = []

        # File handler (rotating, max 10MB per file, keep 5 backup files)
        log_file = os.path.join(log_dir, f"trading_bot_{login}_{current_time.strftime('%Y%m%d')}.log")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - [%(name)s] - [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler with custom formatter
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(CustomFormatter(current_time, login))
        logger.addHandler(console_handler)

        # Log initialization
        logger.info(f"""
{'='*50}
Trading Bot Logger Initialized
Time: {current_time} UTC
Login: {login}
Log File: {log_file}
{'='*50}
        """)

        return logger

    except Exception as e:
        print(f"Error setting up logger: {str(e)}")
        return logging.getLogger(name)

def log_trade(logger, trade_info, current_time=None, login=None):
    """Log trade information with standardized format"""
    try:
        if current_time is None:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if login is None:
            login = "zzzz14"

        trade_log = f"""
{'='*50}
TRADE EXECUTION
Time: {current_time} UTC
Login: {login}
{'='*50}

Symbol: {trade_info.get('symbol', 'N/A')}
Type: {trade_info.get('type', 'N/A')}
Volume: {trade_info.get('volume', 'N/A')}
Entry Price: {trade_info.get('entry_price', 'N/A')}
Stop Loss: {trade_info.get('sl', 'N/A')}
Take Profit: {trade_info.get('tp', 'N/A')}
Ticket: {trade_info.get('ticket', 'N/A')}

Analysis:
- Technical: {trade_info.get('technical_analysis', 'N/A')}
- Sentiment: {trade_info.get('sentiment_analysis', 'N/A')}
- Risk: {trade_info.get('risk_analysis', 'N/A')}

Parameters:
- Risk %: {trade_info.get('risk_percent', 'N/A')}
- ATR Multiple: {trade_info.get('atr_multiple', 'N/A')}
- RR Ratio: {trade_info.get('rr_ratio', 'N/A')}
{'='*50}
        """

        logger.info(trade_log)

    except Exception as e:
        logger.error(f"Error logging trade: {str(e)}")

def log_error(logger, error_info, current_time=None, login=None):
    """Log error information with standardized format"""
    try:
        if current_time is None:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if login is None:
            login = "zzzz14"

        error_log = f"""
{'='*50}
ERROR OCCURRED
Time: {current_time} UTC
Login: {login}
{'='*50}

Error Type: {error_info.get('type', 'N/A')}
Description: {error_info.get('description', 'N/A')}
Location: {error_info.get('location', 'N/A')}
Stack Trace: {error_info.get('stack_trace', 'N/A')}

Context:
- Symbol: {error_info.get('symbol', 'N/A')}
- Operation: {error_info.get('operation', 'N/A')}
- Parameters: {error_info.get('parameters', 'N/A')}
{'='*50}
        """

        logger.error(error_log)

    except Exception as e:
        logger.error(f"Error logging error: {str(e)}")