import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def fix():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/nowing")
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE new_llm_configs SET api_key = 'sk-RnuZ301cRuheBEG1XpOIBGZrvSsN3kHGVgGk05lx1UwEcrFM', api_base = 'https://v98store.com/v1', model_name = 'claude-sonnet-4-6' WHERE name = 'Pro AI'"))
        await conn.execute(text("UPDATE searchspaces SET agent_llm_id = (SELECT id FROM new_llm_configs WHERE name = 'Pro AI') WHERE id = 1"))
    print("Fixed!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix())
