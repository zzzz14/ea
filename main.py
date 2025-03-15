import MetaTrader5 as mt5
import logging
import time
from datetime import datetime
import sys
import signal
import traceback
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import local modules
from tb.config.mt5_config import MT5Config
from tb.config.trading_config import TradingConfig
from tb.core.trader import MT5Trader
from tb.utils.logger import setup_logger
from tb.utils.stats import TradingStats

class TradingBot:
    def __init__(self):
        self.current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.login = MT5Config.LOGIN_ID
        self.logger = setup_logger()
        self.trader = MT5Trader()
        self.stats = TradingStats()
        self.is_running = False
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """Setup handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"""
{'='*50}
SHUTDOWN SIGNAL RECEIVED
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}
        """)
        self.cleanup()
        sys.exit(0)

    def initialize(self):
        """Initialize MT5 connection and verify setup"""
        try:
            # Initialize MT5
            if not mt5.initialize():
                self.logger.error(f"""
{'='*50}
MT5 INITIALIZATION FAILED
Time: {self.current_time} UTC
Login: {self.login}
Error: {mt5.last_error()}
{'='*50}
                """)
                return False

            # Verify account configuration
            account_info = mt5.account_info()
            if not account_info:
                self.logger.error("Failed to get account info")
                return False

            # Log initialization success
            self.logger.info(f"""
{'='*50}
TRADING BOT INITIALIZED
Time: {self.current_time} UTC
Login: {self.login}
Account: {account_info.login} ({account_info.server})
Name: {account_info.name}
Balance: ${account_info.balance:.2f}
Equity: ${account_info.equity:.2f}
{'='*50}

Trading Configuration:
- Symbols: {', '.join(MT5Config.SYMBOLS)}
- Risk Per Trade: {TradingConfig.RISK_PERCENT}%
- Max Daily Loss: {TradingConfig.MAX_DAILY_LOSS_PERCENT}%
- Max Trades: {TradingConfig.MAX_TOTAL_TRADES}
{'='*50}
            """)

            return True

        except Exception as e:
            self.logger.error(f"""
{'='*50}
INITIALIZATION ERROR
Time: {self.current_time} UTC
Login: {self.login}
Error: {str(e)}
Traceback: {traceback.format_exc()}
{'='*50}
            """)
            return False

    def run(self):
        """Main trading loop"""        
        try:
            if not self.initialize():
                return

            self.is_running = True
            self.logger.info(f"""
{'='*50}
STARTING TRADING BOT
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}
            """)

            while self.is_running:
                try:
                    # Update current time
                    self.current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Check for new day
                    self.trader.check_trading_session()

                    # Process each symbol
                    for symbol in MT5Config.SYMBOLS:
                        try:
                            # Generate and execute signals
                            self.trader.process_symbol(symbol)

                            # Update trailing stops and breakeven
                            self.trader.manage_positions(symbol)

                        except Exception as e:
                            self.logger.error(f"""
{'='*50}
SYMBOL PROCESSING ERROR
Time: {self.current_time} UTC
Login: {self.login}
Symbol: {symbol}
Error: {str(e)}
Traceback: {traceback.format_exc()}
{'='*50}
                            """)

                    # Update statistics
                    self.stats.calculate_daily_stats()

                    # Optimize parameters if needed
                    trading_history = self.trader.get_trading_history()
                    self.trader.optimize_parameters(trading_history)

                    # Sleep for next iteration
                    time.sleep(TradingConfig.RECONNECT_WAIT_TIME)

                except Exception as e:
                    self.logger.error(f"""
{'='*50}
MAIN LOOP ERROR
Time: {self.current_time} UTC
Login: {self.login}
Error: {str(e)}
Traceback: {traceback.format_exc()}
{'='*50}
                    """)
                    time.sleep(10)  # Wait before retrying

        except Exception as e:
            self.logger.error(f"""
{'='*50}
CRITICAL ERROR
Time: {self.current_time} UTC
Login: {self.login}
Error: {str(e)}
Traceback: {traceback.format_exc()}
{'='*50}
            """)
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources and close positions if needed"""
        try:
            self.is_running = False
            
            if TradingConfig.CLOSE_POSITIONS_ON_STOP:
                self.trader.close_all_positions()

            mt5.shutdown()
            
            self.logger.info(f"""
{'='*50}
TRADING BOT SHUTDOWN COMPLETE
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}
            """)

        except Exception as e:
            self.logger.error(f"""
{'='*50}
CLEANUP ERROR
Time: {self.current_time} UTC
Login: {self.login}
Error: {str(e)}
Traceback: {traceback.format_exc()}
{'='*50}
            """)

def main():
    """Main entry point"""
    bot = TradingBot()
    bot.run()

if __name__ == "__main__":
    main()
