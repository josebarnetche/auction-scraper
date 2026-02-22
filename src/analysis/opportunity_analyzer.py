"""AI-Powered Opportunity Analyzer using Claude.

Provides ACTIONABLE INTELLIGENCE for auction buyers:
- Detailed item specifications extraction
- Market value estimation with reasoning
- Profit potential calculation
- Risk assessment
- Bid strategy recommendations
- Similar sold items comparison
"""

import json
import logging
import base64
import httpx
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict

if TYPE_CHECKING:
    from src.models.listing import LotItem, AuctionListing

logger = logging.getLogger(__name__)


@dataclass
class ItemSpecs:
    """Extracted item specifications."""
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    condition: str = "unknown"  # new, like_new, good, fair, poor, unknown
    condition_notes: str = ""
    quantity: int = 1
    key_features: list = None
    dimensions: Optional[str] = None
    weight: Optional[str] = None

    def __post_init__(self):
        if self.key_features is None:
            self.key_features = []


@dataclass
class MarketValueEstimate:
    """Market value estimation with reasoning."""
    min_usd: float
    max_usd: float
    typical_usd: float
    confidence: float  # 0.0 to 1.0
    reasoning: str
    data_sources: list  # Where the estimate comes from
    comparable_items: list  # Similar items for reference

    def __post_init__(self):
        if self.data_sources is None:
            self.data_sources = []
        if self.comparable_items is None:
            self.comparable_items = []


@dataclass
class ProfitAnalysis:
    """Profit potential calculation."""
    buy_price_usd: float
    estimated_resale_usd: float
    gross_profit_usd: float
    profit_margin_percent: float
    estimated_costs_usd: float  # Transport, repairs, fees
    net_profit_usd: float
    time_to_sell_days: int
    liquidity: str  # high, medium, low
    reasoning: str


@dataclass
class RiskAssessment:
    """Risk factors and concerns."""
    overall_risk: str  # low, medium, high
    risk_score: int  # 1-10 (10 = highest risk)
    legal_concerns: list
    condition_concerns: list
    location_concerns: list
    market_concerns: list
    hidden_costs: list
    red_flags: list
    mitigation_suggestions: list

    def __post_init__(self):
        for field in ['legal_concerns', 'condition_concerns', 'location_concerns',
                      'market_concerns', 'hidden_costs', 'red_flags', 'mitigation_suggestions']:
            if getattr(self, field) is None:
                setattr(self, field, [])


@dataclass
class BidStrategy:
    """Recommended bidding strategy."""
    max_bid_usd: float
    opening_bid_usd: float
    bid_increments: list  # Suggested increments
    timing_recommendation: str  # early, late, snipe
    competition_level: str  # low, medium, high
    walk_away_price_usd: float
    reasoning: str

    def __post_init__(self):
        if self.bid_increments is None:
            self.bid_increments = []


@dataclass
class OpportunityAnalysis:
    """Complete opportunity analysis result."""
    listing_id: str
    analyzed_at: str

    # Core analysis
    specs: ItemSpecs
    market_value: MarketValueEstimate
    profit_analysis: ProfitAnalysis
    risk_assessment: RiskAssessment
    bid_strategy: BidStrategy

    # Summary
    opportunity_score: int  # 1-10
    action_recommendation: str  # BUY, WATCH, SKIP
    one_liner: str  # Quick summary
    detailed_reasoning: str

    # Metadata
    images_analyzed: int
    model_used: str
    analysis_cost_usd: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "listing_id": self.listing_id,
            "analyzed_at": self.analyzed_at,
            "specs": asdict(self.specs),
            "market_value": asdict(self.market_value),
            "profit_analysis": asdict(self.profit_analysis),
            "risk_assessment": asdict(self.risk_assessment),
            "bid_strategy": asdict(self.bid_strategy),
            "opportunity_score": self.opportunity_score,
            "action_recommendation": self.action_recommendation,
            "one_liner": self.one_liner,
            "detailed_reasoning": self.detailed_reasoning,
            "images_analyzed": self.images_analyzed,
            "model_used": self.model_used,
            "analysis_cost_usd": self.analysis_cost_usd,
        }


