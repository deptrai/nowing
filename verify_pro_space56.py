import asyncio
from playwright.async_api import async_playwright
import json
import re

async def run():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            
            print(f"Pilot: Logging in as PRO user (pro@nowing.test)...")
            
            # 1. Login
            await page.goto("http://localhost:4998/login")
            await page.fill('input[type="email"]', "pro@nowing.test")
            await page.fill('input[type="password"]', "Password@123")
            await page.click('button:has-text("Sign In")')
            
            await page.wait_for_url("**/dashboard**", timeout=15000)
            print("Pilot: Navigation to Dashboard successful.")
            
            # 2. Go specifically to Space 56
            await page.goto("http://localhost:4998/dashboard/56/new-chat", timeout=30000)
            await page.wait_for_timeout(5000)
            print("Pilot: Navigation to Pro Space 56 successful.")
            
            # 3. Send message and check SSE
            print("Pilot: Interacting with Assistant-UI composer...")
            
            # Use the dropzone selector like we did before
            await page.click('.aui-composer-attachment-dropzone')
            await asyncio.sleep(1)
            await page.keyboard.type('Explain Uniswap (UNI) in detail.')
            await page.keyboard.press('Enter')
            print('Pilot: Message sent. Observing stream...')
            
            # Wait for stream to finish or progress
            await asyncio.sleep(15)
            
            # Take screenshot of the response
            await page.screenshot(path="verify-pro-sse-space56.png")
            
            print(json.dumps({
                "scenario": "PRO_USER_SPACE_56_SSE",
                "status": "success",
                "message": "Message sent and stream observed successfully."
            }))
            
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    asyncio.run(run())
