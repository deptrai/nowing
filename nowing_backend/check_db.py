import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/nowing")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, name, agent_llm_id FROM searchspaces WHERE id = 1"))
        print(res.fetchall())
        res = await conn.execute(text("SELECT id, name FROM new_llm_configs"))
        print(res.fetchall())
    await engine.dispose()

asyncio.run(check())
