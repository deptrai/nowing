import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            
            print(f"Pilot: Testing FREE user (Space 55) on {page.url}")
            
            # 1. Force logout and login
            await page.goto("http://localhost:4998/login")
            await page.fill('input[type="email"]', "free@nowing.test")
            await page.fill('input[type="password"]', "Password@123")
            await page.click('button:has-text("Sign In")')
            
            await page.wait_for_url("**/dashboard/55**", timeout=15000)
            print("Pilot: Login successful into Space 55.")
            
            # 2. Go to Crypto Report
            await page.goto("http://localhost:4998/dashboard/55/crypto", timeout=30000)
            await page.wait_for_timeout(7000) # Wait for UI and gating to trigger
            
            # 3. Verify Gating (AC#4)
            # Find the "Upgrade to Pro" text
            upgrade_prompt = page.get_by_text("Upgrade to Pro", exact=False).first
            is_gated = await upgrade_prompt.is_visible()
            
            # Take proof screenshot
            await page.screenshot(path="verify-quota-gate-free-user-final.png")
            
            print(json.dumps({
                "scenario": "FREE_USER_SPACE_55",
                "is_gated": is_gated,
                "screenshot": "verify-quota-gate-free-user-final.png",
                "status": "success",
                "message": "SUCCESS: Gate is active for free user." if is_gated else "FAILED: Gate not visible."
            }))
            
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    asyncio.run(run())
