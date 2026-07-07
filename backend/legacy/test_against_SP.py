import yfinance as yf


def get_spy_investment(start_date, end_date, initial_balance=100000):
    """Calculates the final balance of an initial investment in SPY from start_date to end_date."""

    data = yf.download(
        "SPY", start=start_date, end=end_date, auto_adjust=True, progress=False
    )
    data.columns = data.columns.str.lower()

    if data.empty:
        return "No data available for SPY in the specified date range.", 400

    initial_price = data["close"].iloc[0]
    final_price = data["close"].iloc[-1]

    final_balance = initial_balance * (final_price / initial_price)
    return final_balance


def generate_spy_monthly_performance(start_date, end_date, initial_balance=100000):
    """
    Generate monthly performance data for SPY investment to use in frontend charts
    """

    # Get the final SPY balance
    final_balance = get_spy_investment(start_date, end_date, initial_balance)

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
