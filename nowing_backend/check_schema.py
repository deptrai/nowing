import asyncio
from sqlalchemy import text
from app.db import async_session_maker

async def main():
    async with async_session_maker() as session:
        res = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'new_llm_configs';
        """))
        columns = res.fetchall()
        for c in columns:
            print(c)

if __name__ == "__main__":
    asyncio.run(main())
