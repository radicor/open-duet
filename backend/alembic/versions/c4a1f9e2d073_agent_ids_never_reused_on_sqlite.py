"""Agent ids are never reused on SQLite.

SQLite gives a plain INTEGER PRIMARY KEY the value max(id) + 1, so deleting the
newest agent handed its id to the next one. An agent's default folder is
workspace_dir()/agents/<id> and team.lead_agent_id names an agent by id, so a
reused id handed the deleted agent's working directory -- and, if it was the
team lead, its authority -- to a brand-new agent. AUTOINCREMENT never reuses an
id. PostgreSQL identity columns never did, so this does nothing there.

SQLite cannot add AUTOINCREMENT to an existing table, so `agent` is rebuilt:
copied aside, dropped, created again, refilled with the same ids, and its index
recreated. Existing databases already hold bare integer references to agents
(team.lead_agent_id, thread.agent_id, agent_job.*, room*, ...), and a delete
before this upgrade left some of them dangling; the next id must start above
every id any surviving row still names, so those references never land on a new
agent. Everything runs in this migration's one transaction, so a failure leaves
the database as it was. The desktop app copies the database file aside first.

The DDL is spelled out (not generated from the models) so this migration never
changes.

Revision ID: c4a1f9e2d073
Revises: b9d3e7a1c502
"""

from alembic import context, op

revision = "c4a1f9e2d073"
down_revision = "b9d3e7a1c502"
branch_labels = None
depends_on = None

_COLUMNS = (
    "id", "owner_id", "name", "title", "description", "instructions", "provider",
    "model", "fallback_provider", "fallback_model", "workspace_path", "approval_mode",
    "memory_enabled", "recall_enabled", "pinned", "team_id", "delegation_enabled",
    "created_by_agent_id", "instructions_reviewed_at", "archived_at", "created_at",
    "updated_at",
)

# Every column, anywhere, that names an agent by id but is not a foreign key.
_REFERENCES = (
    ("team", "lead_agent_id"),
    ("team_event", "agent_id"),
    ("agent_job", "requester_agent_id"),
    ("agent_job", "assignee_agent_id"),
    ("room", "default_responder_agent_id"),
    ("room_member", "agent_id"),
    ("room_dispatch", "agent_id"),
    ("thread", "agent_id"),
    ("computer", "agent_id"),
    ("routine", "agent_id"),
    ("agent", "created_by_agent_id"),
)

def _agent_sql(autoincrement: bool) -> str:
    id_column = (
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,"
        if autoincrement
        else "id INTEGER NOT NULL,"
    )
    primary_key = "" if autoincrement else ",\n\tPRIMARY KEY (id)"
    return f"""CREATE TABLE agent (
	{id_column}
	owner_id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	title VARCHAR,
	description TEXT,
	instructions TEXT DEFAULT '' NOT NULL,
	provider VARCHAR DEFAULT 'claude' NOT NULL,
	model VARCHAR,
	fallback_provider VARCHAR,
	fallback_model VARCHAR,
	workspace_path VARCHAR,
	approval_mode VARCHAR DEFAULT 'ask' NOT NULL,
	memory_enabled BOOLEAN DEFAULT 1 NOT NULL,
	recall_enabled BOOLEAN DEFAULT 1 NOT NULL,
	pinned BOOLEAN DEFAULT 0 NOT NULL,
	team_id BIGINT,
	delegation_enabled BOOLEAN DEFAULT 1 NOT NULL,
	created_by_agent_id BIGINT,
	instructions_reviewed_at DATETIME,
	archived_at DATETIME,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL{primary_key}
)"""

_INDEX_SQL = (
    "CREATE UNIQUE INDEX uq_agent_owner_name_live ON agent (owner_id, name) "
    "WHERE archived_at IS NULL",
)


def _highest_referenced_id(bind) -> int:
    """The highest agent id any surviving row still names, or 0."""
    tables = {
        row[0]
        for row in bind.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    highest = 0
    for table, column in _REFERENCES:
        if table not in tables:
            continue
        columns = {row[1] for row in bind.exec_driver_sql(f'PRAGMA table_info("{table}")')}
        if column not in columns:
            continue
        value = bind.exec_driver_sql(f'SELECT MAX("{column}") FROM "{table}"').scalar()
        if isinstance(value, int) and not isinstance(value, bool):
            highest = max(highest, value)
    return highest


def _rebuild(autoincrement: bool) -> None:
    bind = op.get_bind()
    columns = ", ".join(_COLUMNS)
    bind.exec_driver_sql("DROP TABLE IF EXISTS _rebuild_agent")
    bind.exec_driver_sql(f"CREATE TABLE _rebuild_agent AS SELECT {columns} FROM agent")
    bind.exec_driver_sql("DROP TABLE agent")
    bind.exec_driver_sql(_agent_sql(autoincrement))
    bind.exec_driver_sql(
        f"INSERT INTO agent ({columns}) SELECT {columns} FROM _rebuild_agent ORDER BY rowid"
    )
    bind.exec_driver_sql("DROP TABLE _rebuild_agent")
    for statement in _INDEX_SQL:
        bind.exec_driver_sql(statement)

    if autoincrement:
        floor = _highest_referenced_id(bind)
        current = bind.exec_driver_sql(
            "SELECT seq FROM sqlite_sequence WHERE name = 'agent'"
        ).scalar() or 0
        if floor > current:
            if bind.exec_driver_sql(
                "SELECT COUNT(*) FROM sqlite_sequence WHERE name = 'agent'"
            ).scalar():
                bind.exec_driver_sql(
                    "UPDATE sqlite_sequence SET seq = ? WHERE name = 'agent'", (floor,)
                )
            else:
                bind.exec_driver_sql(
                    "INSERT INTO sqlite_sequence (name, seq) VALUES ('agent', ?)", (floor,)
                )


def upgrade():
    if context.is_offline_mode() or op.get_bind().dialect.name != "sqlite":
        return
    _rebuild(autoincrement=True)


def downgrade():
    if context.is_offline_mode() or op.get_bind().dialect.name != "sqlite":
        return
    _rebuild(autoincrement=False)
