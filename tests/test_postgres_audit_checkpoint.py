from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from precog.audit_integrity import GENESIS_HASH
from precog.postgres_promotion_audit import PostgresPromotionAuditLog


class Cursor:
    def __init__(self, fetchone_values=(), rows=()):
        self.fetchone_values = list(fetchone_values)
        self.rows = list(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        self.executed.append((query, params))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, fetchone_values=(), rows=()):
        self.cursor_obj = Cursor(fetchone_values, rows)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_export_checkpoint_signs_empty_chain_genesis():
    private = Ed25519PrivateKey.generate()
    connection = Connection(fetchone_values=[(GENESIS_HASH,), None])
    log = PostgresPromotionAuditLog(connection)

    checkpoint = log.export_checkpoint(
        private_key=private,
        public_key_id="test-key",
        created_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
    )

    assert checkpoint.sequence == 0
    assert checkpoint.head_hash == GENESIS_HASH
    assert connection.commits == 2
    assert "event_hash IS NOT NULL" in connection.cursor_obj.executed[-1][0]
