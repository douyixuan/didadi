"""Validate metadata-only document outcomes independently of human reply text."""
import json
import re


def encode_outcome(value):
    if value is None:
        return None
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError('unsupported outcome version')
    status = value.get('status')
    if not isinstance(status, str) or status not in {'saved', 'read', 'conflict', 'rejected'}:
        raise ValueError('invalid outcome status')
    allowed = {'version', 'status', 'path', 'commit', 'blob', 'reason'}
    if set(value) - allowed:
        raise ValueError('outcome must contain metadata only')
    hashes = {'path', 'commit', 'blob'} & set(value)
    if status == 'saved' or hashes:
        if not isinstance(status, str) or status not in {'saved', 'read'} or hashes != {'path', 'commit', 'blob'} or value['path'] != 'demo.md':
            raise ValueError('invalid outcome document reference')
        if any(not isinstance(value[k], str) or not re.fullmatch('[0-9a-f]{40}', value[k]) for k in ('commit', 'blob')):
            raise ValueError('invalid outcome Git reference')
    if 'reason' in value and (status not in {'conflict', 'rejected'} or not isinstance(value['reason'], str) or value['reason'] not in {'stale_version', 'invalid_request', 'source_not_granted'}):
        raise ValueError('invalid outcome reason')
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def outcome(status, **metadata):
    result = {'version': 1, 'status': status, **metadata}
    encode_outcome(result)
    return result
