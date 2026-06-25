import asyncio
from sqlalchemy import text
from app.db import async_session_maker

async def main():
    async with async_session_maker() as session:
        res = await session.execute(text("SELECT id, name, provider, model_name, api_base FROM new_llm_configs"))
        configs = res.fetchall()
        for c in configs:
            print(f"ID: {c.id}, Name: {c.name}, Provider: {c.provider}, Model: {c.model_name}, Base: {c.api_base}")

if __name__ == "__main__":
    asyncio.run(main())
