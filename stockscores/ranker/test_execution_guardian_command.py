from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class ExecutionGuardianCommandTests(SimpleTestCase):
    @patch("ranker.management.commands.execution_guardian.run_paper_trade_executor")
    @patch("ranker.management.commands.execution_guardian.run_execution_guardian")
    def test_stale_heartbeat_runs_original_executor_fallback(self, guardian, executor):
        guardian.return_value = {"status": "degraded", "reason": "stale_heartbeat"}
        executor.return_value = {"status": "ok", "signals": {}}
        output = StringIO()

        call_command("execution_guardian", "--once", stdout=output)

        executor.assert_called_once_with()
        self.assertIn("fallback", output.getvalue())

    @patch("ranker.management.commands.execution_guardian.run_paper_trade_executor")
    @patch("ranker.management.commands.execution_guardian.run_execution_guardian")
    def test_non_stale_degradation_does_not_compete_with_executor(self, guardian, executor):
        guardian.return_value = {"status": "degraded", "reason": "Alpaca unavailable"}

        call_command("execution_guardian", "--once")

        executor.assert_not_called()
