import platform

from playwright.async_api import Page

from utils.logger import log


def _cmd_key() -> str:
    """Return the correct modifier key for the current OS."""
    return "Meta" if platform.system() == "Darwin" else "Control"


async def _wait_for_whatsapp_ready(page: Page) -> bool:
    """Wait for WhatsApp Web to fully load. Returns False if QR code screen is shown."""
    await page.wait_for_timeout(5000)

    # Check if we're on the QR code / login screen
    page_text = await page.inner_text("body")
    qr_indicators = [
        "Scan the QR code", "סרוק את קוד ה-QR",
        "Use WhatsApp on your phone", "Link a device",
    ]
    for indicator in qr_indicators:
        if indicator.lower() in page_text.lower():
            return False

    # Wait a bit more for chats to render
    await page.wait_for_timeout(5000)
    return True


async def _search_and_open_group(page: Page, group_name: str) -> bool:
    """Search for a WhatsApp group by name and open it."""
    modifier = _cmd_key()

    # Use keyboard shortcut to focus search
    # Ctrl/Cmd + F doesn't work reliably; clicking the search area is better
    # Try the universal search shortcut first
    await page.keyboard.press(f"{modifier}+k")
    await page.wait_for_timeout(1000)

    # Type the group name
    await page.keyboard.type(group_name, delay=50)
    await page.wait_for_timeout(2000)

    # Press down arrow and enter to select first result
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(500)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(2000)

    # Verify we opened the correct group by checking the header
    try:
        header = await page.locator("header span[title]").first.inner_text(timeout=5000)
        if group_name.lower() in header.lower():
            log.info(f"Opened WhatsApp group: {group_name}")
            return True
        else:
            log.warning(f"Expected group '{group_name}', but header shows '{header}'")
            return False
    except Exception:
        log.warning(f"Could not verify group header for '{group_name}'")
        # Still try to send — the group might be open but header selector changed
        return True


async def _type_and_send_message(page: Page, message: str) -> None:
    """Type a message in the chat input and send it."""
    # Click the message input area (bottom of chat)
    # Use the contenteditable div that WhatsApp uses for message input
    input_selector = 'div[contenteditable="true"][data-tab="10"]'
    fallback_selector = 'div[contenteditable="true"]'

    try:
        input_box = page.locator(input_selector)
        if await input_box.count() == 0:
            input_box = page.locator(fallback_selector).last
        await input_box.click()
    except Exception:
        # Fallback: Tab to the input area
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(500)

    await page.wait_for_timeout(500)

    # Type the message line by line to handle multiline properly
    lines = message.split("\n")
    for i, line in enumerate(lines):
        if line:
            await page.keyboard.type(line, delay=10)
        if i < len(lines) - 1:
            # Shift+Enter for newline within message
            await page.keyboard.press("Shift+Enter")

    await page.wait_for_timeout(500)

    # Send with Enter
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(2000)
    log.info("Message sent successfully")


async def send_to_whatsapp(page: Page, group_name: str, message: str) -> bool:
    """Send a message to a specific WhatsApp group.

    Args:
        page: An already-loaded WhatsApp Web page.
        group_name: The exact name of the WhatsApp group to send to.
        message: The text message to send.

    Returns:
        True if message was sent, False if group was not found.
    """
    log.info(f"Sending message to WhatsApp group: {group_name}")

    found = await _search_and_open_group(page, group_name)
    if not found:
        log.error(f"WhatsApp group not found: {group_name}")
        return False

    await _type_and_send_message(page, message)
    return True


async def check_whatsapp_session(page: Page) -> bool:
    """Check if WhatsApp Web session is active.

    Returns True if logged in, False if QR code screen is showing.
    """
    return await _wait_for_whatsapp_ready(page)
