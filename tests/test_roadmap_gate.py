"""Gate regression: prevent false completion and broken handoff, without transport."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts.check_roadmap import validate, historical_allowances

SHA = 'a' * 40


class RoadmapGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ('roadmap', 'docs'):
            (self.root / folder).mkdir()
        (self.root / 'ROADMAP.md').write_text('# App\n\n## Module\n\n### Feature\n\n- [ ] Outcome\n')
        for file in ('docs/PRODUCT_WORKFLOW.md', 'roadmap/README.md', 'roadmap/_template.md'):
            (self.root / file).write_text('# Entry\n')
        (self.root / 'evidence.md').write_text('# Actual evidence\n\n## Observed\n')
        (self.root / 'roadmap/_checks.json').write_text(json.dumps({'roadmap': 'ROADMAP.md', 'features': 'roadmap', 'legacy_checked': {}}))
        self.feature = {'id': 'flow', 'leaves': ['Module/Feature/Outcome'], 'owner': 'existing executor', 'sources': ['../evidence.md'], 'plan': '../evidence.md', 'versions': {'main': SHA, 'candidate': SHA, 'installed': None, 'online': None}, 'target': 'local', 'review': {'status': 'passed', 'version': SHA, 'evidence': '../evidence.md#observed'}, 'acceptance': {'status': 'blocked', 'version': None, 'evidence': None}, 'delivery': {'status': 'not-released', 'version': None, 'evidence': None}, 'design': {'required': False, 'status': 'pending', 'reference': None, 'visual_evidence': None}, 'blockers': ['actual flow not run'], 'reopened': False}
        self.save()

    def save(self):
        (self.root / 'roadmap/flow.md').write_text('# Flow\n\n```product-feature\n' + json.dumps(self.feature) + '\n```\n')

    def complete(self):
        self.feature['acceptance'] = {'status': 'passed', 'kind': 'actual-user-flow', 'version': SHA, 'evidence': '../evidence.md#observed', 'environment': 'isolated device', 'data': 'synthetic', 'actor': 'executor', 'date': '2026-10-22', 'steps': 'create/edit/save/reopen/retry', 'observed': 'same content recovered, draft kept'}
        self.feature['delivery'] = {'status': 'delivered', 'version': SHA, 'evidence': '../evidence.md#observed'}
        self.feature['blockers'] = []
        self.save()

    def check_leaf(self):
        path = self.root / 'ROADMAP.md'
        path.write_text(path.read_text().replace('[ ]', '[x]'))

    def test_blocked_feature_is_valid_but_not_checkable(self):
        self.assertEqual(validate(self.root), (1, 1))
        with self.assertRaises(ValueError): validate(self.root, 'flow')
        self.check_leaf()
        with self.assertRaises(ValueError): validate(self.root)

    def test_actual_flow_review_and_delivery_allow_check(self):
        self.complete(); self.check_leaf()
        self.assertEqual(validate(self.root, 'flow'), (1, 1))

    def test_ci_or_mock_cannot_be_actual_acceptance(self):
        self.complete(); self.check_leaf()
        self.feature['acceptance']['kind'] = 'mock'; self.save()
        with self.assertRaises(ValueError): validate(self.root)

    def test_stale_review_or_missing_actual_steps_block_check(self):
        self.complete(); self.check_leaf()
        self.feature['review']['version'] = 'b' * 40; self.save()
        with self.assertRaises(ValueError): validate(self.root)
        self.feature['review']['version'] = SHA
        del self.feature['acceptance']['steps']; self.save()
        with self.assertRaises(ValueError): validate(self.root)

    def test_reopened_defect_revokes_completion(self):
        self.complete(); self.check_leaf()
        self.feature['reopened'] = True; self.save()
        with self.assertRaises(ValueError): validate(self.root)

    def test_ui_needs_visual_evidence_not_just_design(self):
        self.complete(); self.check_leaf()
        self.feature['design']['required'] = True; self.save()
        with self.assertRaises(ValueError): validate(self.root)
        self.feature['design'].update(status='passed', version=SHA, visual_evidence='../evidence.md#observed'); self.save()
        self.assertEqual(validate(self.root), (1, 1))

    def test_online_target_needs_known_matching_version(self):
        self.complete(); self.check_leaf()
        self.feature['target'] = 'online'; self.save()
        with self.assertRaises(ValueError): validate(self.root)
        self.feature['versions']['online'] = SHA; self.save()
        self.assertEqual(validate(self.root), (1, 1))

    def test_link_anchor_and_path_escape_are_rejected(self):
        for ref in ('../evidence.md#missing', '../../outside.md'):
            self.feature['sources'] = [ref]; self.save()
            with self.assertRaises(ValueError): validate(self.root)

    def test_unknown_or_duplicate_leaf_is_rejected(self):
        self.feature['leaves'] = ['Module/Feature/Unknown']; self.save()
        with self.assertRaises(ValueError): validate(self.root)
        self.feature['leaves'] = ['Module/Feature/Outcome'] * 2; self.save()
        with self.assertRaises(ValueError): validate(self.root)

    def test_nested_or_parent_checkbox_is_rejected(self):
        for text in ('# App\n- [ ] Parent\n', '# App\n## Module\n### Feature\n  - [ ] nested\n'):
            (self.root / 'ROADMAP.md').write_text(text)
            with self.assertRaises(ValueError): validate(self.root)

    def test_new_historical_allowance_cannot_bypass_acceptance(self):
        with self.assertRaises(ValueError):
            historical_allowances({'Module/Feature/Outcome': {}}, {'Module/Feature/Outcome': False})
        historical_allowances({'Module/Feature/Outcome': {}}, {'Module/Feature/Outcome': True})

    def test_historical_allowance_is_explicit_and_linked(self):
        (self.root / 'roadmap/flow.md').unlink(); self.check_leaf()
        with self.assertRaises(ValueError): validate(self.root)
        config = self.root / 'roadmap/_checks.json'
        value = json.loads(config.read_text())
        value['legacy_checked']['Module/Feature/Outcome'] = {'scope': 'original narrow runtime evidence only', 'evidence': 'evidence.md#observed'}
        config.write_text(json.dumps(value))
        self.assertEqual(validate(self.root), (1, 0))


if __name__ == '__main__':
    unittest.main()

class StableProductGateTests(unittest.TestCase):
    """Mutate reads only: never change the real repository during validation."""
    def test_stable_product_gate_and_negative_cases(self):
        from unittest.mock import patch
        root = Path(__file__).resolve().parents[1]
        original = Path.read_text
        roadmap = original(root/'ROADMAP.md')
        config = json.loads(original(root/'roadmap/_checks.json'))
        self.assertEqual(validate(root), (16, 1))
        cases = [
            {'ROADMAP.md': roadmap.replace('- [ ] [房间通信隔离](https://github.com/douyixuan/didadi/issues/70)\n', '')},
            {'ROADMAP.md': roadmap.replace('/issues/70)', '/issues/69)')},
            {'ROADMAP.md': roadmap.replace('- [ ] [房间通信隔离]', '- [x] [房间通信隔离]')},
            {'roadmap/README.md': original(root/'roadmap/README.md').replace('- 真实登录（待接入）', '')},
        ]
        no_proof = json.loads(json.dumps(config)); no_proof['accepted'] = {}
        cases.append({'roadmap/_checks.json': json.dumps(no_proof)})
        bad_version = json.loads(json.dumps(config)); bad_version['accepted']['69']['version'] = 'a'*40
        cases.append({'roadmap/_checks.json': json.dumps(bad_version)})
        fake = json.loads(json.dumps(config)); fake['accepted']['69']['kind'] = 'mock'
        cases.append({'roadmap/_checks.json': json.dumps(fake)})
        # Keep the archive digest valid so this proves anchor checking, not hash checking.
        import hashlib
        historical='roadmap/discussion-search.md'
        broken=original(root/historical).replace('#今晚四目标实际对账','#missing-historical-anchor')
        archive_config=json.loads(json.dumps(config))
        archive_config['historical_files'][historical]=hashlib.sha256(broken.encode()).hexdigest()
        cases.append({historical:broken,'roadmap/_checks.json':json.dumps(archive_config)})
        archive='artifact/032-requirements-completion/historical-20261022.md'
        cases.append({archive:original(root/archive).replace('### 今晚四目标实际对账','### Removed historical anchor')})
        for replacements in cases:
            def read(path, *args, **kwargs):
                relative = str(path.relative_to(root)) if path.is_relative_to(root) else ''
                return replacements[relative] if relative in replacements else original(path, *args, **kwargs)
            with self.subTest(case=list(replacements)), patch.object(Path, 'read_text', read):
                with self.assertRaises(ValueError): validate(root)
