// Base Mainnet Configuration
export const BASE_CHAIN_ID = 8453;
export const BASE_RPC = "https://mainnet.base.org";

// USDC on Base
export const USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" as const;
export const USDC_DECIMALS = 6;

// Your wallet to receive payments
export const PAYMENT_WALLET = process.env.PAYMENT_WALLET || "0x29E007249b744892a1da17F4289f75cfC871d6Fe";

// Pricing in USDC (6 decimals) - volume-based
export const PRICES = {
  premium: 0.01,         // $0.01 - curated picks (~12)
  opportunities: 0.02,   // $0.02 - hot deals (~70)
  auctions: 0.05,        // $0.05 - all listings (864+)
} as const;

// Anti-replay: tx must be within this many seconds
export const TX_MAX_AGE_SECONDS = 3600; // 1 hour

// Subscription tiers
export type SubscriptionTier = 'free' | 'pro' | 'enterprise';

export const SUBSCRIPTION_TIERS: Record<SubscriptionTier, {
  name: string;
  price: number;
  dailyCredits: number;
  requestsPerDay: number;
  durationDays: number;
  features: string[];
}> = {
  free: {
    name: 'Free',
    price: 0,
    dailyCredits: 10,
    requestsPerDay: 10,
    durationDays: 0,
    features: ['Basic search', '10 credits/day', 'Email support']
  },
  pro: {
    name: 'Pro',
    price: 5,
    dailyCredits: 1000,
    requestsPerDay: 1000,
    durationDays: 30,
    features: ['Unlimited search', '1000 credits/day', 'Priority support', 'API access']
  },
  enterprise: {
    name: 'Enterprise',
    price: 20,
    dailyCredits: 10000,
    requestsPerDay: 10000,
    durationDays: 30,
    features: ['Everything in Pro', '10000 credits/day', 'Dedicated support', 'Custom integrations']
  }
};

// Credit packages for one-time purchases
export const CREDIT_PACKAGES: Record<string, {
  credits: number;
  price: number;
  bonus: string;
  description: string;
  savingsPercent: number;
}> = {
  starter: { credits: 50, price: 1, bonus: '', description: 'Try it out', savingsPercent: 0 },
  basic: { credits: 300, price: 5, bonus: '+50 bonus', description: 'Best for casual users', savingsPercent: 10 },
  standard: { credits: 700, price: 10, bonus: '+100 bonus', description: 'Most popular', savingsPercent: 20 },
  premium: { credits: 4000, price: 50, bonus: '+500 bonus', description: 'Best value for power users', savingsPercent: 30 }
};
