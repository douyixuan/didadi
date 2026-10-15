"""Fail-closed room eligibility shared by durable and legacy agents."""
from src.matrix_http import MatrixError, segment


def allowed(api, room, agent_id):
    path = '/rooms/' + segment(room)
    try:
        api('GET', path + '/state/m.room.encryption')
        return False
    except MatrixError as error:
        if error.status == 403 and error.body.get('errcode') == 'M_FORBIDDEN':
            return False
        if error.status != 404 or error.body.get('errcode') != 'M_NOT_FOUND':
            raise
    try:
        return api('GET', path + '/state/m.room.member/' + segment(agent_id)).get('membership') == 'join'
    except MatrixError as error:
        if (error.status, error.body.get('errcode')) in {(403, 'M_FORBIDDEN'), (404, 'M_NOT_FOUND')}:
            return False
        raise
