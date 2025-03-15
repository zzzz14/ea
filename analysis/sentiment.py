import logging
import requests
import json
import time
import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd
import numpy as np
import pandas_ta as ta
from textblob import TextBlob
from newsapi import NewsApiClient
from tb.config.trading_config import TradingConfig
from tb.analysis.technical import TechnicalAnalyzer

class SentimentAnalyzer:
    def __init__(self):
        self.current_time = datetime.strptime("2025-03-12 00:04:15", "%Y-%m-%d %H:%M:%S")
        self.login = "zzzz14"
        self.news_api = NewsApiClient(api_key='your-news-api-key')  # Replace with your API key
        self.sentiment_cache = {}
        self.last_update = {}
        
        # Economic calendar cache
        self.calendar_cache = {
            'data': None,
            'last_update': None
        }
        
        # Currency strength cache
        self.currency_strength = {
            'data': {},
            'last_update': None
        }

    def get_market_sentiment(self, symbol):
        """Get overall market sentiment score for a symbol"""
        try:
            # Check cache freshness (5 minutes)
            if (symbol in self.sentiment_cache and 
                (self.current_time - self.last_update.get(symbol, datetime.min)).total_seconds() < 300):
                return self.sentiment_cache[symbol]

            # Component scores (0 to 1)
            news_score = self.analyze_news(symbol)
            economic_score = self.analyze_economic_calendar(symbol)
            technical_score = self.analyze_technical_sentiment(symbol)
            social_score = self.analyze_social_sentiment(symbol)

            # Weighted average
            weights = {
                'news': 0.3,
                'economic': 0.3,
                'technical': 0.25,
                'social': 0.15
            }

            total_sentiment = (
                news_score * weights['news'] +
                economic_score * weights['economic'] +
                technical_score * weights['technical'] +
                social_score * weights['social']
            )

            # Normalize to -1 to 1 range
            normalized_sentiment = (total_sentiment - 0.5) * 2

            # Cache result
            self.sentiment_cache[symbol] = normalized_sentiment
            self.last_update[symbol] = self.current_time

            # Log analysis
            self.log_sentiment_analysis(symbol, {
                'news': news_score,
                'economic': economic_score,
                'technical': technical_score,
                'social': social_score,
                'total': normalized_sentiment
            })

            return normalized_sentiment

        except Exception as e:
            logging.error(f"Error calculating market sentiment: {str(e)}")
            return 0

    def analyze_news(self, symbol):
        """Analyze news sentiment"""
        try:
            # Extract currencies from symbol
            base_currency = symbol[:3]
            quote_currency = symbol[3:]

            # Get news for both currencies
            news = self.news_api.get_everything(
                q=f'({base_currency} OR {quote_currency}) AND (forex OR currency OR economy)',
                language='en',
                sort_by='relevancy',
                from_param=self.current_time.strftime('%Y-%m-%d'),
                page_size=10
            )

            if not news['articles']:
                return 0.5  # Neutral if no news

            # Analyze sentiment for each article
            sentiments = []
            for article in news['articles']:
                blob = TextBlob(f"{article['title']} {article['description']}")
                sentiments.append(blob.sentiment.polarity)

            # Average sentiment (-1 to 1)
            avg_sentiment = np.mean(sentiments)

            # Normalize to 0 to 1
            return (avg_sentiment + 1) / 2

        except Exception as e:
            logging.error(f"Error analyzing news: {str(e)}")
            return 0.5

    def analyze_economic_calendar(self, symbol):
        """Analyze economic calendar impact"""
        try:
            # Check cache freshness (1 hour)
            if (self.calendar_cache['data'] is not None and 
                self.calendar_cache['last_update'] is not None and
                (self.current_time - self.calendar_cache['last_update']).total_seconds() < 3600):
                calendar_data = self.calendar_cache['data']
            else:
                # Fetch new calendar data (implement your data source)
                calendar_data = self.fetch_economic_calendar()
                self.calendar_cache['data'] = calendar_data
                self.calendar_cache['last_update'] = self.current_time

            # Extract currencies from symbol
            base_currency = symbol[:3]
            quote_currency = symbol[3:]

            # Filter relevant events
            relevant_events = [
                event for event in calendar_data
                if event['currency'] in [base_currency, quote_currency]
                and event['impact'] in ['High', 'Medium']
            ]

            if not relevant_events:
                return 0.5  # Neutral if no events

            # Calculate impact score
            impact_scores = []
            for event in relevant_events:
                score = self.calculate_event_impact(event)
                if event['currency'] == quote_currency:
                    score = -score  # Invert impact for quote currency
                impact_scores.append(score)

            # Average impact (-1 to 1)
            avg_impact = np.mean(impact_scores)

            # Normalize to 0 to 1
            return (avg_impact + 1) / 2

        except Exception as e:
            logging.error(f"Error analyzing economic calendar: {str(e)}")
            return 0.5

    def analyze_technical_sentiment(self, symbol):
        """Analyze technical indicators sentiment"""
        try:
            # Get technical indicators from MT5
            rates = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100))
            
            if rates.empty:
                return 0.5

            # Calculate indicators
            rates['rsi'] = ta.rsi(rates['close'])
            rates['macd'] = ta.macd(rates['close'])['MACD_12_26_9']
            rates['macd_signal'] = ta.macd(rates['close'])['MACDs_12_26_9']
            
            # Get latest values
            rsi = rates['rsi'].iloc[-1]
            macd = rates['macd'].iloc[-1]
            macd_signal = rates['macd_signal'].iloc[-1]

            # Calculate sentiment score
            score = 0.5  # Start neutral

            # RSI contribution
            if rsi > 70:
                score -= 0.2
            elif rsi < 30:
                score += 0.2

            # MACD contribution
            if macd > macd_signal:
                score += 0.1
            else:
                score -= 0.1

            return max(0, min(1, score))  # Ensure between 0 and 1

        except Exception as e:
            logging.error(f"Error analyzing technical sentiment: {str(e)}")
            return 0.5

    def analyze_social_sentiment(self, symbol):
        """Analyze social media sentiment"""
        try:
            # This would typically integrate with social media APIs
            # For demonstration, returning neutral sentiment
            return 0.5

        except Exception as e:
            logging.error(f"Error analyzing social sentiment: {str(e)}")
            return 0.5

    def calculate_event_impact(self, event):
        """Calculate impact score for economic event"""
        try:
            impact_weights = {
                'High': 1.0,
                'Medium': 0.5,
                'Low': 0.2
            }

            # Base score from impact
            score = impact_weights.get(event['impact'], 0)

            # Adjust based on actual vs forecast if available
            if 'actual' in event and 'forecast' in event and event['forecast']:
                try:
                    actual = float(event['actual'])
                    forecast = float(event['forecast'])
                    deviation = (actual - forecast) / forecast
                    score *= (1 + deviation)
                except:
                    pass

            return max(-1, min(1, score))  # Ensure between -1 and 1

        except Exception as e:
            logging.error(f"Error calculating event impact: {str(e)}")
            return 0

    def log_sentiment_analysis(self, symbol, scores):
        """Log sentiment analysis details"""
        try:
            analysis = f"""
{'='*50}
SENTIMENT ANALYSIS - {symbol}
Time: {self.current_time} UTC
Login: {self.login}
{'='*50}

COMPONENT SCORES:
News Sentiment: {scores['news']:.2f}
Economic Impact: {scores['economic']:.2f}
Technical Sentiment: {scores['technical']:.2f}
Social Sentiment: {scores['social']:.2f}

OVERALL SENTIMENT: {scores['total']:.2f}
(-1 = Very Bearish, 0 = Neutral, 1 = Very Bullish)

ANALYSIS SUMMARY:
{self.get_sentiment_description(scores['total'])}
{'='*50}
            """
            
            logging.info(analysis)

        except Exception as e:
            logging.error(f"Error logging sentiment analysis: {str(e)}")

    def get_sentiment_description(self, sentiment):
        """Get descriptive summary of sentiment score"""
        if sentiment > 0.5:
            strength = "Strong" if sentiment > 0.75 else "Moderate"
            return f"{strength} Bullish Sentiment"
        elif sentiment < -0.5:
            strength = "Strong" if sentiment < -0.75 else "Moderate"
            return f"{strength} Bearish Sentiment"
        else:
            return "Neutral Sentiment"

    def fetch_economic_calendar(self):
        """Fetch economic calendar data"""
        # Implement your data source integration here
        # For example, using an economic calendar API
        return []