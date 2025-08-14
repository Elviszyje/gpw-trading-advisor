"""
Tracking models for GPW Trading Advisor.
Performance tracking and analytics.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import SoftDeleteModel, StockSymbol
from apps.analysis.models import TradingSignal
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from decimal import Decimal
from datetime import date

User = get_user_model()

if TYPE_CHECKING:
    from django.db.models import QuerySet


class Portfolio(SoftDeleteModel):
    """
    User's virtual portfolio for tracking performance.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='portfolios'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Portfolio configuration
    initial_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('10000.00'),
        help_text="Starting balance in PLN"
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('10000.00'),
        help_text="Current available balance"
    )
    invested_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Currently invested amount"
    )
    
    # Performance metrics
    total_return = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total return in PLN"
    )
    total_return_percent = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.00'),
        help_text="Total return percentage"
    )
    
    # Risk management
    max_position_size_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(0.1), MaxValueValidator(100)],
        help_text="Maximum position size as percentage of portfolio"
    )
    stop_loss_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        validators=[MinValueValidator(0.1), MaxValueValidator(50)],
        help_text="Default stop loss percentage"
    )
    
    # Settings
    is_default = models.BooleanField(default=False)
    auto_follow_signals = models.BooleanField(
        default=False,
        help_text="Automatically execute signals"
    )
    
    # Statistics
    total_trades = models.PositiveIntegerField(default=0)
    winning_trades = models.PositiveIntegerField(default=0)
    losing_trades = models.PositiveIntegerField(default=0)
    
    # Last update
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.name}"

    @property
    def total_value(self) -> Decimal:
        """Calculate total portfolio value."""
        return self.current_balance + self.invested_amount

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def is_profitable(self) -> bool:
        """Check if portfolio is profitable."""
        return self.total_return > 0

    def update_performance(self) -> None:
        """Recalculate portfolio performance metrics."""
        # Calculate current invested amount from active positions
        from apps.tracking.models import Position  # Avoid circular import
        active_positions = Position.objects.filter(portfolio=self, is_active=True)
        self.invested_amount = sum(
            position.current_value for position in active_positions
        )
        
        # Calculate total return
        self.total_return = self.total_value - self.initial_balance
        
        # Calculate return percentage
        if self.initial_balance > 0:
            self.total_return_percent = (self.total_return / self.initial_balance) * 100
        
        # Update trade statistics
        from apps.tracking.models import Trade  # Avoid circular import
        all_trades = Trade.objects.filter(portfolio=self, status='closed')
        self.total_trades = all_trades.count()
        self.winning_trades = all_trades.filter(profit_loss__gt=0).count()
        self.losing_trades = all_trades.filter(profit_loss__lt=0).count()
        
        self.save(update_fields=[
            'invested_amount', 'total_return', 'total_return_percent',
            'total_trades', 'winning_trades', 'losing_trades', 'last_updated'
        ])

    def can_buy(self, amount: Decimal) -> bool:
        """Check if portfolio has enough balance to buy."""
        return self.current_balance >= amount

    def execute_buy(self, stock: StockSymbol, quantity: int, price: Decimal) -> bool:
        """Execute a buy order."""
        total_cost = quantity * price
        
        if not self.can_buy(total_cost):
            return False
        
        # Create or update position
        position, created = Position.objects.get_or_create(
            portfolio=self,
            stock=stock,
            is_active=True,
            defaults={
                'quantity': quantity,
                'average_buy_price': price,
                'current_price': price,
            }
        )
        
        if not created:
            # Update existing position
            total_shares = position.quantity + quantity
            total_cost_existing = position.quantity * position.average_buy_price
            new_average = (total_cost_existing + total_cost) / total_shares
            
            position.quantity = total_shares
            position.average_buy_price = new_average
            position.current_price = price
            position.save()
        
        # Update portfolio balance
        self.current_balance -= total_cost
        self.save(update_fields=['current_balance'])
        
        return True

    class Meta(SoftDeleteModel.Meta):
        db_table = 'tracking_portfolio'
        verbose_name = 'Portfolio'
        verbose_name_plural = 'Portfolios'
        unique_together = ['user', 'name']
        ordering = ['-is_default', 'name']


