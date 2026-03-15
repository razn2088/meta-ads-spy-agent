import json
from dataclasses import dataclass, field
from pathlib import Path

from utils.logger import log


@dataclass
class Competitor:
    name: str
    meta_ads_url: str


@dataclass
class Client:
    client_id: str
    client_name: str
    whatsapp_group_name: str
    competitors: list[Competitor] = field(default_factory=list)


@dataclass
class AdRecord:
    ad_id: str
    competitor_name: str
    ad_text: str
    start_date: str
    platforms: list[str]
    creative_type: str
    cta_text: str
    scraped_at: str


@dataclass
class AdDiff:
    competitor_name: str
    new_ads: list[AdRecord]
    removed_ads: list[AdRecord]
    unchanged_ads: list[AdRecord]


def load_clients(config_path: Path) -> list[Client]:
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    clients = []
    for entry in data:
        competitors = [
            Competitor(name=c["name"], meta_ads_url=c["url"])
            for c in entry.get("competitors", [])
        ]
        client = Client(
            client_id=entry["client_id"],
            client_name=entry["client_name"],
            whatsapp_group_name=entry["whatsapp_group_name"],
            competitors=competitors,
        )
        clients.append(client)

    log.info(f"Loaded {len(clients)} clients from config")
    return clients
