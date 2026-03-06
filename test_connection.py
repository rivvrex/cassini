# test_connection.py
import MetaTrader5 as mt5
import config  # Assuming your credentials are in config.py

print("Attempting to connect to MetaTrader 5...")

# 1. Initialize the connection
if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

print("MT5 Initialized successfully.")

# 2. Log in to your account
if not mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
    print("login() failed, error code =", mt5.last_error())
    mt5.shutdown()
    quit()

print(f"Logged into account {config.MT5_LOGIN} successfully.")

# 3. Test getting symbol info
symbol_info = mt5.symbol_info("USDJPY")
if symbol_info is None:
    print("symbol_info(\"USDJPY\") failed, error code =", mt5.last_error())
else:
    print("symbol_info(\"USDJPY\") successful:", symbol_info)

# 4. Shut down the connection
mt5.shutdown()
print("Connection to MT5 closed.")