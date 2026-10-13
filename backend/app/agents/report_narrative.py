import logging
from typing import Dict, Any
from app.agents.llm_client import complete

logger = logging.getLogger(__name__)

FORBIDDEN_WORDS = [
    "lifestyle", "opulent", "humble", "poor", "wealthy", "rich", "luxurious",
    "extravagant", "impressive", "poverty", "lavish", "shabby"
]


def _contains_forbidden_language(text: str) -> bool:
    t_lower = text.lower()
    for word in FORBIDDEN_WORDS:
        if f" {word} " in f" {t_lower} " or f" {word}." in f" {t_lower} ":
            return True
    return False


def generate_narrative_section(section_name: str, source_data: Dict[str, Any]) -> str:
    """
    Generates a factual, underwriter-grade narrative section (Section 11):
    - source_data contains ONLY fields relevant to this section (never full case dump)
    - Factual only: every claim traceable to source_data, no evaluative/lifestyle language
    - Validates against subjective language: retries once on failure, flags for manual review on second failure
    """
    prompt = f"""
    You are an expert credit underwriter preparing a Credit Assessment Memorandum (CAM) narrative.
    Section to generate: {section_name.upper()}
    
    Source Data (Verified ground facts only):
    {source_data}

    Strict Underwriting Guidelines:
    1. Only use facts explicitly present in the source data.
    2. Maintain a professional, neutral, factual tone.
    3. Do NOT use evaluative or lifestyle language (e.g. do NOT use: humble, rich, poor, lavish, luxurious, modest, opulent).
    4. Keep the summary concise (2-4 paragraphs).

    Generate the narrative text for section: {section_name}
    """

    # First attempt
    output = complete(prompt, response_format="text")
    if isinstance(output, dict):
        output = str(output.get("text", output))

    if not _contains_forbidden_language(output):
        return output.strip()

    # Retry once on subjective/lifestyle language detection
    logger.warning(f"Forbidden evaluative language detected in narrative for {section_name}. Retrying once...")
    strict_prompt = (
        f"{prompt}\n\n"
        "CRITICAL ERROR: Your previous response contained forbidden subjective/lifestyle adjectives. "
        "Remove all evaluative adjectives. State ONLY cold, verified financial and operational facts."
    )
    retry_output = complete(strict_prompt, response_format="text")
    if isinstance(retry_output, dict):
        retry_output = str(retry_output.get("text", retry_output))

    if not _contains_forbidden_language(retry_output):
        return retry_output.strip()

    # Flag for manual review if second attempt fails
    logger.error(f"Narrative generation for {section_name} failed strict tone validation after retry. Flagging for manual review.")
    return f"[FLAGGED FOR MANUAL UNDERWRITER REVIEW: Subjective phrasing detected]\n\n{retry_output.strip()}"
