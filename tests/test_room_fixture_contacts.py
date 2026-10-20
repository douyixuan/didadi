import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.room_fixture_contacts import configure

class FixtureContactsTests(unittest.TestCase):
    def test_only_existing_synthetic_ids_are_written(self):
        with tempfile.TemporaryDirectory() as root:
            state=Path(root)/'state.json';state.write_text(json.dumps({'tokens':['alice-secret','bob-secret']}));output=Path(root)/'contacts.json'
            with patch('scripts.room_fixture_contacts.request',side_effect=[{'user_id':'@alice_a123:didadi.localhost'},{'user_id':'@bob_a123:didadi.localhost'}]) as request:
                self.assertEqual(configure(state,'http://127.0.0.1:8008',output),['@bob_a123:didadi.localhost'])
                self.assertEqual([call.args[1] for call in request.call_args_list],['GET','GET'])
            self.assertEqual(json.loads(output.read_text()),['@bob_a123:didadi.localhost']);self.assertEqual(output.stat().st_mode&0o777,0o600)
            self.assertNotIn('secret',output.read_text())
    def test_other_identity_or_existing_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            state=Path(root)/'state.json';state.write_text(json.dumps({'tokens':['a','b']}));output=Path(root)/'contacts.json'
            with patch('scripts.room_fixture_contacts.request',side_effect=[{'user_id':'@alice_a123:didadi.localhost'},{'user_id':'@realperson:didadi.localhost'}]):
                with self.assertRaises(ValueError):configure(state,'http://127.0.0.1:8008',output)
            self.assertFalse(output.exists());output.write_text('["keep"]')
            with patch('scripts.room_fixture_contacts.request',side_effect=[{'user_id':'@alice_a123:didadi.localhost'},{'user_id':'@bob_a123:didadi.localhost'}]):
                with self.assertRaises(ValueError):configure(state,'http://127.0.0.1:8008',output)
            self.assertEqual(output.read_text(),'["keep"]')
