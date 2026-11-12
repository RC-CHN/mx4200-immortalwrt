"""The legacy rolling build must not publish on a schedule in this fork."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class BuildScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load(
            (ROOT / '.github/workflows/MX4200.yml').read_text())

    def test_legacy_build_is_manual_only(self):
        triggers = self.workflow.get('on', self.workflow.get(True))
        self.assertEqual(set(triggers), {'workflow_dispatch'})

    def test_build_runs_without_date_gate(self):
        self.assertEqual(set(self.workflow['jobs']), {'build'})
        build = self.workflow['jobs']['build']
        self.assertNotIn('needs', build)
        self.assertNotIn('if', build)

    def test_manual_dispatch_remains_available(self):
        triggers = self.workflow.get('on', self.workflow.get(True))
        self.assertIn('workflow_dispatch', triggers)
        self.assertIsNone(triggers['workflow_dispatch'])


if __name__ == '__main__':
    unittest.main()
