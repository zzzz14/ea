import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from datetime import datetime
import logging
from ..config.mt5_config import MT5Config
from ..config.trading_config import TradingConfig

class CorrelationAnalyzer:
    def __init__(self):
        self.current_time = datetime.strptime("2025-03-12 00:06:06", "%Y-%m-%d %H:%M:%S")
        self.login = "zzzz14"
        self.correlation_matrix = None
        self.last_update = None
        self.correlation_threshold = 0.7
        self.lookback_period = 100

    def update_correlation_matrix(self):
        """Update correlation matrix for all symbols"""
        try:
            # Check if update is needed (every hour)
            if (self.last_update and 
                (self.current_time - self.last_update).total_seconds() < 3600):
                return

            # Get price data for all symbols
            symbol_data = {}
            for symbol in MT5Config.SYMBOLS:
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, self.lookback_period)
                if rates is not None:
                    df = pd.DataFrame(rates)
                    symbol_data[symbol] = df['close'].pct_change().dropna()

            # Calculate correlation matrix
            if symbol_data:
                data = pd.DataFrame(symbol_data)
                self.correlation_matrix = data.corr()
                self.last_update = self.current_time

                # Log correlation matrix
                self.log_correlation_matrix()

        except Exception as e:
            logging.error(f"Error updating correlation matrix: {str(e)}")

    def check_correlation_risk(self, symbol, signal_type):
        """Check if new trade would exceed correlation risk limits"""
        try:
            self.update_correlation_matrix()
            
            if self.correlation_matrix is None:
                return True  # Allow trade if no correlation data

            # Get current positions
            positions = mt5.positions_get()
            if positions is None:
                return True

            # Calculate potential risk from correlated pairs
            total_correlated_exposure = 0
            base_exposure = 1.0  # Normalized exposure for new trade

            for position in positions:
                if position.symbol == symbol:
                    continue

                correlation = self.get_correlation(symbol, position.symbol)
                position_direction = 1 if position.type == mt5.POSITION_TYPE_BUY else -1
                signal_direction = 1 if signal_type == 'BUY' else -1

                # Adjust for correlation direction
                effective_correlation = correlation * position_direction * signal_direction
                
                # Add to total exposure
                total_correlated_exposure += abs(effective_correlation * position.volume)

            # Log correlation analysis
            self.log_correlation_analysis(symbol, signal_type, total_correlated_exposure)

            # Check against threshold
            max_allowed_exposure = TradingConfig.MAX_CORRELATED_EXPOSURE
            return total_correlated_exposure <= max_allowed_exposure

        except Exception as e:
            logging.error(f"Error checking correlation risk: {str(e)}")
            return True

    def get_correlation(self, symbol1, symbol2):
        """Get correlation coefficient between two symbols"""
        try:
            if self.correlation_matrix is None:
                return 0

            return self.correlation_matrix.loc[symbol1, symbol2]

        except Exception as e:
            logging.error(f"Error getting correlation: {str(e)}")
            return 0

    def get_correlated_pairs(self, symbol, threshold=None):
        """Get list of pairs correlated with given symbol"""
        try:
            if self.correlation_matrix is None:
                return []

            if threshold is None:
                threshold = self.correlation_threshold

            correlations = self.correlation_matrix[symbol]
            correlated_pairs = correlations[abs(correlations) > threshold]
            
            return [(pair, corr) for pair, corr in correlated_pairs.items() if pair != symbol]

        except Exception as e:
            logging.error(f"Error getting correlated pairs: {str(e)}")
            return []

    def get_correlation_groups(self):
        """Identify groups of correlated symbols"""
        try:
            if self.correlation_matrix is None:
                return []

            groups = []
            processed = set()

            for symbol in self.correlation_matrix.index:
                if symbol in processed:
                    continue

                # Find correlated symbols
                correlated = self.get_correlated_pairs(symbol)
                if correlated:
                    group = {symbol}
                    for pair, _ in correlated:
                        group.add(pair)
                    
                    groups.append(list(group))
                    processed.update(group)

            return groups

        except Exception as e:
            logging.error(f"Error getting correlation groups: {str(e)}")
            return []

    def calculate_portfolio_correlation(self):
        """Calculate correlation-based portfolio risk"""
        try:
            positions = mt5.positions_get()
            if positions is None or len(positions) < 2:
                return 0

            # Create position matrix
            position_data = {}
            for position in positions:
                rates = mt5.copy_rates_from_pos(position.symbol, mt5.TIMEFRAME_M5, 0, self.lookback_period)
                if rates is not None:
                    df = pd.DataFrame(rates)
                    position_data[position.symbol] = df['close'].pct_change().dropna()

            if not position_data:
                return 0

            # Calculate portfolio correlation
            portfolio_df = pd.DataFrame(position_data)
            portfolio_corr = portfolio_df.corr().mean().mean()

            return portfolio_corr

        except Exception as e:
            logging.error(f"Error calculating portfolio correlation: {str(e)}")
            return 0

    def log_correlation_matrix(self):
        """Log correlation matrix details"""
        try:
            if self.correlation_matrix is None:
                return

            analysis = f"""
{'='*50}
CORRELATION MATRIX UPDATE
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}

Highly Correlated Pairs (|correlation| > {self.correlation_threshold}):
"""
            for symbol in self.correlation_matrix.index:
                correlated = self.get_correlated_pairs(symbol)
                if correlated:
                    analysis += f"\n{symbol}:"
                    for pair, corr in correlated:
                        analysis += f"\n  - {pair}: {corr:.2f}"

            analysis += f"\n{'='*50}"
            logging.info(analysis)

        except Exception as e:
            logging.error(f"Error logging correlation matrix: {str(e)}")

    def log_correlation_analysis(self, symbol, signal_type, total_exposure):
        """Log correlation analysis for trade signal"""
        try:
            analysis = f"""
{'='*50}
CORRELATION ANALYSIS - {symbol}
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}

Signal Type: {signal_type}
Total Correlated Exposure: {total_exposure:.2f}
Maximum Allowed: {TradingConfig.MAX_CORRELATED_EXPOSURE}

Correlated Pairs:
"""
            correlated_pairs = self.get_correlated_pairs(symbol)
            for pair, corr in correlated_pairs:
                analysis += f"- {pair}: {corr:.2f}\n"

            analysis += f"\nPortfolio Correlation: {self.calculate_portfolio_correlation():.2f}"
            analysis += f"\n{'='*50}"
            
            logging.info(analysis)

        except Exception as e:
            logging.error(f"Error logging correlation analysis: {str(e)}")