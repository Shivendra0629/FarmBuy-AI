import numpy as np
from sklearn.linear_model import LinearRegression


def forecast_demand(history, days_ahead=7):
    """
    Forecast future demand using historical demand data.
    """

    if len(history) < 3:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "At least 3 historical demand values are required."
        }

    X = np.arange(1, len(history) + 1).reshape(-1, 1)
    y = np.array(history)

    model = LinearRegression()
    model.fit(X, y)

    future_days = np.arange(
        len(history) + 1,
        len(history) + days_ahead + 1
    ).reshape(-1, 1)

    predictions = model.predict(future_days)

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