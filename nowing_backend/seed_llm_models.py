import asyncio
from datetime import datetime, timezone
from sqlalchemy import text
from app.db import async_session_maker

async def main():
    async with async_session_maker() as session:
        # Get the API key and base from the existing config
        res = await session.execute(text("SELECT api_key, api_base, search_space_id, user_id FROM new_llm_configs WHERE id = 1"))
        base_config = res.fetchone()
        
        if not base_config:
            print("Base config (ID=1) not found!")
            return
            
        api_key, api_base, space_id, user_id = base_config
        
        models_to_seed = [
            {"name": "GPT-4o", "model_name": "gpt-4o"},
            {"name": "Qwen 2.5 Max", "model_name": "qwen-max"},
            {"name": "MiniMax abab6.5", "model_name": "abab6.5"},
            {"name": "Claude 3.5 Sonnet", "model_name": "claude-3-5-sonnet-20240620"}
        ]
        
        now = datetime.now(timezone.utc)
        
        for m in models_to_seed:
            # Check if it already exists
            check_res = await session.execute(text("SELECT id FROM new_llm_configs WHERE name = :name AND search_space_id = :space_id"), {"name": m["name"], "space_id": space_id})
            if check_res.fetchone():
                print(f"Model {m['name']} already exists.")
                continue
                
            # Insert the new model
            await session.execute(
                text("""
                    INSERT INTO new_llm_configs 
                    (name, provider, model_name, api_key, api_base, search_space_id, user_id, use_default_system_instructions, citations_enabled, system_instructions, created_at) 
                    VALUES 
                    (:name, 'OPENAI', :model_name, :api_key, :api_base, :space_id, :user_id, true, false, '', :now)
                """),
                {
                    "name": m["name"],
                    "model_name": m["model_name"],
                    "api_key": api_key,
                    "api_base": api_base,
                    "space_id": space_id,
                    "user_id": user_id,
                    "now": now
                }
            )
            print(f"Seeded model: {m['name']}")
            
        await session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(main())
