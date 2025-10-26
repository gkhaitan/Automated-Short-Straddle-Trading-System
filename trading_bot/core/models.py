from dataclasses import dataclass
from datetime import datetime

@dataclass
class Candle:
    """
    Represents a single OHLCV candle.
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

@dataclass
class Quote:
    """
    Represents a single price quote.
    """
    timestamp: datetime
    ltp: float

@dataclass
class CombinedPremium:
    """
    Represents a single OHLCV candle for the combined premium series.
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
