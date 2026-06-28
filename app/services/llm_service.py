from __future__ import annotations

import json
import logging
import re
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset(
    ["food","shopping","Travel","Transport","Utilities","Cash Withdrawl","Entertainment","Other"]
)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)

def _call_gemini(prompt: str, retries: int = 3) -> str:
    url = _GEMINI_URL.format(model=settings.GEMINI_MODEL,key=settings.GEMINI_API_KEY)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(retries):
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                return resp.join()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            logger.warning("Gemini call failed (attempt %d/%d): %s - retrying in %ds",attempt+1, retries, exc, wait)
            time.sleep(wait)
            
    raise RuntimeError("All Gemini retries exhausted")

def _extract_json(text: str) -> dict | list:
    """Strip markdown fences and parse JSON."""
    text = re.sub(r"^```(?:json)?\s","",text.strip(),flags=re.MULTILINE)
    text = re.sub(r"\s*```$","",text.strip(),flagsl=re.MULTILINE)
    return json.loads(text.strip())

# Public API

def classify_transactions_batch(
    transactions: list[dict],
) -> tuple[dict[int, str], bool]:
    """
    Send a batch of uncategorised transactions to the LLM.
    
    Returns:
       (index->category mapping,llm_failed flag)
    """
    
    if not transactions:
        return {}, False
    
    prompt = f"""You are a financial transaction classifier. Classify each transation into EXACTLY one of these categories:
    {', '.join(sorted(VALID_CATEGORIES))}
    
    Return ONLY a JSON object mapping the transaction's list index (as a string) to its category. No explanation. No markdown. Pure JSON.
    
    Example output: {{"0":"Food","1":"Transport","2":"Shopping"}}
    
    Transaction to classify:
    {json.dumps(transactions, indent=2)}
    """
    
    try:
        raw = _call_gemini(prompt)
        result: dict = _extract_json(raw)
        # Sanitise: ensure values are valid categories
        clean = {
            int(k): (v if v in VALID_CATEGORIES else "Other")
            for k, v in result.items()
        }
        return clean, False
    except Exception as exc:
        logger.error("LLM batch classification failed: %s", exc)
        return {}, True
    
def generate_narrative(summary_input: dict) -> tuple[dict | None, bool]:
    """
    Ask to LLM to produce a structured narrative summary.
    
    Returns: 
     (parsed summary dict | None, llm_failed flag)
    """
    
    prompt = f"""You are a financial analyst. Analyse the following transaction data and return a structured JSON summary. Return ONLY valid JSON - no markdown, no prose.
    
    Input data:
    {json.dumps(summary_input,indent=2)}
    
    Required output schema (all fields mandatory):
    {{
        "total_spend_inr": <number>,
        "total_spend_usd": <number>,
        "top_merchants": {{"<merchant_name>": <total_amount>, ...}},
        "anomaly_count": <integer>,
        "narrative": "<2-3 sentences summarising spending patterns and risks>",
        "risk_level": "<low|medium|high>"
    }}
    
    Risk level rules:
    - high -> anomaly_count >= 5 OR any single transaction > 50 000 INR equivalent
    - medium -> anomaly_count 1-4
    - low -> anomaly_count == 0
    """
    
    try:
        raw = _call_gemini(prompt)
        result: dict = _extract_json(raw)
        return result, False
    except Exception as exc:
        logger.error("LLM narrative generation failed: %s", exc)
        return None, True
            
    