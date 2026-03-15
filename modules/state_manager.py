import json
import sqlite3
from datetime import datetime
from pathlib import Path

from config.settings import HISTORY_DIR
from modules.config_loader import AdDiff, AdRecord
from utils.logger import log


def _get_db_path(client_id: str) -> Path:
    client_dir = HISTORY_DIR / client_id
    client_dir.mkdir(parents=True, exist_ok=True)
    return client_dir / "ads.db"


def _get_connection(client_id: str) -> sqlite3.Connection:
    db_path = _get_db_path(client_id)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            ad_id TEXT,
            competitor_name TEXT,
            ad_text TEXT,
            start_date TEXT,
            platforms TEXT,
            creative_type TEXT,
            cta_text TEXT,
            first_seen TEXT,
            last_seen TEXT,
            is_active INTEGER DEFAULT 1,
            PRIMARY KEY (ad_id, competitor_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrape_runs (
            run_id TEXT PRIMARY KEY,
            run_date TEXT,
            competitor_name TEXT,
            ads_found INTEGER,
            status TEXT
        )
    """)
    conn.commit()
    return conn


def get_previous_ads(client_id: str, competitor_name: str) -> list[AdRecord]:
    conn = _get_connection(client_id)
    cursor = conn.execute(
        "SELECT ad_id, competitor_name, ad_text, start_date, platforms, creative_type, cta_text, last_seen "
        "FROM ads WHERE competitor_name = ? AND is_active = 1",
        (competitor_name,),
    )
    ads = []
    for row in cursor.fetchall():
        ads.append(AdRecord(
            ad_id=row[0],
            competitor_name=row[1],
            ad_text=row[2],
            start_date=row[3],
            platforms=json.loads(row[4]),
            creative_type=row[5],
            cta_text=row[6],
            scraped_at=row[7],
        ))
    conn.close()
    return ads


def save_ads(client_id: str, competitor_name: str, ads: list[AdRecord]) -> None:
    conn = _get_connection(client_id)
    now = datetime.now().isoformat()

    # Mark all current active ads for this competitor as inactive
    conn.execute(
        "UPDATE ads SET is_active = 0 WHERE competitor_name = ? AND is_active = 1",
        (competitor_name,),
    )

    for ad in ads:
        # Upsert: if ad existed before, reactivate it; if new, insert
        existing = conn.execute(
            "SELECT ad_id FROM ads WHERE ad_id = ? AND competitor_name = ?",
            (ad.ad_id, ad.competitor_name),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE ads SET is_active = 1, last_seen = ? WHERE ad_id = ? AND competitor_name = ?",
                (now, ad.ad_id, ad.competitor_name),
            )
        else:
            conn.execute(
                "INSERT INTO ads (ad_id, competitor_name, ad_text, start_date, platforms, creative_type, cta_text, first_seen, last_seen, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    ad.ad_id,
                    ad.competitor_name,
                    ad.ad_text,
                    ad.start_date,
                    json.dumps(ad.platforms),
                    ad.creative_type,
                    ad.cta_text,
                    now,
                    now,
                ),
            )

    # Log the scrape run
    run_id = f"{competitor_name}_{now}"
    conn.execute(
        "INSERT INTO scrape_runs (run_id, run_date, competitor_name, ads_found, status) VALUES (?, ?, ?, ?, ?)",
        (run_id, now, competitor_name, len(ads), "success"),
    )

    conn.commit()
    conn.close()
    log.info(f"Saved {len(ads)} ads for {competitor_name} (client: {client_id})")


def compute_diff(client_id: str, competitor_name: str, new_ads: list[AdRecord]) -> AdDiff:
    previous_ads = get_previous_ads(client_id, competitor_name)
    prev_ids = {ad.ad_id for ad in previous_ads}
    new_ids = {ad.ad_id for ad in new_ads}

    added = [ad for ad in new_ads if ad.ad_id not in prev_ids]
    removed = [ad for ad in previous_ads if ad.ad_id not in new_ids]
    unchanged = [ad for ad in new_ads if ad.ad_id in prev_ids]

    log.info(
        f"Diff for {competitor_name}: {len(added)} new, {len(removed)} removed, {len(unchanged)} unchanged"
    )

    return AdDiff(
        competitor_name=competitor_name,
        new_ads=added,
        removed_ads=removed,
        unchanged_ads=unchanged,
    )
