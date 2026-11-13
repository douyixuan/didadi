"""Offline assertion sensitivity; never calls the live smoke entrypoint."""
import unittest
from scripts.real_login_smoke import assert_metadata_only

class ReceiptAssertionTests(unittest.TestCase):
    def test_rejects_multiline_body_in_nested_decoded_fields(self):
        body='# Second\n\nPrivate 中文\n'
        for value in [{'content':{'body':body}}, {'content':{'extra':[{'text':'prefix '+body+' suffix'}]}}]:
            with self.subTest(value=value), self.assertRaises(AssertionError):assert_metadata_only(value,body)
    def test_allows_only_metadata_without_the_body(self):
        assert_metadata_only({'content':{'body':'Saved file.md','meta':{'path':'file.md','commit':'a'*40}}},'# Second\n\nPrivate 中文\n')
