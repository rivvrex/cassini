# --- MT5 Credentials ---
# IMPORTANT: Replace with your actual broker MT5 account details
MT5_LOGIN = 1234567
MT5_PASSWORD = "demo"
MT5_SERVER = "Demo"

# --- Trading Parameters ---
DEFAULT_SYMBOL = "USDJPY"
TRADE_THRESHOLD = 0.1
OFFSET_PIPS = 5.0
PRE_NEWS_WINDOW_MINUTES = 5.0
EXECUTION_TOLERANCE_SECONDS = 5.0

# Symbol-Specific Parameters (Pips)
# 1 Pip = 0.10 for Gold (XAUUSD), 0.0001 for most Currencies
SYMBOL_CONFIG = {
    "XAUUSD": {
        "STOP_LOSS_PIPS": 25.0,
        "TAKE_PROFIT_PIPS": 60.0
    },
    "DEFAULT": {
        "STOP_LOSS_PIPS": 25.0,
        "TAKE_PROFIT_PIPS": 60.0
    }
}

# Legacy parameters for backward compatibility (will be overridden by SYMBOL_CONFIG)
STOP_LOSS_PIPS = 30.0
TAKE_PROFIT_PIPS = 90.0

# --- Risk Management ---
MAX_SPREAD_PIPS = 50.0 # Maximum allowable spread (pips) to trigger a trade

# --- Scraper Settings ---
SCHEDULE_FETCH_INTERVAL_HOURS = 0.1

# --- Alternative Data Sources (disabled, use ForexFactory only) ---
USE_NEWS_API = False
NEWS_API_KEY = ""

USE_ALPHA_VANTAGE = False
ALPHA_VANTAGE_KEY = ""

# --- Fallback News Sources ---
USE_INVESTING_COM = False
USE_BLOOMBERG = True
USE_REUTERS = True

# --- Fallback Configuration ---
FALLBACK_TIMEOUT = 30     # Timeout for fallback requests (seconds)
FALLBACK_MAX_RETRIES = 3  # Maximum retries for fallback sources

# --- Ultimate Economic Calendar API (disabled) ---
USE_ULTIMATE_ECONOMIC_CALENDAR = False
ULTIMATE_ECONOMIC_CALENDAR_API_KEY = ""
ULTIMATE_ECONOMIC_CALENDAR_API_HOST = ""

# --- JSON File Configuration ---
# Path to the JSON file containing forex events (instead of scraping)
EVENTS_JSON_FILE = "forex_events.json"  # Change this to your JSON file path

# --- AWS Configuration ---
HEADLESS_MODE = False  # Set to True when deploying to AWS (no GUI)
