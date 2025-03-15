import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import logging
import json
import os

class TradingStats:
    def __init__(self):
        self.current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.login = "zzzz14"
        self.stats_dir = f"stats/user_{self.login}"
        self.ensure_stats_directory()
        self.daily_stats = {}
        self.weekly_stats = {}
        self.monthly_stats = {}
        self.load_stats()

    def ensure_stats_directory(self):
        """Ensure statistics directory exists"""
        if not os.path.exists(self.stats_dir):
            os.makedirs(self.stats_dir)

    def calculate_daily_stats(self):
        """Calculate daily trading statistics"""
        try:
            # Get today's trades
            today = self.current_time = datetime.now()
            today_start = datetime.combine(today, datetime.min.time())
            
            trades = mt5.history_deals_get(today_start, self.current_time)
            if trades is None:
                return
                
            daily_stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'profit': 0.0,
                'loss': 0.0,
                'pnl': 0.0,
                'win_rate': 0.0,
                'risk_reward_ratio': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'profit_factor': 0.0
            }

            # Process trades
            trades_data = []
            for trade in trades:
                if trade.magic == 123456:  # Our bot's trades
                    profit = trade.profit
                    daily_stats['total_trades'] += 1
                    
                    if profit > 0:
                        daily_stats['winning_trades'] += 1
                        daily_stats['profit'] += profit
                    else:
                        daily_stats['losing_trades'] += 1
                        daily_stats['loss'] += abs(profit)
                        
                    trades_data.append({
                        'time': trade.time,
                        'symbol': trade.symbol,
                        'type': trade.type,
                        'volume': trade.volume,
                        'price': trade.price,
                        'profit': profit
                    })

            # Calculate metrics
            daily_stats['pnl'] = daily_stats['profit'] - daily_stats['loss']
            
            if daily_stats['total_trades'] > 0:
                daily_stats['win_rate'] = (daily_stats['winning_trades'] / 
                                         daily_stats['total_trades'] * 100)
                                         
            if daily_stats['loss'] > 0:
                daily_stats['profit_factor'] = daily_stats['profit'] / daily_stats['loss']

            if trades_data:
                df = pd.DataFrame(trades_data)
                daily_stats['max_drawdown'] = self.calculate_max_drawdown(df)
                daily_stats['sharpe_ratio'] = self.calculate_sharpe_ratio(df)
                daily_stats['risk_reward_ratio'] = self.calculate_risk_reward_ratio(df)

            # Save daily stats
            self.daily_stats[today.strftime('%Y-%m-%d')] = daily_stats
            self.save_stats()
            
            # Log daily statistics
            self.log_daily_stats(daily_stats)

            return daily_stats

        except Exception as e:
            logging.error(f"Error calculating daily stats: {str(e)}")
            return None

    def calculate_weekly_stats(self):
        """Calculate weekly trading statistics"""
        try:
            week_start = self.current_time - timedelta(days=self.current_time.weekday())
            week_start = datetime.combine(week_start.date(), datetime.min.time())
            
            trades = mt5.history_deals_get(week_start, self.current_time)
            if trades is None:
                return
                
            weekly_stats = self.aggregate_stats(trades)
            
            # Save weekly stats
            week_key = week_start.strftime('%Y-%W')
            self.weekly_stats[week_key] = weekly_stats
            self.save_stats()
            
            return weekly_stats

        except Exception as e:
            logging.error(f"Error calculating weekly stats: {str(e)}")
            return None

    def calculate_monthly_stats(self):
        """Calculate monthly trading statistics"""
        try:
            month_start = self.current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            trades = mt5.history_deals_get(month_start, self.current_time)
            if trades is None:
                return
                
            monthly_stats = self.aggregate_stats(trades)
            
            # Save monthly stats
            month_key = month_start.strftime('%Y-%m')
            self.monthly_stats[month_key] = monthly_stats
            self.save_stats()
            
            return monthly_stats

        except Exception as e:
            logging.error(f"Error calculating monthly stats: {str(e)}")
            return None

    def aggregate_stats(self, trades):
        """Aggregate statistics from trades"""
        try:
            stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'profit': 0.0,
                'loss': 0.0,
                'pnl': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'average_trade': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'risk_reward_ratio': 0.0
            }

            trades_data = []
            for trade in trades:
                if trade.magic == 123456:  # Our bot's trades
                    stats['total_trades'] += 1
                    profit = trade.profit
                    
                    trades_data.append({
                        'time': trade.time,
                        'symbol': trade.symbol,
                        'type': trade.type,
                        'volume': trade.volume,
                        'price': trade.price,
                        'profit': profit
                    })
                    
                    if profit > 0:
                        stats['winning_trades'] += 1
                        stats['profit'] += profit
                    else:
                        stats['losing_trades'] += 1
                        stats['loss'] += abs(profit)

            if stats['total_trades'] > 0:
                stats['win_rate'] = (stats['winning_trades'] / stats['total_trades'] * 100)
                stats['average_trade'] = (stats['profit'] - stats['loss']) / stats['total_trades']
                
            if stats['loss'] > 0:
                stats['profit_factor'] = stats['profit'] / stats['loss']

            if trades_data:
                df = pd.DataFrame(trades_data)
                stats['max_drawdown'] = self.calculate_max_drawdown(df)
                stats['sharpe_ratio'] = self.calculate_sharpe_ratio(df)
                stats['risk_reward_ratio'] = self.calculate_risk_reward_ratio(df)

            return stats

        except Exception as e:
            logging.error(f"Error aggregating stats: {str(e)}")
            return None

    def calculate_max_drawdown(self, df):
        """Calculate maximum drawdown"""
        try:
            if df.empty:
                return 0.0

            cumulative = df['profit'].cumsum()
            rolling_max = cumulative.expanding().max()
            drawdowns = (cumulative - rolling_max)
            return abs(drawdowns.min())

        except Exception as e:
            logging.error(f"Error calculating max drawdown: {str(e)}")
            return 0.0

    def calculate_sharpe_ratio(self, df, risk_free_rate=0.02):
        """Calculate Sharpe ratio"""
        try:
            if df.empty:
                return 0.0

            returns = df['profit'].pct_change()
            excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
            if excess_returns.std() == 0:
                return 0.0
            return np.sqrt(252) * excess_returns.mean() / excess_returns.std()

        except Exception as e:
            logging.error(f"Error calculating Sharpe ratio: {str(e)}")
            return 0.0

    def calculate_risk_reward_ratio(self, df):
        """Calculate risk/reward ratio"""
        try:
            if df.empty:
                return 0.0

            avg_win = df[df['profit'] > 0]['profit'].mean()
            avg_loss = abs(df[df['profit'] < 0]['profit'].mean())
            
            if avg_loss == 0:
                return 0.0
                
            return avg_win / avg_loss

        except Exception as e:
            logging.error(f"Error calculating risk/reward ratio: {str(e)}")
            return 0.0

    def save_stats(self):
        """Save statistics to file"""
        try:
            stats = {
                'daily': self.daily_stats,
                'weekly': self.weekly_stats,
                'monthly': self.monthly_stats
            }
            
            filename = os.path.join(self.stats_dir, f'trading_stats_{self.login}.json')
            with open(filename, 'w') as f:
                json.dump(stats, f, indent=4)

        except Exception as e:
            logging.error(f"Error saving stats: {str(e)}")

    def load_stats(self):
        """Load statistics from file"""
        try:
            filename = os.path.join(self.stats_dir, f'trading_stats_{self.login}.json')
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    stats = json.load(f)
                    self.daily_stats = stats.get('daily', {})
                    self.weekly_stats = stats.get('weekly', {})
                    self.monthly_stats = stats.get('monthly', {})

        except Exception as e:
            logging.error(f"Error loading stats: {str(e)}")

    def log_daily_stats(self, stats):
        """Log daily statistics"""
        try:
            analysis = f"""
{'='*50}
DAILY TRADING STATISTICS
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}

Performance Metrics:
- Total Trades: {stats['total_trades']}
- Winning Trades: {stats['winning_trades']}
- Losing Trades: {stats['losing_trades']}
- Win Rate: {stats['win_rate']:.2f}%

Profitability:
- Total Profit: ${stats['profit']:.2f}
- Total Loss: ${stats['loss']:.2f}
- Net P&L: ${stats['pnl']:.2f}
- Profit Factor: {stats['profit_factor']:.2f}

Risk Metrics:
- Max Drawdown: ${stats['max_drawdown']:.2f}
- Sharpe Ratio: {stats['sharpe_ratio']:.2f}
- Risk/Reward Ratio: {stats['risk_reward_ratio']:.2f}
{'='*50}
            """
            
            logging.info(analysis)

        except Exception as e:
            logging.error(f"Error logging daily stats: {str(e)}")