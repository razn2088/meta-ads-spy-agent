from dataclasses import asdict

from config.settings import GEMINI_API_KEY, LLM_PROVIDER, OPENAI_API_KEY
from modules.config_loader import AdDiff, Client
from utils.logger import log

SYSTEM_PROMPT = """You are a Senior Marketing Analyst. Write a SHORT competitive intelligence WhatsApp message for your client.

STRICT FORMAT RULES:
- Maximum 4 short paragraphs. No more.
- Paragraph 1: One-line summary of what changed this week (e.g. "ג'נסיס launched 3 new ads focused on leasing deals")
- Paragraph 2: Key takeaways — what is the competitor's strategy? What offers are they pushing? (2-3 bullet points max)
- Paragraph 3: Actionable suggestions — what should the client do in response? (2-3 bullet points max)
- Paragraph 4: Links to ads that require special attention. Use the format: https://www.facebook.com/ads/library/?id=LIBRARY_ID for each ad worth looking at. Add a short note next to each link explaining why it's important.

RULES:
- Write in Hebrew.
- Keep it concise. This is a WhatsApp message, not a document.
- NO technical details (hashes, internal IDs).
- NO long introductions or conclusions.
- If nothing changed, say so in one sentence and skip the rest.
- Tone: Direct, professional, actionable."""


def _build_user_prompt(client: Client, diffs: list[AdDiff]) -> str:
    sections = []
    for diff in diffs:
        section = f"מתחרה: {diff.competitor_name}\n"
        section += f"חדשות: {len(diff.new_ads)} | הוסרו: {len(diff.removed_ads)} | ללא שינוי: {len(diff.unchanged_ads)}\n\n"

        if diff.new_ads:
            section += "מודעות חדשות:\n"
            for ad in diff.new_ads:
                section += f"- [{ad.start_date}] {ad.ad_text[:150]}\n"
                section += f"  CTA: {ad.cta_text} | סוג: {ad.creative_type}\n"
                # Include ad_id which is derived from library_id for link generation
                section += f"  Library ID: {ad.ad_id}\n\n"

        if diff.removed_ads:
            section += "מודעות שהוסרו:\n"
            for ad in diff.removed_ads:
                section += f"- {ad.ad_text[:100]}\n"

        sections.append(section)

    return (
        f"לקוח: {client.client_name}\n\n"
        + "\n---\n".join(sections)
        + "\n\nכתוב דו\"ח קצר ב-4 פסקאות כמו שהוגדר."
    )


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=2000,
    )
    return response.choices[0].message.content


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=system_prompt,
    )
    response = model.generate_content(user_prompt)
    return response.text


def generate_report(client: Client, diffs: list[AdDiff]) -> str:
    """Generate a Hebrew competitive intelligence report using the configured LLM."""
    user_prompt = _build_user_prompt(client, diffs)

    log.info(f"Generating report for {client.client_name} via {LLM_PROVIDER}")

    if LLM_PROVIDER == "openai":
        report = _call_openai(SYSTEM_PROMPT, user_prompt)
    elif LLM_PROVIDER == "gemini":
        report = _call_gemini(SYSTEM_PROMPT, user_prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {LLM_PROVIDER}")

    header = f"📊 דו\"ח שבועי - {client.client_name}\n\n"
    return header + report
