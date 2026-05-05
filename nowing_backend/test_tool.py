import asyncio
from app.agents.new_chat.tools.crypto_smart_money_flow import create_smart_money_flow_tool

async def main():
    tool = create_smart_money_flow_tool()
    res = await tool.ainvoke({"token_address": "PEPE"})
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
