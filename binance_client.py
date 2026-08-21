import logging
import time
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import TOP_SYMBOLS_COUNT

logger = logging.getLogger(__name__)

KLINE_INTERVAL = "5m"
KLINE_REQUEST_LIMIT = 13
COMPLETED_KLINES_COUNT = 12

session = requests.Session()

retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[
        429,
        500,
        502,
        503,
        504,
    ],
    allowed_methods=["GET"],
    respect_retry_after_header=True,
)

adapter = HTTPAdapter(
    max_retries=retry_strategy
)

session.mount("https://", adapter)

# Define excluded base assets
EXCLUDED_BASE_ASSETS = {
    "USDT",
    "USDC",
    "FDUSD",
    "TUSD",
    "USDP",
    "DAI",
    "BUSD",
    "USDD",
    "FRAX",
    "PYUSD",
    "RLUSD",
    "USD1",
    "BFUSD",
    "EURI",
    "EUR"
}

def get_filtered_symbols():
    """
    Step 1: Fetch exchange info and filter symbols where:
    - quoteAsset is USDT
    - status is TRADING
    - baseAsset NOT in EXCLUDED_BASE_ASSETS
    Returns: Set of filtered symbol names for fast lookup
    """
    url = "https://api.binance.com/api/v3/exchangeInfo"
    
    try:
        response = session.get(url, timeout=40)
        response.raise_for_status()
        exchange_info = response.json()
        
        # Filter symbols and store in a set for fast lookup
        filtered_symbols = set()
        for symbol_data in exchange_info.get("symbols", []):
            if (symbol_data.get("quoteAsset") == "USDT" and 
                symbol_data.get("status") == "TRADING" and
                symbol_data.get("baseAsset") not in EXCLUDED_BASE_ASSETS):
                filtered_symbols.add(symbol_data.get("symbol"))
        
        logger.info("Found %d trading symbols with USDT quote asset (excluding stablecoins)", len(filtered_symbols))
        return filtered_symbols
    
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching exchangeInfo from Binance API: %s", e)
        return set()

def fetch_top_volume_symbols(filtered_symbols):
    url = "https://api.binance.com/api/v3/ticker/24hr"

    try:
        response = session.get(url, timeout=40)
        response.raise_for_status()
        tickers = response.json()

        filtered_tickers = [
            ticker
            for ticker in tickers
            if ticker.get("symbol") in filtered_symbols
        ]

        logger.info("Filtered to %d symbols from ticker data", len(filtered_tickers))

        sorted_tickers = sorted(
            filtered_tickers,
            key=lambda item: float(item.get("quoteVolume") or 0),
            reverse=True,
        )

        top_symbols = sorted_tickers[:TOP_SYMBOLS_COUNT]

        logger.info("Top %d symbols by 24hr quote volume", TOP_SYMBOLS_COUNT)

        logger.info(
            f"{'#':<4} "
            f"{'Symbol':<12} "
            f"{'Quote Volume':<20}"
        )

        logger.info("-" * 36)

        for index, ticker in enumerate(
            top_symbols,
            start=1,
        ):
            symbol = ticker.get("symbol", "N/A")
            quote_volume = float(
                ticker.get("quoteVolume") or 0
            )

            logger.info(
                f"{index:<4} "
                f"{symbol:<12} "
                f"{quote_volume:>18,.2f}"
            )

        return top_symbols

    except requests.exceptions.RequestException as error:
        logger.error("Error fetching ticker data from Binance API: %s", error)
        return []

def get_klines(
    symbol,
    interval=KLINE_INTERVAL,
    limit=KLINE_REQUEST_LIMIT,
):
    """
    Fetch recent Binance klines and return the latest
    12 completed candles.

    Returns None if the request fails after retries.

    Retries temporary HTTP errors, including 429,
    and respects the Retry-After header when available.
    """

    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    try:
        response = session.get(
            url,
            params=params,
            timeout=40,
        )

        response.raise_for_status()

        klines = response.json()

        current_time_ms = int(time.time() * 1000)

        completed_klines = [
            kline
            for kline in klines
            if kline[6] <= current_time_ms
        ]

        return completed_klines[-COMPLETED_KLINES_COUNT:]

    except requests.exceptions.RequestException as error:
        logger.error("Error fetching klines for %s after retries: %s", symbol, error)
        return None