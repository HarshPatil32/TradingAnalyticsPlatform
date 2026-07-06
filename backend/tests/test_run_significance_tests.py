"""Tests for run_significance_tests() in statistical_tests.py."""

import random

from statistical_tests import (
    VERDICT_NOT_ENOUGH,
    VERDICT_REAL_EDGE,
    plain_english_verdict,
    run_significance_tests,
    winrate_binomial_test,
)

# Shared fixtures

# 35 consistently profitable trades (mean ~8, sd ~5)
WINNING_TRADES = [
    12.5,
    8.3,
    -3.1,
    15.2,
    9.8,
    -2.4,
    11.0,
    7.6,
    -1.8,
    14.3,
    10.5,
    6.2,
    -4.0,
    13.1,
    8.9,
    -2.9,
    12.0,
    9.3,
    -3.5,
    11.7,
    7.8,
    -1.5,
    14.9,
    10.2,
    8.1,
    -2.2,
    13.5,
    9.7,
    -3.8,
    12.3,
    11.1,
    6.9,
    -2.6,
    15.0,
    8.5,
]

# 35 trades drawn from N(0, 10) — no real edge
rng = random.Random(99)
NOISE_TRADES = [rng.gauss(0, 10) for _ in range(35)]

# 10 trades — below the default 30-trade minimum
SMALL_SAMPLE = [5.0, -2.0, 8.0, 3.0, -1.0, 4.0, 7.0, -3.0, 6.0, 2.0]

# All identical: zero standard deviation
FLAT_TRADES = [5.0] * 30


# 1. Return structure


class TestReturnStructure:
    def test_has_all_top_level_keys(self):
        result = run_significance_tests(WINNING_TRADES)
        expected_keys = {
            "verdict",
            "confidence_level",
            "summary",
            "trade_count",
            "min_trade_count_met",
            "ttest",
            "bootstrap_ci",
            "sharpe",
            "winrate",
            "warnings",
        }
        assert expected_keys.issubset(result.keys())

    def test_ttest_has_required_keys(self):
        result = run_significance_tests(WINNING_TRADES)
        assert {"t_statistic", "p_value", "significant", "interpretation"}.issubset(
            result["ttest"].keys()
        )

    def test_bootstrap_ci_has_required_keys(self):
        result = run_significance_tests(WINNING_TRADES)
        assert {
            "mean",
            "ci_lower",
            "ci_upper",
            "ci_excludes_zero",
            "interpretation",
        }.issubset(result["bootstrap_ci"].keys())

    def test_sharpe_has_required_keys(self):
        result = run_significance_tests(WINNING_TRADES)
        assert {
            "sharpe_ratio",
            "t_statistic",
            "p_value",
            "significant",
            "interpretation",
        }.issubset(result["sharpe"].keys())

    def test_winrate_has_required_keys(self):
        result = run_significance_tests(WINNING_TRADES)
        assert {
            "win_rate",
            "wins",
            "losses",
            "p_value",
            "significant",
            "interpretation",
        }.issubset(result["winrate"].keys())

    def test_warnings_is_list(self):
        result = run_significance_tests(WINNING_TRADES)
        assert isinstance(result["warnings"], list)

    def test_confidence_level_propagated(self):
        result = run_significance_tests(WINNING_TRADES, ci_level=0.90)
        assert result["confidence_level"] == 0.90


# 2. Verdict logic


class TestVerdictLogic:
    def test_winning_trades_significant(self):
        result = run_significance_tests(WINNING_TRADES)
        assert result["verdict"] == "SIGNIFICANT"

    def test_noise_trades_not_significant(self):
        result = run_significance_tests(NOISE_TRADES)
        assert result["verdict"] == "NOT_SIGNIFICANT"

    def test_small_sample_insufficient_data(self):
        # 10 trades is below default min_trades=30
        result = run_significance_tests(SMALL_SAMPLE)
        assert result["verdict"] == "INSUFFICIENT_DATA"

    def test_small_sample_min_trade_count_met_false(self):
        result = run_significance_tests(SMALL_SAMPLE)
        assert result["min_trade_count_met"] is False

    def test_winning_trades_min_trade_count_met_true(self):
        result = run_significance_tests(WINNING_TRADES)
        assert result["min_trade_count_met"] is True

    def test_verdict_is_string(self):
        result = run_significance_tests(WINNING_TRADES)
        assert isinstance(result["verdict"], str)

    def test_verdict_values_are_valid(self):
        valid = {"SIGNIFICANT", "NOT_SIGNIFICANT", "INSUFFICIENT_DATA"}
        for pnl in [WINNING_TRADES, NOISE_TRADES, SMALL_SAMPLE, []]:
            assert run_significance_tests(pnl)["verdict"] in valid

    def test_trade_count_matches_input_length(self):
        result = run_significance_tests(WINNING_TRADES)
        assert result["trade_count"] == len(WINNING_TRADES)


