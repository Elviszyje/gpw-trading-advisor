"""
Machine Learning Engine for GPW Trading Advisor.
Neural networks and ML models that learn from historical data and improve over time.
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, mean_squared_error, classification_report
import joblib
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal
from datetime import date, timedelta, datetime
from django.utils import timezone
from django.db.models import Avg, Max, Min, StdDev, Count, Q
from django.conf import settings
import os

from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData
from apps.analysis.models import AnomalyAlert, PricePrediction, RiskAssessment, PatternDetection


class MLConfig:
    """
    Configurable parameters for ML models - can be learned and adjusted over time.
    """
    
    def __init__(self):
        # Neural Network Architecture
        self.lstm_hidden_size = 128
        self.lstm_num_layers = 2
        self.dropout_rate = 0.2
        self.learning_rate = 0.001
        self.batch_size = 32
        self.sequence_length = 30  # Days to look back
        
        # Feature Engineering
        self.technical_indicators_window = [5, 10, 20, 50]  # Moving averages
        self.volatility_window = 20
        self.volume_ma_window = 10
        
        # Anomaly Detection Thresholds (learnable)
        self.price_spike_threshold = 2.5  # Z-score threshold
        self.volume_spike_threshold = 2.0  # Volume ratio threshold
        self.confidence_threshold = 0.75
        
        # Pattern Recognition
        self.pattern_lookback_days = 60
        self.support_resistance_strength = 3  # Min touches for S/R level
        
        # Model Performance Tracking
        self.model_retrain_threshold = 0.1  # Accuracy drop before retrain
        self.feedback_weight = 0.8  # Weight for user feedback vs model confidence
        
    def update_from_performance(self, performance_metrics: Dict[str, float]):
        """
        Automatically adjust parameters based on model performance.
        """
        accuracy = performance_metrics.get('accuracy', 0.5)
        
        # Adjust thresholds based on false positive/negative rates
        if performance_metrics.get('false_positive_rate', 0) > 0.3:
            self.confidence_threshold += 0.05
            self.price_spike_threshold += 0.1
        elif performance_metrics.get('false_negative_rate', 0) > 0.3:
            self.confidence_threshold -= 0.05
            self.price_spike_threshold -= 0.1
            
        # Keep within reasonable bounds
        self.confidence_threshold = max(0.5, min(0.95, self.confidence_threshold))
        self.price_spike_threshold = max(1.5, min(4.0, self.price_spike_threshold))
    
    def save_config(self, filepath: str):
        """Save configuration to file."""
        config_dict = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        with open(filepath, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    def load_config(self, filepath: str):
        """Load configuration from file."""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                config_dict = json.load(f)
                for key, value in config_dict.items():
                    setattr(self, key, value)


class StockPriceLSTM(nn.Module):
    """
    LSTM Neural Network for stock price prediction and anomaly detection.
    """
    
    def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 2, 
                 dropout: float = 0.2, output_size: int = 1):
        super(StockPriceLSTM, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            batch_first=True
        )
        
        # Fully connected layers
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(hidden_size // 2, output_size)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        # Initialize hidden state
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # LSTM forward pass
        lstm_out, _ = self.lstm(x, (h0, c0))
        
        # Take the last output
        last_output = lstm_out[:, -1, :]
        
        # Fully connected layers
        out = self.relu(self.fc1(last_output))
        out = self.dropout(out)
        out = self.fc2(out)
        
        return out


class RecommendationFeedbackTracker:
    """
    Tracks recommendation performance and learns from outcomes.
    """
    
    def __init__(self):
        self.feedback_data = []
        self.model_performance_history = []
        
    def record_recommendation(self, stock_symbol: str, recommendation_type: str, 
                            confidence: float, predicted_direction: str, 
                            recommendation_data: Dict[str, Any]) -> str:
        """
        Record a recommendation for future performance tracking.
        Returns recommendation_id for tracking.
        """
        recommendation_id = f"{stock_symbol}_{int(datetime.now().timestamp())}"
        
        recommendation_record = {
            'id': recommendation_id,
            'timestamp': datetime.now(),
            'stock_symbol': stock_symbol,
            'recommendation_type': recommendation_type,
            'confidence': confidence,
            'predicted_direction': predicted_direction,
            'recommendation_data': recommendation_data,
            'outcome': None,  # To be filled later
            'actual_performance': None
        }
        
        self.feedback_data.append(recommendation_record)
        return recommendation_id
    
    def record_outcome(self, recommendation_id: str, actual_direction: str, 
                      actual_performance: float, user_satisfaction: Optional[int] = None):
        """
        Record the actual outcome of a recommendation.
        """
        for record in self.feedback_data:
            if record['id'] == recommendation_id:
                record['outcome'] = {
                    'actual_direction': actual_direction,
                    'actual_performance': actual_performance,
                    'user_satisfaction': user_satisfaction,  # 1-5 scale
                    'outcome_timestamp': datetime.now()
                }
                break
    
    def calculate_model_performance(self, days_back: int = 30) -> Dict[str, float]:
        """
        Calculate model performance metrics from recent recommendations.
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_records = [r for r in self.feedback_data 
                         if r['timestamp'] > cutoff_date and r['outcome'] is not None]
        
        if not recent_records:
            return {'accuracy': 0.5, 'precision': 0.5, 'recall': 0.5}
        
        correct_predictions = 0
        total_predictions = len(recent_records)
        
        for record in recent_records:
            predicted = record['predicted_direction']
            actual = record['outcome']['actual_direction']
            
            if predicted == actual:
                correct_predictions += 1
        
        accuracy = correct_predictions / total_predictions
        
        # Calculate false positive/negative rates
        false_positives = sum(1 for r in recent_records 
                            if r['predicted_direction'] == 'up' and r['outcome']['actual_direction'] == 'down')
        false_negatives = sum(1 for r in recent_records 
                            if r['predicted_direction'] == 'down' and r['outcome']['actual_direction'] == 'up')
        
        total_positives = sum(1 for r in recent_records if r['predicted_direction'] == 'up')
        total_negatives = sum(1 for r in recent_records if r['predicted_direction'] == 'down')
        
        return {
            'accuracy': accuracy,
            'false_positive_rate': false_positives / max(1, total_positives),
            'false_negative_rate': false_negatives / max(1, total_negatives),
            'total_recommendations': total_predictions
        }


