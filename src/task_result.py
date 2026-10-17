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
    allowed = {'version', 'status', 'path', 'commit', 'blob', 'reason', 'resource'}
    if set(value) - allowed:
        raise ValueError('outcome must contain metadata only')
    if 'resource' in value:
        resource=value['resource']
        if (status!='read' or any(key in value for key in ('path','commit','blob')) or not isinstance(resource,dict) or
                set(resource)!={'kind','repository','path','commit','blob'} or resource['kind']!='repository' or
                not isinstance(resource['repository'],str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',resource['repository']) or
                not isinstance(resource['path'],str) or not 0<len(resource['path'])<=1024 or
                any(c in resource['path'] for c in '\r\n\0\\') or resource['path'].startswith('/') or
                any(part in {'','.','..'} for part in resource['path'].split('/')) or
                any(not isinstance(resource[key],str) or not re.fullmatch('[0-9a-f]{40}',resource[key]) for key in ('commit','blob'))):
            raise ValueError('invalid resource reference')
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


def metadata_result(event, value):
    """Never interpolate runtime display text into resource-task Matrix replies."""
    content=event.get('content',{})
    if not any(key in content for key in ('org.didadi.document','org.didadi.repository')):return None
    if value is None:return 'Document task completed. Inspect the authorized Document API for its current version.'
    encode_outcome(value)
    label={'saved':'Saved demo.md','read':'Resource read through scoped Document API','conflict':'Document conflict: refresh the Git version and merge','rejected':'Document request rejected'}[value['status']]
    if 'commit' in value:label+='\nGit commit: '+value['commit']+'\nBlob: '+value['blob']
    if 'resource' in value:label+='\nSource commit: '+value['resource']['commit']+'\nBlob: '+value['resource']['blob']
    return label
