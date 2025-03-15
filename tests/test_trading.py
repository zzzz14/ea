import unittest
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from ..core.trader import MT5Trader
from ..core.risk_manager import RiskManager
from ..core.position_manager import PositionManager
from ..analysis.technical import TechnicalAnalyzer
from ..analysis.sentiment import SentimentAnalyzer
from ..analysis.correlation import CorrelationAnalyzer
from ..analysis.ml_optimizer import MLOptimizer
from ..config.trading_config import TradingConfig
from ..utils.stats import TradingStats

class TestTrading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup test environment"""
        cls.current_time = datetime.strptime("2025-03-12 00:17:56", "%Y-%m-%d %H:%M:%S")
        cls.login = "zzzz14"
        
        # Initialize components
        cls.trader = MT5Trader()
        cls.risk_manager = RiskManager()
        cls.position_manager = PositionManager()
        cls.technical_analyzer = TechnicalAnalyzer()
        cls.sentiment_analyzer = SentimentAnalyzer()
        cls.correlation_analyzer = CorrelationAnalyzer()
        cls.ml_optimizer = MLOptimizer()
        cls.trading_stats = TradingStats()
        
        # Connect to MT5
        if not mt5.initialize():
            raise Exception("Failed to initialize MT5")

    def setUp(self):
        """Setup for each test"""
        self.symbol = "EURUSD"
        self.timeframe = mt5.TIMEFRAME_M5

    def test_technical_analysis(self):
        """Test technical analysis functionality"""
        try:
            signal, sl_price, tp_price = self.technical_analyzer.get_signal(self.symbol)
            
            self.assertIn(signal, [None, 'BUY', 'SELL'])
            if signal:
                self.assertIsNotNone(sl_price)
                self.assertIsNotNone(tp_price)
                self.assertIsInstance(sl_price, float)
                self.assertIsInstance(tp_price, float)

        except Exception as e:
            self.fail(f"Technical analysis test failed: {str(e)}")

    def test_risk_management(self):
        """Test risk management calculations"""
        try:
            # Test position size calculation
            equity = 10000.0
            risk_percent = 1.0
            sl_pips = 50
            
            position_size = self.risk_manager.calculate_position_size(
                self.symbol,
                equity,
                risk_percent,
                sl_pips
            )
            
            self.assertGreater(position_size, 0)
            self.assertIsInstance(position_size, float)
            
            # Test risk limits
            can_trade = self.risk_manager.can_open_trade(self.symbol)
            self.assertIsInstance(can_trade, bool)

        except Exception as e:
            self.fail(f"Risk management test failed: {str(e)}")

    def test_position_management(self):
        """Test position management functionality"""
        try:
            # Test position tracking
            positions = self.position_manager.get_positions()
            self.assertIsInstance(positions, dict)
            
            # Test trailing stop
            success = self.position_manager.update_trailing_stops()
            self.assertIsInstance(success, bool)

        except Exception as e:
            self.fail(f"Position management test failed: {str(e)}")

    def test_sentiment_analysis(self):
        """Test sentiment analysis"""
        try:
            sentiment = self.sentiment_analyzer.get_market_sentiment(self.symbol)
            
            self.assertIsInstance(sentiment, float)
            self.assertGreaterEqual(sentiment, -1)
            self.assertLessEqual(sentiment, 1)

        except Exception as e:
            self.fail(f"Sentiment analysis test failed: {str(e)}")

    def test_correlation_analysis(self):
        """Test correlation analysis"""
        try:
            # Test correlation matrix update
            self.correlation_analyzer.update_correlation_matrix()
            
            # Test correlation check
            corr = self.correlation_analyzer.get_correlation("EURUSD", "GBPUSD")
            self.assertIsInstance(corr, float)
            self.assertGreaterEqual(corr, -1)
            self.assertLessEqual(corr, 1)

        except Exception as e:
            self.fail(f"Correlation analysis test failed: {str(e)}")

    def test_ml_optimization(self):
        """Test machine learning optimization"""
        try:
            # Test parameter optimization
            self.ml_optimizer.optimize_parameters({})
            
            # Verify model exists
            self.assertIsNotNone(self.ml_optimizer.model)

        except Exception as e:
            self.fail(f"ML optimization test failed: {str(e)}")

    def test_trading_stats(self):
        """Test trading statistics calculations"""
        try:
            # Test daily stats
            daily_stats = self.trading_stats.calculate_daily_stats()
            self.assertIsInstance(daily_stats, dict)
            
            # Test metrics
            self.assertIn('total_trades', daily_stats)
            self.assertIn('win_rate', daily_stats)
            self.assertIn('profit_factor', daily_stats)

        except Exception as e:
            self.fail(f"Trading stats test failed: {str(e)}")

    def test_trade_execution(self):
        """Test trade execution workflow"""
        try:
            # Test trade signal generation
            signal = self.trader.generate_signal(self.symbol)
            self.assertIn(signal, [None, 'BUY', 'SELL'])
            
            if signal:
                # Test trade validation
                valid = self.trader.validate_trade(self.symbol, signal)
                self.assertIsInstance(valid, bool)

        except Exception as e:
            self.fail(f"Trade execution test failed: {str(e)}")

    def test_config_validation(self):
        """Test configuration validation"""
        try:
            self.assertGreater(TradingConfig.RISK_PERCENT, 0)
            self.assertLess(TradingConfig.RISK_PERCENT, 100)
            
            self.assertGreater(TradingConfig.MAX_DAILY_LOSS_PERCENT, 0)
            self.assertLess(TradingConfig.MAX_DAILY_LOSS_PERCENT, 100)
            
            self.assertGreater(TradingConfig.MAX_TOTAL_TRADES, 0)

        except Exception as e:
            self.fail(f"Config validation test failed: {str(e)}")

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        mt5.shutdown()

if __name__ == '__main__':
    unittest.main()