# 3. Threshold and parameter control


class TestParameters:
    def test_custom_min_trades_raises_insufficient(self):
        # WINNING_TRADES has 35; requiring 50 should flip to INSUFFICIENT_DATA
        result = run_significance_tests(WINNING_TRADES, min_trades=50)
        assert result["verdict"] == "INSUFFICIENT_DATA"

    def test_custom_min_trades_warning_present(self):
        result = run_significance_tests(WINNING_TRADES, min_trades=50)
        assert len(result["warnings"]) > 0

    def test_strict_alpha_can_change_significance(self):
        # Use a very tight alpha so noise_trades still fail, and check winning trades
        run_significance_tests(WINNING_TRADES, alpha=0.05)
        result_strict = run_significance_tests(WINNING_TRADES, alpha=1e-10)
        # With a practically impossible alpha, even winning strategy should not be significant
        assert result_strict["ttest"]["significant"] is False

    def test_risk_free_affects_sharpe(self):
        result_zero_rf = run_significance_tests(WINNING_TRADES, risk_free_per_trade=0.0)
        result_high_rf = run_significance_tests(
            WINNING_TRADES, risk_free_per_trade=100.0
        )
        # High risk-free rate should reduce / eliminate Sharpe significance
        assert (
            result_zero_rf["sharpe"]["sharpe_ratio"]
            > result_high_rf["sharpe"]["sharpe_ratio"]
        )

    def test_bootstrap_seed_reproducible(self):
        r1 = run_significance_tests(NOISE_TRADES, bootstrap_seed=7)
        r2 = run_significance_tests(NOISE_TRADES, bootstrap_seed=7)
        assert r1["bootstrap_ci"]["ci_lower"] == r2["bootstrap_ci"]["ci_lower"]
        assert r1["bootstrap_ci"]["ci_upper"] == r2["bootstrap_ci"]["ci_upper"]

    def test_different_seeds_may_differ(self):
        r1 = run_significance_tests(NOISE_TRADES, bootstrap_seed=1)
        r2 = run_significance_tests(NOISE_TRADES, bootstrap_seed=2)
        # CIs from different seeds are not guaranteed equal for noisy data
        assert r1["bootstrap_ci"]["ci_lower"] != r2["bootstrap_ci"]["ci_lower"]


# 4. Edge cases


class TestEdgeCases:
    def test_integer_inputs_coerced_to_float(self):
        # Should not raise; integers must be accepted
        result = run_significance_tests([1, 2, 3, 4, 5])
        assert isinstance(result, dict)

    def test_flat_trades_ttest_undefined(self):
        # All identical values → std=0 → t-test undefined
        result = run_significance_tests(FLAT_TRADES)
        assert result["ttest"]["t_statistic"] is None

    def test_flat_trades_sharpe_undefined(self):
        result = run_significance_tests(FLAT_TRADES)
        assert result["sharpe"]["sharpe_ratio"] is None

    def test_all_losses_wins_zero(self):
        all_losses = [-1.0] * 30
        result = run_significance_tests(all_losses)
        assert result["winrate"]["wins"] == 0
        assert result["winrate"]["win_rate"] == 0.0

    def test_all_losses_binomial_p_value_significant(self):
        # 0 wins out of 30 is extremely unlikely under H0=0.5; p should be tiny
        result = run_significance_tests([-1.0] * 30)
        assert result["winrate"]["p_value"] < 0.05

    def test_all_losses_verdict_is_not_significant_or_insufficient(self):
        # t-test and sharpe are undefined (zero std), so ttest+CI cannot both confirm
        result = run_significance_tests([-1.0] * 30)
        assert result["verdict"] in {"NOT_SIGNIFICANT", "INSUFFICIENT_DATA"}

    def test_all_wins_losses_zero(self):
        all_wins = [1.0] * 30
        result = run_significance_tests(all_wins)
        assert result["winrate"]["losses"] == 0

    def test_all_wins_binomial_p_value_significant(self):
        # 30 wins out of 30 is extremely unlikely under H0=0.5
        result = run_significance_tests([1.0] * 30)
        assert result["winrate"]["p_value"] < 0.05

    def test_all_wins_verdict_is_not_significant_or_insufficient(self):
        # t-test undefined (zero std) so the SIGNIFICANT verdict cannot be triggered
        result = run_significance_tests([1.0] * 30)
        assert result["verdict"] in {"NOT_SIGNIFICANT", "INSUFFICIENT_DATA"}

    def test_wins_plus_losses_equals_trade_count(self):
        result = run_significance_tests(WINNING_TRADES)
        wr = result["winrate"]
        assert wr["wins"] + wr["losses"] == result["trade_count"]

    def test_negative_mean_warning(self):
        negative_pnl = [-5.0] * 30
        result = run_significance_tests(negative_pnl)
        assert any("negative" in w.lower() for w in result["warnings"])

    def test_high_skewness_warning(self):
        # One massive outlier creates extreme positive skew
        skewed = [1.0] * 29 + [10_000.0]
        result = run_significance_tests(skewed)
        assert any("skew" in w.lower() for w in result["warnings"])

    def test_summary_is_non_empty_string(self):
        for pnl in [WINNING_TRADES, NOISE_TRADES, []]:
            result = run_significance_tests(pnl)
            assert isinstance(result["summary"], str)
            assert len(result["summary"]) > 0

    def test_two_trades_runs_without_error(self):
        result = run_significance_tests([3.0, -1.0])
        assert isinstance(result, dict)
        assert "verdict" in result


