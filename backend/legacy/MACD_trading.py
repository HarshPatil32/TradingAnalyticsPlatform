import yfinance as yf

try:
    import talib

    TALIB_AVAILABLE = True
    print("TA-Lib imported successfully")
except ImportError:
    TALIB_AVAILABLE = False
    print("TA-Lib not available, using pandas implementation")


def calculate_indicators(data, fastperiod, slowperiod, signalperiod):
    """
    Calculate MACD indicators using TA-Lib if available, otherwise use pandas
    """
    if TALIB_AVAILABLE:
        # Use TA-Lib (preferred method)
        data["MACD"], data["Signal"], data["Hist"] = talib.MACD(
            data["close"],
            fastperiod=fastperiod,
            slowperiod=slowperiod,
            signalperiod=signalperiod,
        )
    else:
        # Use pandas implementation as fallback
        # Calculate EMAs
        ema_fast = data["close"].ewm(span=fastperiod).mean()
        ema_slow = data["close"].ewm(span=slowperiod).mean()

        # Calculate MACD line
        data["MACD"] = ema_fast - ema_slow

        # Calculate Signal line (EMA of MACD)
        data["Signal"] = data["MACD"].ewm(span=signalperiod).mean()

        # Calculate Histogram
        data["Hist"] = data["MACD"] - data["Signal"]

    return data


def backtest_strategy_MACD(
    symbols,
    start_date,
    end_date,
    initial_balance=100000,
    trailing_stop_loss=0.15,
    fastperiod=12,
    slowperiod=26,
    signalperiod=9,
    return_monthly_data=False,
):
    portfolio_balance = initial_balance
    total_trade_history = []
    return_str = ""

    for symbol in symbols:

        data = yf.download(
            symbol, start=start_date, end=end_date, auto_adjust=True, progress=False
        )
        data.columns = data.columns.str.lower()

        try:
            data = calculate_indicators(data, fastperiod, slowperiod, signalperiod)
        except KeyError:
            return f"{symbol} is not the name of a real stock"

        position = 0
        balance = portfolio_balance / len(symbols)
        trade_history = []
        highest_price = None

        for index in range(1, len(data)):
            macd_line = data["MACD"].iloc[index]
            signal_line = data["Signal"].iloc[index]
            price = data["close"].iloc[index]

            if (
                macd_line > signal_line
                and data["Hist"].iloc[index] > 0
                and position == 0
            ):
                qty = int(balance / price)
                balance -= qty * price
                position = qty
                highest_price = price
                trade_history.append(
                    {
                        "symbol": symbol,
                        "action": "buy",
                        "price": price,
                        "qty": qty,
                        "date": data.index[index],
                    }
                )

                if position > 0:
                    highest_price = max(highest_price, price)

            if position > 0 and (
                macd_line < signal_line
                or price <= highest_price * (1 - trailing_stop_loss)
            ):
                balance += position * price
                trade_history.append(
                    {
                        "symbol": symbol,
                        "action": "sell",
                        "price": price,
                        "qty": qty,
                        "date": data.index[index],
                    }
                )
                position = 0
                highest_price = None

        if position > 0:
            balance += position * data["close"].iloc[-1]

        portfolio_balance += balance - (initial_balance / len(symbols))
        total_trade_history.extend(trade_history)

        return_str += (
            f"Initial Balance: ${initial_balance / len(symbols):,.2f}, "
            f"Final Balance for {symbol}: ${balance:,.2f}\n"
        )

        return_str += (
            f"Portfolio Initial Balance: ${initial_balance:,.2f}, "
            f"Final Portfolio Balance: ${portfolio_balance:,.2f}\n"
        )
    return return_str, portfolio_balance


def generate_monthly_performance(
    symbols,
    start_date,
    end_date,
    initial_balance=100000,
    fastperiod=12,
    slowperiod=26,
    signalperiod=9,
):
    """
    Generate monthly performance data for MACD strategy to use in frontend charts
    """

    # Get the optimized backtest results
    _, final_balance = backtest_strategy_MACD(
        symbols,
        start_date,
        end_date,
        initial_balance,
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod,
    )

    # Calculate number of months between start and end date
    months = (end_date.year - start_date.year) * 12 + (
        end_date.month - start_date.month
    )
    if months <= 0:
        months = 1

    # Calculate monthly growth rate
    total_return = (final_balance - initial_balance) / initial_balance
    monthly_return = (1 + total_return) ** (1 / months) - 1

    # Generate monthly data points
    monthly_data = []
    current_balance = initial_balance
    current_date = start_date

    for month in range(months + 1):
        if month == 0:
            monthly_data.append(
                {
                    "month": "Start",
                    "balance": initial_balance,
                    "date": current_date.strftime("%Y-%m"),
                }
            )
        elif month == months:
            # Use actual final balance for last month
            monthly_data.append(
                {
                    "month": f"Month {month}",
                    "balance": final_balance,
                    "date": current_date.strftime("%Y-%m"),
                }
            )
        else:
            # Use calculated monthly growth
            current_balance *= 1 + monthly_return
            monthly_data.append(
                {
                    "month": f"Month {month}",
                    "balance": round(current_balance, 2),
                    "date": current_date.strftime("%Y-%m"),
                }
            )

        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)

    return monthly_data
