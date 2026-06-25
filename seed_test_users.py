import asyncio
from app.db import User, async_session_maker, SubscriptionStatus
from sqlalchemy import select
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

async def seed():
    async with async_session_maker() as session:
        users_to_create = [
            {
                "email": "free@nowing.ai",
                "password": "Password@123",
                "plan_id": "free",
                "subscription_status": SubscriptionStatus.FREE,
            },
            {
                "email": "pro@nowing.ai",
                "password": "Password@123",
                "plan_id": "pro_monthly",
                "subscription_status": SubscriptionStatus.ACTIVE,
            }
        ]
        
        for u_data in users_to_create:
            result = await session.execute(select(User).where(User.email == u_data["email"]))
            existing_user = result.scalar_one_or_none()
            
            hashed = hash_password(u_data["password"])
            
            if existing_user:
                print(f"Updating user {u_data['email']}...")
                existing_user.plan_id = u_data["plan_id"]
                existing_user.subscription_status = u_data["subscription_status"]
                existing_user.hashed_password = hashed
            else:
                print(f"Creating user {u_data['email']}...")
                new_user = User(
                    email=u_data["email"],
                    hashed_password=hashed,
                    is_active=True,
                    is_verified=True,
                    plan_id=u_data["plan_id"],
                    subscription_status=u_data["subscription_status"],
                    pages_limit=10 if u_data["plan_id"] == "free" else 1000,
                    monthly_token_limit=10000 if u_data["plan_id"] == "free" else 1000000,
                )
                session.add(new_user)
        
        await session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.join(os.getcwd(), "nowing_backend"))
    asyncio.run(seed())
