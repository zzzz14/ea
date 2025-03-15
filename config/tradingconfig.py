class TradingConfig:
    # Risk Management
    RISK_PERCENT = 1.0
    MAX_DAILY_LOSS_PERCENT = 5.0
    MAX_TOTAL_TRADES = 5
    MAX_TRADES_PER_SYMBOL = 2
    
    # Technical Indicators
    EMA_FAST = 8
    EMA_SLOW = 14
    EMA_LONG = 200
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    BB_PERIOD = 20
    BB_STD = 2.0
    ATR_PERIOD = 14
    
    # Trading Parameters
    TRAILING_STOP = True
    TRAILING_STOP_ACTIVATION = 1.0  # ATR multiplier
    BREAKEVEN_ACTIVATION = 1.5      # ATR multiplier
    TP_ATR_MULTIPLIER = 2.0
    SL_ATR_MULTIPLIER = 1.0
    
    # Market Conditions
    MAX_SPREAD_MULTIPLIER = 1.5
    MIN_VOLATILITY = 0.2
    MAX_VOLATILITY = 3.0
    
    # ML Parameters
    OPTIMIZATION_INTERVAL = 3600  # 1 hour
    TRAINING_HISTORY_DAYS = 30
    
    # Market Sessions (UTC)
    MARKET_SESSIONS = {
        'asian': {'start': 1, 'end': 9},
        'european': {'start': 7, 'end': 16},
        'american': {'start': 13, 'end': 22}
    }
    
    # System Settings
    RECONNECT_ATTEMPTS = 3
    RECONNECT_WAIT_TIME = 10
    CLOSE_POSITIONS_ON_STOP = False
    SIMULATE_ONLY = False
    
    # Notifications
    ENABLE_TELEGRAM = False
    TELEGRAM_BOT_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    
    # Trading Hours (UTC)
    TRADING_HOURS = {
        'start': 0,  # 2 AM UTC
        'end': 21    # 9 PM UTC
    }
    
    @classmethod
    def validate_settings(cls):
        """Validate configuration settings"""
        assert 0 < cls.RISK_PERCENT <= 2, "Risk percent must be between 0 and 2"
        assert cls.MAX_DAILY_LOSS_PERCENT > cls.RISK_PERCENT, "Max daily loss must be greater than risk per trade"
        assert cls.EMA_FAST < cls.EMA_SLOW < cls.EMA_LONG, "EMA periods must be in ascending order"
        assert 0 < cls.RSI_PERIOD <= 50, "RSI period must be between 1 and 50"
        assert cls.RSI_OVERSOLD < cls.RSI_OVERBOUGHT, "RSI levels must be properly ordered"