# 5. Bootstrap CI


class TestBootstrapCI:
    def test_ci_lower_lte_upper(self):
        result = run_significance_tests(WINNING_TRADES)
        bci = result["bootstrap_ci"]
        assert bci["ci_lower"] <= bci["ci_upper"]

    def test_mean_between_ci_bounds(self):
        result = run_significance_tests(WINNING_TRADES)
        bci = result["bootstrap_ci"]
        assert bci["ci_lower"] <= bci["mean"] <= bci["ci_upper"]

    def test_winning_trades_ci_excludes_zero(self):
        result = run_significance_tests(WINNING_TRADES)
        assert result["bootstrap_ci"]["ci_excludes_zero"] is True

    def test_noise_trades_ci_includes_zero(self):
        result = run_significance_tests(NOISE_TRADES)
        assert result["bootstrap_ci"]["ci_excludes_zero"] is False


# 6. P-value sanity (t-test, Sharpe, binomial)


class TestPValues:
    def test_ttest_p_value_in_unit_interval(self):
        for pnl in [WINNING_TRADES, NOISE_TRADES, SMALL_SAMPLE]:
            p = run_significance_tests(pnl)["ttest"]["p_value"]
            if p is not None:
                assert 0.0 <= p <= 1.0

    def test_winning_ttest_p_value_below_alpha(self):
        result = run_significance_tests(WINNING_TRADES)
        assert result["ttest"]["p_value"] < 0.05

    def test_noise_ttest_p_value_above_alpha(self):
        result = run_significance_tests(NOISE_TRADES)
        assert result["ttest"]["p_value"] >= 0.05

    def test_sharpe_p_value_in_unit_interval(self):
        for pnl in [WINNING_TRADES, NOISE_TRADES]:
            p = run_significance_tests(pnl)["sharpe"]["p_value"]
            if p is not None:
                assert 0.0 <= p <= 1.0

    def test_winning_sharpe_p_value_below_alpha(self):
        result = run_significance_tests(WINNING_TRADES)
        assert result["sharpe"]["p_value"] < 0.05

    def test_winrate_p_value_in_unit_interval(self):
        for pnl in [WINNING_TRADES, NOISE_TRADES, SMALL_SAMPLE]:
            p = run_significance_tests(pnl)["winrate"]["p_value"]
            if p is not None:
                assert 0.0 <= p <= 1.0

    def test_fewer_than_30_ttest_p_value_still_valid(self):
        # Under-powered but p-value should still be a well-formed number
        result = run_significance_tests(SMALL_SAMPLE)
        p = result["ttest"]["p_value"]
        assert p is not None
        assert 0.0 <= p <= 1.0

    def test_fewer_than_30_bootstrap_ci_still_computed(self):
        result = run_significance_tests(SMALL_SAMPLE)
        bci = result["bootstrap_ci"]
        assert bci["ci_lower"] is not None
        assert bci["ci_upper"] is not None
        assert bci["ci_lower"] <= bci["ci_upper"]


# 7. Win-rate binomial test — coin-flip reality check

# 25 wins, 5 losses: 83.3% win rate — well above chance
HIGH_WIN_RATE_TRADES = [2.0] * 25 + [-1.0] * 5

# Exactly 50/50: 15 wins, 15 losses
COIN_FLIP_TRADES = [1.0] * 15 + [-1.0] * 15

# 5 wins, 25 losses: 16.7% win rate — well below chance
LOW_WIN_RATE_TRADES = [1.0] * 5 + [-1.0] * 25


