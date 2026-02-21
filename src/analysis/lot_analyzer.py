"""AI-powered lot analysis using Claude.

Analyzes auction lots to extract:
- Structured specifications (brand, model, quantity, condition)
- Market value estimates
- Opportunity scores
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.listing import LotItem

logger = logging.getLogger(__name__)


ANALYSIS_PROMPT = """Analyze this auction lot and provide a JSON response with structured data.

## Lot Information
Title: {title}
Description: {description}
Base Price: {price} {currency}
{additional_context}

## Task
Extract structured information and estimate market value. Return ONLY valid JSON.

## Required JSON Format
{{
  "specs": {{
    "brand": "brand name or null",
    "model": "model number/name or null",
    "quantity": number or 1 if single item,
    "condition": "new|like_new|good|fair|poor|unknown",
    "key_features": ["feature1", "feature2"]
  }},
  "market_value_usd": estimated retail/market value in USD,
  "opportunity_score": 1-10 scale (10 = exceptional deal),
  "reasoning": "one sentence explaining the opportunity score"
}}

## Scoring Guide
- 9-10: Exceptional (70%+ below market, high-demand items)
- 7-8: Very Good (50-70% below market)
- 5-6: Good (30-50% below market)
- 3-4: Fair (10-30% below market)
- 1-2: Low (near or above market value)

## Important
- For Argentine auctions, "base" price is starting bid, not final price
- Industrial equipment often sells 40-60% below new price at auction
- Consider bulk/quantity discounts in market value
- Return ONLY the JSON object, no markdown or explanation
"""


async def analyze_lot(
    lot: "LotItem",
    auction_title: str = "",
    model: str = "claude-3-haiku-20240307"
) -> Optional[dict]:
    """Analyze a lot using Claude AI.

    Args:
        lot: The LotItem to analyze
        auction_title: Title of parent auction for context
        model: Claude model to use (default: Haiku for cost efficiency)

    Returns:
        Dict with specs, market_value_usd, opportunity_score, reasoning
        or None if analysis fails
    """
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed. Run: pip install anthropic")
        return None

    # Build context
    additional_context = ""
    if auction_title:
        additional_context += f"Auction Title: {auction_title}\n"
    if lot.images:
        additional_context += f"Has images: Yes ({len(lot.images)} images)\n"

    prompt = ANALYSIS_PROMPT.format(
        title=lot.title,
        description=lot.description or "(no description)",
        price=lot.base_price,
        currency=lot.currency,
        additional_context=additional_context,
    )

    try:
        client = anthropic.Anthropic()

        response = client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Extract text response
        text = response.content[0].text.strip()

        # Parse JSON (handle potential markdown wrapping)
        if text.startswith("```"):
            # Remove markdown code blocks
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)

        # Validate required fields
        if not all(k in result for k in ["specs", "market_value_usd", "opportunity_score"]):
            logger.warning(f"Incomplete analysis result for lot {lot.lot_id}")
            return None

        # Ensure numeric types
        result["market_value_usd"] = float(result["market_value_usd"])
        result["opportunity_score"] = int(result["opportunity_score"])

        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI response for lot {lot.lot_id}: {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error for lot {lot.lot_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error analyzing lot {lot.lot_id}: {e}")
        return None


def apply_analysis_to_lot(lot: "LotItem", analysis: dict) -> "LotItem":
    """Apply AI analysis results to a lot.

    Args:
        lot: The lot to update
        analysis: Analysis dict from analyze_lot()

    Returns:
        Updated lot with AI fields populated
    """
    lot.ai_specs = analysis.get("specs")
    lot.ai_market_value_usd = analysis.get("market_value_usd")
    lot.ai_opportunity_score = analysis.get("opportunity_score")
    lot.ai_analyzed_at = datetime.now(timezone.utc)

    return lot


def calculate_discount_percent(lot: "LotItem") -> Optional[float]:
    """Calculate discount percentage from market value.

    Args:
        lot: Lot with AI analysis

    Returns:
        Discount percentage or None if cannot calculate
    """
    if not lot.ai_market_value_usd or not lot.base_price_usd:
        return None

    if lot.ai_market_value_usd <= 0:
        return None

    discount = (1 - (lot.base_price_usd / lot.ai_market_value_usd)) * 100
    return round(discount, 1)


async def analyze_lots_batch(
    lots: list["LotItem"],
    auction_title: str = "",
    max_concurrent: int = 5,
    model: str = "claude-3-haiku-20240307"
) -> list["LotItem"]:
    """Analyze multiple lots with rate limiting.

    Args:
        lots: List of lots to analyze
        auction_title: Parent auction title for context
        max_concurrent: Max concurrent API calls
        model: Claude model to use

    Returns:
        List of lots with AI fields populated
    """
    import asyncio

    semaphore = asyncio.Semaphore(max_concurrent)
    analyzed = []

    async def analyze_with_limit(lot: "LotItem") -> "LotItem":
        async with semaphore:
            if lot.ai_analyzed_at:
                # Already analyzed
                return lot

            analysis = await analyze_lot(lot, auction_title, model)
            if analysis:
                return apply_analysis_to_lot(lot, analysis)
            return lot

    tasks = [analyze_with_limit(lot) for lot in lots]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Batch analysis error: {result}")
        elif result:
            analyzed.append(result)

    return analyzed
