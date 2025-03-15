import logging
import MetaTrader5 as mt5
from datetime import datetime

class MT5Config:
    """
    MetaTrader 5 Configuration
    Current Time: 2025-03-12 01:16:39 UTC
    Login: zzzz14
    """
    # MT5 Account Settings
    LOGIN_ID = 101657921  # Ganti dengan ID akun MT5 anda
    PASSWORD = "8~2Jpg#A"  # Ganti dengan password akun anda
    SERVER = "FBS-Demo"    # Ganti dengan server broker anda
    
    # Trading Symbols
    SYMBOLS = []  # Will be populated dynamically
    
    # Timeframes
    TIMEFRAME_MAIN = mt5.TIMEFRAME_M1
    TIMEFRAME_TREND = mt5.TIMEFRAME_M5
    TIMEFRAME_LONG = mt5.TIMEFRAME_M15
    
    # Additional Constants
    HISTORY_DEPTH = 1000
    RETRY_DELAY = 5  # seconds
    MAX_RETRIES = 3
    
    # Market Session Times (UTC)
    MARKET_OPEN_HOUR = 0
    MARKET_CLOSE_HOUR = 23
    WEEKEND_DAYS = [5, 6]  # Saturday and Sunday
    
    @classmethod
    def load_symbols(cls, include_forex=True, include_crypto=True, use_dynamic=True):
        """Load trading symbols dynamically or use static list"""
        try:
            if use_dynamic:
                if not mt5.initialize(
                    login=cls.LOGIN_ID,
                    password=cls.PASSWORD,
                    server=cls.SERVER
                ):
                    logging.error(f"""
{'='*50}
MT5 CONNECTION ERROR
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Error: {mt5.last_error()}
{'='*50}
                    """)
                    return
                    
                symbols = mt5.symbols_get()
                if symbols:
                    filtered_symbols = []
                    for symbol in symbols:
                        name = symbol.name.upper()
                        
                        # Filter Forex pairs
                        if include_forex and len(name) == 6:
                            if name[-3:] in ["USD", "EUR", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD"]:
                                filtered_symbols.append(name)
                        
                        # Filter Crypto pairs
                        if include_crypto and any(crypto in name for crypto in ["BTC", "ETH", "XRP", "LTC"]):
                            filtered_symbols.append(name)
                    
                    cls.SYMBOLS = list(set(filtered_symbols))
                    logging.info(f"""
{'='*50}
SYMBOLS LOADED
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Total Symbols: {len(cls.SYMBOLS)}
Symbols: {', '.join(cls.SYMBOLS)}
{'='*50}
                    """)
                    
                mt5.shutdown()
            else:
                cls.SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
                logging.info(f"""
{'='*50}
USING STATIC SYMBOLS
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Symbols: {', '.join(cls.SYMBOLS)}
{'='*50}
                """)
        
        except Exception as e:
            logging.error(f"""
{'='*50}
SYMBOL LOADING ERROR
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Error: {str(e)}
{'='*50}
            """)
            cls.SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]  # Fallback to default symbols
    
    @classmethod
    def initialize_mt5(cls):
        """Initialize MT5 connection"""
        try:
            if not mt5.initialize(
                login=cls.LOGIN_ID,
                password=cls.PASSWORD,
                server=cls.SERVER
            ):
                logging.error(f"""
{'='*50}
MT5 INITIALIZATION ERROR
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Error: {mt5.last_error()}
{'='*50}
                """)
                return False
                
            # Get account info
            account_info = mt5.account_info()
            if account_info is None:
                logging.error("Failed to get account info")
                return False
                
            logging.info(f"""
{'='*50}
MT5 INITIALIZED SUCCESSFULLY
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Server: {cls.SERVER}
Balance: ${account_info.balance:.2f}
Equity: ${account_info.equity:.2f}
Margin Level: {account_info.margin_level:.2f}%
{'='*50}
            """)
            
            return True
            
        except Exception as e:
            logging.error(f"""
{'='*50}
MT5 INITIALIZATION ERROR
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Error: {str(e)}
{'='*50}
            """)
            return False
    
    @classmethod
    def shutdown_mt5(cls):
        """Shutdown MT5 connection"""
        try:
            mt5.shutdown()
            logging.info(f"""
{'='*50}
MT5 SHUTDOWN COMPLETE
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
{'='*50}
            """)
            return True
        except Exception as e:
            logging.error(f"""
{'='*50}
MT5 SHUTDOWN ERROR
Time: 2025-03-12 01:16:39 UTC
Login: {cls.LOGIN_ID}
Error: {str(e)}
{'='*50}
            """)
            return False