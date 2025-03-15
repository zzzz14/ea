import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
import logging
from datetime import datetime
import MetaTrader5 as mt5
from ..config.trading_config import TradingConfig

class MLOptimizer:
    def __init__(self):
        self.current_time = datetime.strptime("2025-03-12 00:07:07", "%Y-%m-%d %H:%M:%S")
        self.login = "zzzz14"
        self.model = None
        self.scaler = StandardScaler()
        self.last_optimization = None
        self.feature_importance = None
        self.model_path = f"models/trading_model_{self.login}.joblib"
        self.optimization_interval = TradingConfig.OPTIMIZATION_INTERVAL

    def prepare_data(self, symbol, timeframe=mt5.TIMEFRAME_M5):
        """Prepare data for machine learning"""
        try:
            # Get historical data
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 5000)
            if rates is None:
                raise Exception("Failed to get historical data")

            df = pd.DataFrame(rates)
            
            # Calculate features
            df['returns'] = df['close'].pct_change()
            df['volatility'] = df['returns'].rolling(window=20).std()
            
            # Technical indicators
            df['rsi'] = self.calculate_rsi(df['close'])
            df['macd'] = self.calculate_macd(df['close'])
            df['bb_upper'], df['bb_lower'] = self.calculate_bollinger_bands(df['close'])
            
            # Create target variable (1 for profit, 0 for loss)
            df['target'] = (df['close'].shift(-10) > df['close']).astype(int)
            
            # Remove missing values
            df = df.dropna()
            
            # Features for model
            features = ['returns', 'volatility', 'rsi', 'macd', 
                       'bb_upper', 'bb_lower']
            
            X = df[features]
            y = df['target']
            
            return X, y, features

        except Exception as e:
            logging.error(f"Error preparing data: {str(e)}")
            return None, None, None

    def optimize_parameters(self, trading_history):
        """Optimize trading parameters using machine learning"""
        try:
            if params is None:
                raise ValueError("Params should not be None")
            
            # Misalkan params diharapkan sebagai dictionary
            for key in params.keys():
                print(f"Optimizing {key}")
        except Exception as e:
            logging.error(f"""
{'='*50}
Error optimizing parameters
Time: {self.current_time}
Login: {self.login}
Error: {str(e)}
{'='*50}
            """)
        try:
            # Check if optimization is needed
            if (self.last_optimization and 
                (self.current_time - self.last_optimization).total_seconds() < self.optimization_interval):
                return

            logging.info(f"""
{'='*50}
STARTING ML OPTIMIZATION
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}
            """)

            # Prepare data for all symbols
            all_X = []
            all_y = []
            
            for symbol in trading_history.keys():
                X, y, features = self.prepare_data(symbol)
                if X is not None and y is not None:
                    all_X.append(X)
                    all_y.append(y)

            if not all_X:
                raise Exception("No valid data for optimization")

            # Combine data
            X = pd.concat(all_X)
            y = pd.concat(all_y)

            # Scale features
            X_scaled = self.scaler.fit_transform(X)

            # Train model
            self.train_model(X_scaled, y)

            # Update parameters based on model insights
            self.update_trading_parameters()

            # Save model
            self.save_model()

            # Log optimization results
            self.log_optimization_results()

            self.last_optimization = self.current_time

        except Exception as e:
            logging.error(f"Error optimizing parameters: {str(e)}")

    def train_model(self, X, y):
        """Train the machine learning model"""
        try:
            # Initialize model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=5)
            
            # Performance metrics
            metrics = {
                'accuracy': [],
                'precision': [],
                'recall': [],
                'f1': []
            }

            # Train and evaluate
            for train_idx, val_idx in tscv.split(X):
                X_train, X_val = X[train_idx], X[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

                self.model.fit(X_train, y_train)
                predictions = self.model.predict(X_val)

                metrics['accuracy'].append(accuracy_score(y_val, predictions))
                metrics['precision'].append(precision_score(y_val, predictions))
                metrics['recall'].append(recall_score(y_val, predictions))
                metrics['f1'].append(f1_score(y_val, predictions))

            # Store feature importance
            self.feature_importance = pd.Series(
                self.model.feature_importances_,
                index=self.get_feature_names()
            ).sort_values(ascending=False)

            # Log training metrics
            self.log_training_metrics(metrics)

        except Exception as e:
            logging.error(f"Error training model: {str(e)}")

    def update_trading_parameters(self):
        """Update trading parameters based on model insights"""
        try:
            if self.feature_importance is None:
                return

            # Adjust parameters based on feature importance
            for feature, importance in self.feature_importance.items():
                if importance > 0.2:  # High importance threshold
                    if 'rsi' in feature.lower():
                        self.optimize_rsi_parameters()
                    elif 'macd' in feature.lower():
                        self.optimize_macd_parameters()
                    elif 'bollinger' in feature.lower():
                        self.optimize_bollinger_parameters()

        except Exception as e:
            logging.error(f"Error updating parameters: {str(e)}")

    def save_model(self):
        """Save trained model to file"""
        try:
            if self.model is not None:
                joblib.dump(self.model, self.model_path)
                logging.info(f"Model saved to {self.model_path}")

        except Exception as e:
            logging.error(f"Error saving model: {str(e)}")

    def load_model(self):
        """Load trained model from file"""
        try:
            self.model = joblib.load(self.model_path)
            logging.info(f"Model loaded from {self.model_path}")

        except Exception as e:
            logging.error(f"Error loading model: {str(e)}")

    def get_feature_names(self):
        """Get list of feature names"""
        return ['returns', 'volatility', 'rsi', 'macd', 'bb_upper', 'bb_lower']

    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        except Exception as e:
            logging.error(f"Error calculating RSI: {str(e)}")
            return pd.Series(index=prices.index)

    def calculate_macd(self, prices):
        """Calculate MACD indicator"""
        try:
            exp1 = prices.ewm(span=12, adjust=False).mean()
            exp2 = prices.ewm(span=26, adjust=False).mean()
            return exp1 - exp2
        except Exception as e:
            logging.error(f"Error calculating MACD: {str(e)}")
            return pd.Series(index=prices.index)

    def calculate_bollinger_bands(self, prices, period=20, std=2):
        """Calculate Bollinger Bands"""
        try:
            sma = prices.rolling(window=period).mean()
            std_dev = prices.rolling(window=period).std()
            upper = sma + (std_dev * std)
            lower = sma - (std_dev * std)
            return upper, lower
        except Exception as e:
            logging.error(f"Error calculating Bollinger Bands: {str(e)}")
            return pd.Series(index=prices.index), pd.Series(index=prices.index)

    def log_optimization_results(self):
        """Log optimization results"""
        try:
            if self.feature_importance is None:
                return

            analysis = f"""
{'='*50}
ML OPTIMIZATION RESULTS
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}

Feature Importance:
{self.feature_importance.to_string()}

Updated Parameters:
- RSI Period: {TradingConfig.RSI_PERIOD}
- MACD Fast: {TradingConfig.EMA_FAST}
- MACD Slow: {TradingConfig.EMA_SLOW}
- BB Period: {TradingConfig.BB_PERIOD}

Model Performance:
- Accuracy: {self.model.score(self.scaler.transform(self.get_latest_data()), self.get_latest_targets()):.2f}
{'='*50}
            """
            
            logging.info(analysis)

        except Exception as e:
            logging.error(f"Error logging optimization results: {str(e)}")

    def log_training_metrics(self, metrics):
        """Log model training metrics"""
        try:
            analysis = f"""
{'='*50}
MODEL TRAINING METRICS
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}

Cross-validation Results:
- Accuracy:  {np.mean(metrics['accuracy']):.2f} (±{np.std(metrics['accuracy']):.2f})
- Precision: {np.mean(metrics['precision']):.2f} (±{np.std(metrics['precision']):.2f})
- Recall:    {np.mean(metrics['recall']):.2f} (±{np.std(metrics['recall']):.2f})
- F1 Score:  {np.mean(metrics['f1']):.2f} (±{np.std(metrics['f1']):.2f})
{'='*50}
            """
            
            logging.info(analysis)

        except Exception as e:
            logging.error(f"Error logging training metrics: {str(e)}")