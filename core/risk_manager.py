import MetaTrader5 as mt5
import logging
from datetime import datetime
from ..config.trading_config import TradingConfig

class RiskManager:
    def __init__(self):
        self.daily_stats = {
            'trades': 0,
            'loss': 0,
            'profit': 0,
            'drawdown': 0,
            'peak_balance': 0
        }
        self.reset_daily_stats()

    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_stats = {
            'trades': 0,
            'loss': 0,
            'profit': 0,
            'drawdown': 0,
            'peak_balance': self.get_account_equity()
        }

    def calculate_position_size(self, symbol, sl_price):
        """Calculate position size based on risk parameters"""
        try:
            # Get account info
            account_info = mt5.account_info()
            if not account_info:
                logging.error("Failed to get account info")
                return 0.01  # Default minimum lot
                
            equity = account_info.equity
            risk_amount = equity * TradingConfig.RISK_PERCENT / 100
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logging.error(f"Failed to get symbol info for {symbol}")
                return 0.01
                
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                logging.error(f"Failed to get tick info for {symbol}")
                return 0.01
                
            current_price = tick.ask
            
            # Calculate pip value
            point = symbol_info.point
            pip_size = point * 10
            
            # Calculate SL distance in pips
            sl_distance = abs(current_price - sl_price) / pip_size
            
            # Calculate pip value
            contract_size = symbol_info.trade_contract_size
            
            if symbol[-3:] == "JPY":
                pip_value = (pip_size * contract_size) / current_price
            else:
                pip_value = pip_size * contract_size
                
            # Calculate lot size
            if sl_distance > 0 and pip_value > 0:
                lot_size = risk_amount / (sl_distance * pip_value)
            else:
                lot_size = 0.01
                
            # Normalize lot size
            lot_size = self.normalize_lot_size(symbol, lot_size)
            
            logging.info(f"""
            Position Size Calculation for {symbol}:
            - Equity: ${equity:.2f}
            - Risk Amount: ${risk_amount:.2f}
            - SL Distance: {sl_distance:.1f} pips
            - Pip Value: ${pip_value:.5f}
            - Calculated Lot: {lot_size:.2f}
            """)
            
            return lot_size
            
        except Exception as e:
            logging.error(f"Error calculating position size: {str(e)}")
            return 0.01

    def normalize_lot_size(self, symbol, lot_size):
        """Normalize lot size according to symbol requirements"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return 0.01
                
            # Get lot limits
            min_lot = symbol_info.volume_min
            max_lot = symbol_info.volume_max
            lot_step = symbol_info.volume_step
            
            # Round to nearest valid lot size
            normalized_lot = round(lot_size / lot_step) * lot_step
            
            # Ensure within limits
            normalized_lot = max(min_lot, min(normalized_lot, max_lot))
            
            return normalized_lot
            
        except Exception as e:
            logging.error(f"Error normalizing lot size: {str(e)}")
            return 0.01

    def can_open_trade(self, symbol):
        """Check if new trade can be opened"""
        try:
            # Check daily loss limit
            if self.daily_stats['loss'] >= self.get_max_daily_loss():
                logging.warning("Daily loss limit reached")
                return False
                
            # Check maximum trades
            if self.daily_stats['trades'] >= TradingConfig.MAX_TOTAL_TRADES:
                logging.warning("Maximum daily trades reached")
                return False
                
            # Check symbol-specific trades
            symbol_trades = self.count_symbol_trades(symbol)
            if symbol_trades >= TradingConfig.MAX_TRADES_PER_SYMBOL:
                logging.warning(f"Maximum trades for {symbol} reached")
                return False
                
            # Check drawdown
            current_drawdown = self.calculate_drawdown()
            if current_drawdown > TradingConfig.MAX_DAILY_LOSS_PERCENT:
                logging.warning(f"Maximum drawdown reached: {current_drawdown:.2f}%")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Error checking trade conditions: {str(e)}")
            return False

    def count_symbol_trades(self, symbol):
        """Count open trades for specific symbol"""
        try:
            positions = mt5.positions_get(symbol=symbol)
            if positions is None:
                return 0
            return len(positions)
            
        except Exception as e:
            logging.error(f"Error counting symbol trades: {str(e)}")
            return 0

    def get_account_equity(self):
        """Get current account equity"""
        try:
            account_info = mt5.account_info()
            if account_info:
                return account_info.equity
            return 0
            
        except Exception as e:
            logging.error(f"Error getting account equity: {str(e)}")
            return 0

    def get_max_daily_loss(self):
        """Calculate maximum daily loss amount"""
        try:
            account_info = mt5.account_info()
            if account_info:
                return account_info.balance * TradingConfig.MAX_DAILY_LOSS_PERCENT / 100
            return 0
            
        except Exception as e:
            logging.error(f"Error calculating max daily loss: {str(e)}")
            return 0

    def calculate_drawdown(self):
        """Calculate current drawdown percentage"""
        try:
            current_equity = self.get_account_equity()
            if self.daily_stats['peak_balance'] > 0:
                drawdown = ((self.daily_stats['peak_balance'] - current_equity) / 
                          self.daily_stats['peak_balance'] * 100)
                return max(0, drawdown)
            return 0
            
        except Exception as e:
            logging.error(f"Error calculating drawdown: {str(e)}")
            return 0

    def update_stats(self, profit):
        """Update daily trading statistics"""
        try:
            self.daily_stats['trades'] += 1
            
            if profit > 0:
                self.daily_stats['profit'] += profit
            else:
                self.daily_stats['loss'] -= profit
                
            current_equity = self.get_account_equity()
            if current_equity > self.daily_stats['peak_balance']:
                self.daily_stats['peak_balance'] = current_equity
                
            self.daily_stats['drawdown'] = self.calculate_drawdown()
            
        except Exception as e:
            logging.error(f"Error updating stats: {str(e)}")

    def check_new_day(self):
        """Check and reset daily statistics if needed"""
        try:
            current_day = datetime.now().date()
            if not hasattr(self, 'last_reset_day'):
                self.last_reset_day = current_day
                return
                
            if current_day > self.last_reset_day:
                self.reset_daily_stats()
                self.last_reset_day = current_day
                logging.info("Daily statistics reset")
                
        except Exception as e:
            logging.error(f"Error checking new day: {str(e)}")