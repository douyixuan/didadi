"""Live Matrix authority for document reads and mutations."""
from src.matrix_http import segment


class DocumentAccessError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def document_level(api, room, user_id, write=False):
    state = api('GET', '/rooms/' + segment(room) + '/state')
    if not isinstance(state, list) or not all(isinstance(e, dict) for e in state):
        raise DocumentAccessError(403, 'Document room authority could not be verified.')
    if any(e.get('type') == 'm.room.encryption' for e in state):
        raise DocumentAccessError(409, 'Encrypted document rooms are not supported.')
    if not any(e.get('type') == 'm.room.member' and e.get('state_key') == user_id and
               isinstance(e.get('content'), dict) and e['content'].get('membership') == 'join' for e in state):
        raise DocumentAccessError(403, 'Join the document room before accessing this document.')
    power = next((e.get('content', {}) for e in state if e.get('type') == 'm.room.power_levels'), {})
    if not isinstance(power, dict):
        raise DocumentAccessError(403, 'Document power levels could not be verified.')
    users = power.get('users', {})
    level = users.get(user_id, power.get('users_default', 0)) if isinstance(users, dict) else None
    if type(level) is not int or (write and level < 50):
        raise DocumentAccessError(403, 'Document writes require room power level 50 or higher.')
    return level
