import asyncio
import sys
from pathlib import Path

# Ensure project root is in path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.async_api import async_playwright

from config.settings import (
    ADMIN_WHATSAPP_GROUP,
    CLIENTS_CONFIG_PATH,
    DATA_DIR,
    PROXY_URL,
    WHATSAPP_PROFILE_DIR,
)
from modules.analyst import generate_report
from modules.config_loader import load_clients
from modules.scraper import ScrapeError, scrape_competitor
from modules.state_manager import compute_diff, save_ads
from modules.whatsapp_sender import check_whatsapp_session, send_to_whatsapp
from utils.delays import random_delay
from utils.logger import log


async def run():
    clients = load_clients(CLIENTS_CONFIG_PATH)
    if not clients:
        log.error("No clients found in config. Exiting.")
        return

    # ── Phase 1: Scrape all competitors ──
    log.info("=" * 50)
    log.info("PHASE 1: Scraping Meta Ads Library")
    log.info("=" * 50)

    all_diffs = {}  # client_id -> list[AdDiff] or None (on error)

    scraper_profile = str((DATA_DIR / "browser_profile").resolve())
    launch_kwargs = {
        "headless": False,
        "viewport": {"width": 1440, "height": 900},
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    if PROXY_URL:
        launch_kwargs["proxy"] = {"server": PROXY_URL}

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=scraper_profile, **launch_kwargs
        )

        for client in clients:
            log.info(f"\nProcessing client: {client.client_name}")
            client_diffs = []
            scrape_failed = False

            for competitor in client.competitors:
                try:
                    ads = await scrape_competitor(competitor, context)
                    diff = compute_diff(client.client_id, competitor.name, ads)
                    save_ads(client.client_id, competitor.name, ads)
                    client_diffs.append(diff)
                except ScrapeError as e:
                    log.error(f"Scrape error: {e}")
                    scrape_failed = True
                    break

                # Anti-ban delay between competitors
                if competitor != client.competitors[-1]:
                    log.info("Waiting between competitors...")
                    await random_delay()

            all_diffs[client.client_id] = None if scrape_failed else client_diffs

            # Delay between clients too
            if client != clients[-1]:
                await random_delay(5, 15)

        await context.close()

    # ── Phase 2: Generate LLM reports ──
    log.info("\n" + "=" * 50)
    log.info("PHASE 2: Generating reports via LLM")
    log.info("=" * 50)

    reports = {}  # client_id -> (target, message)
    for client in clients:
        diffs = all_diffs.get(client.client_id)
        if diffs is None:
            error_msg = f"⚠️ שגיאה בסריקת המתחרים עבור {client.client_name}. יש לבדוק את הלוגים."
            reports[client.client_id] = ("admin", error_msg)
            log.warning(f"Skipping report for {client.client_name} due to scrape error")
            continue

        try:
            report = generate_report(client, diffs)
            reports[client.client_id] = ("client", report)
        except Exception as e:
            log.error(f"Report generation failed for {client.client_name}: {e}")
            error_msg = f"⚠️ שגיאה ביצירת דו\"ח עבור {client.client_name}: {e}"
            reports[client.client_id] = ("admin", error_msg)

    # ── Phase 3: Send via WhatsApp ──
    log.info("\n" + "=" * 50)
    log.info("PHASE 3: Sending reports via WhatsApp")
    log.info("=" * 50)

    profile_dir = str(Path(WHATSAPP_PROFILE_DIR).resolve())

    async with async_playwright() as p:
        wa_context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        wa_page = wa_context.pages[0] if wa_context.pages else await wa_context.new_page()
        await wa_page.goto("https://web.whatsapp.com")

        # Check if session is active
        session_ok = await check_whatsapp_session(wa_page)
        if not session_ok:
            log.warning(
                "WhatsApp Web shows QR code screen. "
                "Please scan the QR code with your phone to log in."
            )
            log.info("Waiting 60 seconds for QR code scan...")
            await wa_page.wait_for_timeout(60000)

            session_ok = await check_whatsapp_session(wa_page)
            if not session_ok:
                log.error("WhatsApp login failed. Cannot send reports. Exiting.")
                await wa_context.close()
                return

        log.info("WhatsApp Web session active")

        for client in clients:
            target, message = reports.get(client.client_id, ("admin", "Unknown error"))

            if target == "client":
                group = client.whatsapp_group_name
            else:
                group = ADMIN_WHATSAPP_GROUP

            success = await send_to_whatsapp(wa_page, group, message)
            if not success:
                log.error(f"Failed to send to group: {group}")
                # Try sending error to admin instead
                if target == "client":
                    admin_msg = f"⚠️ לא הצלחתי לשלוח דו\"ח לקבוצה '{group}' עבור {client.client_name}"
                    await send_to_whatsapp(wa_page, ADMIN_WHATSAPP_GROUP, admin_msg)

            await random_delay(5, 10)

        await wa_context.close()

    log.info("\n" + "=" * 50)
    log.info("All done! Agent run complete.")
    log.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(run())
