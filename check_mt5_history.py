
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

# Connect to MT5
if not mt5.initialize():
    print(f"initialize() failed, error code = {mt5.last_error()}")
    quit()

# Get history for last 2 days
from_date = datetime.now() - timedelta(days=2)
history = mt5.history_deals_get(from_date, datetime.now())

if history is None:
    print(f"No history found, error code={mt5.last_error()}")
elif len(history) > 0:
    print(f"Found {len(history)} trades in history:")
    print(f"{'Time':<20} | {'Symbol':<10} | {'Type':<5} | {'Volume':<6} | {'Price':<10} | {'Profit':<10} | {'Comment'}")
    print("-" * 90)
    
    for deal in history:
        # Convert timestamp to readable string
        dt = datetime.fromtimestamp(deal.time)
        type_str = "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL"
        if deal.type == mt5.DEAL_TYPE_BALANCE: type_str = "BAL"
        
        print(f"{str(dt):<20} | {deal.symbol:<10} | {type_str:<5} | {deal.volume:<6} | {deal.price:<10} | {deal.profit:<10} | {deal.comment}")
else:
    print("History is empty")

mt5.shutdown()