class SmartMLEngine:
    """
    Main ML engine that combines all models and learns from feedback.
    """
    
    def __init__(self):
        self.config = MLConfig()
        self.feedback_tracker = RecommendationFeedbackTracker()
        self.models = {}
        self.scalers = {}
        self.model_dir = os.path.join(settings.BASE_DIR, 'ml_models')
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Load existing models and config
        self._load_models()
        self._load_config()
        
    def _load_config(self):
        """Load ML configuration from file."""
        config_path = os.path.join(self.model_dir, 'ml_config.json')
        self.config.load_config(config_path)
    
    def _save_config(self):
        """Save ML configuration to file."""
        config_path = os.path.join(self.model_dir, 'ml_config.json')
        self.config.save_config(config_path)
    
    def _load_models(self):
        """Load pre-trained models from disk."""
        model_files = {
            'price_predictor': 'price_predictor.pkl',
            'anomaly_classifier': 'anomaly_classifier.pkl',
            'pattern_recognizer': 'pattern_recognizer.pkl',
            'risk_assessor': 'risk_assessor.pkl'
        }
        
        for model_name, filename in model_files.items():
            filepath = os.path.join(self.model_dir, filename)
            if os.path.exists(filepath):
                try:
                    self.models[model_name] = joblib.load(filepath)
                except Exception as e:
                    print(f"Error loading {model_name}: {e}")
        
        # Load scalers
        scaler_files = {
            'price_scaler': 'price_scaler.pkl',
            'feature_scaler': 'feature_scaler.pkl'
        }
        
        for scaler_name, filename in scaler_files.items():
            filepath = os.path.join(self.model_dir, filename)
            if os.path.exists(filepath):
                try:
                    self.scalers[scaler_name] = joblib.load(filepath)
                except Exception as e:
                    print(f"Error loading {scaler_name}: {e}")
    
    def _save_models(self):
        """Save trained models to disk."""
        for model_name, model in self.models.items():
            filepath = os.path.join(self.model_dir, f"{model_name}.pkl")
            joblib.dump(model, filepath)
        
        for scaler_name, scaler in self.scalers.items():
            filepath = os.path.join(self.model_dir, f"{scaler_name}.pkl")
            joblib.dump(scaler, filepath)
    
    def create_features(self, stock_data: List[StockData]) -> np.ndarray:
        """
        Create feature matrix from stock data.
        Features include: price, volume, technical indicators, etc.
        """
        if len(stock_data) < max(self.config.technical_indicators_window):
            return np.array([])
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame([{
            'close': float(d.close_price or 0),
            'open': float(d.open_price or 0),
            'high': float(d.high_price or 0),
            'low': float(d.low_price or 0),
            'volume': float(d.volume or 0),
            'date': d.trading_session.date
        } for d in stock_data])
        
        df = df.sort_values('date')
        
        features = []
        
        # Price-based features
        features.extend([
            df['close'].iloc[-1],  # Current close price
            df['open'].iloc[-1],   # Current open price
            df['high'].iloc[-1],   # Current high price
            df['low'].iloc[-1],    # Current low price
        ])
        
        # Price change features
        if len(df) > 1:
            features.extend([
                (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2],  # 1-day return
                (df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1],    # Intraday return
            ])
        else:
            features.extend([0, 0])
        
        # Volume features
        features.extend([
            df['volume'].iloc[-1],  # Current volume
            df['volume'].rolling(self.config.volume_ma_window).mean().iloc[-1] if len(df) >= self.config.volume_ma_window else df['volume'].iloc[-1],  # Volume MA
        ])
        
        # Technical indicators
        for window in self.config.technical_indicators_window:
            if len(df) >= window:
                ma = df['close'].rolling(window).mean().iloc[-1]
                features.append(ma)
                features.append((df['close'].iloc[-1] - ma) / ma)  # Distance from MA
            else:
                features.extend([df['close'].iloc[-1], 0])
        
        # Volatility features
        if len(df) >= self.config.volatility_window:
            returns = df['close'].pct_change().dropna()
            volatility = returns.rolling(self.config.volatility_window).std().iloc[-1]
            features.append(volatility if not np.isnan(volatility) else 0)
        else:
            features.append(0)
        
        # Support/Resistance levels
        if len(df) >= 20:
            recent_highs = df['high'].rolling(20).max().iloc[-1]
            recent_lows = df['low'].rolling(20).min().iloc[-1]
            features.extend([recent_highs, recent_lows])
            features.extend([
                (df['close'].iloc[-1] - recent_lows) / (recent_highs - recent_lows) if recent_highs != recent_lows else 0.5
            ])
        else:
            features.extend([df['high'].iloc[-1], df['low'].iloc[-1], 0.5])
        
        return np.array(features).reshape(1, -1)
    
    def train_price_predictor(self, stock: StockSymbol, retrain: bool = False):
        """
        Train LSTM model for price prediction.
        """
        # Get training data
        training_data = self._get_training_data(stock, days=365)
        if len(training_data) < 100:  # Need sufficient data
            return False
        
        # Create features and targets
        X, y = self._prepare_sequences(training_data)
        if len(X) == 0:
            return False
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Scale features
        if 'feature_scaler' not in self.scalers:
            self.scalers['feature_scaler'] = StandardScaler()
        
        X_train_scaled = self.scalers['feature_scaler'].fit_transform(X_train.reshape(-1, X_train.shape[-1])).reshape(X_train.shape)
        X_test_scaled = self.scalers['feature_scaler'].transform(X_test.reshape(-1, X_test.shape[-1])).reshape(X_test.shape)
        
        # Scale targets
        if 'price_scaler' not in self.scalers:
            self.scalers['price_scaler'] = MinMaxScaler()
        
        y_train_scaled = self.scalers['price_scaler'].fit_transform(y_train.reshape(-1, 1)).flatten()
        y_test_scaled = self.scalers['price_scaler'].transform(y_test.reshape(-1, 1)).flatten()
        
        # Create and train LSTM model
        input_size = X_train.shape[2]
        lstm_model = StockPriceLSTM(
            input_size=input_size,
            hidden_size=self.config.lstm_hidden_size,
            num_layers=self.config.lstm_num_layers,
            dropout=self.config.dropout_rate
        )
        
        # Convert to PyTorch tensors
        X_train_tensor = torch.FloatTensor(X_train_scaled)
        y_train_tensor = torch.FloatTensor(y_train_scaled)
        X_test_tensor = torch.FloatTensor(X_test_scaled)
        y_test_tensor = torch.FloatTensor(y_test_scaled)
        
        # Training setup
        criterion = nn.MSELoss()
        optimizer = optim.Adam(lstm_model.parameters(), lr=self.config.learning_rate)
        
        # Training loop
        lstm_model.train()
        epochs = 100
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = lstm_model(X_train_tensor)
            loss = criterion(outputs.squeeze(), y_train_tensor)
            loss.backward()
            optimizer.step()
            
            if epoch % 20 == 0:
                print(f"Epoch {epoch}, Loss: {loss.item():.4f}")
        
        # Evaluate model
        lstm_model.eval()
        with torch.no_grad():
            test_outputs = lstm_model(X_test_tensor)
            test_loss = criterion(test_outputs.squeeze(), y_test_tensor)
            print(f"Test Loss: {test_loss.item():.4f}")
        
        # Save model
        model_path = os.path.join(self.model_dir, f'lstm_{stock.symbol}.pth')
        torch.save(lstm_model.state_dict(), model_path)
        
        self.models[f'lstm_{stock.symbol}'] = lstm_model
        return True
    
    def train_anomaly_detector(self, retrain: bool = False):
        """
        Train anomaly detection classifier using ensemble methods.
        """
        if 'anomaly_classifier' in self.models and not retrain:
            return True
        
        # Get training data from historical anomalies
        training_examples = self._get_anomaly_training_data()
        if len(training_examples) < 50:
            print("Insufficient anomaly data for training")
            return False
        
        X, y = zip(*training_examples)
        X = np.array(X)
        y = np.array(y)
        
        # Train gradient boosting classifier
        classifier = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=6,
            random_state=42
        )
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        classifier.fit(X_train, y_train)
        
        # Evaluate
        y_pred = classifier.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Anomaly classifier accuracy: {accuracy:.3f}")
        print(classification_report(y_test, y_pred))
        
        self.models['anomaly_classifier'] = classifier
        return True
    
    def predict_price_movement(self, stock: StockSymbol, session: TradingSession) -> Dict[str, Any]:
        """
        Predict price movement using trained ML models.
        """
        # Get recent data
        recent_data = self._get_recent_data(stock, session, days=self.config.sequence_length + 10)
        if len(recent_data) < self.config.sequence_length:
            return {'prediction': 'insufficient_data', 'confidence': 0.0}
        
        # Create features
        features = self.create_features(recent_data)
        if features.size == 0:
            return {'prediction': 'feature_error', 'confidence': 0.0}
        
        predictions = {}
        
        # LSTM prediction if available
        lstm_model_key = f'lstm_{stock.symbol}'
        if lstm_model_key in self.models and 'feature_scaler' in self.scalers:
            try:
                # Prepare sequence for LSTM
                sequences, _ = self._prepare_sequences(recent_data)
                if len(sequences) > 0:
                    scaled_sequence = self.scalers['feature_scaler'].transform(
                        sequences[-1].reshape(-1, sequences.shape[-1])
                    ).reshape(1, *sequences[-1].shape)
                    
                    lstm_model = self.models[lstm_model_key]
                    lstm_model.eval()
                    
                    with torch.no_grad():
                        sequence_tensor = torch.FloatTensor(scaled_sequence)
                        prediction = lstm_model(sequence_tensor)
                        
                        # Convert back to original scale
                        if 'price_scaler' in self.scalers:
                            predicted_price = self.scalers['price_scaler'].inverse_transform(
                                prediction.numpy().reshape(-1, 1)
                            )[0, 0]
                            
                            current_price = float(recent_data[0].close_price or 0)
                            price_change = (predicted_price - current_price) / current_price
                            
                            predictions['lstm'] = {
                                'predicted_price': predicted_price,
                                'price_change_percent': price_change * 100,
                                'direction': 'up' if price_change > 0 else 'down',
                                'confidence': min(0.95, abs(price_change) * 10)  # Higher confidence for larger changes
                            }
            except Exception as e:
                print(f"LSTM prediction error: {e}")
        
        # Ensemble prediction combining multiple approaches
        if predictions:
            # For now, return LSTM prediction if available
            return predictions.get('lstm', {'prediction': 'no_model', 'confidence': 0.0})
        
        return {'prediction': 'no_prediction', 'confidence': 0.0}
    
    def detect_anomalies_ml(self, stock: StockSymbol, session: TradingSession) -> List[Dict[str, Any]]:
        """
        Detect anomalies using trained ML models.
        """
        if 'anomaly_classifier' not in self.models:
            return []
        
        recent_data = self._get_recent_data(stock, session, days=30)
        if len(recent_data) < 10:
            return []
        
        features = self.create_features(recent_data)
        if features.size == 0:
            return []
        
        # Predict using trained classifier
        classifier = self.models['anomaly_classifier']
        try:
            is_anomaly = classifier.predict(features)[0]
            confidence = np.max(classifier.predict_proba(features)[0])
            
            if is_anomaly and confidence > self.config.confidence_threshold:
                return [{
                    'type': 'ml_anomaly',
                    'severity': min(5, max(1, int(confidence * 5))),
                    'confidence': confidence,
                    'description': f"ML model detected anomaly with {confidence:.1%} confidence",
                    'details': {
                        'model_type': 'gradient_boosting',
                        'feature_vector': features.tolist()[0],
                        'prediction_confidence': confidence
                    }
                }]
        except Exception as e:
            print(f"ML anomaly detection error: {e}")
        
        return []
    
    def learn_from_feedback(self):
        """
        Update models based on recent feedback and performance.
        """
        # Calculate recent performance
        performance = self.feedback_tracker.calculate_model_performance(days_back=30)
        
        # Update configuration based on performance
        self.config.update_from_performance(performance)
        
        # Check if models need retraining
        if performance['accuracy'] < (0.8 - self.config.model_retrain_threshold):
            print("Performance below threshold, scheduling model retraining...")
            # Could trigger background retraining here
        
        # Save updated configuration
        self._save_config()
        
        return performance
    
    def _get_training_data(self, stock: StockSymbol, days: int = 365) -> List[StockData]:
        """Get training data for ML models."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        sessions = TradingSession.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        data = []
        for session in sessions:
            session_data = StockData.objects.filter(
                stock=stock,
                trading_session=session
            ).order_by('-data_timestamp').first()
            
            if session_data and session_data.close_price:
                data.append(session_data)
        
        return data
    
    def _get_recent_data(self, stock: StockSymbol, current_session: TradingSession, days: int = 30) -> List[StockData]:
        """Get recent stock data for analysis."""
        end_date = current_session.date
        start_date = end_date - timedelta(days=days)
        
        sessions = TradingSession.objects.filter(
            date__gte=start_date,
            date__lt=end_date
        ).order_by('-date')
        
        data = []
        for session in sessions:
            latest_data = StockData.objects.filter(
                stock=stock,
                trading_session=session
            ).order_by('-data_timestamp').first()
            
            if latest_data:
                data.append(latest_data)
        
        return data
    
    def _prepare_sequences(self, stock_data: List[StockData]) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare sequences for LSTM training."""
        if len(stock_data) < self.config.sequence_length + 1:
            return np.array([]), np.array([])
        
        # Create feature sequences
        sequences = []
        targets = []
        
        for i in range(len(stock_data) - self.config.sequence_length):
            # Get sequence data
            sequence_data = stock_data[i + 1:i + self.config.sequence_length + 1]  # Next sequence_length days
            target_data = stock_data[i]  # Current day (target to predict)
            
            # Create features for each day in sequence
            sequence_features = []
            for data_point in sequence_data:
                features = self.create_features([data_point])
                if features.size > 0:
                    sequence_features.append(features[0])
            
            if len(sequence_features) == self.config.sequence_length:
                sequences.append(sequence_features)
                targets.append(float(target_data.close_price or 0))
        
        return np.array(sequences), np.array(targets)
    
    def _get_anomaly_training_data(self) -> List[Tuple[np.ndarray, int]]:
        """Get training data for anomaly detection."""
        # This would collect historical anomaly data and normal data
        # For now, return empty list - would need to implement data collection
        return []


class LLMAnalysisIntegration:
    """
    Optional LLM integration for advanced market analysis and recommendation verification.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.enabled = api_key is not None
    
    def analyze_market_sentiment(self, stock_symbol: str, recent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to analyze market sentiment and provide insights.
        """
        if not self.enabled:
            return {'analysis': 'LLM not configured', 'confidence': 0.0}
        
        # This would integrate with OpenAI, Claude, or other LLM APIs
        # For now, return placeholder
        return {
            'sentiment': 'neutral',
            'key_factors': [],
            'market_context': '',
            'confidence': 0.5
        }
    
    def verify_recommendation(self, recommendation: Dict[str, Any], market_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to verify and enhance ML-generated recommendations.
        """
        if not self.enabled:
            return recommendation
        
        # LLM verification logic would go here
        return recommendation
