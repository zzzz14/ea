import MetaTrader5 as mt5
import logging
import time
from datetime import datetime
import threading
import pandas as pd
import numpy as np
import os
import sys 

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from tb.config.mt5_config import MT5Config
from tb.config.trading_config import TradingConfig
from tb.core.position_manager import PositionManager
from tb.core.risk_manager import RiskManager
from tb.analysis.technical import TechnicalAnalyzer
from tb.analysis.sentiment import SentimentAnalyzer
from tb.analysis.correlation import CorrelationAnalyzer
from tb.analysis.ml_optimizer import MLOptimizer
from tb.utils.stats import TradingStats

class MT5Trader:
    def __init__(self):
        self.connected = False
        self.connection_attempts = 3
        self.exit_flag = False
        self.trade_lock = threading.Lock()
        
        # Initialize components
        self.position_manager = PositionManager()
        self.risk_manager = RiskManager()
        self.technical_analyzer = TechnicalAnalyzer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.ml_optimizer = MLOptimizer()
        self.stats = TradingStats()
        
        # Market data cache
        self.market_data = {
            'last_update': {},
            'data': {},
            'signals': {}
        }
        
        # Performance tracking
        self.performance = {
            'trades_today': 0,
            'profit_today': 0.0,
            'last_update': datetime.now()
        }

    def connect(self):
        """Establish connection to MT5 terminal"""
        try:
            # Add delay before initialization
            time.sleep(0.5)
            
            # Reset MT5 if already initialized
            if mt5.terminal_info() is not None:
                mt5.shutdown()
                time.sleep(1)
            
            # Initialize MT5
            if not mt5.initialize():
                logging.error(f"Failed to initialize MT5: {mt5.last_error()}")
                self.connection_attempts += 1
                return False
            
            # Login to MT5 account
            if not mt5.login(MT5Config.LOGIN_ID, MT5Config.PASSWORD, MT5Config.SERVER):
                logging.error(f"Failed to login: {mt5.last_error()}")
                mt5.shutdown()
                self.connection_attempts += 1
                return False
            
            # Connection successful
            self.connected = True
            self.connection_attempts = 0
            
            # Log account info
            account_info = mt5.account_info()
            if account_info:
                logging.info(f"""
                Connected to MT5:
                - Login: {account_info.login}
                - Server: {MT5Config.SERVER}
                - Balance: ${account_info.balance:.2f}
                - Equity: ${account_info.equity:.2f}
                """)
            
            # Initialize trading symbols
            self.initialize_symbols()
            
            return True
            
        except Exception as e:
            logging.error(f"Connection error: {str(e)}")
            self.connection_attempts += 1
            return False

    def initialize_symbols(self):
        """Initialize trading symbols"""
        for symbol in MT5Config.SYMBOLS:
            try:
                if not mt5.symbol_select(symbol, True):
                    logging.warning(f"Symbol {symbol} not available")
                    continue
                
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    logging.info(f"""
                    Symbol {symbol} initialized:
                    - Spread: {symbol_info.spread} points
                    - Tick Value: {symbol_info.trade_tick_value}
                    - Min Lot: {symbol_info.volume_min}
                    - Max Lot: {symbol_info.volume_max}
                    - Lot Step: {symbol_info.volume_step}
                    """)
                    
                    # Initialize market data cache
                    self.market_data['data'][symbol] = None
                    self.market_data['last_update'][symbol] = 0
                    self.market_data['signals'][symbol] = None
                    
            except Exception as e:
                logging.error(f"Error initializing {symbol}: {str(e)}")

    def update_market_data(self, symbol):
        """Update market data for symbol"""
        try:
            current_time = time.time()
            
            # Check if update is needed (every 1 second)
            if current_time - self.market_data['last_update'].get(symbol, 0) < 1:
                return self.market_data['data'].get(symbol)
            
            # Get new market data
            rates = mt5.copy_rates_from_pos(symbol, MT5Config.TIMEFRAME_MAIN, 0, 100)
            if rates is None:
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            
            # Update cache
            self.market_data['data'][symbol] = df
            self.market_data['last_update'][symbol] = current_time
            
            return df
            
        except Exception as e:
            logging.error(f"Error updating market data for {symbol}: {str(e)}")
            return None

    def process_symbol(self, symbol):
        """Process trading logic for a symbol"""
        try:
            # Update market data
            df = self.update_market_data(symbol)
            if df is None:
                return
            
            # Get technical analysis signal
            signal, sl_price, tp_price = self.technical_analyzer.get_signal(symbol)
            if not signal:
                return
            
            # Validate with sentiment analysis
            sentiment_score = self.sentiment_analyzer.get_market_sentiment(symbol)
            if abs(sentiment_score) < TradingConfig.SENTIMENT_THRESHOLD:
                return
            
            # Check correlation risk
            if not self.correlation_analyzer.check_correlation_risk(symbol, signal):
                return
            
            # Calculate position size
            lot_size = self.risk_manager.calculate_position_size(symbol, sl_price)
            if not lot_size:
                return
            
            # Execute trade
            self.execute_trade(symbol, signal, lot_size, sl_price, tp_price)
            
        except Exception as e:
            logging.error(f"Error processing {symbol}: {str(e)}")

    def execute_trade(self, symbol, signal_type, lot_size, sl_price, tp_price):
        """Execute trading operation"""
        try:
            with self.trade_lock:  # Thread safety
                # Final risk check
                if not self.risk_manager.can_open_trade(symbol):
                    return
                
                # Open position
                ticket = self.position_manager.open_trade(
                    symbol=symbol,
                    trade_type=signal_type,
                    lot_size=lot_size,
                    sl_price=sl_price,
                    tp_price=tp_price
                )
                
                if ticket:
                    # Update statistics
                    self.performance['trades_today'] += 1
                    self.stats.update_trade_opened(symbol, signal_type, lot_size)
                    
                    logging.info(f"""
                    New trade opened:
                    - Symbol: {symbol}
                    - Type: {signal_type}
                    - Lot Size: {lot_size}
                    - SL: {sl_price}
                    - TP: {tp_price}
                    - Ticket: {ticket}
                    """)
                    
        except Exception as e:
            logging.error(f"Error executing trade: {str(e)}")

    def trading_cycle(self):
        """Main trading cycle"""
        try:
            # Check connection
            if not self.check_connection():
                return
            
            # Update daily stats if needed
            self.update_daily_stats()
            
            # Manage existing positions
            self.position_manager.manage_positions()
            
            # Process each symbol
            for symbol in MT5Config.SYMBOLS:
                if self.can_trade(symbol):
                    self.process_symbol(symbol)
                    
            # Optimize parameters if needed
            trading_history = self.get_trading_history()
            self.optimize_parameters(trading_history)
            
        except Exception as e:
            logging.error(f"Error in trading cycle: {str(e)}")

    def can_trade(self, symbol):
        """Check if trading is allowed for symbol"""
        return (
            self.check_market_conditions(symbol) and
            self.risk_manager.can_open_trade(symbol) and
            self.check_trading_session()
        )

    def check_market_conditions(self, symbol):
        """Check market conditions for trading"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return False
            
            # Check spread
            current_spread = symbol_info.spread
            avg_spread = symbol_info.spread_float
            
            if current_spread > TradingConfig.MAX_SPREAD_MULTIPLIER * avg_spread:
                return False
            
            # Check volatility
            df = self.market_data['data'].get(symbol)
            if df is not None:
                atr = df['high'].rolling(14).max() - df['low'].rolling(14).min()
                current_atr = atr.iloc[-1]
                avg_atr = atr.mean()
                
                if current_atr > avg_atr * 2:  # Too volatile
                    return False
                if current_atr < avg_atr * 0.3:  # Too quiet
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error checking market conditions: {str(e)}")
            return False

    def check_trading_session(self):
        """Check if current time is within trading session"""
        current_hour = datetime.now().hour
        
        for session in TradingConfig.MARKET_SESSIONS.values():
            if session['start'] <= current_hour < session['end']:
                return True
                
        return False

    def optimize_parameters(self, trading_history):
        """Optimize trading parameters using ML"""
        try:
            current_time = time.time()
            last_optimization = getattr(self, 'last_optimization', 0)
            
            # Optimize every hour
            if current_time - last_optimization > 3600:
                self.ml_optimizer.optimize_parameters(trading_history)
                self.last_optimization = current_time
                
        except Exception as e:
            logging.error(f"Error optimizing parameters: {str(e)}")

    def update_daily_stats(self):
        """Update daily trading statistics"""
        try:
            current_date = datetime.now().date()
            last_update = self.performance['last_update'].date()
            
            if current_date > last_update:
                # Reset daily counters
                self.performance['trades_today'] = 0
                self.performance['profit_today'] = 0.0
                self.performance['last_update'] = datetime.now()
                
                # Log daily summary
                self.stats.log_daily_summary()
                
        except Exception as e:
            logging.error(f"Error updating daily stats: {str(e)}")

    def check_connection(self):
        """Check and maintain MT5 connection"""
        if not self.connected or not mt5.terminal_info():
            logging.warning("Connection lost, attempting to reconnect...")
            
            if self.connection_attempts < TradingConfig.RECONNECT_ATTEMPTS:
                time.sleep(TradingConfig.RECONNECT_WAIT_TIME)
                return self.connect()
            
            logging.error("Failed to reconnect after maximum attempts")
            return False
            
        return True

    def get_trading_history(self):
        """Get trading history for optimization"""
        try:
            # Define the timeframe for history retrieval
            end_time = datetime.now()
            start_time = end_time - pd.Timedelta(days=30)  # Last 30 days
            
            # Retrieve trading history
            history = mt5.history_deals_get(start_time, end_time)
            if history is None:
                raise Exception("Failed to get trading history")
            
            return history
            
        except Exception as e:
            logging.error(f"Error getting trading history: {str(e)}")
            return None

    def run(self):
        """Main bot running method"""
        try:
            logging.info("Starting MT5 Trading Bot...")
        
            if not self.connect():
                logging.error("Failed to connect to MT5. Exiting.")
                return
            
            # Get initial account info
            account_info = mt5.account_info()
            if account_info:
                logging.info(f"Connected to account {account_info.login}")
                logging.info(f"Balance: ${account_info.balance:.2f}, Equity: ${account_info.equity:.2f}")
            
            # Initialize peak balance
            self.stats.stats['peak_balance'] = account_info.balance
            self.stats.save_stats()
        
            # Main loop
            while not self.exit_flag:
                try:
                    self.trading_cycle()
                except Exception as e:
                    logging.error(f"Error in trading cycle: {str(e)}")
                
            # Sleep between cycles
            time.sleep(3)      
        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
        finally:
            self.cleanup()
            logging.info("Trading bot stopped")

    def cleanup(self):
        """Cleanup resources before stopping"""
        try:
            if self.connected:
                # Close all positions if needed
                if TradingConfig.CLOSE_POSITIONS_ON_STOP:
                    self.position_manager.close_all_positions()
                
                # Disconnect from MT5
                mt5.shutdown()
                self.connected = False
            
            logging.info("Trading bot stopped")
            
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")

    def stop(self):
        """Stop the trading bot"""
        self.exit_flag = True
        logging.info("Stopping trading bot...")
