import yfinance as yf


def current_price(df, ticker="AAPL"):

    data = yf.download("AAPL", period="max", interval="1m")

    return round(df[("Close", ticker)].iloc[-1], 2)


x = current_price(data)
print(x)
