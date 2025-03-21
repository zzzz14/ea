import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
import logging
import numpy as np
from datetime import datetime, timedelta
import threading
import json
import os
import requests
from scipy import stats

# Setup logging dengan rotasi file
from logging.handlers import RotatingFileHandler

# Membuat direktori logs jika belum ada
if not os.path.exists('logs'):
    os.makedirs('logs')

# Setup rotating log handler
log_file = f'logs/trading_bot_{datetime.now().strftime("%Y%m%d")}.log'
rotating_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        rotating_handler,
        logging.StreamHandler()  # Tambahkan output ke console juga
    ]
)

# Konfigurasi akun MT5
class MT5Config:
    LOGIN_ID = 101657921  # Ganti dengan ID akun MT5 kamu
    PASSWORD = "8~2Jpg#A" # Ganti dengan password akun kamu
    SERVER = "FBS-Demo"  # Ganti dengan nama server broker kamu
    SYMBOLS = []
    TIMEFRAME_MAIN = mt5.TIMEFRAME_M1
    TIMEFRAME_TREND = mt5.TIMEFRAME_M5
    TIMEFRAME_LONG = mt5.TIMEFRAME_M15  # Timeframe tambahan untuk konfirmasi tren jangka panjang

    @classmethod
    def load_symbols(cls, include_forex=True, include_crypto=True, use_dynamic=True):
        """Load symbols: bisa pilih dynamic/static dan filter kategori."""
        if use_dynamic:
            if not mt5.initialize():
                logging.error("Gagal menghubungkan ke MT5 untuk mengambil simbol!")
                return
            
            symbols = mt5.symbols_get()
            if symbols:
                filtered_symbols = []
                for symbol in symbols:
                    name = symbol.name.upper()
                    
                    # Filter Forex (6 karakter + pasangan mata uang utama)
                    if include_forex and len(name) == 6 and name[-3:] in ["USD", "EUR", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD"]:
                        filtered_symbols.append(name)
                    
                    # Filter Crypto (biasanya ada 'USD' atau nama koin populer)
                    if include_crypto and ("XAU" in name or "BTC" in name or "ETH" in name or "DOGE" in name):
                        filtered_symbols.append(name)
                
                cls.SYMBOLS = list(set(filtered_symbols))  # Hilangkan simbol duplikat
                logging.info(f"{len(cls.SYMBOLS)} simbol berhasil dimuat (Forex: {include_forex}, Crypto: {include_crypto})")
            else:
                logging.warning("Tidak ada simbol yang ditemukan di MT5.")
            
            mt5.shutdown()
        else:
            logging.info(f"Menggunakan simbol statis: {cls.SYMBOLS}")

# Konfigurasi strategi dengan parameter yang dioptimalkan
class TradingConfig:
    MAX_TRADES_PER_PAIR = 2
    MAX_TOTAL_TRADES = 2  # Kurangi jumlah maksimum trade simultan untuk mengelola risiko
    RISK_PERCENT = 0.1  # Risiko 1% per trade
    PROFIT_TARGET_PERCENT = 0.5  # Target profit 1.5% dari ekuitas per trade
    MAX_DAILY_LOSS_PERCENT = 10000000000000000000000000000000000000000000  # Maksimal kerugian harian
    MAX_DRAWDOWN_PERCENT = 60  # Maksimal drawdown sebelum berhenti trading
    
    # Indikator Teknikal
    EMA_FAST = 8
    EMA_SLOW = 14
    EMA_LONG = 50  # EMA jangka panjang untuk filter tren
    RSI_PERIOD = 8
    RSI_OVERBOUGHT_MIN = 70
    RSI_OVERBOUGHT_MAX = 90
    RSI_OVERSOLD_MIN = 10
    RSI_OVERSOLD_MAX = 30   
    ATR_PERIOD = 14  # Tingkatkan periode ATR untuk pengukuran volatilitas yang lebih stabil
    BB_LENGTH = 20
    BB_STD = 2.0
    SR_LENGTH = 15
    ADX_PERIOD = 14
    ADX_THRESHOLD = 15  # Turunkan threshold ADX untuk capture lebih banyak tren
    
    # Money Management
    TP_ATR_MULTIPLIER = 1.5
    SL_ATR_MULTIPLIER = 3
    TRAILING_STOP_ACTIVATION = 0.2  # Aktivasi trailing stop setelah profit 1x ATR
    BREAKEVEN_ACTIVATION = 0.8  # Pindahkan ke breakeven setelah profit 0.8x ATR
    
    # Fitur Keamanan
    MAX_SPREAD_MULTIPLIER = 1.7  # Maksimal spread relatif terhadap spread rata-rata
    SLIPPAGE_POINTS = 10
    RECONNECT_ATTEMPTS = 3
    RECONNECT_WAIT_TIME = 10  # Waktu tunggu dalam detik antar percobaan koneksi
    
    # Fitur Tambahan
    ENABLE_TELEGRAM_NOTIFICATIONS = False  # Set True untuk mengaktifkan notifikasi
    SIMULATE_ONLY = False  # Set True untuk mode simulasi (tidak eksekusi trade riil)
    MARKET_SESSIONS = {
        'asian': {'start': 1, 'end': 9},  # Jam dalam UTC
        'european': {'start': 7, 'end': 16},
        'american': {'start': 13, 'end': 24}
    }


# Konfigurasi Telegram Bot (opsional)
class TelegramConfig:
    BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    CHAT_ID = "YOUR_CHAT_ID"
    
class Stats:
    """Kelas untuk melacak statistik dan kinerja trading"""
    def __init__(self, stats_file='trading_stats_acc5$new.json'):
        self.stats_file = stats_file
        self.stats = self.load_stats()
        
    def load_stats(self):
        """Load statistik dari file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as file:
                    return json.load(file)
            except Exception as e:
                logging.error(f"Error loading stats: {str(e)}")
        
        # Default stats jika file tidak ada atau error
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'profit_sum': 0.0,
            'loss_sum': 0.0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'peak_balance': 0.0,
            'trades_by_symbol': {},
            'daily_results': {},
            'monthly_results': {},
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def save_stats(self):
        """Simpan statistik ke file"""
        try:
            with open(self.stats_file, 'w') as file:
                json.dump(self.stats, file, indent=4)
        except Exception as e:
            logging.error(f"Error saving stats: {str(e)}")
    
    def update_after_trade(self, symbol, profit, trade_type):
        """Update statistik setelah trade selesai"""
        today = datetime.now().strftime('%Y-%m-%d')
        month = datetime.now().strftime('%Y-%m')
        
        # Update total trades
        self.stats['total_trades'] += 1
        
        # Update trades by result
        if profit > 0:
            self.stats['winning_trades'] += 1
            self.stats['profit_sum'] += profit
        else:
            self.stats['losing_trades'] += 1
            self.stats['loss_sum'] += abs(profit)
        
        # Update trades by symbol
        if symbol not in self.stats['trades_by_symbol']:
            self.stats['trades_by_symbol'][symbol] = {'total': 0, 'win': 0, 'loss': 0, 'profit': 0.0}
        
        self.stats['trades_by_symbol'][symbol]['total'] += 1
        if profit > 0:
            self.stats['trades_by_symbol'][symbol]['win'] += 1
        else:
            self.stats['trades_by_symbol'][symbol]['loss'] += 1
        self.stats['trades_by_symbol'][symbol]['profit'] += profit
        
        # Update daily results
        if today not in self.stats['daily_results']:
            self.stats['daily_results'][today] = {'trades': 0, 'profit': 0.0}
        
        self.stats['daily_results'][today]['trades'] += 1
        self.stats['daily_results'][today]['profit'] += profit
        
        # Update monthly results
        if month not in self.stats['monthly_results']:
            self.stats['monthly_results'][month] = {'trades': 0, 'profit': 0.0}
        
        self.stats['monthly_results'][month]['trades'] += 1
        self.stats['monthly_results'][month]['profit'] += profit
        
        # Update drawdown metrics
        try:
            account_info = mt5.account_info()
            if account_info:
                current_balance = account_info.balance
                
                # Update peak balance
                if current_balance > self.stats['peak_balance']:
                    self.stats['peak_balance'] = current_balance
                
                # Calculate current drawdown
                if self.stats['peak_balance'] > 0:
                    current_dd = (self.stats['peak_balance'] - current_balance) / self.stats['peak_balance'] * 100
                    self.stats['current_drawdown'] = current_dd
                    
                    # Update max drawdown if needed
                    if current_dd > self.stats['max_drawdown']:
                        self.stats['max_drawdown'] = current_dd
        except Exception as e:
            logging.error(f"Error updating drawdown stats: {str(e)}")
        
        # Update timestamp
        self.stats['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save to file
        self.save_stats()
    
    def get_win_rate(self):
        """Hitung win rate secara keseluruhan"""
        if self.stats['total_trades'] == 0:
            return 0
        return (self.stats['winning_trades'] / self.stats['total_trades']) * 100
    
    def get_profit_factor(self):
        """Hitung profit factor (gross profit / gross loss)"""
        if self.stats['loss_sum'] == 0:
            return float('inf')  # Tidak ada loss
        return self.stats['profit_sum'] / self.stats['loss_sum']
    
    def get_symbol_performance(self, symbol):
        """Dapatkan performa untuk simbol tertentu"""
        if symbol not in self.stats['trades_by_symbol']:
            return None
        
        symbol_stats = self.stats['trades_by_symbol'][symbol]
        win_rate = 0 if symbol_stats['total'] == 0 else (symbol_stats['win'] / symbol_stats['total']) * 100
        
        return {
            'total_trades': symbol_stats['total'],
            'win_rate': win_rate,
            'profit': symbol_stats['profit']
        }

class MT5Trader:
    def __init__(self):
        self.connected = False
        self.stats = Stats()
        self.last_signals = {}  # Simpan sinyal terakhir
        self.average_spreads = {}  # Simpan spread rata-rata
        self.indicators_cache = {}  # Cache untuk data indikator
        self.connection_attempts = 0
        self.exit_flag = False  # Flag untuk stop bot
        self.trade_lock = threading.Lock()  # Lock untuk operasi trading (thread safety)
        
        # Dictionary untuk menyimpan data pasar
        self.market_data = {
            'atr_values': {},
            'volatility_index': {},
            'support_levels': {},
            'resistance_levels': {}
        }
    
    def connect(self):
        try:
            # Tambah usleep sebelum initialize untuk menghindari masalah
            time.sleep(0.5)
            
            # Reset MT5 jika sudah diinisialisasi
            if mt5.terminal_info() is not None:
                mt5.shutdown()
                time.sleep(1)
            
            if not mt5.initialize():
                logging.error(f"Gagal menghubungkan ke MetaTrader 5: {mt5.last_error()}")
                self.connection_attempts += 1
                return False
                
            if not mt5.login(MT5Config.LOGIN_ID, MT5Config.PASSWORD, MT5Config.SERVER):
                logging.error(f"Gagal login ke akun {MT5Config.LOGIN_ID}. Error: {mt5.last_error()}")
                mt5.shutdown()
                self.connection_attempts += 1
                return False
           
            self.connected = True
            self.connection_attempts = 0  # Reset counter
            logging.info(f"Berhasil login ke akun {MT5Config.LOGIN_ID} di server {MT5Config.SERVER}")
            
            # Tambahkan cek koneksi dan informasi akun
            account_info = mt5.account_info()
            if account_info:
                logging.info(f"Akun: {account_info.login}, Balance: ${account_info.balance:.2f}, Equity: ${account_info.equity:.2f}")
                
                # Initialize peak balance saat pertama kali connect
                if self.stats.stats['peak_balance'] == 0:
                    self.stats.stats['peak_balance'] = account_info.balance
                    self.stats.save_stats()
            
            # Initialize symbol data for all trading symbols
            for symbol in MT5Config.SYMBOLS:
                if not mt5.symbol_select(symbol, True):
                    logging.warning(f"Simbol {symbol} tidak tersedia")
                else:
                    # Simpan spread awal untuk referensi
                    symbol_info = mt5.symbol_info(symbol)
                    if symbol_info:
                        self.average_spreads[symbol] = symbol_info.spread
                        logging.info(f"Simbol {symbol} siap. Spread: {symbol_info.spread} points, Tick Value: {symbol_info.trade_tick_value}")
            
            return True
        except Exception as e:
            logging.error(f"Exception saat connect: {str(e)}")
            self.connection_attempts += 1
            return False
    def run_trading_cycle(self):
        try:
            if not self.check_connection():
                return
            
            # Manage existing positions
            self.manage_open_positions()
        
            # Update statistics
            self.update_statistics()
        
            # Check for new trading opportunities
            for symbol in MT5Config.SYMBOLS:
            # Check if trading is allowed for this symbol
                if not self.check_trade_allowed(symbol):
                    continue
                
                # Get signal
            signal, sl_price = self.get_signal(symbol)
            
            if signal:
                # Calculate lot size based on risk management
                sl_points = 0
                
                if sl_price:
                    tick = mt5.symbol_info_tick(symbol)
                    if signal == 'BUY':
                        sl_points = abs(tick.ask - sl_price) / mt5.symbol_info(symbol).point
                    else:  # SELL
                        sl_points = abs(tick.bid - sl_price) / mt5.symbol_info(symbol).point
                
                if sl_points > 0:
                    lot_size = self.calculate_lot_size(symbol, sl_points)
                    
                    if lot_size > 0:
                        # Open trade
                        self.open_trade(symbol, signal, lot_size, sl_price)
        
        except Exception as e:
            logging.error(f"Error in trading cycle: {str(e)}")
      
    def run(self):
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
                    self.run_trading_cycle()
                except Exception as e:
                    logging.error(f"Error in trading cycle: {str(e)}")
                
            # Sleep between cycles
            time.sleep(3)      
        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
        finally:
            self.disconnect()
            logging.info("Trading bot stopped")

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logging.info("Disconnected from MT5")
    
    def check_connection(self):
        if not self.connected or not mt5.terminal_info():
            logging.warning("Koneksi terputus, mencoba menghubungkan kembali...")
            
            # Exponential backoff for reconnection attempts
            if self.connection_attempts < TradingConfig.RECONNECT_ATTEMPTS:
                wait_time = TradingConfig.RECONNECT_WAIT_TIME * (2 ** self.connection_attempts)
                logging.info(f"Menunggu {wait_time} detik sebelum mencoba koneksi ulang...")
                time.sleep(wait_time)
                return self.connect()
            else:
                logging.error(f"Gagal menghubungkan kembali setelah {TradingConfig.RECONNECT_ATTEMPTS} percobaan")
                return False
                
        return True
    
    def send_telegram_notification(self, message):
        """Kirim notifikasi ke Telegram"""
        if not TradingConfig.ENABLE_TELEGRAM_NOTIFICATIONS:
            return
            
        try:
            url = f"https://api.telegram.org/bot{TelegramConfig.BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TelegramConfig.CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                logging.error(f"Failed to send Telegram notification: {response.text}")
        except Exception as e:
            logging.error(f"Error sending Telegram notification: {str(e)}")
    
    def calculate_lot_size(self, symbol, sl_pips):
        try:
            account_info = mt5.account_info()
            if not account_info:
                logging.error("Gagal mendapatkan info akun")
                return 0.01  # default minimum lot
                
            equity = account_info.equity
            risk_amount = equity * TradingConfig.RISK_PERCENT / 100
            
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logging.error(f"Gagal mendapatkan info simbol {symbol}")
                return 0.01
                
            # Tambahkan validasi bahwa simbol dapat diperdagangkan
            if symbol_info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                logging.warning(f"Simbol {symbol} tidak dapat diperdagangkan sepenuhnya (Mode: {symbol_info.trade_mode})")
                if symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                    return 0  # Trading dinonaktifkan untuk simbol ini
            
            # Hitung nilai per pip
            contract_size = symbol_info.trade_contract_size
            price = mt5.symbol_info_tick(symbol).ask
            
            # Untuk pasangan mata uang
            if 'USD' in symbol or 'JPY' in symbol:
                if 'JPY' in symbol:
                    point_value = symbol_info.point * 100  # Untuk pair JPY, 1 pip biasanya 0.01
                else:
                    point_value = symbol_info.point * 10   # Untuk pair non-JPY, 1 pip biasanya 0.0001
                
                pip_value = (point_value * contract_size) / price if 'USD' not in symbol[:3] else (point_value * contract_size)
            else:  # Untuk instrumen lain seperti XAUUSD
                pip_value = symbol_info.point * contract_size
                
            # Hitung lot size berdasarkan risiko
            if pip_value > 0 and sl_pips > 0:
                lot_size = risk_amount / (sl_pips * pip_value)
            else:
                lot_size = 0.01
                
            # Batasi ke minimum dan maksimum lot
            min_lot = symbol_info.volume_min
            max_lot = min(symbol_info.volume_max, 1.0)  # Batasi maksimum ke 1 lot untuk keamanan
            step = symbol_info.volume_step
            
            # Bulatkan ke step lot
            lot_size = min_lot + step * round((lot_size - min_lot) / step)
            lot_size = max(min_lot, min(lot_size, max_lot))
            
            logging.info(f"Lot size untuk {symbol} dengan SL {sl_pips} pips dan risiko {TradingConfig.RISK_PERCENT}%: {lot_size}")
            return lot_size
        except Exception as e:
            logging.error(f"Error calculating lot size: {str(e)}")
            return 0.01  # default minimal lot
    
    def check_market_session(self):
        """Periksa sesi market yang aktif saat ini"""
        hour_utc = datetime.now().hour
        active_sessions = []
        
        for session, times in TradingConfig.MARKET_SESSIONS.items():
            start = times['start']
            end = times['end']
            
            # Handle sessions that span overnight
            if start <= end:
                if start <= hour_utc < end:
                    active_sessions.append(session)
            else:  # Session spans overnight
                if hour_utc >= start or hour_utc < end:
                    active_sessions.append(session)
        
        return active_sessions
    
    def check_volatility(self, symbol):
        """Check if the market is too volatile"""
        try:
            # Get current ATR
            if symbol in self.market_data['atr_values']:
                current_atr = self.market_data['atr_values'][symbol]
            else:
                rates = mt5.copy_rates_from_pos(symbol, MT5Config.TIMEFRAME_MAIN, 0, 100)
                if rates is None or len(rates) == 0:
                    return False
                df = pd.DataFrame(rates)
                current_atr = ta.atr(df['high'], df['low'], df['close'], length=TradingConfig.ATR_PERIOD).iloc[-1]
                self.market_data['atr_values'][symbol] = current_atr
            
            # Get historical ATR for comparison
            rates = mt5.copy_rates_from_pos(symbol, MT5Config.TIMEFRAME_MAIN, 0, 200)
            if rates is None or len(rates) == 0:
                return False
            df = pd.DataFrame(rates)
            atr = ta.atr(df['high'], df['low'], df['close'], length=TradingConfig.ATR_PERIOD)
            avg_atr = atr.mean()
            atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1
            
            # Check if too volatile or too quiet
            too_volatile = atr_ratio > 2.0
            too_quiet = atr_ratio < 0.3
            
            if too_volatile:
                logging.info(f"{symbol} volatilitas terlalu tinggi (ATR Ratio: {atr_ratio:.2f})")
            elif too_quiet:
                logging.info(f"{symbol} volatilitas terlalu rendah (ATR Ratio: {atr_ratio:.2f})")
                
            return not (too_volatile or too_quiet)
        except Exception as e:
            logging.error(f"Error checking volatility for {symbol}: {str(e)}")
            return False
    
    def check_spread(self, symbol):
        """Check if spread is acceptable"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return False
                
            current_spread = symbol_info.spread
            
            # Update average spread with exponential moving average
            if symbol in self.average_spreads:
                self.average_spreads[symbol] = 0.9 * self.average_spreads[symbol] + 0.1 * current_spread
            else:
                self.average_spreads[symbol] = current_spread
                
            # Check if current spread is too high compared to average
            if self.average_spreads[symbol] > 0:
                spread_ratio = current_spread / self.average_spreads[symbol]
                
                if spread_ratio > TradingConfig.MAX_SPREAD_MULTIPLIER:
                    logging.info(f"{symbol} spread terlalu tinggi: {current_spread} points (ratio: {spread_ratio:.2f})")
                    return False
                    
            return True
        except Exception as e:
            logging.error(f"Error checking spread for {symbol}: {str(e)}")
            return False
    
    def is_trending(self, symbol):
        try:
            # Gunakan cache jika tersedia
            cache_key = f"{symbol}_trend_{MT5Config.TIMEFRAME_TREND}"
            if cache_key in self.indicators_cache:
                cache_data = self.indicators_cache[cache_key]
                # Gunakan cache jika masih fresh (kurang dari 5 menit)
                if (datetime.now() - cache_data['timestamp']).total_seconds() < 300:
                    return cache_data['value']
            
            rates = mt5.copy_rates_from_pos(symbol, MT5Config.TIMEFRAME_TREND, 0, 100)
            if rates is None or len(rates) == 0:
                logging.warning(f"Gagal mendapatkan data rates untuk {symbol}")
                return False
                
            df = pd.DataFrame(rates)
            adx = ta.adx(df['high'], df['low'], df['close'], length=TradingConfig.ADX_PERIOD)
            current_adx = adx[f'ADX_{TradingConfig.ADX_PERIOD}'].iloc[-1]
            
            is_trend = current_adx > TradingConfig.ADX_THRESHOLD
            
            # Simpan ke cache
            self.indicators_cache[cache_key] = {
                'value': is_trend,
                'timestamp': datetime.now()
            }
            
            logging.info(f"{symbol} ADX: {current_adx:.2f} - {'Trending' if is_trend else 'Ranging'}")
            return is_trend
        except Exception as e:
            logging.error(f"Error checking trend: {str(e)}")
            return False
    
    def check_higher_tf_trend(self, symbol):
        try:
            # Gunakan cache jika tersedia
            cache_key = f"{symbol}_higher_trend_{MT5Config.TIMEFRAME_TREND}"
            if cache_key in self.indicators_cache:
                cache_data = self.indicators_cache[cache_key]
                # Gunakan cache jika masih fresh (kurang dari 15 menit)
                if (datetime.now() - cache_data['timestamp']).total_seconds() < 900:
                    return cache_data['value']
            
            rates = mt5.copy_rates_from_pos(symbol, MT5Config.TIMEFRAME_TREND, 0, 100)
            if rates is None or len(rates) == 0:
                logging.warning(f"Gagal mendapatkan data trend untuk {symbol}")
                return None
            
            df = pd.DataFrame(rates)
            df['ema_fast'] = df['close'].ewm(span=TradingConfig.EMA_FAST, adjust=False).mean()
            df['ema_slow'] = df['close'].ewm(span=TradingConfig.EMA_SLOW, adjust=False).mean()
            df['ema_long'] = df['close'].ewm(span=TradingConfig.EMA_LONG, adjust=False).mean()
            
            # Check price in relation to EMAs
            last_close = df['close'].iloc[-1]
            ema_fast = df['ema_fast'].iloc[-1]
            ema_slow = df['ema_slow'].iloc[-1]
            ema_long = df['ema_long'].iloc[-1]
            
            # Tentukan trend strength score
            trend_score = 0
            
            # Pengecekan EMA crossovers
            if ema_fast > ema_slow:
                trend_score += 1
            if ema_slow > ema_long:
                trend_score += 1
                
            # Pengecekan price vs EMAs
            if last_close > ema_fast:
                trend_score += 1
            if last_close > ema_slow:
                trend_score += 1
            if last_close > ema_long:
                trend_score += 1
                
            # Tentukan trend direction berdasarkan score
            if trend_score >= 3:
                trend = 'UP'
            elif trend_score <= 1:
                trend = 'DOWN'
            else:
                trend = 'SIDEWAYS'
                
            # Simpan ke cache
            self.indicators_cache[cache_key] = {
                'value': trend,
                'timestamp': datetime.now()
            }
            
            logging.info(f"{symbol} Higher Timeframe Trend: {trend} (Score: {trend_score}/5)")
            return trend
        except Exception as e:
            logging.error(f"Error checking higher timeframe trend: {str(e)}")
            return None
    
    def check_support_resistance(self, symbol, df):
        """Calculate key support and resistance levels"""
        try:
            # Calculate pivot points
            df['PP'] = (df['high'] + df['low'] + df['close']) / 3
            df['R1'] = (2 * df['PP']) - df['low']
            df['S1'] = (2 * df['PP']) - df['high']
            
            # Get the most recent values
            last_pp = df['PP'].iloc[-1]
            last_r1 = df['R1'].iloc[-1]
            last_s1 = df['S1'].iloc[-1]
            
            # Store in market data for later use
            self.market_data['support_levels'][symbol] = last_s1
            self.market_data['resistance_levels'][symbol] = last_r1
            
            return {
                'pivot': last_pp,
                'resistance': last_r1,
                'support': last_s1
            }
        except Exception as e:
            logging.error(f"Error calculating support/resistance: {str(e)}")
            return None
    def check_price_action(self, df):
        """Analyze price action for reversal patterns"""
        try:
            # Calculate basic candlestick properties
            df['body'] = abs(df['close'] - df['open'])
            df['upper_wick'] = df.apply(lambda x: max(x['high'] - x['close'], x['high'] - x['open']), axis=1)
            df['lower_wick'] = df.apply(lambda x: max(x['open'] - x['low'], x['close'] - x['low']), axis=1)

            # Calculate average body size
            avg_body = df['body'].mean()

            # Get the last 3 candles
            last_candles = df.iloc[-3:].copy()

            # Check for bullish patterns
            bullish_engulfing = (
                last_candles['close'].iloc[-1] > last_candles['open'].iloc[-1] and  # Current candle bullish
                last_candles['open'].iloc[-2] > last_candles['close'].iloc[-2] and  # Previous candle bearish
                last_candles['open'].iloc[-1] < last_candles['close'].iloc[-2] and  # Current open below previous close
                last_candles['close'].iloc[-1] > last_candles['open'].iloc[-2]  # Current close above previous open
            )

            bullish_hammer = (
                last_candles['body'].iloc[-1] < avg_body * 0.5 and  # Small body
                last_candles['lower_wick'].iloc[-1] > last_candles['body'].iloc[-1] * 2 and  # Long lower wick
                last_candles['upper_wick'].iloc[-1] < last_candles['body'].iloc[-1] * 0.5  # Small upper wick
            )

            # Check for bearish patterns
            bearish_engulfing = (
                last_candles['close'].iloc[-1] < last_candles['open'].iloc[-1] and  # Current candle bearish
                last_candles['open'].iloc[-2] < last_candles['close'].iloc[-2] and  # Previous candle bullish
                last_candles['open'].iloc[-1] > last_candles['close'].iloc[-2] and  # Current open above previous close
                last_candles['close'].iloc[-1] < last_candles['open'].iloc[-2]  # Current close below previous open
            )

            bearish_shooting_star = (
                last_candles['body'].iloc[-1] < avg_body * 0.5 and  # Small body
                last_candles['upper_wick'].iloc[-1] > last_candles['body'].iloc[-1] * 2 and  # Long upper wick
                last_candles['lower_wick'].iloc[-1] < last_candles['body'].iloc[-1] * 0.5  # Small lower wick
            )

            # Determine patterns
            if bullish_engulfing or bullish_hammer:
                return 'BULLISH'
            elif bearish_engulfing or bearish_shooting_star:
                return 'BEARISH'
            else:
                return 'NEUTRAL'

        except Exception as e:
            logging.error(f"Error analyzing price action: {str(e)}")
            return 'NEUTRAL'

    def get_signal(self, symbol):
        """Get trading signal based on technical indicators and market conditions"""
        try:
            # Check if symbol is available
            if not mt5.symbol_select(symbol, True):
                logging.warning(f"Symbol {symbol} is not available")
                return None, None

            # Get price data
            rates = mt5.copy_rates_from_pos(symbol, MT5Config.TIMEFRAME_MAIN, 0, 100)
            if rates is None or len(rates) == 0:
                logging.warning(f"Failed to get rates data for {symbol}")
                return None, None

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')

            # Calculate key indicators
            df['ema_fast'] = df['close'].ewm(span=TradingConfig.EMA_FAST, adjust=False).mean()
            df['ema_slow'] = df['close'].ewm(span=TradingConfig.EMA_SLOW, adjust=False).mean()
            df['ema_long'] = df['close'].ewm(span=TradingConfig.EMA_LONG, adjust=False).mean()
            df['rsi'] = ta.rsi(df['close'], length=TradingConfig.RSI_PERIOD)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=TradingConfig.ATR_PERIOD)
            bollinger = ta.bbands(df['close'], length=TradingConfig.BB_LENGTH, std=TradingConfig.BB_STD)
            df = pd.concat([df, bollinger], axis=1)

            # Support and resistance levels
            sr_levels = self.check_support_resistance(symbol, df)

            # Price action analysis
            price_action = self.check_price_action(df)

            # Get higher timeframe trend
            higher_tf_trend = self.check_higher_tf_trend(symbol)

            # Update ATR values for later use
            self.market_data['atr_values'][symbol] = df['atr'].iloc[-1]

            # Current close price
            current_close = df['close'].iloc[-1]

            # Build signal score
            buy_score = 0
            sell_score = 0
            max_score = 7  # Total number of conditions

            # 1. EMA alignment
            if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1] > df['ema_long'].iloc[-1]:
                buy_score += 1
            elif df['ema_fast'].iloc[-1] < df['ema_slow'].iloc[-1] < df['ema_long'].iloc[-1]:
                sell_score += 1

            # 2. Price vs EMAs
            if current_close > df['ema_fast'].iloc[-1] and current_close > df['ema_slow'].iloc[-1]:
                buy_score += 1
            elif current_close < df['ema_fast'].iloc[-1] and current_close < df['ema_slow'].iloc[-1]:
                sell_score += 1

            # 3. RSI conditions
            current_rsi = df['rsi'].iloc[-1]
            prev_rsi = df['rsi'].iloc[-2]
            if TradingConfig.RSI_OVERSOLD_MIN <= current_rsi <= TradingConfig.RSI_OVERSOLD_MAX and prev_rsi < current_rsi:  # RSI oversold dalam rentang dan naik
                buy_score += 1
            elif TradingConfig.RSI_OVERBOUGHT_MIN <= current_rsi <= TradingConfig.RSI_OVERBOUGHT_MAX and prev_rsi > current_rsi:  # RSI overbought dalam rentang dan turun
                sell_score += 1

            # 4. Bollinger Bands
            bb_upper = df['BBU_20_2.0'].iloc[-1]
            bb_lower = df['BBL_20_2.0'].iloc[-1]
            if current_close < bb_lower:  # Price below lower band (potential buy)
                buy_score += 1
            elif current_close > bb_upper:  # Price above upper band (potential sell)
                sell_score += 1

            # 5. Price Action
            if price_action == 'BULLISH':
                buy_score += 1
            elif price_action == 'BEARISH':
                sell_score += 1

            # 6. Higher Timeframe Trend
            if higher_tf_trend == 'UP':
                buy_score += 1
            elif higher_tf_trend == 'DOWN':
                sell_score += 1

            # 7. Support/Resistance
            if sr_levels:
                if current_close < sr_levels['support']:  # Near support level
                    buy_score += 1
                elif current_close > sr_levels['resistance']:  # Near resistance level
                    sell_score += 1

            # Calculate final signal strength as a percentage
            buy_strength = (buy_score / max_score) * 100
            sell_strength = (sell_score / max_score) * 100

            # Log detailed analysis
            logging.info(f"{symbol} Signal Analysis: Buy Score {buy_score}/{max_score} ({buy_strength:.1f}%), "
                         f"Sell Score {sell_score}/{max_score} ({sell_strength:.1f}%)")

            # Determine minimum threshold for signal strength
            min_strength = 50  # At least 60% confidence, set % yang akan open posisi

            # Generate final signal
            if buy_strength >= min_strength and buy_strength > sell_strength:
                signal = 'BUY'
                sl_price = mt5.symbol_info_tick(symbol).bid - (df['atr'].iloc[-1] * TradingConfig.SL_ATR_MULTIPLIER)
            elif sell_strength >= min_strength and sell_strength > buy_strength:
                signal = 'SELL'
                sl_price = mt5.symbol_info_tick(symbol).ask + (df['atr'].iloc[-1] * TradingConfig.SL_ATR_MULTIPLIER)
            else:
                signal = None
                sl_price = None

            # Cache the signal
            self.last_signals[symbol] = (signal, sl_price)

            return signal, sl_price

        except Exception as e:
            logging.error(f"Error getting signal for {symbol}: {str(e)}")
            return None, None

    def open_trade(self, symbol, trade_type, lot_size, sl_price):
        """Open a new trade"""
        if TradingConfig.SIMULATE_ONLY:
            logging.info(f"SIMULATION: Opening {trade_type} position for {symbol}, lot: {lot_size}, SL: {sl_price}")
            return None

        try:
            with self.trade_lock:  # Ensure thread safety
                if not self.check_connection():
                    return None

                # Get latest price
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    logging.error(f"Failed to get tick info for {symbol}")
                    return None

                # Calculate TP based on RR ratio
                if trade_type == 'BUY':
                    entry_price = tick.ask
                    tp_price = entry_price + ((entry_price - sl_price) * TradingConfig.TP_ATR_MULTIPLIER / TradingConfig.SL_ATR_MULTIPLIER)
                else:  # SELL
                    entry_price = tick.bid
                    tp_price = entry_price - ((sl_price - entry_price) * TradingConfig.TP_ATR_MULTIPLIER / TradingConfig.SL_ATR_MULTIPLIER)

                # Create a trade request
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot_size,
                    "type": mt5.ORDER_TYPE_BUY if trade_type == 'BUY' else mt5.ORDER_TYPE_SELL,
                    "price": entry_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "deviation": TradingConfig.SLIPPAGE_POINTS,
                    "magic": 12345,  # Magic number for identifying this bot's trades
                    "comment": f"MT5 Trader Bot",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_FOK,
                }

                # Send the trade request
                result = mt5.order_send(request)

                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"Failed to open trade for {symbol}. Error code: {result.retcode}")
                    logging.error(f"Komentar broker: {result.comment}")
                    logging.error(f"Detail permintaan: {request}")
                    return None
                else:
                    trade_info = f"{trade_type} {symbol} at {entry_price:.5f}, SL: {sl_price:.5f}, TP: {tp_price:.5f}, Lot: {lot_size}"
                    logging.info(f"Trade opened successfully: {trade_info}")

                    # Send notification
                    if TradingConfig.ENABLE_TELEGRAM_NOTIFICATIONS:
                        self.send_telegram_notification(f"🔔 *New Trade*\n{trade_info}")

                    return result.order

        except Exception as e:
            logging.error(f"Error opening trade: {str(e)}")
            return None

    def check_daily_loss(self):
        """Check if daily loss threshold has been reached"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')

            if today in self.stats.stats['daily_results']:
                daily_profit = self.stats.stats['daily_results'][today]['profit']
                account_info = mt5.account_info()

                if account_info:
                    equity = account_info.equity
                    daily_loss_pct = -daily_profit / equity * 100

                    if daily_loss_pct > TradingConfig.MAX_DAILY_LOSS_PERCENT:
                        logging.warning(f"Daily loss threshold reached: {daily_loss_pct:.2f}% (Limit: {TradingConfig.MAX_DAILY_LOSS_PERCENT}%)")
                        return True

            return False

        except Exception as e:
            logging.error(f"Error checking daily loss: {str(e)}")
            return False

    def check_drawdown(self):
        """Check if drawdown threshold has been reached"""
        try:
            account_info = mt5.account_info()
            if account_info:
                current_equity = account_info.equity
                peak_balance = self.stats.stats['peak_balance']

                if peak_balance > 0:
                    drawdown_pct = (peak_balance - current_equity) / peak_balance * 100

                    if drawdown_pct > TradingConfig.MAX_DRAWDOWN_PERCENT:
                        logging.warning(f"Maximum drawdown threshold reached: {drawdown_pct:.2f}% (Limit: {TradingConfig.MAX_DRAWDOWN_PERCENT}%)")
                        return True

            return False

        except Exception as e:
            logging.error(f"Error checking drawdown: {str(e)}")
            return False

    def manage_open_positions(self):
        """Manage existing positions (move SL to breakeven, trailing stop, etc.)"""
        try:
            if not self.check_connection():
                return

            # Get all positions
            positions = mt5.positions_get()

            if positions is None:
                logging.info("No open positions to manage")
                return

            for position in positions:
                # Verify if it's our bot's position by magic number
                if position.magic != 12345:
                    continue

                symbol = position.symbol
                position_id = position.ticket
                position_type = 'BUY' if position.type == mt5.POSITION_TYPE_BUY else 'SELL'

                # Get current symbol info
                symbol_info = mt5.symbol_info(symbol)
                if not symbol_info:
                    continue

                # Current price
                current_bid = mt5.symbol_info_tick(symbol).bid
                current_ask = mt5.symbol_info_tick(symbol).ask

                # Calculate current profit in pips
                entry_price = position.price_open

                if position_type == 'BUY':
                    current_price = current_bid
                    profit_pips = (current_price - entry_price) / symbol_info.point
                    current_sl = position.sl
                else:  # SELL
                    current_price = current_ask
                    profit_pips = (entry_price - current_price) / symbol_info.point
                    current_sl = position.sl

                # Get ATR for this symbol
                atr_value = self.market_data['atr_values'].get(symbol, 0)

                if atr_value > 0:
                    # Calculate breakeven and trailing stop thresholds in pips
                    breakeven_pips = atr_value * TradingConfig.BREAKEVEN_ACTIVATION / symbol_info.point
                    trailing_pips = atr_value * TradingConfig.TRAILING_STOP_ACTIVATION / symbol_info.point

                    # Modify SL
                    should_modify = False
                    new_sl = current_sl

                    # 1. Breakeven condition
                    if profit_pips >= breakeven_pips and current_sl != entry_price:
                        if (position_type == 'BUY' and current_sl < entry_price) or \
                           (position_type == 'SELL' and (current_sl > entry_price or current_sl == 0)):
                            new_sl = entry_price
                            should_modify = True
                            logging.info(f"Moving {symbol} #{position_id} to breakeven")

                    # 2. Trailing stop condition
                    if profit_pips >= trailing_pips:
                        # Calculate trailing stop level
                        if position_type == 'BUY':
                            trail_level = current_price - (atr_value * TradingConfig.SL_ATR_MULTIPLIER)
                            if trail_level > new_sl:
                                new_sl = trail_level
                                should_modify = True
                        else:  # SELL
                            trail_level = current_price + (atr_value * TradingConfig.SL_ATR_MULTIPLIER)
                            if trail_level < new_sl or new_sl == 0:
                                new_sl = trail_level
                                should_modify = True

                    # Apply SL modification if needed
                    if should_modify and not TradingConfig.SIMULATE_ONLY:
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "symbol": symbol,
                            "position": position_id,
                            "sl": new_sl,
                            "tp": position.tp
                        }

                        result = mt5.order_send(request)
                        if result.retcode != mt5.TRADE_RETCODE_DONE:
                            logging.error(f"Failed to modify SL for {symbol} #{position_id}. Error code: {result.retcode}")
                        else:
                            logging.info(f"Modified SL for {symbol} #{position_id} to {new_sl:.5f}")

                            if TradingConfig.ENABLE_TELEGRAM_NOTIFICATIONS:
                                self.send_telegram_notification(f"🔄 *SL Modified*\n{symbol} #{position_id} to {new_sl:.5f}")

                    elif should_modify and TradingConfig.SIMULATE_ONLY:
                        logging.info(f"SIMULATION: Would modify SL for {symbol} #{position_id} to {new_sl:.5f}")

        except Exception as e:
            logging.error(f"Error managing positions: {str(e)}")

    def update_statistics(self):
        """Update trading statistics from closed positions"""
        try:
            # Get account history for today
            from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            to_date = from_date + timedelta(days=1)

            from_stamp = int(from_date.timestamp())
            to_stamp = int(to_date.timestamp())

            # Get history deals
            deals = mt5.history_deals_get(from_stamp, to_stamp)

            if deals is None:
                return

            # Process closed positions
            for deal in deals:
                # Skip non-closing deals
                if deal.entry != mt5.DEAL_ENTRY_OUT:
                    continue

                # Skip deals not from our bot
                if deal.magic != 12345:
                    continue

                # Calculate profit in account currency
                symbol = deal.symbol
                profit = deal.profit

                # Update stats
                trade_type = 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL'
                self.stats.update_after_trade(symbol, profit, trade_type)

        except Exception as e:
            logging.error(f"Error updating statistics: {str(e)}")

    def count_open_trades(self, symbol=None):
        """Count open trades for a symbol or total"""
        try:
            if not self.check_connection():
                return 0

            # Get positions
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()

            if positions is None:
                return 0

            # Count only positions with our magic number
            count = sum(1 for pos in positions if pos.magic == 12345)
            return count

        except Exception as e:
            logging.error(f"Error counting open trades: {str(e)}")
            return 0

    def check_trade_allowed(self, symbol):
        """Check if trading is allowed for this symbol"""
        # Check market session
        active_sessions = self.check_market_session()
        if not active_sessions:
            logging.info(f"No active market sessions currently, skipping {symbol}")
            return False

        # Check max trades per symbol
        symbol_trades = self.count_open_trades(symbol)
        if symbol_trades >= TradingConfig.MAX_TRADES_PER_PAIR:
            return False

        # Check total trades
        total_trades = self.count_open_trades()
        if total_trades >= TradingConfig.MAX_TOTAL_TRADES:
            return False

        # Check drawdown
        if self.check_drawdown():
            return False

        # Check daily loss
        if self.check_daily_loss():
            return False

        # Check spread
        if not self.check_spread(symbol):
            return False

        # Check volatility
        if not self.check_volatility(symbol):
            return False

        return True

    def run_trading_cycle(self):
        """Run one cycle of the trading algorithm"""
        try:
            if not self.check_connection():
                return

            # Manage existing positions
            self.manage_open_positions()

            # Update statistics
            self.update_statistics()

            # Check for new trading opportunities
            for symbol in MT5Config.SYMBOLS:
                # Check if trading is allowed for this symbol
                if not self.check_trade_allowed(symbol):
                    continue

                # Get signal
                signal, sl_price = self.get_signal(symbol)

                if signal:
                    # Calculate lot size based on risk management
                    sl_points = 0

                    if sl_price:
                        tick = mt5.symbol_info_tick(symbol)
                        if signal == 'BUY':
                            sl_points = abs(tick.ask - sl_price) / mt5.symbol_info(symbol).point
                        else:  # SELL
                            sl_points = abs(tick.bid - sl_price) / mt5.symbol_info(symbol).point

                    if sl_points > 0:
                        lot_size = self.calculate_lot_size(symbol, sl_points)

                        if lot_size > 0:
                            # Open trade
                            self.open_trade(symbol, signal, lot_size, sl_price)

        except Exception as e:
            logging.error(f"Error in trading cycle: {str(e)}")

    def run(self):
        """Main trading bot loop"""
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
                    self.run_trading_cycle()
                except Exception as e:
                    logging.error(f"Error in trading cycle: {str(e)}")

                # Sleep between cycles
                time.sleep(5)

        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
        finally:
            self.disconnect()
            logging.info("Trading bot stopped")

    def stop(self):
        """Stop the trading bot"""
        self.exit_flag = True
        logging.info("Stopping trading bot...")

# Main execution function
def run_bot():
    try:
        logging.info("Starting MT5 Trading Bot...")

        #Cek all symbol
        MT5Config.load_symbols(include_forex=True, include_crypto=True, use_dynamic=True)
        logging.info(f"Symbol list yang akan dipakai: {MT5Config.SYMBOLS}")

        # Create and run trader
        trader = MT5Trader()

        # Run in a separate thread
        trading_thread = threading.Thread(target=trader.run)
        trading_thread.daemon = True
        trading_thread.start()

        # Keep main thread alive for keyboard interrupt
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Bot stopping by user request...")
        trader.stop()

if __name__ == "__main__":
    run_bot()       
