import MetaTrader5 as mt5

if not mt5.initialize():
    print("Failed to connect:", mt5.last_error())
else:
    print("Connected.")
    info = mt5.account_info()
    print("Account:", info.login, "| Balance:", info.balance, info.currency)
    tick = mt5.symbol_info_tick("EURUSD")
    print("EUR/USD price:", tick.ask)
    mt5.shutdown()