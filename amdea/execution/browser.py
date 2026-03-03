from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from pathlib import Path
import urllib.parse
from amdea import config

class ElementNotFoundError(Exception): pass

_playwright = None
_browser: Browser = None
_context: BrowserContext = None
_page: Page = None

async def _init_browser():
    """Initializes the browser, prioritizing the system Chrome profile for access to logged-in accounts."""
    global _playwright, _browser, _context, _page
    if _page is None:
        from amdea.logging_config import get_logger
        logger = get_logger("Browser")
        try:
            logger.info("Starting Playwright/Chromium...")
            _playwright = await async_playwright().start()
            
            # Default AMDEA profile as fallback
            amdea_data_dir = Path.home() / ".amdea" / "browser_data"
            
            # System Chrome profile detection (Windows)
            import platform
            import os
            
            launch_args = {
                "channel": "chrome", # Use the real Google Chrome instead of bundled Chromium
                "headless": False,
                "viewport": {'width': 1280, 'height': 720},
                "accept_downloads": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "timeout": 30000
            }

            if platform.system() == "Windows":
                chrome_data = Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))
                if chrome_data.exists():
                    try:
                        logger.info(f"Attempting to attach to your real Google Chrome profile...")
                        _context = await _playwright.chromium.launch_persistent_context(
                            user_data_dir=str(chrome_data),
                            **launch_args
                        )
                        logger.info("Successfully loaded your Google Chrome profile.")
                    except Exception as e:
                        logger.warning(f"Could not use main profile (likely because Chrome is already open). Falling back to isolated AMDEA profile.")
                        # If the main profile is locked, we MUST use the fallback dir
                        _context = await _playwright.chromium.launch_persistent_context(
                            user_data_dir=str(amdea_data_dir),
                            **launch_args
                        )
                else:
                    _context = await _playwright.chromium.launch_persistent_context(
                        user_data_dir=str(amdea_data_dir),
                        **launch_args
                    )
            else:
                _context = await _playwright.chromium.launch_persistent_context(
                    user_data_dir=str(amdea_data_dir),
                    **launch_args
                )

            _page = _context.pages[0] if _context.pages else await _context.new_page()
            logger.info("Browser session initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

async def get_page() -> Page:
    """Ensures the browser is open and returns the current page."""
    await _init_browser()
    return _page

async def navigate(url: str) -> None:
    """Navigates the browser to a specific URL."""
    page = await get_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=15000)

async def browser_search(query: str, engine: str = "google") -> None:
    """Performs a web search using the specified engine."""
    engines = {
        "google": "https://www.google.com/search?q={}",
        "bing": "https://www.bing.com/search?q={}",
        "duckduckgo": "https://duckduckgo.com/?q={}"
    }
    url_tpl = engines.get(engine, engines["google"])
    url = url_tpl.format(urllib.parse.quote_plus(query))
    await navigate(url)

async def click_element(selector: str, selector_type: str = "css") -> None:
    """Clicks an element on the page."""
    page = await get_page()
    if selector_type == "text":
        locator = page.get_by_text(selector).first
    elif selector_type == "aria":
        locator = page.get_by_role("button", name=selector, exact=False).first
    else:
        locator = page.locator(selector).first
        
    await locator.wait_for(state="visible", timeout=10000)
    await locator.click()

async def fill_form(selector: str, text: str, selector_type: str = "css", enter: bool = True) -> None:
    """Fills an input field and optionally presses Enter."""
    page = await get_page()
    if selector_type == "text":
        locator = page.get_by_text(selector).first
    elif selector_type == "placeholder":
        locator = page.get_by_placeholder(selector).first
    else:
        locator = page.locator(selector).first
        
    await locator.wait_for(state="visible", timeout=10000)
    await locator.fill(text)
    if enter:
        await page.keyboard.press("Enter")

async def read_element(selector: str, selector_type: str = "css") -> str:
    """Reads and returns the text content of an element."""
    page = await get_page()
    if selector_type == "text":
        locator = page.get_by_text(selector).first
    else:
        locator = page.locator(selector).first
        
    if await locator.count() == 0:
        raise ElementNotFoundError(f"Element not found: {selector}")
    return await locator.inner_text()

async def download_from_page(selector: str, destination: str) -> str:
    """Clicks an element and saves the resulting download."""
    page = await get_page()
    async with page.expect_download() as download_info:
        await page.click(selector)
        
    download = await download_info.value
    dest_path = Path(destination).expanduser()
    dest_path.mkdir(parents=True, exist_ok=True)
    
    save_path = dest_path / download.suggested_filename
    await download.save_as(save_path)
    return str(save_path)

async def get_element_attribute(selector: str, attribute: str) -> str | None:
    """Returns the value of a specific attribute for an element."""
    page = await get_page()
    locator = page.locator(selector).first
    if await locator.count() == 0:
        return None
    return await locator.get_attribute(attribute)

async def get_current_url() -> str | None:
    """Returns the URL of the active browser page."""
    if _page:
        return _page.url
    return None

async def close_browser() -> None:
    """Closes the browser and cleans up resources."""
    global _playwright, _browser, _context, _page
    if _context:
        await _context.close()
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()
    _page = _context = _browser = _playwright = None
