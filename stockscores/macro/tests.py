from django.test import SimpleTestCase

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