# Analysis prompt for Claude
OPPORTUNITY_ANALYSIS_PROMPT = """You are an expert auction analyst for Argentine auctions. Analyze this listing and provide ACTIONABLE INTELLIGENCE for a potential buyer.

## Listing Information
Title: {title}
Description: {description}
Base Price: {price} {currency} (~USD ${price_usd:.2f})
Category: {category}
Source: {source}
Location: {location}
Auction End: {end_date}
{image_context}

## Your Task
Provide a comprehensive analysis with specific, actionable recommendations. Return ONLY valid JSON.

## Required JSON Format
{{
  "specs": {{
    "brand": "brand name or null",
    "model": "model number/name or null",
    "year": year as integer or null,
    "condition": "new|like_new|good|fair|poor|unknown",
    "condition_notes": "specific observations about condition",
    "quantity": 1,
    "key_features": ["feature1", "feature2"],
    "dimensions": "dimensions if visible/mentioned or null",
    "weight": "weight if mentioned or null"
  }},

  "market_value": {{
    "min_usd": minimum realistic market value,
    "max_usd": maximum realistic market value,
    "typical_usd": most likely resale value,
    "confidence": 0.0 to 1.0,
    "reasoning": "explain how you arrived at this valuation",
    "data_sources": ["MercadoLibre", "historical auctions", "dealer prices", etc.],
    "comparable_items": [
      {{"description": "Similar item sold", "price_usd": 0, "source": "where"}}
    ]
  }},

  "profit_analysis": {{
    "buy_price_usd": current auction base price in USD,
    "estimated_resale_usd": realistic resale price,
    "gross_profit_usd": resale minus buy price,
    "profit_margin_percent": percentage,
    "estimated_costs_usd": transport + repairs + fees + taxes,
    "net_profit_usd": gross profit minus costs,
    "time_to_sell_days": estimated days to resell,
    "liquidity": "high|medium|low",
    "reasoning": "explain profit potential"
  }},

  "risk_assessment": {{
    "overall_risk": "low|medium|high",
    "risk_score": 1-10,
    "legal_concerns": ["any title/ownership issues", "judicial complications"],
    "condition_concerns": ["potential hidden damage", "maintenance needs"],
    "location_concerns": ["pickup logistics", "transport costs"],
    "market_concerns": ["demand issues", "price volatility"],
    "hidden_costs": ["registration fees", "repairs needed", "storage"],
    "red_flags": ["anything suspicious or concerning"],
    "mitigation_suggestions": ["how to reduce each risk"]
  }},

  "bid_strategy": {{
    "max_bid_usd": absolute maximum you should bid,
    "opening_bid_usd": suggested opening bid,
    "bid_increments": [suggested bid levels],
    "timing_recommendation": "early|late|snipe",
    "competition_level": "low|medium|high",
    "walk_away_price_usd": price at which to stop bidding,
    "reasoning": "explain the strategy"
  }},

  "opportunity_score": 1-10,
  "action_recommendation": "BUY|WATCH|SKIP",
  "one_liner": "One sentence summary of the opportunity",
  "detailed_reasoning": "2-3 sentences explaining your recommendation"
}}

## Scoring Guide
- 9-10: EXCEPTIONAL - Buy immediately, very high profit potential, low risk
- 7-8: VERY GOOD - Strong opportunity, bid aggressively
- 5-6: GOOD - Worth bidding, but be careful on price
- 3-4: MARGINAL - Only if you have specific use case
- 1-2: SKIP - Not worth the risk/effort

## Argentine Market Context
- Judicial auctions often sell 40-70% below market
- "Base" price is starting bid, not expected final price
- Consider 21% IVA for commercial buyers
- Transport within Argentina: ~$0.50-1.50/km for vehicles
- Blue dollar rate matters for actual USD value
- Judicial auctions may have title transfer delays
- Bank auctions (Banco Ciudad) are generally safer than judicial

## Important
- Be SPECIFIC with numbers and recommendations
- Consider Argentine market conditions
- Factor in all realistic costs
- Return ONLY the JSON object, no markdown
"""


