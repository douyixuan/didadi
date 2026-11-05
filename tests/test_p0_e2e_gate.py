"""Guard the P0 real-acceptance workflow against silently skipped PR checks.

This static contract is not real Matrix/browser acceptance; the GitHub Actions
job itself must actually execute and report success against a PR head.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/real-matrix.yml"


class P0RealE2EGateTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_real_workflow_triggers_for_every_pull_request(self):
        # A path-filtered workflow may publish no check at all on docs-only PRs.
        pull_request = self.workflow.split("\n  push:", 1)[0]
        self.assertIn("\n  pull_request:\n", pull_request)
        self.assertNotIn("\n    paths:\n", pull_request)

    def test_stable_gate_fails_if_live_job_is_skipped_or_failed(self):
        # The job must exist even if the live Matrix job was not eligible.
        self.assertIn("\n  p0-real-e2e-gate:\n", self.workflow)
        gate = self.workflow.split("\n  p0-real-e2e-gate:\n", 1)[1]
        self.assertIn("if: ${{ always() }}", gate)
        self.assertIn("needs: [matrix-smoke]", gate)
        self.assertIn("MATRIX_RESULT: ${{ needs.matrix-smoke.result }}", gate)
        self.assertIn('if [ "$MATRIX_RESULT" != "success" ]; then', gate)


if __name__ == "__main__":
    unittest.main()