class Position(SoftDeleteModel):
    """
    Individual stock positions in portfolios.
    """
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='positions'
    )
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='positions'
    )
    
    # Position details
    quantity = models.PositiveIntegerField()
    average_buy_price = models.DecimalField(max_digits=10, decimal_places=4)
    current_price = models.DecimalField(max_digits=10, decimal_places=4)
    
    # Position status
    is_active = models.BooleanField(default=True, db_index=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Stop loss and target
    stop_loss_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )
    target_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    # Performance tracking
    unrealized_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    unrealized_pnl_percent = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.00')
    )

    def __str__(self) -> str:
        return f"{self.portfolio.name} - {self.stock.symbol} ({self.quantity} shares)"

    @property
    def current_value(self) -> Decimal:
        """Calculate current position value."""
        return Decimal(self.quantity) * self.current_price

    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost of position."""
        return Decimal(self.quantity) * self.average_buy_price

    @property
    def profit_loss(self) -> Decimal:
        """Calculate profit/loss in PLN."""
        return self.current_value - self.total_cost

    @property
    def profit_loss_percent(self) -> Decimal:
        """Calculate profit/loss percentage."""
        if self.total_cost == 0:
            return Decimal('0.00')
        return (self.profit_loss / self.total_cost) * 100

    @property
    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.profit_loss > 0

    def update_current_price(self, new_price: Decimal) -> None:
        """Update current price and recalculate P&L."""
        self.current_price = new_price
        self.unrealized_pnl = self.profit_loss
        self.unrealized_pnl_percent = self.profit_loss_percent
        self.save(update_fields=['current_price', 'unrealized_pnl', 'unrealized_pnl_percent'])

    def close_position(self, sell_price: Decimal) -> 'Trade':
        """Close position and create trade record."""
        # Calculate final P&L
        total_sell_value = Decimal(self.quantity) * sell_price
        profit_loss = total_sell_value - self.total_cost
        
        # Create trade record
        trade = Trade.objects.create(
            portfolio=self.portfolio,
            stock=self.stock,
            trade_type='sell',
            quantity=self.quantity,
            entry_price=self.average_buy_price,
            exit_price=sell_price,
            profit_loss=profit_loss,
            opened_at=self.opened_at,
            closed_at=timezone.now(),
            status='closed'
        )
        
        # Update portfolio balance
        self.portfolio.current_balance += total_sell_value
        self.portfolio.save(update_fields=['current_balance'])
        
        # Close position
        self.is_active = False
        self.closed_at = timezone.now()
        self.save(update_fields=['is_active', 'closed_at'])
        
        return trade

    class Meta(SoftDeleteModel.Meta):
        db_table = 'tracking_position'
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'
        unique_together = ['portfolio', 'stock', 'is_active']
        ordering = ['-opened_at']


class Trade(SoftDeleteModel):
    """
    Completed trades for performance tracking.
    """
    TRADE_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]

    TRADE_STATUS = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='trades'
    )
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='trades'
    )
    related_signal = models.ForeignKey(
        TradingSignal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trades'
    )
    
    # Trade details
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES)
    quantity = models.PositiveIntegerField()
    entry_price = models.DecimalField(max_digits=10, decimal_places=4)
    exit_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    # Performance
    profit_loss = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    profit_loss_percent = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0.00')
    )
    
    # Timing
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=TRADE_STATUS, default='open')
    
    # Trade analysis
    entry_reason = models.TextField(blank=True)
    exit_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.portfolio.name} - {self.trade_type.upper()} {self.stock.symbol}"

    @property
    def trade_value(self) -> Decimal:
        """Calculate trade value."""
        return Decimal(self.quantity) * self.entry_price

    @property
    def duration_days(self) -> Optional[int]:
        """Calculate trade duration in days."""
        if not self.closed_at:
            return None
        delta = self.closed_at - self.opened_at
        return delta.days

    @property
    def is_profitable(self) -> bool:
        """Check if trade was profitable."""
        return self.profit_loss > 0

    def calculate_performance(self) -> None:
        """Calculate trade performance metrics."""
        if self.exit_price and self.status == 'closed':
            total_entry = self.trade_value
            total_exit = Decimal(self.quantity) * self.exit_price
            
            self.profit_loss = total_exit - total_entry
            
            if total_entry > 0:
                self.profit_loss_percent = (self.profit_loss / total_entry) * 100
            
            self.save(update_fields=['profit_loss', 'profit_loss_percent'])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'tracking_trade'
        verbose_name = 'Trade'
        verbose_name_plural = 'Trades'
        ordering = ['-opened_at']
        indexes = [
            models.Index(fields=['portfolio', 'status']),
            models.Index(fields=['stock', 'opened_at']),
        ]


class PerformanceMetrics(models.Model):
    """
    Aggregated performance metrics for portfolios.
    """
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='performance_metrics'
    )
    date = models.DateField()
    
    # Portfolio values
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    cash_balance = models.DecimalField(max_digits=15, decimal_places=2)
    invested_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Performance
    daily_return = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.00'))
    total_return = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.00'))
    
    # Risk metrics
    volatility = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Daily volatility percentage"
    )
    max_drawdown = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Maximum drawdown percentage"
    )
    
    # Trade statistics
    trades_count = models.PositiveIntegerField(default=0)
    winning_trades = models.PositiveIntegerField(default=0)
    losing_trades = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.portfolio.name} - {self.date}"

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.trades_count == 0:
            return 0.0
        return (self.winning_trades / self.trades_count) * 100

    @classmethod
    def calculate_for_portfolio(cls, portfolio: 'Portfolio', calculation_date: 'date') -> 'PerformanceMetrics':
        """Calculate and save performance metrics for a portfolio on a specific date."""
        # Get previous day's metrics for comparison
        previous_metrics = cls.objects.filter(
            portfolio=portfolio,
            date__lt=calculation_date
        ).order_by('-date').first()
        
        # Calculate daily return
        daily_return = Decimal('0.00')
        if previous_metrics:
            if previous_metrics.total_value > 0:
                daily_return = ((portfolio.total_value - previous_metrics.total_value) / 
                              previous_metrics.total_value) * 100
        
        # Count trades for the period
        from apps.tracking.models import Trade  # Avoid circular import
        trades_count = Trade.objects.filter(
            portfolio=portfolio, 
            opened_at__date=calculation_date
        ).count()
        winning_trades = Trade.objects.filter(
            portfolio=portfolio,
            opened_at__date=calculation_date,
            profit_loss__gt=0
        ).count()
        losing_trades = Trade.objects.filter(
            portfolio=portfolio,
            opened_at__date=calculation_date,
            profit_loss__lt=0
        ).count()
        
        # Create or update metrics
        metrics, created = cls.objects.get_or_create(
            portfolio=portfolio,
            date=calculation_date,
            defaults={
                'total_value': portfolio.total_value,
                'cash_balance': portfolio.current_balance,
                'invested_amount': portfolio.invested_amount,
                'daily_return': daily_return,
                'total_return': portfolio.total_return_percent,
                'trades_count': trades_count,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
            }
        )
        
        if not created:
            # Update existing metrics
            metrics.total_value = portfolio.total_value
            metrics.cash_balance = portfolio.current_balance
            metrics.invested_amount = portfolio.invested_amount
            metrics.daily_return = daily_return
            metrics.total_return = portfolio.total_return_percent
            metrics.trades_count = trades_count
            metrics.winning_trades = winning_trades
            metrics.losing_trades = losing_trades
            metrics.save()
        
        return metrics

    class Meta:
        db_table = 'tracking_performance_metrics'
        verbose_name = 'Performance Metrics'
        verbose_name_plural = 'Performance Metrics'
        unique_together = ['portfolio', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['portfolio', 'date']),
        ]
