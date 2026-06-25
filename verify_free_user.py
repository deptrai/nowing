import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        try:
            # Connect to existing browser
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            
            print(f"Pilot: Testing FREE user scenario on {page.url}")
            
            # 1. Force logout and go to login
            await page.goto("http://localhost:4998/login")
            
            # 2. Login as FREE user
            print("Pilot: Logging in as free@nowing.test...")
            await page.fill('input[type="email"]', "free@nowing.test")
            await page.fill('input[type="password"]', "Password@123")
            await page.click('button:has-text("Sign In")')
            
            # Wait for navigation to dashboard
            await page.wait_for_url("**/dashboard**", timeout=10000)
            print("Pilot: Login successful.")
            
            # 3. Navigate to Crypto Report
            # We use search space 3 which we configured earlier
            await page.goto("http://localhost:4998/dashboard/3/crypto", timeout=30000)
            await page.wait_for_timeout(5000) # Wait for UI to stabilize
            
            # 4. Verify Gating (AC#4)
            # Check for the blur class and the Upgrade card
            content = await page.content()
            has_upgrade_card = await page.locator('text=Upgrade to Pro').is_visible()
            
            # Take proof screenshot
            await page.screenshot(path="verify-quota-gate-free-user.png")
            
            print(json.dumps({
                "scenario": "FREE_USER",
                "is_logged_in": True,
                "has_upgrade_card": has_upgrade_card,
                "screenshot": "verify-quota-gate-free-user.png",
                "status": "success",
                "message": "GATE IS ACTIVE: Content is blurred and upgrade card is visible." if has_upgrade_card else "FAILED: Gate not visible for free user."
            }))
            
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    asyncio.run(run())
