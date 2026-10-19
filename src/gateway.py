"""Single-node durable gateway for one explicitly invited external agent."""
from contextlib import contextmanager
import hashlib
import json
import secrets
import sqlite3
import time

from src.matrix_as import AGENT
from src.matrix_http import MatrixError, segment
from src.room_access import allowed
from src.document_access import document_level, DocumentAccessError
from src.task_result import encode_outcome


class TaskError(ValueError):
    def __init__(self, code, retryable=False):
        self.code, self.retryable = code, retryable
        super().__init__(code)


class Gateway:
    def __init__(self, path, agent, *, max_attempts=8, lease_seconds=60, retry_seconds=2):
        if max_attempts < 1 or lease_seconds <= 0 or retry_seconds < 0:
            raise ValueError('invalid retry policy')
        self.path, self.agent = str(path), agent
        self.max_attempts, self.lease_seconds, self.retry_seconds = max_attempts, lease_seconds, retry_seconds
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS task_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL, action TEXT NOT NULL, at REAL NOT NULL, attempt INTEGER NOT NULL, reason TEXT);
                CREATE INDEX IF NOT EXISTS task_event_lookup ON task_events(task_id,sequence);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, event TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                    lease TEXT, until REAL DEFAULT 0, result TEXT, reply TEXT);
            ''')
            db.execute('BEGIN IMMEDIATE')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(tasks)')}
            for name, definition in [('attempts', 'INTEGER NOT NULL DEFAULT 0'),
                                     ('last_error', 'TEXT'), ('outcome', 'TEXT'), ('available', 'REAL NOT NULL DEFAULT 0')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {definition}')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _record(self, db, task_id, action, attempt=0, reason=None):
        db.execute('INSERT INTO task_events(task_id,action,at,attempt,reason) VALUES (?,?,?,?,?)',
                   (task_id,action,time.time(),attempt,reason))

    def audit(self, task_id):
        with self.db() as db:
            return [dict(row) for row in db.execute(
                'SELECT sequence,action,at,attempt,reason FROM task_events WHERE task_id=? ORDER BY sequence', (task_id,))]

    def cancel(self, task_id):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
            if row is None:
                raise TaskError('task_not_found',retryable=True)
            if row['status'] not in {'pending','unverified'}:
                return {'status':row['status'],'cancelled':row['status']=='cancelled'}
            db.execute("UPDATE tasks SET status='cancelled',last_error='task_cancelled',lease=NULL,until=0 WHERE id=?",(task_id,))
            self._record(db,task_id,'cancelled',row['attempts'],'task_cancelled')
        return {'status':'cancelled','cancelled':True}

    def allowed(self, room):
        return allowed(self.agent.api, room, AGENT)

    def accept(self, txn, events):
        with self.db() as db:
            if db.execute('SELECT 1 FROM transactions WHERE id=?', (txn,)).fetchone():
                return
        candidates = []
        for event in events:
            if not isinstance(event, dict):
                continue
            content = event.get('content', {})
            mentions = content.get('m.mentions', {}) if isinstance(content, dict) else None
            users = mentions.get('user_ids', []) if isinstance(mentions, dict) else None
            if (not isinstance(content, dict) or not isinstance(users, list)
                    or any(not isinstance(event.get(key), str) for key in ('room_id','event_id','sender'))):
                continue
            if (event.get('type') != 'm.room.message' or 'state_key' in event or
                event.get('sender', '').startswith('@_didadi_') or
                content.get('msgtype') != 'm.text' or
                AGENT not in users or
                not isinstance(content.get('body'), str) or
                not event.get('room_id') or not event.get('event_id')):
                continue
            try:
                eligible = self.allowed(event['room_id'])
                status = 'pending'
            except (MatrixError, OSError):
                eligible, status = True, 'unverified'
            if eligible:
                candidates.append((event, status))
            else:
                print('gateway_skip source_event=' + event['event_id'], flush=True)
        # Commit both transaction and task before ACK; uniqueness also handles concurrent callbacks.
        with self.db() as db:
            for event, status in candidates:
                inserted=db.execute('INSERT OR IGNORE INTO tasks(id,event,status) VALUES (?,?,?)',
                           (event['event_id'], json.dumps(event), status)).rowcount
                if inserted:self._record(db,event['event_id'],'accepted',reason=status)
            db.execute('INSERT OR IGNORE INTO transactions VALUES (?)', (txn,))

    def status(self, task_id):
        with self.db() as db:
            row = db.execute('SELECT status,reply,attempts,last_error,outcome,result AS body FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:return None
            result = dict(row)
            if row['status'] != 'done':result['body'] = None
            result['outcome'] = json.loads(row['outcome']) if row['status'] == 'done' and row['outcome'] else None
            return result

    def claim(self):
        # Reserve a lease in a short transaction. Network checks never hold the database lock.
        # Each due task is considered once per call, so an unavailable room cannot starve others.
        with self.db() as db:
            due = [row['id'] for row in db.execute(
                "SELECT id FROM tasks WHERE status IN ('pending','unverified') AND until < ? AND available <= ? ORDER BY rowid",
                (time.time(), time.time()))]
        for task_id in due:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute("SELECT * FROM tasks WHERE id=? AND status IN ('pending','unverified') AND until < ? AND available <= ?",
                                 (task_id, time.time(), time.time())).fetchone()
                if row is None:
                    continue
                if row['attempts'] >= self.max_attempts:
                    db.execute("UPDATE tasks SET status='failed',last_error='attempts_exhausted',lease=NULL WHERE id=?", (task_id,))
                    self._record(db,task_id,'failed',row['attempts'],'attempts_exhausted')
                    continue
                lease = secrets.token_hex(24)
                db.execute('UPDATE tasks SET lease=?,until=?,attempts=attempts+1 WHERE id=?',
                           (lease, time.time() + min(300, self.lease_seconds * 2 ** min(row['attempts'], 8)), task_id))
            event = json.loads(row['event'])
            try:
                eligible = self.allowed(event['room_id'])
            except (MatrixError, OSError):
                self.fail(task_id, lease, 'room_unavailable', retryable=True)
                continue
            if not eligible:
                self.fail(task_id, lease, 'room_forbidden')
                continue
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                updated = db.execute("UPDATE tasks SET status='pending' WHERE id=? AND lease=? AND status IN ('pending','unverified') AND until > ?", (task_id, lease, time.time())).rowcount
                if not updated:
                    continue
                self._record(db,task_id,'leased',row['attempts']+1)
            return {'id': task_id, 'event': event, 'lease': lease,
                    'result': row['result'], 'outcome': json.loads(row['outcome']) if row['outcome'] else None, 'agent': AGENT, 'attempts': row['attempts'] + 1}
        return None

    def fail(self, task_id, lease, reason='runtime_error', *, retryable=False):
        if reason not in {'runtime_error','room_forbidden','room_unavailable','delivery_forbidden'}:
            raise TaskError('invalid_failure')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None or not secrets.compare_digest(row['lease'] or '', lease):
                raise TaskError('invalid_lease', retryable=True)
            if row['status'] in {'done','failed'} or row['until'] < time.time():
                raise TaskError('invalid_lease', retryable=True)
            terminal = not retryable or row['attempts'] >= self.max_attempts
            delay = min(300, self.retry_seconds * 2 ** min(row['attempts'] - 1, 8))
            status = 'failed' if terminal else 'pending'
            self._record(db,task_id,'failed' if terminal else 'retry_scheduled',row['attempts'],reason)
            db.execute('UPDATE tasks SET status=?,last_error=?,lease=NULL,until=0,available=? WHERE id=?',
                       (status, reason, time.time() + delay, task_id))
        return {'status': status, 'retryable': not terminal}

    def validate(self, task_id, lease):
        """Recheck the current lease and room immediately before a runtime side effect."""
        with self.db() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is not None and row['status']=='cancelled':
            raise TaskError('task_cancelled')
        if (row is None or row['status'] in {'done', 'failed'} or row['until'] < time.time()
                or not secrets.compare_digest(row['lease'] or '', lease)):
            raise TaskError('invalid_lease', retryable=True)
        if not self.allowed(json.loads(row['event'])['room_id']):
            self.fail(task_id, lease, 'room_forbidden')
            raise TaskError('room_forbidden')
        event = json.loads(row['event'])
        content = event['content']
        document, repository = content.get('org.didadi.document'), content.get('org.didadi.repository')
        mutation = (isinstance(document, dict) and document.get('action') == 'write' or
                    isinstance(repository, dict) and repository.get('action') == 'report')
        if isinstance(document, dict) or isinstance(repository, dict):
            try:
                document_level(self.agent.api, event['room_id'], event['sender'], write=mutation)
            except DocumentAccessError:
                self.fail(task_id, lease, 'room_forbidden')
                raise TaskError('room_forbidden') from None
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute("SELECT 1 FROM tasks WHERE id=? AND lease=? AND status='pending' AND until > ?", (task_id,lease,time.time())).fetchone()
            if current is None:
                raise TaskError('invalid_lease', retryable=True)
        return {'allowed': True}

    def complete(self, task_id, lease, result, outcome=None):
        encoded_outcome = encode_outcome(outcome)
        if not isinstance(result, str) or not 0 < len(result) <= 16000:
            raise ValueError('result must contain 1..16000 characters')
        # Serialize completion against lease replacement. Persist the first result before outbound I/O.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is not None and row['status']=='cancelled':
                raise TaskError('task_cancelled')
            if row is None or not secrets.compare_digest(row['lease'] or '', lease):
                raise TaskError('invalid_lease', retryable=True)
            if row['status'] == 'done':
                if row['result'] != result or row['outcome'] != encoded_outcome:
                    raise ValueError('result already fixed')
                return {'event_id': row['reply']}
            if row['status'] == 'failed':
                raise TaskError('task_failed')
            if row['until'] < time.time():
                raise TaskError('invalid_lease', retryable=True)
            if row['result'] is not None and (row['result'] != result or row['outcome'] != encoded_outcome):
                raise ValueError('result already fixed')
            if row['result'] is None:self._record(db,task_id,'result_ready',row['attempts'])
            db.execute('UPDATE tasks SET result=?,outcome=? WHERE id=?', (result, encoded_outcome, task_id))
        event = json.loads(row['event'])
        self.validate(task_id, lease)
        relation = event['content'].get('m.relates_to', {})
        root = relation.get('event_id') if relation.get('rel_type') == 'm.thread' else event['event_id']
        txn = hashlib.sha256(('task:' + task_id).encode()).hexdigest()
        try:
            reply = self.agent.api('PUT', '/rooms/' + segment(event['room_id']) + '/send/m.room.message/' + txn, {
            'msgtype': 'm.text', 'body': result,
            'm.relates_to': {'rel_type': 'm.thread', 'event_id': root,
                             'm.in_reply_to': {'event_id': event['event_id']}},
            'org.didadi.task': {'id': task_id}, **({'org.didadi.task.result': outcome} if outcome is not None else {})})
        except MatrixError as error:
            if error.status == 403 and error.body.get('errcode') == 'M_FORBIDDEN':
                self.fail(task_id, lease, 'delivery_forbidden')
                raise TaskError('room_forbidden') from None
            raise
        with self.db() as db:
            updated = db.execute("UPDATE tasks SET status='done',reply=? WHERE id=? AND lease=? AND status='pending'",
                                 (reply['event_id'], task_id, lease)).rowcount
            if not updated:
                raise TaskError('invalid_lease', retryable=True)
            self._record(db,task_id,'completed',row['attempts'])
        return reply
