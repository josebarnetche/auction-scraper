// Base Mainnet Configuration
export const BASE_CHAIN_ID = 8453;
export const BASE_RPC = "https://mainnet.base.org";

// USDC on Base
export const USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" as const;
export const USDC_DECIMALS = 6;

// Your wallet to receive payments
export const PAYMENT_WALLET = process.env.PAYMENT_WALLET || "0x29E007249b744892a1da17F4289f75cfC871d6Fe";

// Pricing in USDC (6 decimals)
export const PRICES = {
  auctions: 0.01,        // $0.01 - full listings
  opportunities: 0.05,   // $0.05 - hot deals only
  premium: 0.10,         // $0.10 - premium picks
} as const;

// Anti-replay: tx must be within this many seconds
export const TX_MAX_AGE_SECONDS = 3600; // 1 hour
