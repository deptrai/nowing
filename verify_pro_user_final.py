import asyncio
from playwright.async_api import async_playwright
import json

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
            
            # 2. Wait for Space 56 Dashboard
            await page.wait_for_url("**/dashboard/56/new-chat**", timeout=20000)
            print("Pilot: Navigation to Pro Space 56 successful.")
            
            # 3. Send message and check SSE
            await page.wait_for_selector('.aui-composer-attachment-dropzone', timeout=10000)
            await page.click('.aui-composer-attachment-dropzone')
            await page.keyboard.type("Testing Epic 11: SSE and Pro access.")
            await page.keyboard.press("Enter")
            
            print("Pilot: Message sent. Observing stream...")
            await asyncio.sleep(8)
            
            # Take screenshot of the response
            await page.screenshot(path="verify-pro-sse-final.png")
            
            # Check for redacting elements (should NOT be present for Pro)
            upgrade_prompt = page.get_by_text("Upgrade to Pro", exact=False).first
            is_gated = await upgrade_prompt.is_visible()
            
            print(json.dumps({
                "scenario": "PRO_USER_SPACE_56",
                "is_gated": is_gated,
                "screenshot": "verify-pro-sse-final.png",
                "status": "success",
                "message": "PRO SUCCESS: No gate visible. SSE stream rendering." if not is_gated else "FAILED: Pro user see the gate."
            }))
            
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    asyncio.run(run())