class TestWinrateBinomialTest:
    def test_empty_trade_list_returns_none(self):
        result = winrate_binomial_test([])
        assert result["win_rate"] is None
        assert result["wins"] == 0
        assert result["losses"] == 0
        assert result["significant"] is False
        assert "no nonzero" in result["interpretation"].lower()

    def test_all_breakeven_trades(self):
        result = winrate_binomial_test([0, 0, 0, 0])
        assert result["win_rate"] is None
        assert result["wins"] == 0
        assert result["losses"] == 0
        assert result["significant"] is False
        assert "no nonzero" in result["interpretation"].lower()

    def test_high_win_rate_is_significant(self):
        result = run_significance_tests(HIGH_WIN_RATE_TRADES)
        assert result["winrate"]["significant"] is True

    def test_high_win_rate_p_value_below_alpha(self):
        result = run_significance_tests(HIGH_WIN_RATE_TRADES)
        assert result["winrate"]["p_value"] < 0.05

    def test_coin_flip_not_significant(self):
        result = run_significance_tests(COIN_FLIP_TRADES)
        assert result["winrate"]["significant"] is False

    def test_coin_flip_p_value_above_alpha(self):
        result = run_significance_tests(COIN_FLIP_TRADES)
        assert result["winrate"]["p_value"] >= 0.05

    def test_winning_trades_win_rate_above_half(self):
        result = run_significance_tests(WINNING_TRADES)
        assert result["winrate"]["win_rate"] > 0.5

    def test_winning_trades_win_rate_significant(self):
        # WINNING_TRADES has 25W/10L = 71.4% win rate
        result = run_significance_tests(WINNING_TRADES)
        assert result["winrate"]["significant"] is True

    def test_noise_trades_win_rate_not_significant(self):
        result = run_significance_tests(NOISE_TRADES)
        assert result["winrate"]["significant"] is False

    def test_win_rate_is_fraction(self):
        for pnl in [
            WINNING_TRADES,
            NOISE_TRADES,
            HIGH_WIN_RATE_TRADES,
            COIN_FLIP_TRADES,
        ]:
            wr = run_significance_tests(pnl)["winrate"]["win_rate"]
            assert 0.0 <= wr <= 1.0

    def test_interpretation_mentions_win_rate(self):
        result = run_significance_tests(WINNING_TRADES)
        assert "win rate" in result["winrate"]["interpretation"].lower()

    def test_direct_below_50pct_is_significant(self):
        # 5/30 wins = 16.7% — far below 50%, two-tailed test should catch this
        result = winrate_binomial_test(LOW_WIN_RATE_TRADES)
        assert result["significant"] is True
        assert result["p_value"] < 0.05

    def test_direct_custom_null_win_rate_runs(self):
        # Comparing against a 70% null: result should be a valid p-value
        result = winrate_binomial_test([1.0] * 24 + [-1.0] * 6, null_win_rate=0.70)
        assert result["p_value"] is not None
        assert 0.0 <= result["p_value"] <= 1.0

    def test_direct_high_win_rate_significant(self):
        result = winrate_binomial_test([1.0] * 24 + [-1.0] * 6)
        assert result["significant"] is True
        assert result["p_value"] < 0.05


# 8. Plain-English verdict


PLAIN_ENGLISH_VERDICTS = {VERDICT_NOT_ENOUGH, VERDICT_REAL_EDGE}


class TestPlainEnglishVerdict:
    def test_not_significant_returns_not_enough(self):
        # Coin-flip trades pass min_trades but have no edge — NOT_SIGNIFICANT path
        result = run_significance_tests(COIN_FLIP_TRADES)
        assert result["verdict"] == "NOT_SIGNIFICANT"
        assert plain_english_verdict(COIN_FLIP_TRADES) == VERDICT_NOT_ENOUGH

    def test_winning_trades_returns_real_edge(self):
        assert plain_english_verdict(WINNING_TRADES) == VERDICT_REAL_EDGE

    def test_noise_trades_returns_not_enough(self):
        assert plain_english_verdict(NOISE_TRADES) == VERDICT_NOT_ENOUGH

    def test_small_sample_returns_not_enough(self):
        assert plain_english_verdict(SMALL_SAMPLE) == VERDICT_NOT_ENOUGH

    def test_empty_list_returns_not_enough(self):
        assert plain_english_verdict([]) == VERDICT_NOT_ENOUGH

    def test_returns_one_of_two_valid_strings(self):
        for pnl in [WINNING_TRADES, NOISE_TRADES, SMALL_SAMPLE, [], FLAT_TRADES]:
            assert plain_english_verdict(pnl) in PLAIN_ENGLISH_VERDICTS

    def test_custom_min_trades_affects_verdict(self):
        # WINNING_TRADES (35) is significant at default min_trades=30
        # Raising the bar to 50 should flip it to "not enough trades to know yet"
        assert (
            plain_english_verdict(WINNING_TRADES, min_trades=50) == VERDICT_NOT_ENOUGH
        )

    def test_returns_string(self):
        assert isinstance(plain_english_verdict(WINNING_TRADES), str)
