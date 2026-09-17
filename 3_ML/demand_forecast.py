import numpy as np


def forecast_demand(history, days_ahead=7):
    """
    Forecast future demand using historical demand data.
    """

    if len(history) < 3:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "At least 3 historical demand values are required."
        }

    x = np.arange(1, len(history) + 1, dtype=float)
    y = np.array(history, dtype=float)

    # Analytical Ordinary Least Squares (OLS) - zero external C/Fortran or Scipy deadlock risk
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    denom = float(np.sum((x - x_mean) ** 2))
    slope = float(np.sum((x - x_mean) * (y - y_mean)) / denom) if denom != 0 else 0.0
    intercept = float(y_mean - slope * x_mean)

    future_days = np.arange(
        len(history) + 1,
        len(history) + days_ahead + 1,
        dtype=float
    )

    predictions = slope * future_days + intercept

    predictions = [
        round(max(0, float(value)), 2)
        for value in predictions
    ]

    return {
        "status": "SUCCESS",
        "historical_demand": history,
        "forecast_days": days_ahead,
        "predicted_demand": predictions
    }