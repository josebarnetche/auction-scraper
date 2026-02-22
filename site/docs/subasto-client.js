/**
 * Subasto API JavaScript/Node.js Client
 *
 * Official JavaScript SDK for the Subasto Argentine Auction API.
 * Supports USDC micropayments on Base network.
 *
 * Installation:
 *   npm install viem
 *
 * Usage (Node.js):
 *   import SubastoClient from './subasto-client.js';
 *
 *   // Without wallet (manual payment)
 *   const client = new SubastoClient();
 *   const pricing = await client.getPricing();
 *   console.log('Payment wallet:', pricing.payment.wallet);
 *
 *   // With wallet (automated payment)
 *   const client = new SubastoClient('0xYourPrivateKey...');
 *   const txHash = await client.sendPayment(0.01);
 *   const data = await client.getPremium(txHash);
 *   console.log(`Found ${data.data.count} premium picks`);
 *
 * Usage (Browser):
 *   <script type="module">
 *     import SubastoClient from './subasto-client.js';
 *     const client = new SubastoClient();
 *     const pricing = await client.getPricing();
 *   </script>
 *
 * Documentation: https://subasto.com.ar/docs/agents.html
 */

// Configuration
const CONFIG = {
  BASE_URL: 'https://subasto.com.ar/api/v1',
  USDC_ADDRESS: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
  PAYMENT_WALLET: '0x29E007249b744892a1da17F4289f75cfC871d6Fe',
  USDC_DECIMALS: 6,
  CHAIN_ID: 8453, // Base mainnet
  RPC_URL: 'https://mainnet.base.org',

  // Pricing in USDC
  PRICES: {
    premium: 0.01,
    opportunities: 0.02,
    auctions: 0.05
  }
};

// Error classes
class SubastoError extends Error {
  constructor(message, code = null) {
    super(message);
    this.name = 'SubastoError';
    this.code = code;
  }
}

class PaymentRequiredError extends SubastoError {
  constructor(message) {
    super(message, 402);
    this.name = 'PaymentRequiredError';
  }
}

class TransactionAlreadyUsedError extends SubastoError {
  constructor(message) {
    super(message, 400);
    this.name = 'TransactionAlreadyUsedError';
  }
}

/**
 * Subasto API Client
 */
class SubastoClient {
  /**
   * Create a new Subasto client
   * @param {string|null} privateKey - Optional private key for automated payments
   * @param {object} options - Configuration options
   * @param {string} options.rpcUrl - Base network RPC URL
   * @param {number} options.timeout - Request timeout in ms
   */
  constructor(privateKey = null, options = {}) {
    this.privateKey = privateKey;
    this.rpcUrl = options.rpcUrl || CONFIG.RPC_URL;
    this.timeout = options.timeout || 30000;

    // These will be initialized lazily when needed
    this.publicClient = null;
    this.walletClient = null;
    this.account = null;
  }

  /**
   * Initialize viem clients (lazy loading)
   */
  async _initWeb3() {
    if (this.publicClient) return;

    try {
      const viem = await import('viem');
      const chains = await import('viem/chains');
      const accounts = await import('viem/accounts');

      this.publicClient = viem.createPublicClient({
        chain: chains.base,
        transport: viem.http(this.rpcUrl)
      });

      if (this.privateKey) {
        this.account = accounts.privateKeyToAccount(this.privateKey);
        this.walletClient = viem.createWalletClient({
          account: this.account,
          chain: chains.base,
          transport: viem.http(this.rpcUrl)
        });
      }
    } catch (e) {
      throw new SubastoError(
        'viem package required for payments. Install with: npm install viem'
      );
    }
  }

