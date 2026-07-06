import random
from datetime import datetime

import numpy as np
from MACD_trading import backtest_strategy_MACD
from scipy.optimize import minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern


# Set random seeds for deterministic results - must be set each time the function is called
def set_random_seeds():
    np.random.seed(42)
    random.seed(42)


parameter_bounds = {
    "fastperiod": (8, 15),
    "slowperiod": (20, 30),
    "signalperiod": (5, 10),
}


def optimize_macd_parameters(
    symbols, start_date, end_date, initial_balance=100000, n_iterations=15
):
    """
    Optimize MACD parameters for given stocks and date range using Bayesian optimization
    """
    # Reset random seeds at the start of each optimization
    set_random_seeds()

    def objective(parameters):
        fastperiod, slowperiod, signalperiod = parameters
        try:
            _, final_balance = backtest_strategy_MACD(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                trailing_stop_loss=0.1,
                fastperiod=int(fastperiod),
                slowperiod=int(slowperiod),
                signalperiod=int(signalperiod),
            )
            return -final_balance
        except Exception as e:
            print(f"Error in objective function: {e}")
            return -initial_balance  # Return negative initial balance if error occurs

    kernel = Matern(nu=2.5)
    gp = GaussianProcessRegressor(
        kernel=kernel,
        alpha=1e-5,
        normalize_y=True,
        n_restarts_optimizer=10,
        random_state=42,  # Add random state for deterministic results
    )

    def generate_initial_samples(n_samples=5):
        return [
            [
                random.uniform(*parameter_bounds["fastperiod"]),
                random.uniform(*parameter_bounds["slowperiod"]),
                random.uniform(*parameter_bounds["signalperiod"]),
            ]
            for _ in range(n_samples)
        ]

    X_init = np.array(generate_initial_samples())
    y_init = np.array([objective(x) for x in X_init])

    gp.fit(X_init, y_init)

    for i in range(n_iterations):

        def acquisition(x):
            mean, std = gp.predict(np.array(x).reshape(1, -1), return_std=True)
            best_y = min(y_init)
            if std > 0:
                z = (best_y - mean) / std
                return -(mean + std * z)
            else:
                return -mean

        next_sample = []
        best_acq_value = float("inf")

        # Use deterministic sampling instead of random
        np.random.seed(42 + i)  # Different seed per iteration but still deterministic
        random.seed(42 + i)

        for j in range(100):
            random_sample = [
                random.uniform(*parameter_bounds["fastperiod"]),
                random.uniform(*parameter_bounds["slowperiod"]),
                random.uniform(*parameter_bounds["signalperiod"]),
            ]

            res = minimize(
                acquisition,
                random_sample,
                bounds=[
                    parameter_bounds["fastperiod"],
                    parameter_bounds["slowperiod"],
                    parameter_bounds["signalperiod"],
                ],
                method="L-BFGS-B",  # Use deterministic method
            )
            if res.fun < best_acq_value:
                best_acq_value = res.fun
                next_sample = res.x

        next_sample = np.array(next_sample)
        next_y = objective(next_sample)
        X_init = np.vstack((X_init, next_sample))
        y_init = np.append(y_init, next_y)
        gp.fit(X_init, y_init)

    best_params = X_init[np.argmin(y_init)]
    best_balance = -min(y_init)

    return {
        "optimized_params": {
            "fastperiod": int(best_params[0]),
            "slowperiod": int(best_params[1]),
            "signalperiod": int(best_params[2]),
        },
        "best_balance": best_balance,
        "total_return": ((best_balance - initial_balance) / initial_balance) * 100,
    }


# Legacy function - keeping for backward compatibility
def objective(parameters):
    fastperiod, slowperiod, signalperiod = parameters
    _, final_balance = backtest_strategy_MACD(
        symbols=["SVRA", "JIRE", "BUCK", "SCCE", "HIDV"],
        start_date=datetime(2021, 3, 15),
        end_date=datetime(2024, 11, 15),
        initial_balance=100000,
        trailing_stop_loss=0.1,
        fastperiod=int(fastperiod),
        slowperiod=int(slowperiod),
        signalperiod=int(signalperiod),
    )

    return -final_balance


# Legacy optimization code - keeping for standalone execution
if __name__ == "__main__":
    kernel = Matern(nu=2.5)
    gp = GaussianProcessRegressor(
        kernel=kernel, alpha=1e-5, normalize_y=True, n_restarts_optimizer=10
    )

    def generate_initial_samples(n_samples=5):
        return [
            [
                random.uniform(*parameter_bounds["fastperiod"]),
                random.uniform(*parameter_bounds["slowperiod"]),
                random.uniform(*parameter_bounds["signalperiod"]),
            ]
            for _ in range(n_samples)
        ]

    X_init = np.array(generate_initial_samples())
    y_init = np.array([objective(x) for x in X_init])

    n_iterations = 25

    for i in range(n_iterations):

        def acquisition(x):
            mean, std = gp.predict(np.array(x).reshape(1, -1), return_std=True)
            best_y = min(y_init)
            z = (best_y - mean) / std
            return -(mean + std * z)

        next_sample = []
        best_acq_value = float("inf")
        for _ in range(100):
            random_sample = [
                random.uniform(*parameter_bounds["fastperiod"]),
                random.uniform(*parameter_bounds["slowperiod"]),
                random.uniform(*parameter_bounds["signalperiod"]),
            ]

            res = minimize(
                acquisition,
                random_sample,
                bounds=[
                    parameter_bounds["fastperiod"],
                    parameter_bounds["slowperiod"],
                    parameter_bounds["signalperiod"],
                ],
            )
            if res.fun < best_acq_value:
                best_acq_value = res.fun
                next_sample = res.x

        next_sample = np.array(next_sample)
        next_y = objective(next_sample)
        X_init = np.vstack((X_init, next_sample))
        y_init = np.append(y_init, next_y)
        gp.fit(X_init, y_init)

    best_params = X_init[np.argmin(y_init)]
    print(
        f"Optimized Parameters: fastperiod={int(best_params[0])}, slowperiod={int(best_params[1])}, signalperiod={int(best_params[2])}"
    )
    print(f"Best Final Portfolio Balance: {-min(y_init)}")
