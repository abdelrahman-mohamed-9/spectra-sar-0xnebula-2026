"""Alembic runner: authoritative connection comes from .env / DATABASE_URL."""
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from spectra.core.config import get_settings
from spectra.persistence.database import normalize_database_url
from spectra.persistence.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = get_settings().database_url
if not url:
    raise RuntimeError("DATABASE_URL must be set before running migrations")
# set_main_option interprets percent signs for interpolation; escape encoded passwords
config.set_main_option("sqlalchemy.url", normalize_database_url(url).replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=normalize_database_url(url), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = engine_from_config(config.get_section(config.config_ini_section),
                                prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