async def fetch_image_as_base64(url: str, timeout: float = 10.0) -> Optional[str]:
    """Fetch image from URL and convert to base64.

    Args:
        url: Image URL
        timeout: Request timeout in seconds

    Returns:
        Base64 encoded image string or None if failed
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout, follow_redirects=True)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/jpeg")
                if "image" in content_type:
                    return base64.standard_b64encode(response.content).decode("utf-8")
    except Exception as e:
        logger.debug(f"Failed to fetch image {url}: {e}")
    return None


def get_image_media_type(url: str) -> str:
    """Determine media type from URL."""
    url_lower = url.lower()
    if ".png" in url_lower:
        return "image/png"
    elif ".gif" in url_lower:
        return "image/gif"
    elif ".webp" in url_lower:
        return "image/webp"
    return "image/jpeg"


async def analyze_opportunity(
    listing_id: str,
    title: str,
    description: str,
    base_price: float,
    currency: str,
    category: str = "other",
    source: str = "",
    location: str = "",
    end_date: str = "",
    images: list[str] = None,
    blue_dollar_rate: float = 1430.0,
    model: str = "claude-3-5-haiku-20241022",
    max_images: int = 3,
) -> Optional[OpportunityAnalysis]:
    """Analyze an auction listing for opportunity potential.

    Args:
        listing_id: Unique identifier for the listing
        title: Listing title
        description: Listing description
        base_price: Base/starting price
        currency: Currency code (ARS/USD)
        category: Item category
        source: Auction source (banco_ciudad, csjn, etc.)
        location: Item location
        end_date: Auction end date
        images: List of image URLs
        blue_dollar_rate: Current blue dollar exchange rate
        model: Claude model to use
        max_images: Maximum images to analyze (for cost control)

    Returns:
        OpportunityAnalysis or None if analysis fails
    """
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed. Run: pip install anthropic")
        return None

    # Calculate USD price
    if currency == "USD":
        price_usd = base_price
    else:
        price_usd = base_price / blue_dollar_rate

    # Build image context
    image_context = ""
    images_analyzed = 0
    content_parts = []

    if images:
        # Limit images for cost efficiency
        images_to_analyze = images[:max_images]

        # Fetch and encode images
        for i, img_url in enumerate(images_to_analyze):
            img_base64 = await fetch_image_as_base64(img_url)
            if img_base64:
                media_type = get_image_media_type(img_url)
                content_parts.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_base64,
                    }
                })
                images_analyzed += 1

        if images_analyzed > 0:
            image_context = f"Images provided: {images_analyzed} image(s) attached for visual analysis"
        else:
            image_context = f"Images listed ({len(images)}) but could not be fetched"
    else:
        image_context = "No images available"

    # Build prompt
    prompt = OPPORTUNITY_ANALYSIS_PROMPT.format(
        title=title,
        description=description or "(no description provided)",
        price=f"{base_price:,.0f}",
        currency=currency,
        price_usd=price_usd,
        category=category,
        source=source,
        location=location or "Not specified",
        end_date=end_date or "Not specified",
        image_context=image_context,
    )

    # Add text prompt to content
    content_parts.append({
        "type": "text",
        "text": prompt
    })

    try:
        client = anthropic.Anthropic()

        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": content_parts
            }]
        )

        # Extract text response
        text = response.content[0].text.strip()

        # Parse JSON (handle potential markdown wrapping)
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)

        # Build structured response
        analysis = OpportunityAnalysis(
            listing_id=listing_id,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            specs=ItemSpecs(**result.get("specs", {})),
            market_value=MarketValueEstimate(**result.get("market_value", {
                "min_usd": 0, "max_usd": 0, "typical_usd": 0,
                "confidence": 0, "reasoning": "", "data_sources": [], "comparable_items": []
            })),
            profit_analysis=ProfitAnalysis(**result.get("profit_analysis", {
                "buy_price_usd": price_usd, "estimated_resale_usd": 0,
                "gross_profit_usd": 0, "profit_margin_percent": 0,
                "estimated_costs_usd": 0, "net_profit_usd": 0,
                "time_to_sell_days": 0, "liquidity": "unknown", "reasoning": ""
            })),
            risk_assessment=RiskAssessment(**result.get("risk_assessment", {
                "overall_risk": "unknown", "risk_score": 5,
                "legal_concerns": [], "condition_concerns": [],
                "location_concerns": [], "market_concerns": [],
                "hidden_costs": [], "red_flags": [], "mitigation_suggestions": []
            })),
            bid_strategy=BidStrategy(**result.get("bid_strategy", {
                "max_bid_usd": price_usd, "opening_bid_usd": price_usd,
                "bid_increments": [], "timing_recommendation": "late",
                "competition_level": "unknown", "walk_away_price_usd": price_usd,
                "reasoning": ""
            })),
            opportunity_score=int(result.get("opportunity_score", 5)),
            action_recommendation=result.get("action_recommendation", "WATCH"),
            one_liner=result.get("one_liner", ""),
            detailed_reasoning=result.get("detailed_reasoning", ""),
            images_analyzed=images_analyzed,
            model_used=model,
            analysis_cost_usd=calculate_analysis_cost(model, images_analyzed),
        )

        return analysis

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI response for {listing_id}: {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error for {listing_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error analyzing {listing_id}: {e}")
        return None


def calculate_analysis_cost(model: str, images_analyzed: int) -> float:
    """Estimate the cost of an analysis call.

    Based on Claude pricing (as of 2024):
    - Haiku: $0.25/MTok input, $1.25/MTok output
    - Images: ~1000 tokens per image

    Args:
        model: Model used
        images_analyzed: Number of images analyzed

    Returns:
        Estimated cost in USD
    """
    if "haiku" in model.lower():
        # Estimate ~2000 tokens input (prompt + images) + ~1500 tokens output
        input_tokens = 2000 + (images_analyzed * 1000)
        output_tokens = 1500
        cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)
        return round(cost, 4)
    elif "sonnet" in model.lower():
        # Sonnet is 5x more expensive
        input_tokens = 2000 + (images_analyzed * 1000)
        output_tokens = 1500
        cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
        return round(cost, 4)
    return 0.02  # Default estimate


async def analyze_listing(
    listing: "AuctionListing",
    blue_dollar_rate: float = 1430.0,
    model: str = "claude-3-5-haiku-20241022",
) -> Optional[OpportunityAnalysis]:
    """Analyze an AuctionListing object.

    Convenience wrapper for analyze_opportunity.

    Args:
        listing: AuctionListing to analyze
        blue_dollar_rate: Current blue dollar rate
        model: Claude model to use

    Returns:
        OpportunityAnalysis or None
    """
    location = ""
    if listing.location:
        location = f"{listing.location.get('city', '')}, {listing.location.get('province', '')}"

    end_date = ""
    if listing.ends_at:
        end_date = listing.ends_at.isoformat()

    return await analyze_opportunity(
        listing_id=listing.id,
        title=listing.title,
        description=listing.description,
        base_price=listing.base_price,
        currency=listing.currency,
        category=listing.category,
        source=listing.source,
        location=location,
        end_date=end_date,
        images=listing.images,
        blue_dollar_rate=blue_dollar_rate,
        model=model,
    )


async def analyze_lot(
    lot: "LotItem",
    auction_title: str = "",
    auction_source: str = "",
    auction_location: str = "",
    blue_dollar_rate: float = 1430.0,
    model: str = "claude-3-5-haiku-20241022",
) -> Optional[OpportunityAnalysis]:
    """Analyze a LotItem object.

    Args:
        lot: LotItem to analyze
        auction_title: Parent auction title for context
        auction_source: Source of the auction
        auction_location: Location of the auction
        blue_dollar_rate: Current blue dollar rate
        model: Claude model to use

    Returns:
        OpportunityAnalysis or None
    """
    # Combine lot title with auction title for context
    full_title = lot.title
    if auction_title:
        full_title = f"{lot.title} (from: {auction_title})"

    end_date = ""
    if lot.ends_at:
        end_date = lot.ends_at.isoformat()

    return await analyze_opportunity(
        listing_id=lot.lot_id,
        title=full_title,
        description=lot.description,
        base_price=lot.base_price,
        currency=lot.currency,
        category="other",  # Lots don't have category
        source=auction_source,
        location=auction_location,
        end_date=end_date,
        images=lot.images,
        blue_dollar_rate=blue_dollar_rate,
        model=model,
    )


async def batch_analyze(
    items: list[dict],
    blue_dollar_rate: float = 1430.0,
    model: str = "claude-3-5-haiku-20241022",
    max_concurrent: int = 5,
    max_items: int = 100,
) -> list[OpportunityAnalysis]:
    """Analyze multiple items in batch with rate limiting.

    Args:
        items: List of dicts with listing data (id, title, description, etc.)
        blue_dollar_rate: Current blue dollar rate
        model: Claude model to use
        max_concurrent: Maximum concurrent API calls
        max_items: Maximum items to analyze

    Returns:
        List of OpportunityAnalysis results
    """
    import asyncio

    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    # Limit items
    items_to_analyze = items[:max_items]

    async def analyze_with_limit(item: dict) -> Optional[OpportunityAnalysis]:
        async with semaphore:
            return await analyze_opportunity(
                listing_id=item.get("id", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                base_price=item.get("base_price", 0),
                currency=item.get("currency", "ARS"),
                category=item.get("category", "other"),
                source=item.get("source", ""),
                location=item.get("location", ""),
                end_date=item.get("end_date", ""),
                images=item.get("images", []),
                blue_dollar_rate=blue_dollar_rate,
                model=model,
            )

    tasks = [analyze_with_limit(item) for item in items_to_analyze]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in task_results:
        if isinstance(result, Exception):
            logger.error(f"Batch analysis error: {result}")
        elif result:
            results.append(result)

    return results


def format_analysis_summary(analysis: OpportunityAnalysis) -> str:
    """Format analysis as human-readable summary.

    Args:
        analysis: OpportunityAnalysis to format

    Returns:
        Formatted string summary
    """
    action_emoji = {
        "BUY": "[BUY]",
        "WATCH": "[WATCH]",
        "SKIP": "[SKIP]"
    }

    summary = f"""
{'='*60}
{analysis.one_liner}
{'='*60}

