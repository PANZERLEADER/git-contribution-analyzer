from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.dialects.sqlite import insert

from git_contribution_analyzer.adapters.storage.sqlite.models import repositories
from git_contribution_analyzer.domain.errors import WorkspaceError
from git_contribution_analyzer.domain.models.repository import DiscoveredRepository


def database_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def create_database_engine(path: Path) -> Engine:
    engine = create_engine(database_url(path), future=True)

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def _alembic_config(path: Path) -> Config:
    config = Config()
    migrations = Path(__file__).with_name("migrations")
    config.set_main_option("script_location", str(migrations))
    config.set_main_option("sqlalchemy.url", database_url(path))
    return config


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        command.upgrade(_alembic_config(path), "head")
    except Exception as exc:
        raise WorkspaceError(f"Unable to initialize database: {path}") from exc


def upsert_repository(
    path: Path,
    repository: DiscoveredRepository,
    default_branch: str,
) -> str:
    repository_id = str(uuid5(NAMESPACE_URL, repository.root.as_uri()))
    engine = create_database_engine(path)
    statement = insert(repositories).values(
        id=repository_id,
        root_path=str(repository.root),
        git_dir=str(repository.git_dir),
        default_branch=default_branch,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[repositories.c.root_path],
        set_={
            "git_dir": str(repository.git_dir),
            "default_branch": default_branch,
            "updated_at": text("CURRENT_TIMESTAMP"),
        },
    )
    try:
        with engine.begin() as connection:
            connection.execute(statement)
    except Exception as exc:
        raise WorkspaceError(f"Unable to register repository: {repository.root}") from exc
    finally:
        engine.dispose()
    return repository_id


def check_database(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        engine = create_database_engine(path)
        with engine.connect() as connection:
            quick_check = connection.execute(text("PRAGMA quick_check")).scalar_one()
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        engine.dispose()
        return quick_check == "ok" and bool(revision)
    except Exception:
        return False
