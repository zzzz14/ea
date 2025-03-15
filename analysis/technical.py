import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import pandas_ta as ta
import logging
from datetime import datetime
from ..config.trading_config import TradingConfig

class TechnicalAnalyzer:
    def __init__(self):
        self.signal_cache = {}
        self.last_update = {}
        self.login = "zzzz14"  # Current user's login
        self.current_time = datetime.strptime("2025-03-12 00:02:13", "%Y-%m-%d %H:%M:%S")

    def calculate_indicators(self, df):
        """Calculate technical indicators"""
        try:
            # EMA Calculations
            df['ema_fast'] = ta.ema(df['close'], length=TradingConfig.EMA_FAST)
            df['ema_slow'] = ta.ema(df['close'], length=TradingConfig.EMA_SLOW)
            df['ema_long'] = ta.ema(df['close'], length=TradingConfig.EMA_LONG)
            
            # RSI
            df['rsi'] = ta.rsi(df['close'], length=TradingConfig.RSI_PERIOD)
            
            # Bollinger Bands
            bbands = ta.bbands(df['close'], length=TradingConfig.BB_PERIOD, std=TradingConfig.BB_STD)
            df = pd.concat([df, bbands], axis=1)
            
            # ATR
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=TradingConfig.ATR_PERIOD)
            
            # Additional Indicators
            df['macd'] = ta.macd(df['close'])['MACD_12_26_9']
            df['macd_signal'] = ta.macd(df['close'])
                        # Stochastic
            stoch = ta.stoch(df['high'], df['low'], df['close'])
            df = pd.concat([df, stoch], axis=1)
            
            return df
            
        except Exception as e:
            logging.error(f"Error calculating indicators: {str(e)}")
            return df

    def get_signal(self, symbol):
        """Generate trading signal based on technical analysis"""
        try:
            # Get current timestamp
            current_time = datetime.strptime("2025-03-12 00:03:12", "%Y-%m-%d %H:%M:%S")
            
            # Check cache freshness (5 seconds)
            if (symbol in self.signal_cache and 
                (current_time - self.last_update.get(symbol, datetime.min)).total_seconds() < 5):
                return self.signal_cache[symbol]

            # Get market data
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            if rates is None:
                logging.error(f"Failed to get rates for {symbol}")
                return None, None, None

            df = pd.DataFrame(rates)
            df = self.calculate_indicators(df)

            # Generate signal
            signal, sl_price, tp_price = self.analyze_signals(df, symbol)

            # Cache results
            self.signal_cache[symbol] = (signal, sl_price, tp_price)
            self.last_update[symbol] = current_time

            # Log analysis if signal found
            if signal:
                self.log_signal_analysis(symbol, df, signal, sl_price, tp_price)

            return signal, sl_price, tp_price

        except Exception as e:
            logging.error(f"Error generating signal: {str(e)}")
            return None, None, None

    def analyze_signals(self, df, symbol):
        """Analyze technical indicators for trading signals"""
        try:
            # Get latest values
            current_price = df['close'].iloc[-1]
            ema_fast = df['ema_fast'].iloc[-1]
            ema_slow = df['ema_slow'].iloc[-1]
            ema_long = df['ema_long'].iloc[-1]
            rsi = df['rsi'].iloc[-1]
            atr = df['atr'].iloc[-1]
            
            # Initialize signal scores
            buy_score = 0
            sell_score = 0
            
            # Trend Analysis
            if ema_fast > ema_slow > ema_long:
                buy_score += 2
            elif ema_fast < ema_slow < ema_long:
                sell_score += 2
                
            # RSI Analysis
            if rsi < TradingConfig.RSI_OVERSOLD:
                buy_score += 1
            elif rsi > TradingConfig.RSI_OVERBOUGHT:
                sell_score += 1
                
            # MACD Analysis
            if df['macd'].iloc[-1] > df['macd_signal'].iloc[-1] and \
               df['macd'].iloc[-2] <= df['macd_signal'].iloc[-2]:
                buy_score += 1
            elif df['macd'].iloc[-1] < df['macd_signal'].iloc[-1] and \
                 df['macd'].iloc[-2] >= df['macd_signal'].iloc[-2]:
                sell_score += 1
                
            # Bollinger Bands Analysis
            if current_price < df['BBL_20_2.0'].iloc[-1]:
                buy_score += 1
            elif current_price > df['BBU_20_2.0'].iloc[-1]:
                sell_score += 1
                
            # Generate Signal
            signal = None
            sl_price = None
            tp_price = None
            
            # Minimum score required for signal
            min_score = 3
            
            if buy_score > sell_score and buy_score >= min_score:
                signal = 'BUY'
                sl_price = current_price - (atr * TradingConfig.SL_ATR_MULTIPLIER)
                tp_price = current_price + (atr * TradingConfig.TP_ATR_MULTIPLIER)
            elif sell_score > buy_score and sell_score >= min_score:
                signal = 'SELL'
                sl_price = current_price + (atr * TradingConfig.SL_ATR_MULTIPLIER)
                tp_price = current_price - (atr * TradingConfig.TP_ATR_MULTIPLIER)
                
            return signal, sl_price, tp_price
            
        except Exception as e:
            logging.error(f"Error analyzing signals: {str(e)}")
            return None, None, None

    def log_signal_analysis(self, symbol, df, signal, sl_price, tp_price):
        """Log detailed analysis of the signal"""
        try:
            current_time = datetime.strptime("2025-03-12 00:03:12", "%Y-%m-%d %H:%M:%S")
            
            analysis = f"""
{'='*50}
SIGNAL ANALYSIS - {symbol}
Time: {current_time} UTC
Login: {self.login}
{'='*50}

SIGNAL DETAILS:
Direction: {signal}
Entry Price: {df['close'].iloc[-1]:.5f}
Stop Loss: {sl_price:.5f}
Take Profit: {tp_price:.5f}

TECHNICAL INDICATORS:
EMA Fast: {df['ema_fast'].iloc[-1]:.5f}
EMA Slow: {df['ema_slow'].iloc[-1]:.5f}
EMA Long: {df['ema_long'].iloc[-1]:.5f}
RSI: {df['rsi'].iloc[-1]:.2f}
ATR: {df['atr'].iloc[-1]:.5f}
MACD: {df['macd'].iloc[-1]:.5f}
BB Upper: {df['BBU_20_2.0'].iloc[-1]:.5f}
BB Lower: {df['BBL_20_2.0'].iloc[-1]:.5f}

ANALYSIS SUMMARY:
- Trend Direction: {self.get_trend_description(df)}
- RSI Condition: {self.get_rsi_description(df)}
- Volatility: {self.get_volatility_description(df)}
- Support/Resistance: {self.get_sr_description(df)}

RISK METRICS:
- Risk/Reward Ratio: {abs(tp_price - df['close'].iloc[-1]) / abs(sl_price - df['close'].iloc[-1]):.2f}
- ATR Ratio: {abs(sl_price - df['close'].iloc[-1]) / df['atr'].iloc[-1]:.2f}
{'='*50}
            """
            
            logging.info(analysis)
            
        except Exception as e:
            logging.error(f"Error logging signal analysis: {str(e)}")

    def get_trend_description(self, df):
        """Get trend description"""
        try:
            ema_fast = df['ema_fast'].iloc[-1]
            ema_slow = df['ema_slow'].iloc[-1]
            ema_long = df['ema_long'].iloc[-1]
            
            if ema_fast > ema_slow > ema_long:
                return "UPTREND (Strong)"
            elif ema_fast > ema_slow and ema_slow < ema_long:
                return "UPTREND (Weak)"
            elif ema_fast < ema_slow < ema_long:
                return "DOWNTREND (Strong)"
            elif ema_fast < ema_slow and ema_slow > ema_long:
                return "DOWNTREND (Weak)"
            else:
                return "SIDEWAYS"
                
        except Exception as e:
            logging.error(f"Error getting trend description: {str(e)}")
            return "UNKNOWN"

    def get_rsi_description(self, df):
        """Get RSI condition description"""
        try:
            rsi = df['rsi'].iloc[-1]
            
            if rsi > TradingConfig.RSI_OVERBOUGHT:
                return f"OVERBOUGHT ({rsi:.2f})"
            elif rsi < TradingConfig.RSI_OVERSOLD:
                return f"OVERSOLD ({rsi:.2f})"
            else:
                return f"NEUTRAL ({rsi:.2f})"
                
        except Exception as e:
            logging.error(f"Error getting RSI description: {str(e)}")
            return "UNKNOWN"

    def get_volatility_description(self, df):
        """Get volatility description"""
        try:
            atr = df['atr'].iloc[-1]
            atr_avg = df['atr'].mean()
            
            ratio = atr / atr_avg
            
            if ratio > 1.5:
                return f"HIGH (ATR: {atr:.5f})"
            elif ratio < 0.5:
                return f"LOW (ATR: {atr:.5f})"
            else:
                return f"NORMAL (ATR: {atr:.5f})"
                
        except Exception as e:
            logging.error(f"Error getting volatility description: {str(e)}")
            return "UNKNOWN"

    def get_sr_description(self, df):
        """Get support/resistance description"""
        try:
            current_price = df['close'].iloc[-1]
            bb_upper = df['BBU_20_2.0'].iloc[-1]
            bb_lower = df['BBL_20_2.0'].iloc[-1]
            
            if current_price > bb_upper:
                return f"Above resistance ({bb_upper:.5f})"
            elif current_price < bb_lower:
                return f"Below support ({bb_lower:.5f})"
            else:
                return f"Between S/R ({bb_lower:.5f} - {bb_upper:.5f})"
                
        except Exception as e:
            logging.error(f"Error getting S/R description: {str(e)}")
            return "UNKNOWN"