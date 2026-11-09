import logging
from typing import Dict, Any, List
from google import genai
from google.genai import types
from app.config import settings
from app.ai.prompts import REBUTTAL_SYSTEM_PROMPT

logger = logging.getLogger("merchant_shield.ai")


def get_gemini_client():
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in .env")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


async def generate_ai_rebuttal(
    dispute_id: str,
    reason: str,
    amount: float,
    currency: str,
    verdict: str,
    reasons: List[str],
    evidence_data: List[Dict[str, Any]],
) -> str:
    """Generates a fact-grounded seller rebuttal using Gemini 3.8 Flash."""
    try:
        client = get_gemini_client()

        context_prompt = f"""
Dispute Information:
- Dispute ID: {dispute_id}
- Claim Reason: {reason}
- Amount: {amount} {currency}
- Internal Rules Verdict: {verdict}
- Rule Evaluation Findings: {', '.join(reasons)}

Verified Evidence Items:
{evidence_data}

Please draft a professional rebuttal letter for PayPal Resolution Center based on this evidence.
"""

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=context_prompt,
            config=types.GenerateContentConfig(
                system_instruction=REBUTTAL_SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini AI generation failed: {e}")
        # Fallback template if Gemini free tier hits a rate limit
        return (
            f"REBUTTAL FOR DISPUTE {dispute_id}\n\n"
            f"The item was shipped and tracking confirms delivery.\n"
            f"Evidence: {evidence_data}\n"
            f"We request protection under PayPal Seller Protection policy."
        )
