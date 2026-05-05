import asyncio
from sqlalchemy import text
from app.db import async_session_maker

async def main():
    async with async_session_maker() as session:
        # Update the model_name to gpt-5.4
        await session.execute(text("UPDATE new_llm_configs SET model_name = 'gpt-5.4' WHERE id = 1"))
        await session.commit()
        print("Updated model to gpt-5.4")

if __name__ == "__main__":
    asyncio.run(main())