ACTION: {action_emoji.get(analysis.action_recommendation, '')} {analysis.action_recommendation}
SCORE: {analysis.opportunity_score}/10

SPECS:
  Brand: {analysis.specs.brand or 'Unknown'}
  Model: {analysis.specs.model or 'Unknown'}
  Year: {analysis.specs.year or 'Unknown'}
  Condition: {analysis.specs.condition}

MARKET VALUE:
  Range: ${analysis.market_value.min_usd:,.0f} - ${analysis.market_value.max_usd:,.0f}
  Typical: ${analysis.market_value.typical_usd:,.0f}
  Confidence: {analysis.market_value.confidence:.0%}

PROFIT POTENTIAL:
  Buy at: ${analysis.profit_analysis.buy_price_usd:,.0f}
  Sell at: ${analysis.profit_analysis.estimated_resale_usd:,.0f}
  Gross Profit: ${analysis.profit_analysis.gross_profit_usd:,.0f} ({analysis.profit_analysis.profit_margin_percent:.0f}%)
  Est. Costs: ${analysis.profit_analysis.estimated_costs_usd:,.0f}
  Net Profit: ${analysis.profit_analysis.net_profit_usd:,.0f}
  Time to Sell: {analysis.profit_analysis.time_to_sell_days} days
  Liquidity: {analysis.profit_analysis.liquidity}

RISK ASSESSMENT:
  Overall: {analysis.risk_assessment.overall_risk.upper()} (Score: {analysis.risk_assessment.risk_score}/10)
  Red Flags: {', '.join(analysis.risk_assessment.red_flags) or 'None'}

BID STRATEGY:
  Max Bid: ${analysis.bid_strategy.max_bid_usd:,.0f}
  Walk Away: ${analysis.bid_strategy.walk_away_price_usd:,.0f}
  Timing: {analysis.bid_strategy.timing_recommendation}
  Competition: {analysis.bid_strategy.competition_level}

REASONING:
{analysis.detailed_reasoning}

Analysis Cost: ${analysis.analysis_cost_usd:.4f}
{'='*60}
"""
    return summary
