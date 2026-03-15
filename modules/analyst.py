from dataclasses import asdict

from config.settings import GEMINI_API_KEY, LLM_PROVIDER, OPENAI_API_KEY
from modules.config_loader import AdDiff, Client
from utils.logger import log

SYSTEM_PROMPT = """You are a Senior Marketing Analyst specializing in competitive intelligence.
You are looking at data from competitors' Meta ad accounts.
Your goal is to give a C-Level summary to your client.

Rules:
- DO NOT list technical details (ID numbers, hashes).
- DO focus on Strategy, Offers, Visual/Creative changes, and Targeting signals.
- If there are new ads, analyze what messaging and offers the competitor is pushing.
- If ads were removed, note what the competitor stopped promoting.
- If nothing changed, confirm that no changes were detected and the competitor's strategy appears stable.
- Write in Hebrew.
- Tone: Professional, Insightful, Actionable.
- Use bullet points for clarity.
- Structure the report with a section per competitor."""


def _build_user_prompt(client: Client, diffs: list[AdDiff]) -> str:
    sections = []
    for diff in diffs:
        section = f"## מתחרה: {diff.competitor_name}\n"
        section += f"מודעות חדשות: {len(diff.new_ads)}\n"
        section += f"מודעות שהוסרו: {len(diff.removed_ads)}\n"
        section += f"מודעות ללא שינוי: {len(diff.unchanged_ads)}\n\n"

        if diff.new_ads:
            section += "### מודעות חדשות:\n"
            for ad in diff.new_ads:
                section += f"- טקסט: {ad.ad_text[:200]}\n"
                section += f"  תאריך התחלה: {ad.start_date}\n"
                section += f"  פלטפורמות: {', '.join(ad.platforms)}\n"
                section += f"  סוג קריאייטיב: {ad.creative_type}\n"
                section += f"  CTA: {ad.cta_text}\n\n"

        if diff.removed_ads:
            section += "### מודעות שהוסרו:\n"
            for ad in diff.removed_ads:
                section += f"- טקסט: {ad.ad_text[:200]}\n"
                section += f"  סוג קריאייטיב: {ad.creative_type}\n\n"

        sections.append(section)

    full_prompt = (
        f"לקוח: {client.client_name}\n\n"
        f"להלן נתוני המתחרים מהסריקה השבועית:\n\n"
        + "\n---\n".join(sections)
        + "\n\nאנא נתח את הנתונים וכתוב דו\"ח תובנות תחרותי."
    )
    return full_prompt


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

    # Add header
    header = f"📊 דו\"ח מודיעין תחרותי שבועי - {client.client_name}\n{'=' * 40}\n\n"
    return header + report
