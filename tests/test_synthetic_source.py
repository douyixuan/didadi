"""Fresh-start fixture must fail without touching existing or unconfigured data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.create_synthetic_source import create


class SyntheticSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.local=self.root/'.local'/'bundle'
    def state(self):
        self.local.mkdir(parents=True)
        (self.local/'smoke-state.json').write_text(json.dumps({'room':'!fixture','tokens':['synthetic-test-token']}))
    def test_missing_state_and_unavailable_identity_create_nothing(self):
        with self.assertRaises(FileNotFoundError):create(self.root,'http://127.0.0.1:8020')
        self.assertFalse((self.root/'.local').exists())
        self.state()
        with patch('scripts.create_synthetic_source.request',side_effect=OSError('offline')):
            with self.assertRaises(OSError):create(self.root,'http://127.0.0.1:8020')
        self.assertFalse((self.local/'synthetic-source').exists())
        self.assertFalse((self.local/'repository-grants.json').exists())
    def test_fixed_synthetic_commit_and_second_run_preserves_existing_files(self):
        self.state()
        with patch('scripts.create_synthetic_source.request',return_value={'user_id':'@fixture'}):
            grants=create(self.root,'http://127.0.0.1:8020')
        source=self.local/'synthetic-source';original=(source/'example.py').read_bytes()
        item=grants['repositories']['synthetic-example']
        self.assertEqual(item['files'],['example.py']);self.assertEqual(item['rooms'],['!fixture'])
        self.assertEqual(item['senders'],['@fixture']);self.assertRegex(item['commit'],r'^[0-9a-f]{40}$')
        with self.assertRaises(ValueError):create(self.root,'http://127.0.0.1:8020')
        self.assertEqual((source/'example.py').read_bytes(),original)
    def test_existing_grant_and_both_symlink_forms_preserve_targets(self):
        self.state();path=self.local/'repository-grants.json'
        outside=self.root/'existing';outside.write_text('preserve me')
        for kind in ('regular','valid-link','dangling-link'):
            with self.subTest(kind=kind):
                if kind=='regular':path.write_text('original grant')
                elif kind=='valid-link':path.symlink_to(outside)
                else:path.symlink_to(self.root/'absent')
                with patch('scripts.create_synthetic_source.request') as api:
                    with self.assertRaises(ValueError):create(self.root,'http://127.0.0.1:8020')
                    api.assert_not_called()
                self.assertFalse((self.local/'synthetic-source').exists())
                self.assertEqual(outside.read_text(),'preserve me')
                self.assertFalse((self.root/'absent').exists())
                if kind=='regular':self.assertEqual(path.read_text(),'original grant')
                else:self.assertTrue(path.is_symlink())
                path.unlink()

    def test_symlink_and_external_url_are_rejected_before_write(self):
        outside=self.root/'outside';outside.mkdir();(self.root/'.local').symlink_to(outside)
        with self.assertRaises(ValueError):create(self.root,'http://127.0.0.1:8020')
        self.assertEqual(list(outside.iterdir()),[])
        with self.assertRaises(ValueError):create(self.root,'https://example.invalid')
