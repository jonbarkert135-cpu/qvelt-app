import asyncio
import os

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from qvelt_api.database import metadata


async def migrate() -> None:
    engine = create_async_engine(os.environ["QVELT_DATABASE_URL"], hide_parameters=True)
    try:
        async with engine.connect() as connection:
            def run(sync_connection: Connection) -> None:
                context.configure(connection=sync_connection, target_metadata=metadata)
                with context.begin_transaction():
                    context.run_migrations()
            await connection.run_sync(run)
    finally:
        await engine.dispose()


asyncio.run(migrate())
