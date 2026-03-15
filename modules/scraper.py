import hashlib
import random
from datetime import datetime
from pathlib import Path

from playwright.async_api import BrowserContext, Page

from config.settings import MAX_SCROLLS, SCROLL_PAUSE
from modules.config_loader import AdRecord, Competitor
from utils.logger import log
from utils.screenshots import save_error_screenshot


class ScrapeError(Exception):
    pass


JS_EXTRACT_ADS = """() => {
    const ads = [];
    const body = document.body.innerText;
    const sections = body.split(/Library ID:/);

    for (let i = 1; i < sections.length; i++) {
        const section = sections[i];
        const libraryId = (section.split('\\n')[0] || '').trim();

        const dateMatch = section.match(/Started running on\\s+(.+)/);
        const startDate = dateMatch ? dateMatch[1].split('\\n')[0].trim() : 'unknown';

        const platforms = [];
        if (section.includes('Facebook')) platforms.push('Facebook');
        if (section.includes('Instagram')) platforms.push('Instagram');
        if (section.includes('Messenger')) platforms.push('Messenger');
        if (section.includes('Audience Network')) platforms.push('Audience Network');

        const sponsoredIdx = section.indexOf('Sponsored');
        let adText = '';
        if (sponsoredIdx > -1) {
            adText = section.substring(sponsoredIdx + 9, sponsoredIdx + 509)
                .split('\\n').slice(0, 10).join(' ').trim();
        }

        let creativeType = 'image';
        if (section.includes('video') || section.includes('Video')) creativeType = 'video';
        if (section.includes('multiple versions') || section.includes('carousel')) creativeType = 'carousel';

        const ctaList = ['Shop Now', 'Sign Up', 'Learn More', 'Order Now',
                         'Book Now', 'Download', 'Contact Us', 'Apply Now',
                         'Get Offer', 'Subscribe', 'Watch More', 'Send Message'];
        let cta = '';
        for (const c of ctaList) {
            if (section.includes(c)) { cta = c; break; }
        }

        if (libraryId) {
            ads.push({
                library_id: libraryId,
                start_date: startDate,
                platforms: platforms,
                ad_text: adText,
                creative_type: creativeType,
                cta: cta,
            });
        }
    }
    return ads;
}"""


def _generate_ad_id(competitor_name: str, library_id: str) -> str:
    raw = f"{competitor_name}|{library_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def _scroll_to_load_all(page: Page) -> None:
    for i in range(MAX_SCROLLS):
        prev_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollBy(0, 800)")
        await page.wait_for_timeout(int(SCROLL_PAUSE * 1000))
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == prev_height:
            log.info(f"Scrolling complete after {i + 1} scrolls")
            break


async def _handle_popups(page: Page) -> None:
    """Dismiss common popups on Meta Ads Library."""
    try:
        for btn_text in ["Allow all cookies", "Allow All Cookies",
                         "Accept All", "Close", "Decline optional cookies"]:
            btn = page.get_by_text(btn_text, exact=False)
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_timeout(1000)
                log.info(f"Dismissed popup: {btn_text}")
                break
    except Exception:
        pass


async def scrape_competitor(competitor: Competitor, context: BrowserContext) -> list[AdRecord]:
    """Scrape all visible ads for a competitor from Meta Ads Library."""
    log.info(f"Scraping ads for: {competitor.name} ({competitor.meta_ads_url})")

    page = await context.new_page()
    try:
        await page.goto(competitor.meta_ads_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(8000)

        await _handle_popups(page)

        # Check if the page loaded properly
        page_text = await page.evaluate("document.body.innerText.substring(0, 2000)")

        if not page_text or len(page_text.strip()) < 50:
            screenshot_path = await save_error_screenshot(page, f"blank_{competitor.name}")
            raise ScrapeError(
                f"Page did not render for {competitor.name}. "
                f"Meta may be blocking the request. Screenshot: {screenshot_path}"
            )

        # Check for "no ads" message
        no_ads_indicators = [
            "No ads match", "no results",
            "isn't running ads", "אין מודעות",
        ]
        for indicator in no_ads_indicators:
            if indicator.lower() in page_text.lower():
                log.info(f"No active ads found for {competitor.name}")
                return []

        # Scroll to load all ads
        await _scroll_to_load_all(page)

        # Extract ads using text-based parsing
        now = datetime.now().isoformat()
        raw_ads = await page.evaluate(JS_EXTRACT_ADS)

        records = []
        for ad in raw_ads:
            ad_id = _generate_ad_id(competitor.name, ad["library_id"])
            records.append(AdRecord(
                ad_id=ad_id,
                competitor_name=competitor.name,
                ad_text=ad["ad_text"],
                start_date=ad["start_date"],
                platforms=ad["platforms"] if ad["platforms"] else ["Facebook"],
                creative_type=ad["creative_type"],
                cta_text=ad["cta"],
                scraped_at=now,
            ))

        log.info(f"Found {len(records)} ads for {competitor.name}")

        if not records:
            screenshot_path = await save_error_screenshot(page, f"empty_{competitor.name}")
            log.warning(
                f"No ads extracted for {competitor.name}. "
                f"Screenshot: {screenshot_path}"
            )

        return records

    except ScrapeError:
        raise
    except Exception as e:
        try:
            await save_error_screenshot(page, f"crash_{competitor.name}")
        except Exception:
            pass
        raise ScrapeError(f"Scraping failed for {competitor.name}: {e}") from e
    finally:
        await page.close()