  /**
   * Make API request
   * @private
   */
  async _request(endpoint, params = {}) {
    const url = new URL(`${CONFIG.BASE_URL}/${endpoint}`);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, value);
      }
    });

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'SubastoClient/1.0 JavaScript'
        },
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      const data = await response.json();

      if (response.status === 402) {
        throw new PaymentRequiredError(data.message || 'Payment required');
      }

      if (response.status === 400) {
        if (data.message?.toLowerCase().includes('already used')) {
          throw new TransactionAlreadyUsedError(data.message);
        }
        throw new SubastoError(data.message || 'Bad request', 400);
      }

      if (response.status >= 500) {
        throw new SubastoError(`Server error: ${response.status}`, response.status);
      }

      if (!response.ok) {
        throw new SubastoError(`Request failed: ${response.status}`, response.status);
      }

      return data;
    } catch (e) {
      clearTimeout(timeoutId);
      if (e.name === 'AbortError') {
        throw new SubastoError('Request timed out');
      }
      if (e instanceof SubastoError) {
        throw e;
      }
      throw new SubastoError(`Request failed: ${e.message}`);
    }
  }

  /**
   * Get API pricing and payment instructions (free endpoint)
   * @returns {Promise<object>} Pricing info and payment wallet
   */
  async getPricing() {
    return this._request('price');
  }

  /**
   * Send USDC payment and return transaction hash
   * @param {number} amountUsdc - Amount in USDC
   * @returns {Promise<string>} Transaction hash
   */
  async sendPayment(amountUsdc) {
    if (!this.privateKey) {
      throw new SubastoError(
        "Private key required for payments. " +
        "Initialize client with: new SubastoClient('0x...')"
      );
    }

    await this._initWeb3();

    const viem = await import('viem');
    const amountWei = BigInt(Math.floor(amountUsdc * 10 ** CONFIG.USDC_DECIMALS));

    const hash = await this.walletClient.writeContract({
      address: CONFIG.USDC_ADDRESS,
      abi: viem.parseAbi(['function transfer(address to, uint256 amount) returns (bool)']),
      functionName: 'transfer',
      args: [CONFIG.PAYMENT_WALLET, amountWei]
    });

    // Wait for confirmation
    const receipt = await this.publicClient.waitForTransactionReceipt({
      hash,
      timeout: 120000
    });

    if (receipt.status !== 'success') {
      throw new SubastoError('Transaction failed on-chain');
    }

    return hash;
  }

  /**
   * Get premium picks (top 12 curated opportunities)
   * @param {string} txHash - Transaction hash of $0.01 USDC payment
   * @returns {Promise<object>} Premium picks data
   */
  async getPremium(txHash) {
    return this._request('premium', { tx: txHash });
  }

  /**
   * Get hot deals with 40%+ discount vs market
   * @param {string} txHash - Transaction hash of $0.02 USDC payment
   * @returns {Promise<object>} Opportunities data
   */
  async getOpportunities(txHash) {
    return this._request('opportunities', { tx: txHash });
  }

  /**
   * Get all auction listings from 14 sources
   * @param {string} txHash - Transaction hash of $0.05 USDC payment
   * @returns {Promise<object>} Full auction data
   */
  async getAuctions(txHash) {
    return this._request('auctions', { tx: txHash });
  }

  /**
   * Filter opportunities by category
   * @param {Array} opportunities - Array of opportunities
   * @param {string} category - Category to filter by
   * @returns {Array} Filtered opportunities
   */
  filterByCategory(opportunities, category) {
    return opportunities.filter(opp =>
      opp.listing?.category === category
    );
  }

  /**
   * Filter opportunities by minimum discount
   * @param {Array} opportunities - Array of opportunities
   * @param {number} minDiscount - Minimum discount percentage
   * @returns {Array} Filtered opportunities
   */
  filterByDiscount(opportunities, minDiscount) {
    return opportunities.filter(opp =>
      (opp.discount_percentage || 0) >= minDiscount
    );
  }

  /**
   * Calculate potential profit for an opportunity
   * @param {object} opportunity - Opportunity to analyze
   * @param {number} sellingCostsPercent - Estimated selling costs (default 15%)
   * @returns {object} Profit analysis
   */
  calculateProfit(opportunity, sellingCostsPercent = 15) {
    const buyPrice = opportunity.auction_price_usd || 0;
    const marketPrice = opportunity.market_median_usd || 0;
    const netSellPrice = marketPrice * (1 - sellingCostsPercent / 100);
    const profit = netSellPrice - buyPrice;
    const roi = buyPrice > 0 ? (profit / buyPrice) * 100 : 0;

    return {
      buyPriceUsd: buyPrice,
      marketPriceUsd: marketPrice,
      netSellPriceUsd: netSellPrice,
      profitUsd: profit,
      roiPercent: roi
    };
  }
}

// Categories enum
const Category = {
  VEHICLES: 'vehicles',
  REAL_ESTATE: 'real_estate',
  MACHINERY: 'machinery',
  GENERAL_GOODS: 'general_goods',
  OTHER: 'other'
};

// Export for different module systems
export {
  SubastoClient,
  SubastoError,
  PaymentRequiredError,
  TransactionAlreadyUsedError,
  Category,
  CONFIG
};

export default SubastoClient;

// CommonJS compatibility
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SubastoClient;
  module.exports.SubastoClient = SubastoClient;
  module.exports.SubastoError = SubastoError;
  module.exports.PaymentRequiredError = PaymentRequiredError;
  module.exports.TransactionAlreadyUsedError = TransactionAlreadyUsedError;
  module.exports.Category = Category;
  module.exports.CONFIG = CONFIG;
}
