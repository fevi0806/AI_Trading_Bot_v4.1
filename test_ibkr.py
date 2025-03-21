from ib_insync import *

# Connect to IBKR API (Port 7497 for paper trading)
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Get account summary
account_summary = ib.accountSummary()
print(account_summary)

# Disconnect
ib.disconnect()
