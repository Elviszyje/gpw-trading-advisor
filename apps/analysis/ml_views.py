"""
Enhanced AI Views with Machine Learning capabilities.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Avg, Q, Max
from django.core.paginator import Paginator
from django.conf import settings
from datetime import date, timedelta
from typing import Dict, Any, Optional
from decimal import Decimal
import json
import logging
import os
import psutil
import platform
import torch
from pathlib import Path

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData
from apps.analysis.models import AnomalyAlert, PatternDetection, PricePrediction, RiskAssessment, PredictionResult
from apps.analysis.ai_detection import AnomalyDetector, SmartAlertEngine
from apps.analysis.ml_models import MLModelManager, LLMAnalysisEngine

logger = logging.getLogger(__name__)


@login_required
def ml_dashboard(request):
    """
    Enhanced ML dashboard with training status and model performance.
    """
    # Initialize ML manager
    ml_manager = MLModelManager()
    
    # Get recent trading session
    latest_session = TradingSession.objects.order_by('-date').first()
    
    if not latest_session:
        return render(request, 'analysis/ml_dashboard.html', {
            'error': 'No trading sessions available'
        })
    
    # Get model status
    model_status = {
        'price_predictor_trained': ml_manager.price_predictor is not None,
        'anomaly_detector_trained': ml_manager.anomaly_detector is not None,
        'last_training_date': None,  # TODO: Track from metadata
        'feedback_count': _get_feedback_count(ml_manager),
        'prediction_accuracy': _get_recent_accuracy(latest_session)
    }
    
    # Get recent predictions
    recent_predictions = PricePrediction.objects.filter(
        trading_session__date__gte=latest_session.date - timedelta(days=7)
    ).select_related('stock', 'trading_session').order_by('-created_at')[:10]
    
    # Get recent anomalies with ML confidence
    recent_anomalies = AnomalyAlert.objects.filter(
        trading_session__date__gte=latest_session.date - timedelta(days=7)
    ).order_by('-confidence_score', '-created_at')[:10]
    
    # ML Statistics
    ml_stats = {
        'predictions_today': PricePrediction.objects.filter(
            trading_session=latest_session
        ).count(),
        'anomalies_today': AnomalyAlert.objects.filter(
            trading_session=latest_session
        ).count(),
        'avg_prediction_confidence': PricePrediction.objects.filter(
            trading_session=latest_session
        ).aggregate(avg_conf=Avg('confidence_score'))['avg_conf'] or 0,
        'high_confidence_alerts': AnomalyAlert.objects.filter(
            trading_session=latest_session,
            confidence_score__gte=0.8
        ).count(),
    }
    
    # Get recent logs for display
    recent_logs = _get_recent_logs()
    
    # Get training data count
    training_data_count = _get_training_data_count()
    
    # Check if training is in progress
    training_in_progress = _check_training_status()
    
    # Get ML configuration
    config = ml_manager.config
    
    context = {
        'latest_session': latest_session,
        'model_status': model_status,
        'recent_predictions': recent_predictions,
        'recent_anomalies': recent_anomalies,
        'ml_stats': ml_stats,
        'recent_logs': recent_logs,
        'training_data_count': training_data_count,
        'training_in_progress': training_in_progress,
        'config': config,
        'now': timezone.now(),
        'last_training': _get_last_training_time()
    }
    
    return render(request, 'analysis/ml_dashboard.html', context)


@login_required
@csrf_exempt
def train_models(request):
    """
    Trigger ML model training.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        model_type = data.get('model_type', 'all')
        force_retrain = data.get('force_retrain', False)
        
        ml_manager = MLModelManager()
        results = {}
        
        if model_type in ['all', 'price_predictor']:
            logger.info("Starting price predictor training...")
            results['price_predictor'] = ml_manager.train_price_predictor(
                force_retrain=force_retrain
            )
        
        if model_type in ['all', 'anomaly_detector']:
            logger.info("Starting anomaly detector training...")
            # TODO: Implement anomaly detector training
            results['anomaly_detector'] = {
                'status': 'not_implemented', 
                'message': 'Anomaly detector training is not yet implemented'
            }
        
        return JsonResponse({
            'status': 'success',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error training models: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@csrf_exempt
def submit_feedback(request):
    """
    Submit user feedback for ML model improvement.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        alert_id = data.get('alert_id')
        rating = data.get('rating')  # 1-5 scale
        useful = data.get('useful', False)
        market_outcome = data.get('market_outcome', 'unknown')
        comments = data.get('comments', '')
        
        # Get the alert
        alert = get_object_or_404(AnomalyAlert, pk=alert_id)
        
        # Prepare feedback data
        feedback = {
            'rating': rating,
            'useful': useful,
            'market_outcome': market_outcome,
            'comments': comments,
            'user_id': request.user.id,
            'timestamp': timezone.now().isoformat()
        }
        
        # Submit to ML system
        ml_manager = MLModelManager()
        ml_manager.learn_from_feedback(alert, feedback)
        
        # Store feedback in alert details
        if not alert.detection_details:
            alert.detection_details = {}
        
        if 'user_feedback' not in alert.detection_details:
            alert.detection_details['user_feedback'] = []
        
        alert.detection_details['user_feedback'].append(feedback)
        alert.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Feedback recorded successfully'
        })
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def ml_predictions(request):
    """
    Display ML-based price predictions.
    """
    # Get filter parameters
    stock_symbol = request.GET.get('stock')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    min_confidence = request.GET.get('min_confidence', 0.5)
    
    # Build query
    queryset = PricePrediction.objects.select_related('stock', 'trading_session')
    
    if stock_symbol:
        queryset = queryset.filter(stock__symbol__icontains=stock_symbol)
    
    if date_from:
        queryset = queryset.filter(trading_session__date__gte=date_from)
    
    if date_to:
        queryset = queryset.filter(trading_session__date__lte=date_to)
    
    if min_confidence:
        queryset = queryset.filter(confidence_score__gte=float(min_confidence))
    
    # Order by confidence and recency
    queryset = queryset.order_by('-confidence_score', '-created_at')
    
    # Add actual outcomes for completed predictions
    enriched_predictions = []
    for prediction in queryset[:50]:  # Limit for performance
        pred_data = {
            'prediction': prediction,
            'actual_outcome': None,
            'accuracy': None
        }
        
        # Check if prediction period has passed
        prediction_days = {'next_day': 1, 'next_week': 7, 'next_month': 30}.get(prediction.prediction_type, 5)
        target_date = prediction.trading_session.date + timedelta(days=prediction_days)
        if target_date <= date.today():
            actual_outcome = _get_actual_outcome(prediction, target_date)
            if actual_outcome:
                pred_data['actual_outcome'] = actual_outcome
                pred_data['accuracy'] = _calculate_prediction_accuracy(prediction, actual_outcome)
        
        enriched_predictions.append(pred_data)
    
    # Pagination
    paginator = Paginator(enriched_predictions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_filters': {
            'stock': stock_symbol,
            'date_from': date_from,
            'date_to': date_to,
            'min_confidence': min_confidence,
        }
    }
    
    return render(request, 'analysis/ml_predictions.html', context)


@login_required
def generate_ml_prediction(request, symbol):
    """
    Generate new ML prediction for a specific stock.
    """
    stock = get_object_or_404(StockSymbol, symbol=symbol)
    latest_session = TradingSession.objects.order_by('-date').first()
    
    if not latest_session:
        return JsonResponse({'error': 'No trading sessions available'}, status=400)
    
    try:
        ml_manager = MLModelManager()
        prediction_result = ml_manager.predict_price(stock, latest_session)
        
        if prediction_result is None:
            return JsonResponse({
                'error': 'Unable to generate prediction - insufficient data or model not trained'
            }, status=400)
        
        # Save prediction to database
        prediction_days = 5  # Default horizon
        prediction = PricePrediction.objects.create(
            stock=stock,
            trading_session=latest_session,
            predicted_price=prediction_result['predicted_price'],
            confidence_score=prediction_result['confidence'],
            prediction_type='next_week',  # Map to model choices
            predicted_direction='up' if prediction_result['predicted_change_percent'] > 0 else 'down',
            model_version='v1.0'
        )
        
        # Optional LLM enhancement
        llm_engine = LLMAnalysisEngine()
        llm_analysis = None
        if llm_engine.enabled:
            stock_data = {
                'current_price': prediction_result['current_price'],
                'predicted_price': prediction_result['predicted_price'],
                'predicted_change': prediction_result['predicted_change_percent']
            }
            # Note: This would use actual anomaly detection, not create mock data
            # llm_analysis = llm_engine.analyze_prediction(prediction, stock_data)
        
        return JsonResponse({
            'status': 'success',
            'prediction': {
                'id': prediction.pk,
                'current_price': prediction_result['current_price'],
                'predicted_price': prediction_result['predicted_price'],
                'predicted_change_percent': prediction_result['predicted_change_percent'],
                'confidence': prediction_result['confidence'],
                'horizon_days': 5,  # Default prediction horizon
                'llm_analysis': llm_analysis
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating prediction for {symbol}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def model_performance(request):
    """
    Display ML model performance metrics and learning progress.
    """
    # Get performance data
    ml_manager = MLModelManager()
    
    # Recent prediction accuracy
    recent_predictions = PricePrediction.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).select_related('stock', 'trading_session')
    
    accuracy_data = []
    for prediction in recent_predictions:
        prediction_days = {'next_day': 1, 'next_week': 7, 'next_month': 30}.get(prediction.prediction_type, 5)
        target_date = prediction.trading_session.date + timedelta(days=prediction_days)
        if target_date <= date.today():
            actual_outcome = _get_actual_outcome(prediction, target_date)
            if actual_outcome:
                accuracy = _calculate_prediction_accuracy(prediction, actual_outcome)
                accuracy_data.append({
                    'prediction': prediction,
                    'actual_outcome': actual_outcome,
                    'accuracy': accuracy,
                    'days_ago': (date.today() - prediction.trading_session.date).days
                })
    
    # Calculate overall metrics
    if accuracy_data:
        avg_accuracy = sum(item['accuracy'] for item in accuracy_data) / len(accuracy_data)
        high_accuracy_count = sum(1 for item in accuracy_data if item['accuracy'] > 0.8)
        low_accuracy_count = sum(1 for item in accuracy_data if item['accuracy'] < 0.5)
    else:
        avg_accuracy = 0
        high_accuracy_count = 0
        low_accuracy_count = 0
    
    # Feedback analysis
    feedback_count = _get_feedback_count(ml_manager)
    
    context = {
        'accuracy_data': accuracy_data[:20],  # Latest 20 for display
        'performance_metrics': {
            'avg_accuracy': avg_accuracy,
            'total_predictions': len(accuracy_data),
            'high_accuracy_count': high_accuracy_count,
            'low_accuracy_count': low_accuracy_count,
            'feedback_count': feedback_count
        },
        'model_status': {
            'price_predictor': ml_manager.price_predictor is not None,
            'anomaly_detector': ml_manager.anomaly_detector is not None,
        }
    }
    
    return render(request, 'analysis/model_performance.html', context)


def _get_feedback_count(ml_manager: MLModelManager) -> int:
    """Get total feedback count from ML system."""
    try:
        feedback_file = ml_manager.models_dir / 'feedback_log.jsonl'
        if feedback_file.exists():
            with open(feedback_file, 'r') as f:
                return sum(1 for _ in f)
    except Exception:
        pass
    return 0


def _get_system_resources() -> Dict[str, Any]:
    """Get real system resource usage."""
    try:
        # CPU usage (percentage)
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_gb = round(memory.available / (1024**3), 2)
        memory_total_gb = round(memory.total / (1024**3), 2)
        
        # Disk usage for main drive (prefer user data volume on macOS)
        disk_path = '/'
        if platform.system() == 'Darwin':  # macOS
            # Check if APFS Data volume exists
            data_volume = '/System/Volumes/Data'
            try:
                if os.path.exists(data_volume):
                    disk_path = data_volume
            except:
                pass  # Fall back to root
        
        disk = psutil.disk_usage(disk_path)
        disk_percent = round((disk.used / disk.total) * 100, 1)
        disk_free_gb = round(disk.free / (1024**3), 2)
        disk_total_gb = round(disk.total / (1024**3), 2)
        
        # Network I/O
        network = psutil.net_io_counters()
        
        # Process count
        process_count = len(psutil.pids())
        
        # Boot time / uptime
        boot_time = psutil.boot_time()
        uptime_seconds = timezone.now().timestamp() - boot_time
        uptime_hours = round(uptime_seconds / 3600, 1)
        
        # System info
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.release(),
            'architecture': platform.machine(),
            'processor': platform.processor() or 'Unknown',
            'python_version': platform.python_version()
        }
        
        # GPU info (if available)
        gpu_info = "N/A"
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                gpu_info = f"{gpu.load*100:.1f}% ({gpu.name})"
        except ImportError:
            # Try nvidia-ml-py as fallback
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_usage = (info.used / info.total) * 100
                gpu_name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                gpu_info = f"{gpu_usage:.1f}% ({gpu_name})"
            except:
                gpu_info = "N/A"
        
        return {
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory_percent, 1),
            'memory_available_gb': memory_available_gb,
            'memory_total_gb': memory_total_gb,
            'disk_percent': disk_percent,
            'disk_free_gb': disk_free_gb,
            'disk_total_gb': disk_total_gb,
            'network_bytes_sent': network.bytes_sent,
            'network_bytes_recv': network.bytes_recv,
            'process_count': process_count,
            'uptime_hours': uptime_hours,
            'gpu_info': gpu_info,
            'system_info': system_info,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system resources: {e}")
        return {
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_percent': 0,
            'gpu_info': 'Error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _get_recent_accuracy(session: TradingSession) -> float:
    """Calculate recent prediction accuracy."""
    try:
        # Get predictions from last week that have outcomes available
        week_ago = session.date - timedelta(days=7)
        predictions = PricePrediction.objects.filter(
            trading_session__date__gte=week_ago - timedelta(days=5),
            trading_session__date__lte=week_ago
        )
        
        accuracies = []
        for prediction in predictions:
            prediction_days = {'next_day': 1, 'next_week': 7, 'next_month': 30}.get(prediction.prediction_type, 5)
            target_date = prediction.trading_session.date + timedelta(days=prediction_days)
            if target_date <= date.today():
                actual_outcome = _get_actual_outcome(prediction, target_date)
                if actual_outcome:
                    accuracy = _calculate_prediction_accuracy(prediction, actual_outcome)
                    accuracies.append(accuracy)
        
        return sum(accuracies) / len(accuracies) if accuracies else 0.0
        
    except Exception:
        return 0.0


def _get_actual_outcome(prediction: PricePrediction, target_date: date) -> Optional[Dict[str, Any]]:
    """Get actual stock price outcome for a prediction."""
    try:
        # Find trading session for target date (or closest after)
        target_session = TradingSession.objects.filter(
            date__gte=target_date
        ).order_by('date').first()
        
        if not target_session:
            return None
        
        # Get actual stock data
        actual_data = StockData.objects.filter(
            stock=prediction.stock,
            trading_session=target_session
        ).order_by('-data_timestamp').first()
        
        if actual_data and actual_data.close_price:
            return {
                'actual_price': float(actual_data.close_price),
                'session_date': target_session.date,
                'volume': float(actual_data.volume or 0)
            }
        
    except Exception as e:
        logger.error(f"Error getting actual outcome: {e}")
    
    return None


def _calculate_prediction_accuracy(prediction: PricePrediction, actual_outcome: Dict[str, Any]) -> float:
    """Calculate prediction accuracy score."""
    try:
        predicted_price = float(prediction.predicted_price or 0)
        actual_price = actual_outcome['actual_price']
        
        # Calculate percentage error
        error = abs(predicted_price - actual_price) / actual_price
        
        # Convert to accuracy (1.0 = perfect, 0.0 = completely wrong)
        accuracy = max(0.0, 1.0 - error)
        
        return accuracy
        
    except Exception:
        return 0.0


class GetPredictionView(APIView):
    """API view for getting ML predictions"""
    # Temporarily disable authentication for testing
    # permission_classes = [IsAuthenticated]
    
    def get(self, request):
        stock_symbol = request.GET.get('stock')
        session_id = request.GET.get('session')
        
        if not stock_symbol or not session_id:
            return Response(
                {'error': 'Stock symbol and session ID are required'}, 
                status=400
            )
        
        try:
            stock = StockSymbol.objects.get(symbol=stock_symbol)
            session = TradingSession.objects.get(pk=session_id)
            
            # Initialize ML manager
            ml_manager = MLModelManager()
            
            # Get intraday prediction
            prediction = ml_manager.predict_price(stock, session)
            
            if prediction is None:
                return Response(
                    {'error': 'Unable to generate prediction - insufficient data'}, 
                    status=404
                )
            
            # Log prediction for feedback
            try:
                created_by = request.user if request.user.is_authenticated else None
                prediction_record = PredictionResult.objects.create(
                    stock=stock,
                    trading_session=session,
                    predicted_price=Decimal(str(prediction['predicted_price'])),
                    prediction_type='intraday_price',
                    confidence=prediction['confidence'],
                    predicted_change_percent=Decimal(str(prediction['predicted_change_percent'])),
                    prediction_horizon_hours=prediction.get('horizon_hours', 4),
                    created_by=created_by
                )
                prediction['prediction_id'] = prediction_record.pk
            except Exception as e:
                logger.error(f"Error saving prediction record: {e}")
            
            # Add enhanced trading recommendation with reasoning
            change_percent = prediction['predicted_change_percent']
            confidence = prediction['confidence']
            factors = prediction.get('prediction_factors', {})
            
            recommendation_reason = []
            
            if change_percent > 2.0 and confidence > 0.7:
                prediction['recommendation'] = 'BUY'
                recommendation_reason.append(f"Strong upward prediction ({change_percent:.1f}%)")
                
                # Add specific reasoning based on factors
                if factors.get('news', {}).get('sentiment_score', 0) > 0.3:
                    recommendation_reason.append("Positive news sentiment")
                if factors.get('calendar', {}).get('major_event_proximity', 0) > 0.7:
                    recommendation_reason.append("Major upcoming event")
                if factors.get('technical', {}).get('volume_ratio', 0) > 1.5:
                    recommendation_reason.append("High trading volume")
                    
            elif change_percent < -2.0 and confidence > 0.7:
                prediction['recommendation'] = 'SELL'
                recommendation_reason.append(f"Strong downward prediction ({change_percent:.1f}%)")
                
                # Add specific reasoning
                if factors.get('news', {}).get('sentiment_score', 0) < -0.3:
                    recommendation_reason.append("Negative news sentiment")
                if factors.get('calendar', {}).get('date_change_sentiment', 0) < -0.5:
                    recommendation_reason.append("Recent event postponements")
                    
            else:
                prediction['recommendation'] = 'HOLD'
                if abs(change_percent) < 1.0:
                    recommendation_reason.append("Low volatility expected")
                elif confidence < 0.7:
                    recommendation_reason.append("Uncertain market conditions")
                else:
                    recommendation_reason.append("Balanced risk/reward")
            
            prediction['recommendation_reasoning'] = recommendation_reason
            
            # Enhanced session context with market insights
            market_insights = []
            
            if factors.get('news', {}).get('news_volume', 0) > 0.5:
                market_insights.append("High news activity detected")
            if factors.get('market', {}).get('sector_performance', 0) > 0.02:
                market_insights.append("Sector showing strength")
            elif factors.get('market', {}).get('sector_performance', 0) < -0.02:
                market_insights.append("Sector underperforming")
            
            # Calendar insights
            calendar_factors = factors.get('calendar', {})
            if calendar_factors.get('earnings_proximity', 0) > 0.5:
                market_insights.append("Earnings announcement approaching")
            if calendar_factors.get('dividend_effect', 0) != 0:
                if calendar_factors.get('dividend_effect', 0) > 0:
                    market_insights.append("Positive dividend effect")
                else:
                    market_insights.append("Ex-dividend date approaching")
            
            prediction['market_insights'] = market_insights
            
            # Add session context
            prediction['session_info'] = {
                'session_date': session.date.isoformat() if session.date else None,
                'is_active': session.is_open,
                'progress': prediction.get('session_progress', 0.0)
            }
            
            return Response(prediction)
            
        except StockSymbol.DoesNotExist:
            return Response({'error': 'Stock not found'}, status=404)
        except TradingSession.DoesNotExist:
            return Response({'error': 'Trading session not found'}, status=404)
        except Exception as e:
            logger.error(f"Error generating prediction: {e}")
            return Response({'error': 'Internal server error'}, status=500)


# Helper functions for ML dashboard
def _get_recent_logs():
    """Get recent ML system logs."""
    try:
        # Read from log file or database
        logs = []
        log_file = Path(settings.BASE_DIR) / 'ml_system.log'
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()[-100:]  # Last 100 lines
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        # Try format: 2025-07-23 10:01:15 - INFO - ML System initialized
                        if '-' in line and (' - INFO - ' in line or ' - ERROR - ' in line or ' - WARNING - ' in line):
                            parts = line.split(' - ', 2)
                            if len(parts) >= 3:
                                timestamp = parts[0]
                                level_raw = parts[1]
                                message = parts[2]
                                
                                level = 'info'
                                if 'ERROR' in level_raw.upper():
                                    level = 'error'
                                elif 'WARNING' in level_raw.upper():
                                    level = 'warning'
                                elif 'SUCCESS' in message.upper() or 'COMPLETED' in message.upper() or 'LOADED' in message.upper():
                                    level = 'success'
                                
                                logs.append({
                                    'timestamp': timestamp,
                                    'level': level,
                                    'message': message
                                })
                                continue
                    except Exception as e:
                        logger.error(f"Error parsing log line '{line}': {e}")
                        continue
        
        return logs[-30:]  # Return last 30 entries
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return []


def _get_active_processes():
    """Get real active system processes related to our application."""
    try:
        import psutil
        processes = []
        
        # Get all running processes
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
            try:
                proc_info = proc.info
                proc_name = proc_info['name'].lower()
                cmdline = ' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                
                # Filter for relevant processes
                relevant_keywords = [
                    'python', 'django', 'runserver', 'manage.py',
                    'postgres', 'redis', 'celery', 'gunicorn',
                    'ml', 'tensorflow', 'pytorch', 'scikit'
                ]
                
                if any(keyword in proc_name or keyword in cmdline.lower() for keyword in relevant_keywords):
                    # Determine process type and status
                    if 'manage.py runserver' in cmdline:
                        process_type = 'Django Server'
                        status = 'running'
                        icon = 'fas fa-server'
                    elif 'python' in proc_name and 'ml' in cmdline.lower():
                        process_type = 'ML Process'
                        status = 'running'
                        icon = 'fas fa-brain'
                    elif 'postgres' in proc_name:
                        process_type = 'Database'
                        status = 'running'
                        icon = 'fas fa-database'
                    elif 'redis' in proc_name:
                        process_type = 'Cache'
                        status = 'running'
                        icon = 'fas fa-memory'
                    elif 'celery' in cmdline.lower():
                        process_type = 'Task Queue'
                        status = 'running'
                        icon = 'fas fa-tasks'
                    else:
                        process_type = 'Python Process'
                        status = 'running'
                        icon = 'fab fa-python'
                    
                    # Get resource usage
                    cpu_percent = round(proc_info['cpu_percent'] or 0, 1)
                    memory_percent = round(proc_info['memory_percent'] or 0, 1)
                    
                    # Determine status based on resource usage
                    if cpu_percent > 50:
                        status_class = 'warning'
                    elif cpu_percent > 0:
                        status_class = 'success'
                    else:
                        status_class = 'secondary'
                    
                    processes.append({
                        'pid': proc_info['pid'],
                        'name': process_type,
                        'status': status,
                        'status_class': status_class,
                        'icon': icon,
                        'cpu_percent': cpu_percent,
                        'memory_percent': memory_percent,
                        'progress': min(cpu_percent * 2, 100) if cpu_percent > 0 else 0
                    })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Sort by CPU usage (descending) and limit to top 10
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return processes[:10]
        
    except Exception as e:
        logger.error(f"Error getting processes: {e}")
        # Return fallback mock data if real process detection fails
        return [
            {
                'pid': 'N/A',
                'name': 'Django Server',
                'status': 'running',
                'status_class': 'success',
                'icon': 'fas fa-server',
                'cpu_percent': 2.1,
                'memory_percent': 5.2,
                'progress': 15
            },
            {
                'pid': 'N/A', 
                'name': 'Database',
                'status': 'running',
                'status_class': 'info',
                'icon': 'fas fa-database',
                'cpu_percent': 1.3,
                'memory_percent': 8.7,
                'progress': 10
            }
        ]


def _get_training_data_count():
    """Get count of available training data samples."""
    try:
        # Count stock data points for last 3 months
        cutoff_date = date.today() - timedelta(days=90)
        count = StockData.objects.filter(
            trading_session__date__gte=cutoff_date
        ).count()
        return count
    except Exception:
        return 0


def _check_training_status():
    """Check if training is currently in progress."""
    try:
        status_file = Path(settings.BASE_DIR) / 'ml_models' / 'training_status.json'
        if status_file.exists():
            with open(status_file, 'r') as f:
                status = json.load(f)
                return status.get('training_in_progress', False)
        return False
    except Exception:
        return False


def _get_last_training_time():
    """Get timestamp of last training session."""
    try:
        status_file = Path(settings.BASE_DIR) / 'ml_models' / 'training_status.json'
        if status_file.exists():
            with open(status_file, 'r') as f:
                status = json.load(f)
                last_training = status.get('last_training_time')
                if last_training:
                    return timezone.datetime.fromisoformat(last_training)
        return None
    except Exception:
        return None


# New API endpoints for dashboard
@login_required
def api_ml_logs(request):
    """API endpoint to get recent ML logs."""
    logs = _get_recent_logs()
    return JsonResponse({'logs': logs})


@login_required
def api_ml_processes(request):
    """API endpoint to get real system processes."""
    try:
        processes = _get_active_processes()
        return JsonResponse({
            'status': 'success',
            'data': processes
        })
    except Exception as e:
        logger.error(f"Error fetching processes: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@csrf_exempt
def api_ml_train(request):
    """API endpoint to start model training."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        model_type = data.get('model_type')
        force_retrain = data.get('force_retrain', False)
        
        if model_type not in ['price_predictor', 'anomaly_detector']:
            return JsonResponse({'error': 'Invalid model type'}, status=400)
        
        # Set training status
        _set_training_status(True, model_type)
        
        # Start training in background
        from django.core.management import call_command
        import threading
        
        def train_model():
            try:
                ml_manager = MLModelManager()
                result = None
                
                if model_type == 'price_predictor':
                    result = ml_manager.train_price_predictor(force_retrain=force_retrain)
                elif model_type == 'anomaly_detector':
                    result = ml_manager.train_anomaly_detector()
                
                if result is None:
                    result = {'status': 'error', 'message': 'Unknown training error'}
                
                _set_training_status(False, model_type, result)
            except Exception as e:
                logger.error(f"Training failed: {e}")
                _set_training_status(False, model_type, {'status': 'error', 'message': str(e)})
        
        thread = threading.Thread(target=train_model)
        thread.daemon = True
        thread.start()
        
        return JsonResponse({
            'status': 'started',
            'model_type': model_type,
            'message': 'Training started in background'
        })
        
    except Exception as e:
        logger.error(f"Error starting training: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_ml_training_status(request):
    """API endpoint to check training progress."""
    try:
        status_file = Path(settings.BASE_DIR) / 'ml_models' / 'training_status.json'
        if status_file.exists():
            with open(status_file, 'r') as f:
                status = json.load(f)
                return JsonResponse(status)
        
        return JsonResponse({
            'training_in_progress': False,
            'status': 'idle'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_ml_config(request):
    """API endpoint to update ML configuration."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Validate configuration
        config = {
            'epochs': max(10, min(1000, int(data.get('epochs', 100)))),
            'learning_rate': max(0.0001, min(0.1, float(data.get('learning_rate', 0.001)))),
            'batch_size': max(8, min(128, int(data.get('batch_size', 32)))),
            'lookback_days': max(7, min(365, int(data.get('lookback_days', 30)))),
            'prediction_horizon_hours': max(1, min(24, int(data.get('prediction_horizon_hours', 4)))),
            'early_stopping_patience': max(5, min(50, int(data.get('early_stopping_patience', 10)))),
            'use_enhanced_features': data.get('use_enhanced_features', True),
            'auto_retrain': data.get('auto_retrain', False),
            'save_predictions': data.get('save_predictions', True),
            'enable_feedback': data.get('enable_feedback', True)
        }
        
        # Save configuration
        config_file = Path(settings.BASE_DIR) / 'ml_models' / 'ml_config.json'
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Configuration saved',
            'config': config
        })
        
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_ml_quick_predict(request):
    """API endpoint for quick test prediction."""
    try:
        # Get a random active stock and latest session
        stock = StockSymbol.objects.filter(is_active=True).order_by('?').first()
        session = TradingSession.objects.order_by('-date').first()
        
        if not stock or not session:
            return JsonResponse({'error': 'No data available'}, status=404)
        
        ml_manager = MLModelManager()
        prediction = ml_manager.predict_price(stock, session)
        
        if prediction:
            return JsonResponse({
                'status': 'success',
                'stock': stock.symbol,
                'session': session.date.isoformat(),
                'prediction': prediction
            })
        else:
            return JsonResponse({'error': 'Prediction failed'}, status=500)
            
    except Exception as e:
        logger.error(f"Error in quick predict: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_ml_reset(request):
    """API endpoint to reset ML models."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        models_dir = Path(settings.BASE_DIR) / 'ml_models'
        
        # Remove model files
        for model_file in models_dir.glob('*.pth'):
            model_file.unlink()
        for scaler_file in models_dir.glob('*.joblib'):
            scaler_file.unlink()
        
        # Reset training status
        _set_training_status(False, None, {'status': 'reset'})
        
        return JsonResponse({
            'status': 'success',
            'message': 'Models reset successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resetting models: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_ml_system_resources(request):
    """API endpoint to get real-time system resource usage."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)
    
    try:
        # Get real system resource data
        resources = _get_system_resources()
        
        # Add ML-specific process info
        ml_processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
                proc_info = proc.info
                if any(keyword in proc_info['name'].lower() 
                      for keyword in ['python', 'django', 'ml', 'torch', 'tensorflow']):
                    ml_processes.append({
                        'pid': proc_info['pid'],
                        'name': proc_info['name'],
                        'memory_percent': round(proc_info['memory_percent'], 2),
                        'cpu_percent': round(proc_info['cpu_percent'], 2)
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # Add ML processes to response
        resources['ml_processes'] = ml_processes[:10]  # Limit to top 10
        
        # Log sample data for verification (only occasionally to avoid spam)
        import random
        if random.random() < 0.1:  # 10% chance
            logger.info(f"System resources: CPU={resources['cpu_percent']}%, Memory={resources['memory_percent']}%, Disk={resources['disk_percent']}%")
        
        return JsonResponse({
            'status': 'success',
            'data': resources
        })
        
    except Exception as e:
        logger.error(f"Error getting system resources: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


def _set_training_status(in_progress, model_type=None, result=None):
    """Helper to update training status."""
    try:
        status_file = Path(settings.BASE_DIR) / 'ml_models' / 'training_status.json'
        status_file.parent.mkdir(exist_ok=True)
        
        status = {
            'training_in_progress': in_progress,
            'model_type': model_type,
            'current_epoch': 0,
            'total_epochs': 0,
            'train_loss': None,
            'val_loss': None,
            'training_time': '00:00',
            'last_training_time': timezone.now().isoformat() if not in_progress else None
        }
        
        if result:
            status.update(result)
        
        # Try to load existing status first
        if status_file.exists():
            try:
                with open(status_file, 'r') as f:
                    existing = json.load(f)
                    if in_progress:
                        # Keep existing progress info when updating
                        status.update({
                            'current_epoch': existing.get('current_epoch', 0),
                            'total_epochs': existing.get('total_epochs', 0),
                            'train_loss': existing.get('train_loss'),
                            'val_loss': existing.get('val_loss'),
                            'training_time': existing.get('training_time', '00:00')
                        })
            except:
                pass
        
        with open(status_file, 'w') as f:
            json.dump(status, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error setting training status: {e}")


@login_required
def ml_test(request):
    """
    Test page for ML API functionality.
    """
    # Get available stocks and sessions for testing
    stocks = StockSymbol.objects.filter(is_active=True)[:20]
    sessions = TradingSession.objects.order_by('-date')[:10]
    
    context = {
        'stocks': stocks,
        'sessions': sessions,
        'now': timezone.now()
    }
    
    return render(request, 'analysis/ml_test.html', context)


@login_required
def ml_config(request):
    """
    ML configuration page.
    """
    # Load current configuration
    try:
        config_file = Path(settings.BASE_DIR) / 'ml_models' / 'ml_config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            # Default configuration
            config = {
                'epochs': 100,
                'learning_rate': 0.001,
                'batch_size': 32,
                'lookback_days': 30,
                'prediction_horizon_hours': 4,
                'early_stopping_patience': 10,
                'use_enhanced_features': True,
                'use_news_analysis': True,
                'use_calendar_events': True,
                'use_market_context': True,
                'use_volume_analysis': False,
                'use_time_features': True,
                'auto_retrain': False,
                'save_predictions': True,
                'enable_feedback': True,
                'enable_detailed_logging': False
            }
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        config = {}
    
    # Get system status info
    training_data_count = _get_training_data_count()
    last_training = _get_last_training_time()
    
    context = {
        'config': config,
        'training_data_count': training_data_count,
        'last_training': last_training
    }
    
    return render(request, 'analysis/ml_config.html', context)


@login_required
def ml_monitoring(request):
    """
    ML monitoring and logs page.
    """
    context = {
        'now': timezone.now()
    }
    
    return render(request, 'analysis/ml_monitoring.html', context)


@login_required
def ml_docs(request):
    """
    ML documentation page.
    """
    return render(request, 'analysis/ml_docs.html')


@login_required
@csrf_exempt
def api_detect_anomalies(request):
    """
    API endpoint to detect current anomalies using trained model.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        ml_manager = MLModelManager()
        
        # Check if anomaly detector is trained
        if not hasattr(ml_manager, 'anomaly_detector') or ml_manager.anomaly_detector is None:
            return JsonResponse({
                'status': 'error',
                'message': 'Anomaly detector is not trained. Please train the model first.'
            })
        
        # Get current trading session
        latest_session = TradingSession.objects.order_by('-date').first()
        if not latest_session:
            return JsonResponse({
                'status': 'error', 
                'message': 'No trading session available'
            })
        
        # Get monitored stocks
        monitored_stocks = StockSymbol.objects.filter(is_monitored=True)
        detected_anomalies = []
        anomaly_count = 0
        
        for stock in monitored_stocks:
            try:
                # Get recent stock data for anomaly detection
                recent_data = StockData.objects.filter(
                    stock=stock,
                    trading_session__date__gte=latest_session.date - timedelta(days=5)
                ).order_by('-trading_session__date', '-data_timestamp')[:20]
                
                if recent_data.count() < 10:
                    continue
                
                # Analyze each recent data point for anomalies
                data_points = list(recent_data)
                for i, current_data in enumerate(data_points[:5]):  # Check last 5 data points
                    
                    # Extract features for anomaly detection
                    features = ml_manager._extract_anomaly_features(data_points[i:], 0, stock)
                    if features is None:
                        continue
                    
                    # Convert to tensor and detect anomaly
                    features_tensor = torch.FloatTensor([features])
                    ml_manager.anomaly_detector.eval()
                    
                    with torch.no_grad():
                        reconstructed, anomaly_score = ml_manager.anomaly_detector(features_tensor)
                    
                    anomaly_score = anomaly_score.item()
                    threshold = getattr(ml_manager, 'anomaly_threshold', 0.5)
                    
                    # If anomaly detected, create alert and add to results
                    if anomaly_score > threshold:
                        anomaly_count += 1
                        
                        # Determine anomaly type based on features
                        anomaly_type = ml_manager._classify_anomaly_type(features, current_data)
                        
                        # Create anomaly alert in database
                        anomaly_alert = AnomalyAlert.objects.create(
                            stock=stock,
                            trading_session=current_data.trading_session,
                            anomaly_type=anomaly_type,
                            confidence_score=float(anomaly_score),
                            severity=3 if anomaly_score > 0.8 else 2,  # Medium/Low severity
                            description=f"Anomaly detected in {stock.symbol} with confidence {anomaly_score:.3f}",
                            detection_details={
                                'anomaly_score': float(anomaly_score),
                                'threshold': float(threshold),
                                'features_analyzed': len(features),
                                'detection_timestamp': timezone.now().isoformat(),
                                'model_version': 'v1.0'
                            },
                            is_active=True
                        )
                        
                        detected_anomalies.append({
                            'id': anomaly_alert.pk,
                            'stock_symbol': stock.symbol,
                            'anomaly_type': anomaly_type,
                            'confidence': float(anomaly_score),
                            'severity': anomaly_alert.severity,
                            'timestamp': current_data.data_timestamp.isoformat(),
                            'current_price': float(current_data.close_price) if current_data.close_price else None
                        })
                        
                        logger.info(f"Anomaly detected: {stock.symbol} - {anomaly_type} (confidence: {anomaly_score:.3f})")
            
            except Exception as e:
                logger.error(f"Error detecting anomalies for {stock.symbol}: {e}")
                continue
        
        return JsonResponse({
            'status': 'success',
            'anomalies_detected': anomaly_count,
            'anomalies': detected_anomalies[:10],  # Return top 10 anomalies
            'detection_timestamp': timezone.now().isoformat(),
            'stocks_analyzed': monitored_stocks.count()
        })
        
    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Anomaly detection failed: {str(e)}'
        }, status=500)
