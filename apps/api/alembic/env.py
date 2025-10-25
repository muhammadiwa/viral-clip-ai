from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base

# Import all models so Alembic can detect them
from app.models.user import UserModel
from app.models.organization import OrganizationModel, MembershipModel
from app.models.project import ProjectModel
from app.models.video import VideoModel
from app.models.clip import ClipModel
from app.models.retell import RetellModel
from app.models.job import JobModel
from app.models.transcript import TranscriptModel
from app.models.artifact import ArtifactModel
from app.models.billing import SubscriptionModel, UsageModel, PaymentTransactionModel
from app.models.branding import BrandKitModel, BrandAssetModel
from app.models.audit import AuditLogModel
from app.models.dmca import DmcaNoticeModel
from app.models.idempotency import IdempotencyRecordModel
from app.models.observability import MetricModel
from app.models.qa import QARunModel, QAFindingModel, QAReviewModel
from app.models.webhook import WebhookEndpointModel, WebhookDeliveryModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Get database URL from PostgreSQL environment variables (same as docker-compose)
db_user = os.getenv('POSTGRES_USER', 'postgres')
db_password = os.getenv('POSTGRES_PASSWORD', 'postgres')
db_host = os.getenv('DB_HOST', 'postgres')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('POSTGRES_DB', 'viralclip')
db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
