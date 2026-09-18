"""
Hand-written correlation math, kept separate from pandas' built-in
`.rolling().corr()`, per BUILD-SPEC-bitcoin-regime-study.md section 6.3.

Why this file exists: section 6.3 requires the headline 90-day Pearson
correlation to be computed two independent ways -- once by calling pandas,
once by computing covariance and standard deviations directly with NumPy --
so the owner can explain what a correlation coefficient actually measures,
not just which library method he called.
"""

import numpy as np
import pandas as pd


def pearson_correlation(x, y):
    """
    Compute the Pearson correlation coefficient between two arrays by hand.

    Why it exists: implements BUILD-SPEC section 6.3's requirement for a
    hand-written correlation function -- covariance and standard deviations
    computed directly, no np.corrcoef or np.cov shortcut.

    Parameters:
        x: numpy.ndarray, 1-D, no NaNs.
        y: numpy.ndarray, 1-D, no NaNs, same length as x.

    Returns:
        float, the Pearson correlation coefficient of x and y.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    assert x.shape == y.shape, "x and y must be the same length"
    assert not np.isnan(x).any() and not np.isnan(y).any(), "pearson_correlation does not accept NaNs"

    x_mean = np.mean(x)
    y_mean = np.mean(y)

    x_deviations = x - x_mean
    y_deviations = y - y_mean

    covariance = np.mean(x_deviations * y_deviations)
    x_std = np.sqrt(np.mean(x_deviations**2))
    y_std = np.sqrt(np.mean(y_deviations**2))

    return covariance / (x_std * y_std)


def rolling_pearson_hand_written(series_a, series_b, window):
    """
    Compute a rolling Pearson correlation window by window, using
    pearson_correlation() instead of any pandas or NumPy built-in
    correlation function.

    Why it exists: this is the second, independently written
    implementation BUILD-SPEC section 6.3 asks for, to be checked against
    src/correlations.py's pandas-based version. Written as an explicit
    loop over window end-dates rather than a vectorised trick, per
    section 1's "choose the obvious one" rule -- the owner needs to be
    able to trace through this by hand.

    Parameters:
        series_a: pandas.Series, aligned to the same date index as series_b.
        series_b: pandas.Series, aligned to the same date index as series_a.
        window: int, number of trading days in the rolling window.

    Returns:
        pandas.Series of correlations, indexed like series_a, with NaN
        before the first full window and at any window containing a NaN
        in either input series -- matching pandas' own
        min_periods=window behaviour.
    """
    assert series_a.index.equals(series_b.index), "series_a and series_b must share the same date index"

    dates = series_a.index
    correlations = pd.Series(np.nan, index=dates, dtype=float)

    for end_position in range(window - 1, len(dates)):
        start_position = end_position - window + 1
        window_a = series_a.iloc[start_position : end_position + 1].to_numpy()
        window_b = series_b.iloc[start_position : end_position + 1].to_numpy()

        if np.isnan(window_a).any() or np.isnan(window_b).any():
            continue

        end_date = dates[end_position]
        correlations.loc[end_date] = pearson_correlation(window_a, window_b)

    return correlations


def annualized_return(log_returns, trading_days_per_year):
    """
    Compute the annualized return implied by a series of daily log returns.

    Why it exists: BUILD-SPEC section 6.4 requires Bitcoin's annualized
    return as one of the per-regime summary statistics. Daily log returns
    sum over time (unlike simple returns, which compound multiplicatively),
    so the average daily log return is scaled up to a full year and then
    converted back to an ordinary (simple) annual return with exp().

    Parameters:
        log_returns: pandas.Series or numpy.ndarray of daily log returns,
            no NaNs.
        trading_days_per_year: int, e.g. config.TRADING_DAYS_PER_YEAR.

    Returns:
        float, the annualized simple return (0.20 means 20% per year).
    """
    log_returns = np.asarray(log_returns, dtype=float)
    assert not np.isnan(log_returns).any(), "annualized_return does not accept NaNs"
    assert len(log_returns) > 0, "annualized_return needs at least one observation"

    mean_daily_log_return = np.mean(log_returns)
    return float(np.exp(mean_daily_log_return * trading_days_per_year) - 1)


def annualized_volatility(log_returns, trading_days_per_year):
    """
    Compute the annualized volatility (standard deviation) of a series of
    daily log returns.

    Why it exists: BUILD-SPEC section 6.4 requires Bitcoin's annualized
    volatility per regime. Uses the population standard deviation
    (mean of squared deviations, not the n-1 sample correction) computed
    the same way as the AVG(x^2) - AVG(x)^2 formula in
    sql/analysis_queries.sql query 6, so the Python and SQL figures agree
    by construction rather than by coincidence.

    Parameters:
        log_returns: pandas.Series or numpy.ndarray of daily log returns,
            no NaNs.
        trading_days_per_year: int, e.g. config.TRADING_DAYS_PER_YEAR.

    Returns:
        float, the annualized standard deviation of daily log returns.
    """
    log_returns = np.asarray(log_returns, dtype=float)
    assert not np.isnan(log_returns).any(), "annualized_volatility does not accept NaNs"
    assert len(log_returns) > 0, "annualized_volatility needs at least one observation"

    daily_variance = np.mean(log_returns**2) - np.mean(log_returns) ** 2
    daily_std = np.sqrt(daily_variance)
    return float(daily_std * np.sqrt(trading_days_per_year))


def max_drawdown(price_series):
    """
    Compute the maximum drawdown of a price series: the largest peak-to-
    trough percentage decline, evaluated at every point in time (the
    trough does not have to be the series' final value).

    Why it exists: BUILD-SPEC section 6.4 requires Bitcoin's maximum
    drawdown as one of the per-regime summary statistics -- the standard
    way of showing how bad the worst decline within a period actually was,
    which "annualized volatility" alone does not capture.

    Parameters:
        price_series: pandas.Series or numpy.ndarray of prices (not
            returns), in chronological order, no NaNs.

    Returns:
        float, the maximum drawdown as a negative fraction (-0.35 means a
        35% decline from a prior peak). 0.0 if the series never declines.
    """
    prices = np.asarray(price_series, dtype=float)
    assert not np.isnan(prices).any(), "max_drawdown does not accept NaNs"
    assert len(prices) > 0, "max_drawdown needs at least one observation"

    running_max = np.maximum.accumulate(prices)
    drawdowns = (prices - running_max) / running_max
    return float(np.min(drawdowns))
