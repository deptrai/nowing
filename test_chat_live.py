import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[-1]
        
        # Refresh to get new config
        await page.reload()
        await page.wait_for_timeout(5000)
        
        print("Pilot: Typing message...")
        chat_input = page.get_by_role("textbox").first
        await chat_input.click()
        await asyncio.sleep(1)
        await chat_input.fill('Explain what is Ethereum and its native token ETH.')
        await page.keyboard.press('Enter')
        
        print("Pilot: Message sent. Waiting for response...")
        # Wait 20 seconds for a substantial response
        await asyncio.sleep(20)
        
        # Take a screenshot to verify
        await page.screenshot(path="final-epic-11-verification.png")
        
        # Read the text of the messages
        messages = await page.locator(".aui-message").all_text_contents()
        print("Messages:", json.dumps(messages))

if __name__ == "__main__":
    asyncio.run(run())
