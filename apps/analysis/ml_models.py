"""
Machine Learning Models for GPW Trading Advisor.
Neural networks and ML models that learn from historical performance.
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb
import joblib
import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal
from datetime import date, timedelta, datetime
from pathlib import Path

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db.models import Q, Avg, Count, Min, Max

from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData, NewsArticleModel, CompanyCalendarEvent, EventDateChange
from apps.analysis.models import AnomalyAlert, PricePrediction, RiskAssessment, PatternDetection

logger = logging.getLogger(__name__)

class SimpleStockPredictor(nn.Module):
    """
    Simple feedforward neural network for stock prediction with fundamental features.
    Handles news sentiment, calendar events, and technical indicators.
    """
    
    def __init__(self, input_size: int = 25, hidden_sizes: List[int] = [128, 64, 32]):
        super().__init__()
        
        layers = []
        prev_size = input_size
        
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.BatchNorm1d(hidden_size),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            prev_size = hidden_size
        
        # Output layer for price change prediction
        layers.append(nn.Linear(prev_size, 1))
        
        self.network = nn.Sequential(*layers)
        
    def forward(self, x):
        return self.network(x)


class StockPricePredictor(nn.Module):
    """
    LSTM Neural Network for stock price prediction.
    """
    
    def __init__(self, input_size: int = 10, hidden_size: int = 128, num_layers: int = 2, dropout: float = 0.2):
        super(StockPricePredictor, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )
        
        # Attention mechanism
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=8,
            dropout=dropout,
            batch_first=True
        )
        
        # Output layers
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.fc2 = nn.Linear(hidden_size // 2, hidden_size // 4)
        self.fc3 = nn.Linear(hidden_size // 4, 1)  # Price prediction
        
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()
        
    def forward(self, x):
        # LSTM forward pass
        lstm_out, (hidden, cell) = self.lstm(x)
        
        # Self-attention
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        
        # Use last timestep output
        last_output = attn_out[:, -1, :]
        
        # Fully connected layers
        out = self.dropout(self.relu(self.fc1(last_output)))
        out = self.dropout(self.relu(self.fc2(out)))
        out = self.fc3(out)
        
        return out


class AnomalyDetectionNN(nn.Module):
    """
    Neural Network for anomaly detection using autoencoder approach with confidence estimation.
    """
    
    def __init__(self, input_size: int = 20, hidden_sizes: List[int] = [256, 128, 64]):
        super(AnomalyDetectionNN, self).__init__()
        
        self.input_size = input_size
        
        # Encoder layers
        encoder_layers = []
        prev_size = input_size
        
        for hidden_size in hidden_sizes:
            encoder_layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.BatchNorm1d(hidden_size),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            prev_size = hidden_size
        
        self.encoder = nn.Sequential(*encoder_layers)
        
        # Decoder layers (mirror of encoder)
        decoder_layers = []
        reversed_sizes = list(reversed(hidden_sizes[:-1])) + [input_size]
        
        for hidden_size in reversed_sizes[:-1]:
            decoder_layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.BatchNorm1d(hidden_size),
                nn.ReLU(),
                nn.Dropout(0.3)
            ])
            prev_size = hidden_size
        
        # Final reconstruction layer
        decoder_layers.append(nn.Linear(prev_size, input_size))
        self.decoder = nn.Sequential(*decoder_layers)
        
        # Anomaly scoring layer
        self.anomaly_score_layer = nn.Sequential(
            nn.Linear(hidden_sizes[-1], 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x):
        # Encode
        encoded = self.encoder(x)
        
        # Decode for reconstruction
        reconstructed = self.decoder(encoded)
        
        # Calculate anomaly score based on encoding
        anomaly_score = self.anomaly_score_layer(encoded)
        
        return reconstructed, anomaly_score.squeeze()


class MLModelManager:
    """
    Manages all ML models, training, and predictions.
    """
    
    def __init__(self):
        self.models_dir = Path(settings.BASE_DIR) / 'ml_models'
        self.models_dir.mkdir(exist_ok=True)
        
        # Model configurations
        self.config = {
            'lookback_days': 30,  # Historical data to analyze
            'prediction_horizon_hours': 4,  # Predict 4 hours ahead (before session close)
            'feature_count': 20,
            'sequence_length': 60,  # Minutes of data for LSTM
            'batch_size': 32,
            'learning_rate': 0.001,
            'epochs': 100,
            'early_stopping_patience': 10
        }
        
        # Load or initialize models
        self.price_predictor = None
        self.anomaly_detector = None
        self.confidence_estimator = None
        self.scaler = StandardScaler()
        
        self._load_models()
    
    def _load_models(self):
        """Load existing models or create new ones."""
        try:
            # Load price predictor with dynamic architecture detection
            price_model_path = self.models_dir / 'price_predictor.pth'
            if price_model_path.exists():
                # Load state dict to determine model architecture
                state_dict = torch.load(price_model_path)
                
                # Check if it's LSTM or SimpleStockPredictor based on keys
                if any('lstm' in key for key in state_dict.keys()):
                    self.price_predictor = StockPricePredictor()
                    self.price_predictor.load_state_dict(state_dict)
                    logger.info("Loaded existing LSTM price predictor model")
                else:
                    # Determine input size from first layer
                    input_size = None
                    for key, tensor in state_dict.items():
                        if 'weight' in key and 'network.0' in key:
                            input_size = tensor.shape[1]
                            break
                    
                    if input_size:
                        self.price_predictor = SimpleStockPredictor(input_size=input_size)
                        self.price_predictor.load_state_dict(state_dict)
                        logger.info(f"Loaded existing SimpleStockPredictor model (input_size={input_size})")
                    else:
                        logger.warning("Could not determine model architecture from state dict")
                
                if self.price_predictor:
                    self.price_predictor.eval()
            
            # Load anomaly detector
            anomaly_model_path = self.models_dir / 'anomaly_detector.pth'
            if anomaly_model_path.exists():
                self.anomaly_detector = AnomalyDetectionNN(
                    input_size=25,  # 25 features for anomaly detection
                    hidden_sizes=[64, 32, 16]
                )
                self.anomaly_detector.load_state_dict(torch.load(anomaly_model_path))
                self.anomaly_detector.eval()
                
                # Load anomaly threshold if available
                threshold_path = self.models_dir / 'anomaly_threshold.pth'
                if threshold_path.exists():
                    self.anomaly_threshold = torch.load(threshold_path).item()
                else:
                    self.anomaly_threshold = 0.5  # Default threshold
                
                logger.info(f"Loaded existing anomaly detector model (threshold: {self.anomaly_threshold:.6f})")
            
            # Load scaler
            scaler_path = self.models_dir / 'scaler.joblib'
            if scaler_path.exists():
                self.scaler = joblib.load(scaler_path)
                logger.info("Loaded existing data scaler")
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def prepare_features(self, stock: StockSymbol, session: TradingSession, 
                        lookback_days: int = 30) -> Optional[np.ndarray]:
        """
        Prepare feature matrix for ML models from real stock data.
        """
        # Get historical data
        end_date = session.date
        start_date = end_date - timedelta(days=lookback_days + 30)  # Extra buffer
        
        # Query real stock data
        stock_data = StockData.objects.filter(
            stock=stock,
            trading_session__date__gte=start_date,
            trading_session__date__lte=end_date
        ).select_related('trading_session').order_by('trading_session__date', 'data_timestamp')
        
        if stock_data.count() < 20:  # Need minimum data
            return None
        
        # Convert to DataFrame for easier processing
        df_data = []
        for data in stock_data:
            if all([data.open_price, data.high_price, data.low_price, data.close_price, data.volume]):
                df_data.append({
                    'date': data.trading_session.date,
                    'open': float(data.open_price or 0),
                    'high': float(data.high_price or 0),
                    'low': float(data.low_price or 0),
                    'close': float(data.close_price or 0),
                    'volume': float(data.volume or 0),
                    'timestamp': data.data_timestamp
                })
        
        if len(df_data) < 20:
            return None
        
        df = pd.DataFrame(df_data)
        df = df.sort_values(['date', 'timestamp'])
        
        # Take latest data per day
        df = df.groupby('date').last().reset_index()
        
        if len(df) < 20:
            return None
        
        # Calculate technical features
        features = self._calculate_technical_features(df)
        
        if features is None or len(features) == 0:
            return None
        
        return np.array(features[-1:])  # Return latest feature vector
    
    def _calculate_technical_features(self, df: pd.DataFrame) -> Optional[List[List[float]]]:
        """
        Calculate comprehensive technical analysis features.
        """
        try:
            features = []
            
            # Price-based features
            df['returns'] = df['close'].pct_change()
            df['high_low_ratio'] = df['high'] / df['low']
            df['open_close_ratio'] = df['open'] / df['close']
            
            # Moving averages
            for period in [5, 10, 20]:
                df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
                df[f'close_sma_{period}_ratio'] = df['close'] / df[f'sma_{period}']
            
            # Volatility
            df['volatility_10'] = df['returns'].rolling(window=10).std()
            df['volatility_20'] = df['returns'].rolling(window=20).std()
            
            # Volume features
            df['volume_sma_10'] = df['volume'].rolling(window=10).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma_10']
            
            # RSI approximation
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            
            # MACD approximation
            ema_12 = df['close'].ewm(span=12).mean()
            ema_26 = df['close'].ewm(span=26).mean()
            df['macd'] = ema_12 - ema_26
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']
            
            # Prepare feature vectors
            feature_columns = [
                'returns', 'high_low_ratio', 'open_close_ratio',
                'close_sma_5_ratio', 'close_sma_10_ratio', 'close_sma_20_ratio',
                'volatility_10', 'volatility_20', 'volume_ratio',
                'rsi', 'bb_position', 'macd', 'macd_signal', 'macd_histogram'
            ]
            
            # Only use rows where all features are available
            df_clean = df[feature_columns].dropna()
            
            if len(df_clean) < 10:
                return None
            
            # Convert to feature vectors
            features = df_clean.values.tolist()
            
            return features
            
        except Exception as e:
            logger.error(f"Error calculating technical features: {e}")
            return None
    
    def train_price_predictor(self, stocks: Optional[List[StockSymbol]] = None, 
                            force_retrain: bool = False) -> Dict[str, Any]:
        """
        Train price prediction model on historical data.
        """
        if not force_retrain and self.price_predictor is not None:
            return {"status": "model_already_trained"}
        
        logger.info("Starting price predictor training...")
        
        # Get stocks to train on
        if stocks is None:
            stocks = list(StockSymbol.objects.filter(is_active=True)[:50])  # Limit for performance
        
        # Collect training data with enhanced features
        X, y = self._collect_enhanced_training_data(stocks)
        
        if X is None or len(X) < 100:
            return {"status": "insufficient_data", "samples": len(X) if X is not None else 0}
        
        if not isinstance(X, np.ndarray) or not isinstance(y, np.ndarray):
            logger.error("Training data is not in correct numpy array format")
            return {"status": "data_format_error"}
        
        logger.info(f"Collected training data: X shape {X.shape}, y shape {y.shape}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # For 2D data (no sequence dimension), use simple normalization
        if len(X_train.shape) == 2:
            # Normalize features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
        else:
            # For 3D data with sequences
            X_train_scaled = self.scaler.fit_transform(X_train.reshape(-1, X_train.shape[-1]))
            X_train_scaled = X_train_scaled.reshape(X_train.shape)
            X_test_scaled = self.scaler.transform(X_test.reshape(-1, X_test.shape[-1]))
            X_test_scaled = X_test_scaled.reshape(X_test.shape)
        
        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train_scaled)
        y_train_tensor = torch.FloatTensor(y_train).unsqueeze(1)
        X_test_tensor = torch.FloatTensor(X_test_scaled)
        y_test_tensor = torch.FloatTensor(y_test).unsqueeze(1)
        
        # Initialize model based on data dimensions
        input_size = X_train.shape[-1]
        
        # For 2D data, use a simple feedforward network instead of LSTM
        if len(X_train.shape) == 2:
            self.price_predictor = SimpleStockPredictor(input_size=input_size)
        else:
            self.price_predictor = StockPricePredictor(input_size=input_size)
        
        # Training loop
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.price_predictor.parameters(), lr=self.config['learning_rate'])
        
        best_loss = float('inf')
        patience_counter = 0
        epoch = 0
        loss = None
        val_loss = None
        
        for epoch in range(self.config['epochs']):
            self.price_predictor.train()
            
            # Forward pass
            outputs = self.price_predictor(X_train_tensor)
            loss = criterion(outputs, y_train_tensor)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Validation
            if epoch % 10 == 0:
                self.price_predictor.eval()
                with torch.no_grad():
                    val_outputs = self.price_predictor(X_test_tensor)
                    val_loss = criterion(val_outputs, y_test_tensor)
                
                logger.info(f"Epoch {epoch}: Train Loss: {loss.item():.6f}, Val Loss: {val_loss.item():.6f}")
                
                # Early stopping
                if val_loss < best_loss:
                    best_loss = val_loss
                    patience_counter = 0
                    # Save best model
                    torch.save(self.price_predictor.state_dict(), self.models_dir / 'price_predictor.pth')
                else:
                    patience_counter += 1
                    
                if patience_counter >= self.config['early_stopping_patience']:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break
        
        # Save scaler
        joblib.dump(self.scaler, self.models_dir / 'scaler.joblib')
        
        return {
            "status": "training_completed",
            "epochs": epoch + 1,
            "final_train_loss": loss.item() if loss is not None else 0.0,
            "final_val_loss": val_loss.item() if val_loss is not None else 0.0,
            "training_samples": len(X_train),
            "test_samples": len(X_test)
        }
    
    def _collect_enhanced_training_data(self, stocks: List[StockSymbol]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Collect enhanced training data including news sentiment and calendar events.
        Combines technical indicators with fundamental analysis.
        """
        X_data, y_data = [], []
        
        for stock in stocks:
            try:
                # Get recent trading sessions (last 3 months for more data)
                end_date = date.today()
                start_date = end_date - timedelta(days=90)
                
                sessions = TradingSession.objects.filter(
                    date__gte=start_date,
                    date__lte=end_date
                ).order_by('date')
                
                if sessions.count() < 20:
                    continue
                
                # For each session, extract enhanced features
                for session in sessions:
                    # Get stock data for this session
                    session_data = StockData.objects.filter(
                        stock=stock,
                        trading_session=session
                    ).order_by('data_timestamp')
                    
                    if session_data.count() < 3:
                        continue
                    
                    # Get current and target data points
                    data_points = list(session_data)
                    for i in range(len(data_points) - self.config['prediction_horizon_hours']):
                        current = data_points[i]
                        if not all([current.open_price, current.high_price, current.low_price, current.close_price]):
                            continue
                        
                        # Target data point (4 hours later)
                        target_idx = min(i + self.config['prediction_horizon_hours'], len(data_points) - 1)
                        target = data_points[target_idx]
                        
                        if not target.close_price or not current.close_price:
                            continue
                        
                        # Calculate price change percentage
                        current_price = float(current.close_price)
                        target_price = float(target.close_price)
                        price_change = (target_price - current_price) / current_price
                        
                        # Extract enhanced features
                        features = self._extract_enhanced_features(stock, session, data_points[:i+1], current)
                        if features is None or len(features) < 20:
                            continue
                        
                        X_data.append(features)
                        y_data.append(price_change)
                
            except Exception as e:
                logger.error(f"Error processing stock {stock.symbol} for enhanced training: {e}")
                continue
        
        if len(X_data) < 100:
            logger.warning(f"Insufficient enhanced training data: only {len(X_data)} samples")
            return None, None
        
        return np.array(X_data), np.array(y_data)
    
    def _extract_enhanced_features(self, stock: StockSymbol, session: TradingSession, 
                                 data_points: List[StockData], current: StockData) -> Optional[List[float]]:
        """
        Extract comprehensive features including technical indicators, news sentiment, and calendar events.
        """
        try:
            features = []
            
            # 1. Technical features (baseline - 10 features)
            tech_features = self._extract_intraday_features(data_points, current)
            if tech_features is None:
                return None
            features.extend(tech_features)
            
            # 2. News sentiment features (5 features)
            news_features = self._extract_news_features(stock, session)
            features.extend(news_features)
            
            # 3. Calendar event features (5 features)
            calendar_features = self._extract_calendar_features(stock, session)
            features.extend(calendar_features)
            
            # 4. Market context features (5 features)
            market_features = self._extract_market_context_features(stock, session, current)
            features.extend(market_features)
            
            # Ensure we have exactly 25 features
            while len(features) < 25:
                features.append(0.0)
            
            return features[:25]
            
        except Exception as e:
            logger.error(f"Error extracting enhanced features for {stock.symbol}: {e}")
            return None
    
    def _extract_news_features(self, stock: StockSymbol, session: TradingSession) -> List[float]:
        """
        Extract sentiment and news impact features for the stock.
        """
        try:
            features = []
            
            # Get news from last 7 days affecting this stock
            start_date = session.date - timedelta(days=7)
            
            # News mentioning this specific stock
            stock_news = NewsArticleModel.objects.filter(
                published_date__date__gte=start_date,
                published_date__date__lte=session.date,
                stock_symbols__contains=[stock.symbol]
            ).filter(deleted_at__isnull=True)
            
            # 1. News sentiment score (weighted average)
            sentiment_scores = []
            relevance_weights = []
            
            for news in stock_news:
                if news.sentiment_score is not None:
                    sentiment_scores.append(float(news.sentiment_score))
                    # Weight by recency and relevance
                    days_ago = (session.date - news.published_date.date()).days
                    recency_weight = max(0.1, 1.0 - (days_ago / 7.0))
                    relevance_weights.append(recency_weight * news.relevance_score)
            
            if sentiment_scores and relevance_weights:
                weighted_sentiment = np.average(sentiment_scores, weights=relevance_weights)
                features.append(weighted_sentiment)
            else:
                features.append(0.0)  # Neutral if no news
            
            # 2. News volume (number of articles in last 7 days)
            news_count = stock_news.count()
            features.append(min(1.0, news_count / 10.0))  # Normalize to 0-1
            
            # 3. News recency impact (boost for very recent news)
            recent_news = stock_news.filter(
                published_date__date=session.date
            ).count()
            features.append(min(1.0, recent_news / 5.0))  # Same-day news impact
            
            # 4. Industry/sector news sentiment
            if stock.primary_industry:
                industry_news = NewsArticleModel.objects.filter(
                    published_date__date__gte=start_date,
                    published_date__date__lte=session.date,
                    tags__contains=[stock.primary_industry.name.lower()]
                ).filter(deleted_at__isnull=True)
                
                industry_sentiments = [
                    float(news.sentiment_score) for news in industry_news 
                    if news.sentiment_score is not None
                ]
                
                if industry_sentiments:
                    features.append(np.mean(industry_sentiments))
                else:
                    features.append(0.0)
            else:
                features.append(0.0)
            
            # 5. News trend (sentiment change over time)
            old_news = stock_news.filter(
                published_date__date__gte=start_date,
                published_date__date__lt=session.date - timedelta(days=3)
            )
            recent_news_objects = stock_news.filter(
                published_date__date__gte=session.date - timedelta(days=3),
                published_date__date__lte=session.date
            )
            
            old_sentiment = np.mean([
                float(news.sentiment_score) for news in old_news 
                if news.sentiment_score is not None
            ]) if old_news.exists() else 0.0
            
            recent_sentiment = np.mean([
                float(news.sentiment_score) for news in recent_news_objects 
                if news.sentiment_score is not None
            ]) if recent_news_objects.exists() else 0.0
            
            sentiment_trend = recent_sentiment - old_sentiment
            features.append(sentiment_trend)
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting news features: {e}")
            return [0.0, 0.0, 0.0, 0.0, 0.0]
    
    def _extract_calendar_features(self, stock: StockSymbol, session: TradingSession) -> List[float]:
        """
        Extract calendar event features that can impact stock price.
        """
        try:
            features = []
            
            # Look at events within next 30 days from session date
            end_date = session.date + timedelta(days=30)
            
            upcoming_events = CompanyCalendarEvent.objects.filter(
                stock_symbol=stock,
                event_date__date__gte=session.date,
                event_date__date__lte=end_date
            ).filter(deleted_at__isnull=True)
            
            # 1. Days until next major event
            next_major_event = upcoming_events.filter(
                impact_level__in=['high', 'critical']
            ).order_by('event_date').first()
            
            if next_major_event:
                days_until = (next_major_event.event_date.date() - session.date).days
                features.append(max(0.0, 1.0 - (days_until / 30.0)))  # Closer = higher impact
            else:
                features.append(0.0)
            
            # 2. Event impact score (weighted by proximity and importance)
            total_impact = 0.0
            for event in upcoming_events:
                days_until = (event.event_date.date() - session.date).days
                proximity_weight = max(0.1, 1.0 - (days_until / 30.0))
                
                # Impact based on event type
                impact_weights = {
                    'earnings': 0.9,
                    'dividend': 0.7,
                    'ex_dividend': 0.6,
                    'agm': 0.5,
                    'conference': 0.4,
                    'split': 0.8,
                    'merger': 1.0,
                    'ipo': 0.9,
                    'delisting': 1.0,
                    'other': 0.3
                }
                
                event_impact = impact_weights.get(event.event_type, 0.3)
                
                # Adjust by impact level
                level_multipliers = {
                    'low': 0.5,
                    'medium': 0.7,
                    'high': 0.9,
                    'critical': 1.0
                }
                event_impact *= level_multipliers.get(event.impact_level, 0.7)
                
                total_impact += event_impact * proximity_weight
            
            features.append(min(1.0, total_impact))
            
            # 3. Earnings event proximity
            earnings_event = upcoming_events.filter(
                event_type='earnings'
            ).order_by('event_date').first()
            
            if earnings_event:
                days_until = (earnings_event.event_date.date() - session.date).days
                features.append(max(0.0, 1.0 - (days_until / 14.0)))  # 2-week horizon
            else:
                features.append(0.0)
            
            # 4. Date change sentiment (recent postponements/advances)
            recent_changes = EventDateChange.objects.filter(
                event__stock_symbol=stock,
                detected_at__gte=session.date - timedelta(days=7)
            )
            
            if recent_changes.exists():
                # Count negative vs positive sentiment impacts
                negative_changes = recent_changes.filter(
                    sentiment_impact='negative'
                ).count()
                positive_changes = recent_changes.filter(
                    sentiment_impact='positive'
                ).count()
                
                change_sentiment = (positive_changes - negative_changes) / max(1, recent_changes.count())
                features.append(change_sentiment)  # -1 to +1
            else:
                features.append(0.0)
            
            # 5. Dividend proximity effect
            dividend_events = upcoming_events.filter(
                event_type__in=['dividend', 'ex_dividend']
            ).order_by('event_date')
            
            if dividend_events.exists():
                next_dividend = dividend_events.first()
                if next_dividend:
                    days_until = (next_dividend.event_date.date() - session.date).days
                    
                    # Dividend events typically cause price movements as ex-date approaches
                    if next_dividend.event_type == 'ex_dividend':
                        # Ex-dividend date approaching - negative pressure expected
                        features.append(-max(0.0, 1.0 - (days_until / 7.0)))
                    else:
                        # Dividend announcement - positive sentiment
                        features.append(max(0.0, 1.0 - (days_until / 14.0)))
                else:
                    features.append(0.0)
            else:
                features.append(0.0)
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting calendar features: {e}")
            return [0.0, 0.0, 0.0, 0.0, 0.0]
    
    def _extract_market_context_features(self, stock: StockSymbol, session: TradingSession, 
                                        current: StockData) -> List[float]:
        """
        Extract broader market context features.
        """
        try:
            features = []
            
            # 1. Sector performance (relative to this stock)
            if stock.primary_industry:
                # Get other stocks in same industry
                sector_stocks = StockSymbol.objects.filter(
                    primary_industry=stock.primary_industry,
                    is_active=True
                ).exclude(pk=stock.pk)[:20]  # Limit for performance
                
                if sector_stocks.exists():
                    # Calculate sector average price change for this session
                    sector_changes = []
                    
                    for sector_stock in sector_stocks:
                        stock_data = StockData.objects.filter(
                            stock=sector_stock,
                            trading_session=session
                        ).aggregate(
                            first_price=Min('open_price'),
                            last_price=Max('close_price')
                        )
                        
                        if stock_data['first_price'] and stock_data['last_price']:
                            change = (float(stock_data['last_price']) - float(stock_data['first_price'])) / float(stock_data['first_price'])
                            sector_changes.append(change)
                    
                    if sector_changes:
                        features.append(np.mean(sector_changes))
                    else:
                        features.append(0.0)
                else:
                    features.append(0.0)
            else:
                features.append(0.0)
            
            # 2. Trading session progress
            session_start = timezone.make_aware(datetime.combine(session.date, datetime.min.time()))
            current_time = current.data_timestamp if current.data_timestamp else session_start
            
            # Ensure current_time is timezone-aware
            if timezone.is_naive(current_time):
                current_time = timezone.make_aware(current_time)
            
            session_progress = min(1.0, (current_time - session_start).total_seconds() / 28800)  # 8 hours
            features.append(session_progress)
            
            # 3. Day of week effect
            day_of_week = session.date.weekday()  # 0=Monday, 6=Sunday
            features.append(day_of_week / 6.0)  # Normalize to 0-1
            
            # 4. Month effect (some months historically more volatile)
            month = session.date.month
            features.append(month / 12.0)  # Normalize to 0-1
            
            # 5. Volume relative to recent average
            recent_volumes = StockData.objects.filter(
                stock=stock,
                trading_session__date__gte=session.date - timedelta(days=20),
                trading_session__date__lt=session.date
            ).aggregate(avg_volume=Avg('volume'))
            
            current_volume = getattr(current, 'volume', 0)
            avg_volume = recent_volumes['avg_volume']
            
            if avg_volume and avg_volume > 0 and current_volume:
                volume_ratio = float(current_volume) / float(avg_volume)
                features.append(min(3.0, volume_ratio) / 3.0)  # Cap at 3x average, normalize
            else:
                features.append(0.5)  # Neutral if no data
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting market context features: {e}")
            return [0.0, 0.0, 0.0, 0.0, 0.5]

    def _collect_price_training_data(self, stocks: List[StockSymbol]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Collect real intraday data for training price prediction model.
        Focus on predicting price movements within the same trading session.
        """
        X_data, y_data = [], []
        
        for stock in stocks:
            try:
                # Get recent trading sessions (last 2 months)
                end_date = date.today()
                start_date = end_date - timedelta(days=60)
                
                sessions = TradingSession.objects.filter(
                    date__gte=start_date,
                    date__lte=end_date
                ).order_by('date')
                
                if sessions.count() < 20:
                    continue
                
                # For each session, build intraday sequences
                for session in sessions:
                    # Get all data points for this session, ordered by timestamp
                    session_data = StockData.objects.filter(
                        stock=stock,
                        trading_session=session
                    ).order_by('data_timestamp')
                    
                    if session_data.count() < 10:  # Need enough intraday points
                        continue
                    
                    # Create sequences within the session
                    data_points = list(session_data)
                    
                    # Use sliding window approach for intraday prediction
                    for i in range(len(data_points) - self.config['prediction_horizon_hours']):
                        # Current data point
                        current = data_points[i]
                        if not all([current.open_price, current.high_price, current.low_price, current.close_price]):
                            continue
                        
                        # Target data point (4 hours later, or closest available)
                        target_idx = min(i + self.config['prediction_horizon_hours'], len(data_points) - 1)
                        target = data_points[target_idx]
                        
                        if not target.close_price or not current.close_price:
                            continue
                        
                        # Calculate price change percentage within session
                        current_price = float(current.close_price)
                        target_price = float(target.close_price)
                        price_change = (target_price - current_price) / current_price
                        
                        # Prepare features based on current state
                        features = self._extract_intraday_features(data_points[:i+1], current)
                        if features is None:
                            continue
                        
                        X_data.append(features)
                        y_data.append(price_change)
                
            except Exception as e:
                logger.error(f"Error processing stock {stock.symbol} for training: {e}")
                continue
        
        if len(X_data) < 100:
            return None, None
        
        return np.array(X_data), np.array(y_data)
    
    def _extract_intraday_features(self, data_points: List[StockData], current: StockData) -> Optional[List[float]]:
        """
        Extract intraday features for real-time trading prediction.
        Focus on features that matter for same-day price movements.
        """
        try:
            if len(data_points) < 3:  # Need minimum data
                return None
            
            features = []
            
            # Current price metrics
            current_price = float(current.close_price or 0)
            current_volume = float(current.volume or 0)
            current_high = float(current.high_price or 0)
            current_low = float(current.low_price or 0)
            current_open = float(current.open_price or 0)
            
            if current_price == 0:
                return None
            
            # Intraday price movements
            session_open = float(data_points[0].open_price or 0)
            if session_open > 0:
                features.append((current_price - session_open) / session_open)  # Session performance
            else:
                features.append(0.0)
            
            # High/Low ratios
            if current_low > 0 and current_high > current_low:
                features.append(current_high / current_low)  # Daily range
                features.append((current_price - current_low) / (current_high - current_low))  # Position in range
            else:
                features.extend([1.0, 0.5])
            
            # Volume analysis (last few data points)
            recent_volumes = [float(dp.volume or 0) for dp in data_points[-5:] if dp.volume]
            if recent_volumes:
                avg_volume = sum(recent_volumes) / len(recent_volumes)
                if avg_volume > 0:
                    features.append(current_volume / avg_volume)  # Volume ratio
                else:
                    features.append(1.0)
            else:
                features.append(1.0)
            
            # Price momentum (last few ticks)
            if len(data_points) >= 3:
                prices = [float(dp.close_price or 0) for dp in data_points[-3:] if dp.close_price]
                if len(prices) >= 2:
                    # Short-term momentum
                    recent_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
                    features.append(recent_change)
                    
                    # Price acceleration
                    if len(prices) >= 3:
                        change1 = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0
                        change2 = (prices[-2] - prices[-3]) / prices[-3] if prices[-3] > 0 else 0
                        features.append(change1 - change2)  # Acceleration
                    else:
                        features.append(0.0)
                else:
                    features.extend([0.0, 0.0])
            else:
                features.extend([0.0, 0.0])
            
            # Time-based features (position in trading session)
            session_start = data_points[0].data_timestamp
            current_time = current.data_timestamp
            session_duration = (current_time - session_start).total_seconds()
            
            # Normalize to session progress (0-1)
            # Assume 8-hour trading session (28800 seconds)
            session_progress = min(1.0, session_duration / 28800)
            features.append(session_progress)
            
            # Market microstructure features
            # Bid-ask spread proxy (high-low as percentage of price)
            if current_price > 0:
                spread_proxy = (current_high - current_low) / current_price
                features.append(spread_proxy)
            else:
                features.append(0.0)
            
            # Recent volatility
            if len(data_points) >= 5:
                recent_prices = [float(dp.close_price or 0) for dp in data_points[-5:] if dp.close_price]
                if len(recent_prices) >= 3:
                    price_returns = []
                    for i in range(1, len(recent_prices)):
                        if recent_prices[i-1] > 0:
                            price_returns.append(recent_prices[i] / recent_prices[i-1] - 1)
                    
                    if price_returns:
                        volatility = np.std(price_returns)
                        features.append(volatility)
                    else:
                        features.append(0.0)
                else:
                    features.append(0.0)
            else:
                features.append(0.0)
            
            # Ensure we have exactly the expected number of features
            while len(features) < 10:
                features.append(0.0)
            
            return features[:10]  # Return first 10 features
            
        except Exception as e:
            logger.error(f"Error extracting intraday features: {e}")
            return None
    
    def predict_price(self, stock: StockSymbol, session: TradingSession) -> Optional[Dict[str, Any]]:
        """
        Predict intraday price movement for same-session trading.
        """
        if self.price_predictor is None:
            return None
        
        try:
            # Get recent intraday data for this session
            session_data = StockData.objects.filter(
                stock=stock,
                trading_session=session
            ).order_by('data_timestamp')
            
            if session_data.count() < 3:
                return None
            
            # Get current data point
            latest_data = session_data.last()
            if not latest_data or not latest_data.close_price:
                return None
            
            # Extract enhanced features (instead of just intraday)
            data_points = list(session_data)
            
            # Try enhanced features first (if we have the enhanced model)
            features = self._extract_enhanced_features(stock, session, data_points, latest_data)
            
            # Fall back to basic intraday features if enhanced extraction fails
            if features is None or len(features) < 20:
                logger.warning(f"Enhanced features failed for {stock.symbol}, falling back to basic features")
                features = self._extract_intraday_features(data_points, latest_data)
                
                if features is None:
                    return None
            
            # Determine model type and prepare input accordingly
            if isinstance(self.price_predictor, SimpleStockPredictor):
                # For feedforward network, use enhanced features directly
                if len(features) == 25:  # Enhanced features
                    features_array = np.array(features).reshape(1, -1)
                else:  # Basic intraday features, pad to expected size
                    features_padded = features + [0.0] * (25 - len(features))
                    features_array = np.array(features_padded[:25]).reshape(1, -1)
                
                # Scale features if scaler exists
                if self.scaler is not None:
                    features_array = self.scaler.transform(features_array)
            else:
                # For LSTM, reshape to sequence format (legacy support)
                features_array = np.array(features).reshape(1, 1, -1)
            
            # Predict using the model
            self.price_predictor.eval()
            with torch.no_grad():
                input_tensor = torch.FloatTensor(features_array)
                prediction = self.price_predictor(input_tensor)
                predicted_change = prediction.item()
            
            # Calculate target price and time
            current_price = float(latest_data.close_price)
            predicted_price = current_price * (1 + predicted_change)
            
            # Calculate confidence based on model certainty and market conditions
            confidence = self._calculate_enhanced_confidence(features, predicted_change, stock, session)
            
            # Extract prediction factors for user insight
            prediction_factors = self._analyze_prediction_factors(features, stock, session)
            
            result = {
                'current_price': current_price,
                'predicted_price': predicted_price,
                'predicted_change_percent': predicted_change * 100,
                'confidence': confidence,
                'horizon_hours': self.config['prediction_horizon_hours'],
                'prediction_type': 'enhanced_intraday',
                'model_type': 'SimpleStockPredictor' if isinstance(self.price_predictor, SimpleStockPredictor) else 'StockPricePredictor',
                'features_used': len(features),
                'prediction_factors': prediction_factors
            }
            
            # Add technical indicator summary
            if len(features) >= 10:
                result['session_progress'] = features[6] if len(features) > 6 else 0.0
                result['volume_indicator'] = features[3] if len(features) > 3 else 0.0
                result['momentum_indicator'] = features[4] if len(features) > 4 else 0.0
            
            return result
            
        except Exception as e:
            logger.error(f"Error predicting intraday price for {stock.symbol}: {e}")
            return None
    
    def _calculate_enhanced_confidence(self, features: List[float], predicted_change: float, 
                                     stock: StockSymbol, session: TradingSession) -> float:
        """
        Calculate enhanced confidence score considering all factors.
        """
        try:
            # Base confidence
            confidence = 0.8
            
            # Adjust based on prediction magnitude
            change_magnitude = abs(predicted_change)
            if change_magnitude > 0.05:  # Large change (>5%)
                confidence *= 0.85  # Less confident in extreme moves
            elif change_magnitude < 0.005:  # Very small change (<0.5%)
                confidence *= 0.9  # Slightly less confident in tiny moves
            
            # Enhanced features boost confidence
            if len(features) >= 25:
                confidence *= 1.1  # Enhanced features available
                
                # News sentiment factor (features 10-14)
                if len(features) > 14:
                    news_sentiment = features[10] if features[10] != 0 else None
                    if news_sentiment is not None:
                        # Strong sentiment (positive or negative) increases confidence
                        sentiment_strength = abs(news_sentiment)
                        confidence *= (1.0 + sentiment_strength * 0.1)
                
                # Calendar events factor (features 15-19)
                if len(features) > 19:
                    event_impact = features[15] if features[15] != 0 else None
                    if event_impact is not None and event_impact > 0.5:
                        confidence *= 1.05  # Major events increase confidence
            
            # Volatility adjustment (if available in features)
            if len(features) > 8:
                volatility = features[8] if len(features) > 8 else 0.02
                if volatility > 0.03:  # High volatility
                    confidence *= 0.9
                elif volatility < 0.01:  # Low volatility  
                    confidence *= 1.05
            
            # Volume confirmation
            if len(features) > 3:
                volume_ratio = features[3]
                if volume_ratio > 1.5:  # High volume supports prediction
                    confidence *= 1.05
                elif volume_ratio < 0.5:  # Low volume reduces confidence
                    confidence *= 0.95
            
            return min(0.95, max(0.3, confidence))
            
        except Exception as e:
            logger.error(f"Error calculating enhanced confidence: {e}")
            return 0.7
    
    def _analyze_prediction_factors(self, features: List[float], stock: StockSymbol, 
                                  session: TradingSession) -> Dict[str, Any]:
        """
        Analyze which factors are most influential in the prediction.
        """
        try:
            factors = {
                'technical': {},
                'news': {},
                'calendar': {},
                'market': {}
            }
            
            if len(features) >= 25:  # Enhanced features
                # Technical factors (0-9)
                factors['technical'] = {
                    'session_performance': features[0],
                    'price_range_position': features[2] if len(features) > 2 else 0,
                    'volume_ratio': features[3] if len(features) > 3 else 0,
                    'momentum': features[4] if len(features) > 4 else 0,
                    'volatility': features[8] if len(features) > 8 else 0
                }
                
                # News factors (10-14)
                factors['news'] = {
                    'sentiment_score': features[10],
                    'news_volume': features[11], 
                    'recent_news_impact': features[12],
                    'industry_sentiment': features[13],
                    'sentiment_trend': features[14]
                }
                
                # Calendar factors (15-19)
                factors['calendar'] = {
                    'major_event_proximity': features[15],
                    'total_event_impact': features[16],
                    'earnings_proximity': features[17],
                    'date_change_sentiment': features[18],
                    'dividend_effect': features[19]
                }
                
                # Market factors (20-24)
                factors['market'] = {
                    'sector_performance': features[20],
                    'session_progress': features[21],
                    'day_of_week': features[22],
                    'month_effect': features[23],
                    'volume_vs_average': features[24]
                }
                
                # Identify dominant factors
                dominant_factors = []
                
                if abs(factors['news']['sentiment_score']) > 0.3:
                    dominant_factors.append('news_sentiment')
                if factors['calendar']['major_event_proximity'] > 0.7:
                    dominant_factors.append('upcoming_event')
                if factors['technical']['volume_ratio'] > 2.0:
                    dominant_factors.append('high_volume')
                if abs(factors['technical']['momentum']) > 0.05:
                    dominant_factors.append('price_momentum')
                    
                factors['dominant_factors'] = dominant_factors
                factors['summary'] = {
                    'total_factors': len(dominant_factors),
                    'primary_driver': dominant_factors[0] if dominant_factors else 'technical'
                }
            
            return factors
            
        except Exception as e:
            logger.error(f"Error analyzing prediction factors: {e}")
            return {'error': str(e)}

    def _calculate_intraday_confidence(self, features: List[float], predicted_change: float) -> float:
        """
        Calculate confidence score for intraday predictions.
        """
        try:
            # Base confidence
            confidence = 0.7
            
            # Adjust based on prediction magnitude
            change_magnitude = abs(predicted_change)
            if change_magnitude > 0.05:  # Large change (>5%)
                confidence *= 0.8  # Less confident in extreme moves
            elif change_magnitude < 0.01:  # Small change (<1%)
                confidence *= 0.9  # Slightly less confident in tiny moves
            
            # Adjust based on volatility
            if len(features) > 8:
                volatility = features[8]  # Recent volatility feature
                if volatility > 0.02:  # High volatility
                    confidence *= 0.85
                elif volatility < 0.005:  # Low volatility
                    confidence *= 1.1
            
            # Adjust based on session progress
            if len(features) > 6:
                session_progress = features[6]
                if session_progress > 0.8:  # Late in session
                    confidence *= 1.05  # More confident near close
                elif session_progress < 0.2:  # Early in session
                    confidence *= 0.95  # Less confident early
            
            return min(0.95, max(0.3, confidence))
            
        except Exception:
            return 0.7
    
    def learn_from_feedback(self, anomaly_alert: AnomalyAlert, user_feedback: Dict[str, Any]):
        """
        Learn from user feedback to improve model accuracy.
        """
        try:
            # Store feedback for future training
            feedback_data = {
                'alert_id': anomaly_alert.pk,
                'stock_symbol': anomaly_alert.stock.symbol,
                'anomaly_type': anomaly_alert.anomaly_type,
                'predicted_confidence': float(anomaly_alert.confidence_score),
                'user_rating': user_feedback.get('rating', 0),  # 1-5 scale
                'was_useful': user_feedback.get('useful', False),
                'feedback_timestamp': timezone.now().isoformat(),
                'market_outcome': user_feedback.get('market_outcome', 'unknown')
            }
            
            # Save to feedback file
            feedback_file = self.models_dir / 'feedback_log.jsonl'
            with open(feedback_file, 'a') as f:
                f.write(json.dumps(feedback_data) + '\n')
            
            logger.info(f"Recorded feedback for alert {anomaly_alert.pk}")
            
            # Trigger retraining if enough feedback accumulated
            self._check_retrain_trigger()
            
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
    
    def _check_retrain_trigger(self):
        """
        Check if enough feedback has been collected to trigger retraining.
        """
        feedback_file = self.models_dir / 'feedback_log.jsonl'
        if not feedback_file.exists():
            return
        
        # Count feedback entries
        with open(feedback_file, 'r') as f:
            feedback_count = sum(1 for _ in f)
        
        # Retrain if we have enough feedback (every 100 entries)
        if feedback_count % 100 == 0:
            logger.info(f"Triggering model retraining with {feedback_count} feedback entries")
            # Schedule retraining task (implement as background job)
            # self._schedule_retraining()

    def train_anomaly_detector(self) -> Dict[str, Any]:
        """
        Train the anomaly detection model for trading recommendations.
        Uses historical patterns to detect unusual market behavior.
        """
        try:
            logger.info("Starting anomaly detector training...")
            
            # Initialize anomaly detector if not exists
            if not hasattr(self, 'anomaly_detector') or self.anomaly_detector is None:
                self.anomaly_detector = AnomalyDetectionNN(
                    input_size=25,  # Number of features for anomaly detection
                    hidden_sizes=[64, 32, 16]  # Hidden layer sizes
                )
            
            # Prepare training data for anomaly detection
            X_normal, X_anomaly = self._prepare_anomaly_training_data()
            
            if X_normal is None or len(X_normal) < 200:
                return {
                    'status': 'error',
                    'message': 'Insufficient normal data for anomaly training',
                    'details': 'Need at least 200 normal patterns'
                }
            
            # Convert to tensors
            X_normal_tensor = torch.FloatTensor(X_normal)
            
            if X_anomaly is not None and len(X_anomaly) > 0:
                X_anomaly_tensor = torch.FloatTensor(X_anomaly)
                logger.info(f"Training with {len(X_normal)} normal + {len(X_anomaly)} anomaly samples")
            else:
                X_anomaly_tensor = None
                logger.info(f"Training with {len(X_normal)} normal samples (unsupervised)")
            
            # Split normal data
            train_size = int(0.8 * len(X_normal_tensor))
            X_train = X_normal_tensor[:train_size]
            X_val = X_normal_tensor[train_size:]
            
            # Training setup for autoencoder approach
            optimizer = torch.optim.Adam(self.anomaly_detector.parameters(), lr=0.001)
            criterion = nn.MSELoss()
            
            # Training loop
            num_epochs = 300
            batch_size = 32
            best_val_loss = float('inf')
            patience = 30
            patience_counter = 0
            epoch = 0  # Initialize epoch counter
            
            train_losses = []
            val_losses = []
            
            logger.info(f"Anomaly detector training with {len(X_train)} samples")
            
            for epoch in range(num_epochs):
                # Training phase - reconstruct normal patterns
                self.anomaly_detector.train()
                train_loss = 0.0
                
                for i in range(0, len(X_train), batch_size):
                    batch_X = X_train[i:i+batch_size]
                    
                    optimizer.zero_grad()
                    
                    # Forward pass - anomaly detector returns reconstruction and anomaly score
                    reconstructed, anomaly_score = self.anomaly_detector(batch_X)
                    
                    # Loss is reconstruction error for normal patterns
                    loss = criterion(reconstructed, batch_X)
                    
                    loss.backward()
                    optimizer.step()
                    
                    train_loss += loss.item()
                
                train_loss /= (len(X_train) // batch_size + 1)
                
                # Validation
                self.anomaly_detector.eval()
                with torch.no_grad():
                    val_reconstructed, _ = self.anomaly_detector(X_val)
                    val_loss = criterion(val_reconstructed, X_val).item()
                
                train_losses.append(train_loss)
                val_losses.append(val_loss)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        logger.info(f"Early stopping at epoch {epoch}")
                        break
                
                if epoch % 50 == 0:
                    logger.info(f"Epoch {epoch}: Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}")
            
            # Calculate anomaly threshold from validation set
            self.anomaly_detector.eval()
            with torch.no_grad():
                _, val_anomaly_scores = self.anomaly_detector(X_val)
                
                # Set threshold at 95th percentile of normal validation scores
                anomaly_threshold = torch.quantile(val_anomaly_scores, 0.95).item()
                self.anomaly_threshold = anomaly_threshold
                
                logger.info(f"Anomaly threshold set to: {anomaly_threshold:.6f}")
            
            # Test on anomaly data if available
            anomaly_detection_accuracy = None
            if X_anomaly_tensor is not None:
                with torch.no_grad():
                    _, anomaly_scores = self.anomaly_detector(X_anomaly_tensor)
                    detected_anomalies = (anomaly_scores > anomaly_threshold).float()
                    anomaly_detection_accuracy = detected_anomalies.mean().item()
                    logger.info(f"Anomaly detection accuracy: {anomaly_detection_accuracy:.3f}")
            
            # Save model and threshold
            torch.save(self.anomaly_detector.state_dict(), self.models_dir / 'anomaly_detector.pth')
            torch.save(torch.tensor(anomaly_threshold), self.models_dir / 'anomaly_threshold.pth')
            logger.info(f"Saved anomaly detector model and threshold: {anomaly_threshold:.6f}")
            
            # Update statistics
            self.last_training_time = timezone.now()
            self.model_performance_stats = {
                'reconstruction_loss': float(best_val_loss),
                'anomaly_threshold': float(anomaly_threshold),
                'training_samples': len(X_train),
                'validation_samples': len(X_val),
                'epochs_trained': epoch + 1 if 'epoch' in locals() else 0,
                'model_type': 'anomaly_detector'
            }
            
            if anomaly_detection_accuracy is not None:
                self.model_performance_stats['anomaly_detection_accuracy'] = float(anomaly_detection_accuracy)
            
            result = {
                'status': 'success',
                'message': f'Anomaly detector trained with {len(X_train)} normal patterns',
                'details': {
                    'reconstruction_loss': float(best_val_loss),
                    'anomaly_threshold': float(anomaly_threshold),
                    'epochs': epoch + 1 if 'epoch' in locals() else 0,
                    'training_samples': len(X_train),
                    'validation_samples': len(X_val)
                }
            }
            
            if anomaly_detection_accuracy is not None:
                result['details']['anomaly_detection_accuracy'] = float(anomaly_detection_accuracy)
            
            logger.info(f"Anomaly detector training completed: {result['details']}")
            return result
            
        except Exception as e:
            logger.error(f"Error during anomaly detector training: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Anomaly training failed: {str(e)}',
                'details': {'error_type': type(e).__name__}
            }

    def _prepare_anomaly_training_data(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Prepare training data specifically for anomaly detection.
        Returns normal patterns and known anomalous patterns separately.
        """
        try:
            normal_patterns = []
            anomalous_patterns = []
            
            # Get monitored stocks
            stocks = StockSymbol.objects.filter(is_monitored=True)
            
            for stock in stocks:
                # Get recent data for pattern analysis
                end_date = date.today()
                start_date = end_date - timedelta(days=60)  # 2 months of data
                
                stock_data = StockData.objects.filter(
                    stock=stock,
                    trading_session__date__gte=start_date,
                    trading_session__date__lte=end_date
                ).order_by('trading_session__date', 'data_timestamp')
                
                if stock_data.count() < 30:
                    continue
                
                # Extract patterns for anomaly detection
                data_points = list(stock_data)
                
                # Calculate statistical measures for each time window
                for i in range(10, len(data_points) - 5):
                    try:
                        # Extract anomaly detection features
                        features = self._extract_anomaly_features(data_points, i, stock)
                        if features is None or len(features) != 25:
                            continue
                        
                        # Determine if this is normal or anomalous pattern
                        is_anomaly = self._is_anomalous_pattern(data_points, i)
                        
                        if is_anomaly:
                            anomalous_patterns.append(features)
                        else:
                            normal_patterns.append(features)
                            
                    except Exception as e:
                        logger.warning(f"Error processing pattern {i} for {stock.symbol}: {e}")
                        continue
            
            if len(normal_patterns) < 200:
                logger.error(f"Insufficient normal patterns: {len(normal_patterns)}")
                return None, None
            
            logger.info(f"Prepared {len(normal_patterns)} normal and {len(anomalous_patterns)} anomalous patterns")
            
            return (
                np.array(normal_patterns) if normal_patterns else None,
                np.array(anomalous_patterns) if anomalous_patterns else None
            )
            
        except Exception as e:
            logger.error(f"Error preparing anomaly training data: {e}", exc_info=True)
            return None, None
    
    def _extract_anomaly_features(self, data_points: List, index: int, stock: StockSymbol) -> Optional[List[float]]:
        """
        Extract features specifically designed for anomaly detection.
        Focus on patterns that indicate unusual market behavior.
        """
        try:
            if index < 10 or index >= len(data_points) - 1:
                return None
            
            features = []
            current = data_points[index]
            
            if not all([current.open_price, current.high_price, current.low_price, current.close_price]):
                return None
            
            # 1. Price volatility features (5 features)
            recent_prices = [float(dp.close_price) for dp in data_points[index-10:index+1] 
                           if dp.close_price is not None]
            
            if len(recent_prices) < 8:
                return None
            
            price_changes = [abs((recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] * 100) 
                           for i in range(1, len(recent_prices))]
            
            features.extend([
                np.mean(price_changes),  # Average volatility
                np.std(price_changes),   # Volatility consistency
                np.max(price_changes),   # Maximum single change
                len([x for x in price_changes if x > 5.0]) / len(price_changes),  # High volatility ratio
                recent_prices[-1] / recent_prices[0] - 1  # Total period change
            ])
            
            # 2. Volume anomaly features (5 features)
            recent_volumes = [float(dp.volume) for dp in data_points[index-10:index+1] 
                            if dp.volume is not None and dp.volume > 0]
            
            if len(recent_volumes) >= 8:
                volume_mean = np.mean(recent_volumes)
                volume_std = np.std(recent_volumes)
                current_volume = recent_volumes[-1]
                
                features.extend([
                    current_volume / volume_mean if volume_mean > 0 else 1.0,  # Volume ratio
                    (current_volume - volume_mean) / volume_std if volume_std > 0 else 0.0,  # Volume Z-score
                    np.std(recent_volumes) / np.mean(recent_volumes) if volume_mean > 0 else 0.0,  # Volume CV
                    len([x for x in recent_volumes if x > volume_mean * 2]) / len(recent_volumes),  # Spike frequency
                    max(recent_volumes) / min(recent_volumes) if min(recent_volumes) > 0 else 1.0  # Volume range ratio
                ])
            else:
                features.extend([1.0, 0.0, 0.0, 0.0, 1.0])
            
            # 3. Price pattern features (5 features)
            current_price = float(current.close_price)
            high_price = float(current.high_price)
            low_price = float(current.low_price)
            open_price = float(current.open_price)
            
            features.extend([
                (high_price - low_price) / current_price,  # Intraday range
                (current_price - open_price) / open_price,  # Intraday change
                (high_price - current_price) / (high_price - low_price) if high_price > low_price else 0.0,  # Upper shadow
                (current_price - low_price) / (high_price - low_price) if high_price > low_price else 0.0,  # Lower shadow
                abs(current_price - open_price) / (high_price - low_price) if high_price > low_price else 0.0  # Body ratio
            ])
            
            # 4. Trend features (5 features)
            if len(recent_prices) >= 10:
                short_ma = np.mean(recent_prices[-5:])
                long_ma = np.mean(recent_prices[-10:])
                
                # Trend strength and consistency
                trend_direction = 1 if short_ma > long_ma else -1
                trend_strength = abs(short_ma - long_ma) / long_ma if long_ma > 0 else 0.0
                
                # Price position relative to trend
                price_vs_short_ma = (current_price - short_ma) / short_ma if short_ma > 0 else 0.0
                price_vs_long_ma = (current_price - long_ma) / long_ma if long_ma > 0 else 0.0
                
                # Trend consistency (how many points follow the trend)
                trend_consistency = sum([1 for i in range(len(recent_prices)-1) 
                                       if (recent_prices[i+1] > recent_prices[i]) == (trend_direction > 0)]) / (len(recent_prices) - 1)
                
                features.extend([
                    trend_direction,
                    trend_strength,
                    price_vs_short_ma,
                    price_vs_long_ma,
                    trend_consistency
                ])
            else:
                features.extend([0.0, 0.0, 0.0, 0.0, 0.5])
            
            # 5. Market context features (5 features)
            session = current.trading_session
            
            # Time-based features
            hour_of_day = session.date.hour if hasattr(session.date, 'hour') else 12
            day_of_week = session.date.weekday()  # 0 = Monday, 6 = Sunday
            
            # Market session timing (normalized)
            features.extend([
                hour_of_day / 24.0,  # Hour normalized
                day_of_week / 6.0,   # Weekday normalized  
                1.0 if day_of_week < 5 else 0.0,  # Is weekday
                1.0 if 9 <= hour_of_day <= 17 else 0.0,  # Market hours
                len([dp for dp in data_points[index-5:index+1] if dp.volume and dp.volume > 0]) / 6.0  # Data completeness
            ])
            
            # Ensure exactly 25 features
            if len(features) != 25:
                logger.warning(f"Feature count mismatch: expected 25, got {len(features)}")
                return None
            
            # Replace any NaN or inf values
            features = [0.0 if not np.isfinite(f) else f for f in features]
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting anomaly features: {e}")
            return None
    
    def _is_anomalous_pattern(self, data_points: List, index: int) -> bool:
        """
        Determine if a pattern represents anomalous market behavior.
        Uses statistical and domain knowledge to identify anomalies.
        """
        try:
            if index < 10 or index >= len(data_points) - 1:
                return False
            
            current = data_points[index]
            if not current.close_price:
                return False
            
            # Calculate recent statistics for comparison
            recent_data = data_points[index-10:index]
            recent_prices = [float(dp.close_price) for dp in recent_data if dp.close_price]
            recent_volumes = [float(dp.volume) for dp in recent_data if dp.volume and dp.volume > 0]
            
            if len(recent_prices) < 5:
                return False
            
            current_price = float(current.close_price)
            current_volume = float(current.volume) if current.volume else 0
            
            # 1. Price spike detection
            price_mean = np.mean(recent_prices)
            price_std = np.std(recent_prices)
            
            if price_std > 0:
                price_z_score = abs(current_price - price_mean) / price_std
                if price_z_score > 3.0:  # More than 3 standard deviations
                    return True
            
            # 2. Volume spike detection
            if len(recent_volumes) >= 5 and current_volume > 0:
                volume_mean = np.mean(recent_volumes)
                volume_std = np.std(recent_volumes)
                
                if volume_std > 0:
                    volume_z_score = (current_volume - volume_mean) / volume_std
                    if volume_z_score > 3.0:  # Unusual volume spike
                        return True
            
            # 3. Extreme price change
            if len(recent_prices) >= 2:
                price_change = abs((current_price - recent_prices[-1]) / recent_prices[-1])
                if price_change > 0.10:  # More than 10% change
                    return True
            
            # 4. Pattern break detection
            if len(recent_prices) >= 10:
                # Check if current price breaks established trend
                trend_prices = recent_prices[-5:]
                is_uptrend = all(trend_prices[i] >= trend_prices[i-1] for i in range(1, len(trend_prices)))
                is_downtrend = all(trend_prices[i] <= trend_prices[i-1] for i in range(1, len(trend_prices)))
                
                if is_uptrend and current_price < recent_prices[-1] * 0.95:  # 5% drop during uptrend
                    return True
                if is_downtrend and current_price > recent_prices[-1] * 1.05:  # 5% rise during downtrend
                    return True
            
            # 5. Intraday anomaly (extreme gaps)
            if current.open_price and current.close_price:
                open_price = float(current.open_price)
                intraday_change = abs((current_price - open_price) / open_price)
                if intraday_change > 0.08:  # More than 8% intraday change
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking anomalous pattern: {e}")
            return False

    def _classify_anomaly_type(self, features: List[float], current_data) -> str:
        """
        Classify the type of anomaly based on features and data patterns.
        """
        try:
            if len(features) < 25:
                return 'unknown'
            
            # Feature indices (based on _extract_anomaly_features)
            volatility_features = features[0:5]  # Price volatility features
            volume_features = features[5:10]     # Volume anomaly features  
            pattern_features = features[10:15]   # Price pattern features
            trend_features = features[15:20]     # Trend features
            context_features = features[20:25]   # Market context features
            
            # Analyze feature patterns to classify anomaly type
            
            # 1. Price spike detection
            if volatility_features[2] > 10.0:  # Max change > 10%
                return 'price_spike'
            
            # 2. Volume spike detection  
            if volume_features[1] > 3.0:  # Volume Z-score > 3
                return 'volume_spike'
            
            # 3. Pattern break detection
            if abs(trend_features[2]) > 0.1 or abs(trend_features[3]) > 0.1:  # Price vs MA deviation
                return 'pattern_break'
            
            # 4. Volatility anomaly
            if volatility_features[1] > 2.0:  # High volatility std
                return 'volatility_anomaly'
            
            # 5. Trading halt pattern
            if volume_features[0] < 0.1:  # Very low volume ratio
                return 'trading_halt'
            
            # 6. Market timing anomaly
            if context_features[3] == 0.0 and current_data.volume and current_data.volume > 0:  # Activity outside market hours
                return 'timing_anomaly'
            
            # 7. Trend reversal
            if trend_features[0] != 0 and trend_features[4] < 0.5:  # Trend exists but low consistency
                return 'trend_reversal'
            
            # 8. Default to general anomaly
            return 'market_anomaly'
            
        except Exception as e:
            logger.error(f"Error classifying anomaly type: {e}")
            return 'unknown'


class LLMAnalysisEngine:
    """
    Optional LLM integration for additional market analysis.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.model = model
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("OpenAI package not installed, LLM features disabled")
                self.enabled = False
    
    def analyze_anomaly(self, anomaly: AnomalyAlert, stock_data: Dict[str, Any]) -> Optional[str]:
        """
        Use LLM to provide additional context for anomaly detection.
        """
        if not self.enabled:
            return None
        
        try:
            prompt = f"""
            Analyze this stock anomaly for {anomaly.stock.symbol}:
            
            Anomaly Type: {anomaly.anomaly_type}
            Severity: {anomaly.severity}/5
            Confidence: {anomaly.confidence_score}
            Description: {anomaly.description}
            
            Stock Data:
            - Current Price: {stock_data.get('current_price', 'N/A')}
            - Volume: {stock_data.get('volume', 'N/A')}
            - Market: {anomaly.stock.market.name if anomaly.stock.market else 'N/A'}
            - Industry: {anomaly.stock.primary_industry.name if anomaly.stock.primary_industry else 'N/A'}
            
            Provide a brief analysis (max 200 words) of what this anomaly might indicate for investors.
            Focus on practical implications and potential causes.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert financial analyst specializing in Polish stock market (GPW)."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return None
