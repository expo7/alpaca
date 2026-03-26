from django.test import SimpleTestCase
from django.test import TestCase
import pandas as pd
from rest_framework.test import APIClient
from unittest.mock import patch

from .data_fetchers import _extract_close_series
from .regimes import compute_confidence_score, compute_regime_scores, determine_regime_label


class MacroRegimeFunctionTests(SimpleTestCase):
    def _signal_row(self, key, ret20, dist50=None):
        return {
            "key": key,
            "ret_20d": ret20,
            "dist_50dma": dist50 if dist50 is not None else ret20,
        }

    def test_scores_are_bounded(self):
        rows = [
            self._signal_row("SPY", 20),
            self._signal_row("QQQ", 24),
            self._signal_row("IWM", 18),
            self._signal_row("EEM", 16),
            self._signal_row("COPPER", 10),
            self._signal_row("CRUDE", 14),
            self._signal_row("GOLD", 5),
            self._signal_row("UST10Y", 8),
            self._signal_row("DXY", -6),
            self._signal_row("UST3M", -4),
            self._signal_row("HYG", 8),
            self._signal_row("LQD", 2),
            self._signal_row("USDJPY", 4),
        ]
        scores = compute_regime_scores(rows)

        for val in scores.values():
            self.assertGreaterEqual(val, -100)
            self.assertLessEqual(val, 100)

    def test_regime_label_examples(self):
        self.assertEqual(
            determine_regime_label(
                {
                    "growth": 32,
                    "inflation": 10,
                    "liquidity": 12,
                    "risk_appetite": 28,
                }
            ),
            "Risk-On Expansion",
        )

        self.assertEqual(
            determine_regime_label(
                {
                    "growth": 20,
                    "inflation": 30,
                    "liquidity": 2,
                    "risk_appetite": 12,
                }
            ),
            "Inflationary Expansion",
        )

        self.assertEqual(
            determine_regime_label(
                {
                    "growth": -20,
                    "inflation": 8,
                    "liquidity": -24,
                    "risk_appetite": -18,
                }
            ),
            "Tightening Risk-Off",
        )

    def test_confidence_increases_with_agreement(self):
        weak = compute_confidence_score(
            {
                "growth": 8,
                "inflation": -7,
                "liquidity": 5,
                "risk_appetite": -6,
            }
        )
        strong = compute_confidence_score(
            {
                "growth": 45,
                "inflation": 22,
                "liquidity": 30,
                "risk_appetite": 40,
            }
        )

        self.assertGreater(strong, weak)
        self.assertGreaterEqual(weak, 35)
        self.assertLessEqual(strong, 95)


class MacroDataFetcherNormalizationTests(SimpleTestCase):
    def test_extract_close_series_handles_multiindex_columns(self):
        idx = pd.date_range("2026-01-01", periods=4, freq="D")
        df = pd.DataFrame(
            {
                ("Close", "SPY"): [600.0, 601.5, 603.2, 604.8],
                ("Close", "QQQ"): [510.0, 511.2, 512.1, 514.0],
                ("Open", "SPY"): [598.0, 600.0, 602.0, 603.0],
            },
            index=idx,
        )

        series = _extract_close_series(df)

        self.assertIsInstance(series, pd.Series)
        self.assertEqual(len(series), 4)
        self.assertAlmostEqual(float(series.iloc[-1]), 604.8)


class MacroScoreTrustworthinessTests(SimpleTestCase):
    def test_score_outputs_follow_expected_direction(self):
        signals = [
            {"key": "SPY", "ret_20d": 4.0, "dist_50dma": 3.0},
            {"key": "QQQ", "ret_20d": 5.0, "dist_50dma": 4.0},
            {"key": "IWM", "ret_20d": 3.0, "dist_50dma": 2.0},
            {"key": "EEM", "ret_20d": 2.0, "dist_50dma": 1.0},
            {"key": "COPPER", "ret_20d": 2.0, "dist_50dma": 1.0},
            {"key": "CRUDE", "ret_20d": 3.0, "dist_50dma": 1.0},
            {"key": "GOLD", "ret_20d": 1.0, "dist_50dma": 0.0},
            {"key": "UST10Y", "ret_20d": 2.0, "dist_50dma": 0.0},
            {"key": "DXY", "ret_20d": -1.0, "dist_50dma": 0.0},
            {"key": "UST3M", "ret_20d": -0.5, "dist_50dma": 0.0},
            {"key": "HYG", "ret_20d": 2.0, "dist_50dma": 1.0},
            {"key": "LQD", "ret_20d": 1.0, "dist_50dma": 0.5},
            {"key": "USDJPY", "ret_20d": 1.5, "dist_50dma": 0.0},
        ]

        scores = compute_regime_scores(signals)

        self.assertGreater(scores["growth"], 0)
        self.assertGreater(scores["risk_appetite"], 0)
        self.assertGreater(scores["liquidity"], 0)
        self.assertGreater(scores["inflation"], 0)

    def test_regime_label_avoids_inflationary_when_risk_negative(self):
        label = determine_regime_label(
            {
                "growth": 20,
                "inflation": 30,
                "liquidity": 5,
                "risk_appetite": -15,
            }
        )
        self.assertNotEqual(label, "Inflationary Expansion")


class MacroDashboardEndpointShapeTests(TestCase):
    client_class = APIClient

    @patch("macro.views.fetch_macro_dataset")
    @patch("macro.views.build_signal_table")
    def test_dashboard_endpoint_returns_expected_shape(self, mock_signal_table, mock_dataset):
        idx = pd.date_range("2026-01-01", periods=3, freq="D")
        mock_dataset.return_value = {
            "SPY": {
                "key": "SPY",
                "name": "SPDR S&P 500 ETF",
                "symbol": "SPY",
                "series": pd.Series([500.0, 501.0, 502.0], index=idx),
                "fallback_candidates": ["SPY"],
            }
        }
        mock_signal_table.return_value = [
            {
                "key": "SPY",
                "symbol": "SPY",
                "name": "SPDR S&P 500 ETF",
                "price": 502.0,
                "ret_5d": 1.0,
                "ret_20d": 2.0,
                "ret_60d": 3.0,
                "dist_50dma": 1.5,
                "signal": "Bullish",
                "interpretation": "Momentum is positive and price sits above its 50DMA.",
            }
        ]

        res = self.client.get("/api/macro/dashboard/")
        body = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertIn("as_of", body)
        self.assertIn("overall_regime", body)
        self.assertIn("confidence", body)
        self.assertIn("scores", body)
        self.assertIn("signals", body)
        self.assertIn("narrative", body)
        self.assertIn("playbook", body)
        self.assertIsInstance(body["signals"], list)
        self.assertIsInstance(body["scores"], dict)
