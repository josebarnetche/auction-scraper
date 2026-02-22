"""
Subasto API Python Client

Official Python SDK for the Subasto Argentine Auction API.
Supports USDC micropayments on Base network.

Installation:
    pip install requests web3

Usage:
    from subasto_client import SubastoClient

    # Without wallet (manual payment)
    client = SubastoClient()
    pricing = client.get_pricing()
    print(f"Payment wallet: {pricing['payment']['wallet']}")

    # With wallet (automated payment)
    client = SubastoClient(private_key="0x...")
    tx_hash = client.send_payment(0.01)
    data = client.get_premium(tx_hash)
    print(f"Found {data['data']['count']} premium picks")

Documentation: https://subasto.com.ar/docs/agents.html
"""

import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import json
import time

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False


class Category(Enum):
    """Auction listing categories."""
    VEHICLES = "vehicles"
    REAL_ESTATE = "real_estate"
    MACHINERY = "machinery"
    GENERAL_GOODS = "general_goods"
    OTHER = "other"


@dataclass
class Listing:
    """Auction listing data structure."""
    id: str
    source: str
    source_url: str
    title: str
    description: str
    category: str
    base_price: float
    currency: str
    status: str
    starts_at: Optional[str]
    ends_at: Optional[str]
    location: Dict[str, str]
    images: List[str]
    scraped_at: str

    @classmethod
    def from_dict(cls, data: Dict) -> 'Listing':
        return cls(
            id=data.get('id', ''),
            source=data.get('source', ''),
            source_url=data.get('source_url', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            category=data.get('category', 'other'),
            base_price=data.get('base_price', 0),
            currency=data.get('currency', 'ARS'),
            status=data.get('status', 'published'),
            starts_at=data.get('starts_at'),
            ends_at=data.get('ends_at'),
            location=data.get('location', {}),
            images=data.get('images', []),
            scraped_at=data.get('scraped_at', '')
        )


@dataclass
class Opportunity:
    """Market opportunity with discount analysis."""
    listing: Listing
    market_median_usd: float
    auction_price_usd: float
    discount_percentage: float
    confidence_score: float
    comparables_count: int
    comparable_urls: List[str]
    analysis_notes: str
    analyzed_at: str

    @classmethod
    def from_dict(cls, data: Dict) -> 'Opportunity':
        return cls(
            listing=Listing.from_dict(data.get('listing', {})),
            market_median_usd=data.get('market_median_usd', 0),
            auction_price_usd=data.get('auction_price_usd', 0),
            discount_percentage=data.get('discount_percentage', 0),
            confidence_score=data.get('confidence_score', 0),
            comparables_count=data.get('comparables_count', 0),
            comparable_urls=data.get('comparable_urls', []),
            analysis_notes=data.get('analysis_notes', ''),
            analyzed_at=data.get('analyzed_at', '')
        )


class SubastoError(Exception):
    """Base exception for Subasto API errors."""
    pass


class PaymentRequiredError(SubastoError):
    """Raised when payment is required but not provided."""
    pass


class TransactionAlreadyUsedError(SubastoError):
    """Raised when transaction hash has already been used."""
    pass


class InsufficientPaymentError(SubastoError):
    """Raised when payment amount is insufficient."""
    pass


class SubastoClient:
    """
    Subasto API client with USDC payment support.

    Args:
        private_key: Optional Ethereum private key for automated payments
        rpc_url: Base network RPC URL (default: https://mainnet.base.org)
        timeout: Request timeout in seconds (default: 30)
    """

    BASE_URL = "https://subasto.com.ar/api/v1"
    USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    PAYMENT_WALLET = "0x29E007249b744892a1da17F4289f75cfC871d6Fe"
    USDC_DECIMALS = 6

    # Pricing in USDC
    PRICES = {
        "premium": 0.01,
        "opportunities": 0.02,
        "auctions": 0.05
    }

    def __init__(
        self,
        private_key: Optional[str] = None,
        rpc_url: str = "https://mainnet.base.org",
        timeout: int = 30
    ):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "SubastoClient/1.0 Python"
        })

        self.private_key = private_key
        self.w3 = None
        self.account = None

        if private_key:
            if not WEB3_AVAILABLE:
                raise ImportError(
                    "web3 package required for payments. "
                    "Install with: pip install web3"
                )
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            self.account = self.w3.eth.account.from_key(private_key)

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request with error handling."""
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            data = response.json()

            if response.status_code == 402:
                error_msg = data.get('message', 'Payment required')
                if 'Insufficient' in error_msg:
                    raise InsufficientPaymentError(error_msg)
                raise PaymentRequiredError(error_msg)

            if response.status_code == 400:
                if 'already used' in data.get('message', '').lower():
                    raise TransactionAlreadyUsedError(data.get('message'))
                raise SubastoError(data.get('message', 'Bad request'))

            if response.status_code >= 500:
                raise SubastoError(f"Server error: {response.status_code}")

            response.raise_for_status()
            return data

        except requests.exceptions.Timeout:
            raise SubastoError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise SubastoError(f"Request failed: {str(e)}")

    def get_pricing(self) -> Dict[str, Any]:
        """
        Get API pricing and payment instructions.

        Returns:
            Dict containing pricing info and payment wallet address

        Example:
            >>> client = SubastoClient()
            >>> pricing = client.get_pricing()
            >>> print(pricing['payment']['wallet'])
            0x29E007249b744892a1da17F4289f75cfC871d6Fe
        """
        return self._request("price")

    def send_payment(self, amount_usdc: float, wait_confirmations: int = 1) -> str:
        """
        Send USDC payment and return transaction hash.

        Args:
            amount_usdc: Amount in USDC (e.g., 0.01, 0.02, 0.05)
            wait_confirmations: Number of confirmations to wait for

        Returns:
            Transaction hash (0x...)

        Raises:
            ValueError: If private key not provided
            SubastoError: If transaction fails
        """
        if not self.w3 or not self.account:
            raise ValueError(
                "Private key required for payments. "
                "Initialize client with: SubastoClient(private_key='0x...')"
            )

        # Convert to wei (USDC has 6 decimals)
        amount_wei = int(amount_usdc * 10**self.USDC_DECIMALS)

        # ERC20 transfer ABI
        usdc_abi = [
            {
                "inputs": [
                    {"name": "to", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"type": "bool"}],
                "type": "function"
            }
        ]

        usdc = self.w3.eth.contract(
            address=self.w3.to_checksum_address(self.USDC_ADDRESS),
            abi=usdc_abi
        )

        # Build transaction
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        gas_price = self.w3.eth.gas_price

        tx = usdc.functions.transfer(
            self.w3.to_checksum_address(self.PAYMENT_WALLET),
            amount_wei
        ).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': gas_price * 2,
            'maxPriorityFeePerGas': self.w3.to_wei(0.001, 'gwei'),
            'chainId': 8453  # Base mainnet
        })

        # Sign and send
        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=120
        )

        if receipt['status'] != 1:
            raise SubastoError("Transaction failed on-chain")

        return tx_hash.hex()

    def get_premium(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get premium picks (top 12 curated opportunities).

        Args:
            tx_hash: Transaction hash of $0.01 USDC payment

        Returns:
            Dict with premium_picks array and metadata
        """
        return self._request("premium", params={"tx": tx_hash})

    def get_opportunities(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get hot deals with 40%+ discount vs market.

        Args:
            tx_hash: Transaction hash of $0.02 USDC payment

        Returns:
            Dict with opportunities array and metadata
        """
        return self._request("opportunities", params={"tx": tx_hash})

    def get_auctions(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get all auction listings from 14 sources.

        Args:
            tx_hash: Transaction hash of $0.05 USDC payment

        Returns:
            Dict with full listings data and statistics
        """
        return self._request("auctions", params={"tx": tx_hash})

    def get_premium_typed(self, tx_hash: str) -> List[Dict]:
        """
        Get premium picks as typed Listing objects.

        Returns:
            List of premium pick dictionaries
        """
        data = self.get_premium(tx_hash)
        return data.get('data', {}).get('premium_picks', [])

    def get_opportunities_typed(self, tx_hash: str) -> List[Opportunity]:
        """
        Get opportunities as typed Opportunity objects.

        Returns:
            List of Opportunity dataclass instances
        """
        data = self.get_opportunities(tx_hash)
        return [
            Opportunity.from_dict(opp)
            for opp in data.get('data', {}).get('opportunities', [])
        ]

    def filter_by_category(
        self,
        opportunities: List[Opportunity],
        category: Category
    ) -> List[Opportunity]:
        """Filter opportunities by category."""
        return [
            opp for opp in opportunities
            if opp.listing.category == category.value
        ]

    def filter_by_discount(
        self,
        opportunities: List[Opportunity],
        min_discount: float
    ) -> List[Opportunity]:
        """Filter opportunities by minimum discount percentage."""
        return [
            opp for opp in opportunities
            if opp.discount_percentage >= min_discount
        ]

    def calculate_profit(
        self,
        opportunity: Opportunity,
        selling_costs_percent: float = 15.0
    ) -> Dict[str, float]:
        """
        Calculate potential profit for an opportunity.

        Args:
            opportunity: Opportunity to analyze
            selling_costs_percent: Estimated selling costs (default 15%)

        Returns:
            Dict with buy_price, net_sell_price, profit, and roi
        """
        buy_price = opportunity.auction_price_usd
        market_price = opportunity.market_median_usd
        net_sell_price = market_price * (1 - selling_costs_percent / 100)
        profit = net_sell_price - buy_price
        roi = (profit / buy_price * 100) if buy_price > 0 else 0

        return {
            "buy_price_usd": buy_price,
            "market_price_usd": market_price,
            "net_sell_price_usd": net_sell_price,
            "profit_usd": profit,
            "roi_percent": roi
        }


# Convenience functions for quick usage
def get_pricing() -> Dict[str, Any]:
    """Quick function to get API pricing."""
    return SubastoClient().get_pricing()


def get_premium(tx_hash: str) -> Dict[str, Any]:
    """Quick function to get premium picks."""
    return SubastoClient().get_premium(tx_hash)


def get_opportunities(tx_hash: str) -> Dict[str, Any]:
    """Quick function to get opportunities."""
    return SubastoClient().get_opportunities(tx_hash)


def get_auctions(tx_hash: str) -> Dict[str, Any]:
    """Quick function to get all auctions."""
    return SubastoClient().get_auctions(tx_hash)


if __name__ == "__main__":
    # Demo usage
    client = SubastoClient()

    print("Subasto API Python Client")
    print("=" * 40)

    pricing = client.get_pricing()
    print(f"\nPayment Wallet: {pricing['payment']['wallet']}")
    print(f"Network: {pricing['payment']['network']}")
    print("\nEndpoint Pricing:")
    for endpoint, info in pricing['pricing']['endpoints'].items():
        print(f"  {endpoint}: ${info['price']} USDC")

    print("\n" + "=" * 40)
    print("To make API calls, send USDC to the wallet above,")
    print("then call the endpoint with your transaction hash.")
    print("\nExample:")
    print("  tx_hash = client.send_payment(0.01)")
    print("  data = client.get_premium(tx_hash)")
