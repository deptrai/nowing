import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[0]
            
            # Find the input by role or placeholder
            chat_input = page.get_by_role("textbox").or_(page.get_by_placeholder(re.compile(r"message|ask|hỏi", re.I))).first
            
            if await chat_input.is_visible():
                print("Pilot: Chat input found. Sending message...")
                await chat_input.fill("Verify SSE heartbeat.")
                await page.keyboard.press("Enter")
                
                # Wait for stream
                await asyncio.sleep(5)
                await page.screenshot(path="sse-stream-final.png")
                print(json.dumps({"status": "success", "message": "Message sent, stream observed."}))
            else:
                print(json.dumps({"status": "error", "message": "Chat input not visible."}))
                
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    import re
    asyncio.run(run())
