import MetaTrader5 as mt5
import threading
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from ..config.trading_config import TradingConfig

class PositionManager:
    def __init__(self):
        self.positions = {}  # Track active positions
        self.trade_lock = threading.Lock()
        self.last_check = datetime.now()

    def open_trade(self, symbol, trade_type, lot_size, sl_price, tp_price=None):
        """Open new trading position"""
        try:
            with self.trade_lock:
                if not self.check_connection():
                    return None

                # Get latest price
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    logging.error(f"Failed to get tick info for {symbol}")
                    return None

                # Set entry price based on trade type
                entry_price = tick.ask if trade_type == 'BUY' else tick.bid
                
                # Calculate TP if not provided
                if tp_price is None:
                    if trade_type == 'BUY':
                        tp_price = entry_price + ((entry_price - sl_price) * 
                                                TradingConfig.TP_ATR_MULTIPLIER / 
                                                TradingConfig.SL_ATR_MULTIPLIER)
                    else:
                        tp_price = entry_price - ((sl_price - entry_price) * 
                                                TradingConfig.TP_ATR_MULTIPLIER / 
                                                TradingConfig.SL_ATR_MULTIPLIER)

                # Create trade request
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot_size,
                    "type": mt5.ORDER_TYPE_BUY if trade_type == 'BUY' else mt5.ORDER_TYPE_SELL,
                    "price": entry_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "deviation": 10,  # Maximum price deviation in points
                    "magic": 123456,  # Expert Advisor ID
                    "comment": f"MT5 Bot Trade - {datetime.now()} - Login: zzzz14",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_FOK,
                }

                # Send trade request
                result = mt5.order_send(request)
                
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"""
                    Failed to open trade for {symbol}
                    Error code: {result.retcode}
                    Error description: {mt5.last_error()}
                    Comment: {result.comment}
                    Request: {request}
                    """)
                    return None
                else:
                    trade_info = {
                        'ticket': result.order,
                        'symbol': symbol,
                        'type': trade_type,
                        'volume': lot_size,
                        'entry_price': entry_price,
                        'sl': sl_price,
                        'tp': tp_price,
                        'open_time': datetime.now(),
                        'trailing_activated': False
                    }
                    
                    self.positions[result.order] = trade_info
                    
                    logging.info(f"""
                    Trade opened successfully:
                    - Symbol: {symbol}
                    - Type: {trade_type}
                    - Volume: {lot_size}
                    - Entry: {entry_price}
                    - SL: {sl_price}
                    - TP: {tp_price}
                    - Ticket: {result.order}
                    - Time: {datetime.now()}
                    - Account: zzzz14
                    """)
                    
                    return result.order

        except Exception as e:
            logging.error(f"Error opening trade: {str(e)}")
            return None

    def manage_positions(self):
        """Manage all open positions"""
        try:
            if not mt5.initialize():
                return

            positions = mt5.positions_get()
            if positions is None:
                return

            current_time = datetime.now()
            
            for position in positions:
                if position.magic != 123456:  # Skip non-bot trades
                    continue

                # Update trailing stop
                if TradingConfig.TRAILING_STOP:
                    self.update_trailing_stop(position)

                # Check breakeven
                self.check_breakeven(position)

                # Check position age
                self.check_position_age(position)

            self.last_check = current_time

        except Exception as e:
            logging.error(f"Error managing positions: {str(e)}")
        finally:
            mt5.shutdown()

    def update_trailing_stop(self, position):
        """Update trailing stop for position"""
        try:
            symbol = position.symbol
            position_id = position.ticket
            current_sl = position.sl
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return

            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return

            # Calculate ATR-based trail amount
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, TradingConfig.ATR_PERIOD)
            if rates is None:
                return
                
            df = pd.DataFrame(rates)
            atr = ta.atr(df['high'], df['low'], df['close'], length=TradingConfig.ATR_PERIOD).iloc[-1]
            trail_amount = atr * TradingConfig.TRAILING_STOP_ACTIVATION

            # Update stop loss if needed
            if position.type == mt5.POSITION_TYPE_BUY:
                new_sl = tick.bid - trail_amount
                if new_sl > current_sl:
                    self.modify_sl(position_id, new_sl)
            else:  # SELL
                new_sl = tick.ask + trail_amount
                if new_sl < current_sl or current_sl == 0:
                    self.modify_sl(position_id, new_sl)

        except Exception as e:
            logging.error(f"Error updating trailing stop: {str(e)}")

    def check_breakeven(self, position):
        """Move stop loss to breakeven if conditions met"""
        try:
            # Calculate profit in ATR units
            rates = mt5.copy_rates_from_pos(position.symbol, mt5.TIMEFRAME_M5, 0, TradingConfig.ATR_PERIOD)
            if rates is None:
                return
                
            df = pd.DataFrame(rates)
            atr = ta.atr(df['high'], df['low'], df['close'], length=TradingConfig.ATR_PERIOD).iloc[-1]
            
            profit_threshold = atr * TradingConfig.BREAKEVEN_ACTIVATION
            
            if position.profit >= profit_threshold:
                entry_price = position.price_open
                current_sl = position.sl

                if position.type == mt5.POSITION_TYPE_BUY and current_sl < entry_price:
                    self.modify_sl(position.ticket, entry_price)
                elif position.type == mt5.POSITION_TYPE_SELL and (current_sl > entry_price or current_sl == 0):
                    self.modify_sl(position.ticket, entry_price)

        except Exception as e:
            logging.error(f"Error checking breakeven: {str(e)}")

    def modify_sl(self, ticket, new_sl):
        """Modify stop loss for position"""
        try:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": new_sl,
                "magic": 123456
            }
            
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Failed to modify SL. Error code: {result.retcode}")
            else:
                logging.info(f"Modified SL for position #{ticket} to {new_sl}")

        except Exception as e:
            logging.error(f"Error modifying SL: {str(e)}")

    def check_position_age(self, position):
        """Check and handle old positions"""
        try:
            # Maximum position age (24 hours)
            max_age = 24 * 60 * 60  # seconds
            
            position_age = (datetime.now() - position.time).total_seconds()
            
            if position_age > max_age:
                logging.warning(f"Position #{position.ticket} is older than 24 hours")
                
                # Optional: Close old positions
                if TradingConfig.CLOSE_OLD_POSITIONS:
                    self.close_position(position.ticket)

        except Exception as e:
            logging.error(f"Error checking position age: {str(e)}")

    def close_position(self, ticket):
        """Close specific position"""
        try:
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                return False

            # Create close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": position[0].symbol,
                "volume": position[0].volume,
                "type": mt5.ORDER_TYPE_SELL if position[0].type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "price": mt5.symbol_info_tick(position[0].symbol).bid if position[0].type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(position[0].symbol).ask,
                "deviation": 10,
                "magic": 123456,
                "comment": f"MT5 Bot Close - {datetime.now()} - Login: zzzz14",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }

            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Failed to close position #{ticket}. Error code: {result.retcode}")
                return False
            
            logging.info(f"Position #{ticket} closed successfully")
            return True

        except Exception as e:
            logging.error(f"Error closing position: {str(e)}")
            return False

    def close_all_positions(self):
        """Close all bot positions"""
        try:
            positions = mt5.positions_get()
            if positions is None:
                return

            for position in positions:
                if position.magic == 123456:  # Only close bot positions
                    self.close_position(position.ticket)

        except Exception as e:
            logging.error(f"Error closing all positions: {str(e)}")

    def check_connection(self):
        """Check MT5 connection"""
        if not mt5.initialize():
            logging.error("Failed to initialize MT5 connection")
            return False
        return True