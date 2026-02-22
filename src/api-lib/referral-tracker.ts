/**
 * Referral Tracker for Subasto API
 *
 * Handles referral attribution, commission tracking, and payout management.
 * Uses localStorage-based user IDs on frontend, wallet addresses for affiliates.
 *
 * Commission Structure:
 * - 10% of API payments from referred users
 * - Minimum $1 USDC to withdraw
 * - 30-day attribution window
 * - One referral credit per wallet (anti-fraud)
 */

// Types
export interface Affiliate {
  wallet: string;              // Affiliate's wallet address (receives payouts)
  referralCode: string;        // Unique code (e.g., ABC123)
  displayName?: string;        // Optional display name
  createdAt: number;
  totalClicks: number;
  totalConversions: number;
  totalEarnings: number;       // In USDC
  pendingPayout: number;       // Unpaid earnings
  paidOut: number;             // Total paid out
  status: 'active' | 'suspended' | 'pending_review';
}

export interface ReferralAttribution {
  refereeId: string;           // User ID from localStorage
  refereeWallet?: string;      // Wallet once they pay
  referrerCode: string;        // Affiliate's referral code
  referrerWallet: string;      // Affiliate's wallet
  attributedAt: number;        // When the referral was clicked
  expiresAt: number;           // Attribution window expiration
  converted: boolean;          // Has the user made a payment?
  conversionAmount: number;    // Total payment amount
  commissionEarned: number;    // 10% of payments
}

export interface ReferralClick {
  code: string;
  ip?: string;
  userAgent?: string;
  timestamp: number;
  page?: string;
}

export interface CommissionRecord {
  id: string;
  affiliateWallet: string;
  refereeWallet: string;
  paymentTxHash: string;
  paymentAmount: number;
  commissionAmount: number;    // 10% of payment
  timestamp: number;
  status: 'pending' | 'approved' | 'paid' | 'rejected';
}

export interface PayoutRequest {
  id: string;
  affiliateWallet: string;
  amount: number;
  requestedAt: number;
  status: 'pending' | 'processing' | 'completed' | 'rejected';
  txHash?: string;             // Payout transaction hash
  processedAt?: number;
  note?: string;
}

// Configuration
export const REFERRAL_CONFIG = {
  COMMISSION_RATE: 0.10,           // 10% commission
  MIN_PAYOUT: 1.00,                // $1 USDC minimum
  ATTRIBUTION_WINDOW_DAYS: 30,     // 30-day cookie
  MANUAL_REVIEW_THRESHOLD: 50.00,  // Review payouts > $50
  CODE_LENGTH: 6,                  // Referral code length
  MAX_REFERRALS_PER_WALLET: 1,     // One referral per wallet (anti-fraud)
};

// In-memory storage (MVP - replace with Vercel KV for production)
const storage = {
  affiliates: new Map<string, Affiliate>(),           // wallet -> Affiliate
  codeToWallet: new Map<string, string>(),            // code -> wallet
  attributions: new Map<string, ReferralAttribution>(), // refereeId -> attribution
  walletToReferrer: new Map<string, string>(),        // refereeWallet -> referrerWallet
  commissions: new Map<string, CommissionRecord>(),   // id -> commission
  payouts: new Map<string, PayoutRequest>(),          // id -> payout
  clicks: new Array<ReferralClick>(),                 // Recent clicks for analytics
};

/**
 * Generate a unique referral code
 */
function generateReferralCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // No confusing chars (0/O, 1/I/L)
  let code = '';
  for (let i = 0; i < REFERRAL_CONFIG.CODE_LENGTH; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }

  // Ensure uniqueness
  if (storage.codeToWallet.has(code)) {
    return generateReferralCode();
  }

  return code;
}

/**
 * Normalize wallet address
 */
function normalizeWallet(wallet: string): string {
  return wallet.toLowerCase();
}

/**
 * Generate unique ID
 */
function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
}

// ============================================================================
// AFFILIATE MANAGEMENT
// ============================================================================

/**
 * Register a new affiliate
 */
export function registerAffiliate(
  wallet: string,
  displayName?: string
): { success: boolean; affiliate?: Affiliate; error?: string } {
  const normalizedWallet = normalizeWallet(wallet);

  // Check if already registered
  if (storage.affiliates.has(normalizedWallet)) {
    const existing = storage.affiliates.get(normalizedWallet)!;
    return { success: true, affiliate: existing };
  }

  // Generate unique code
  const referralCode = generateReferralCode();

  const affiliate: Affiliate = {
    wallet: normalizedWallet,
    referralCode,
    displayName,
    createdAt: Date.now(),
    totalClicks: 0,
    totalConversions: 0,
    totalEarnings: 0,
    pendingPayout: 0,
    paidOut: 0,
    status: 'active',
  };

  storage.affiliates.set(normalizedWallet, affiliate);
  storage.codeToWallet.set(referralCode, normalizedWallet);

  return { success: true, affiliate };
}

/**
 * Get affiliate by wallet
 */
export function getAffiliate(wallet: string): Affiliate | null {
  return storage.affiliates.get(normalizeWallet(wallet)) || null;
}

/**
 * Get affiliate by referral code
 */
export function getAffiliateByCode(code: string): Affiliate | null {
  const wallet = storage.codeToWallet.get(code.toUpperCase());
  if (!wallet) return null;
  return storage.affiliates.get(wallet) || null;
}

/**
 * Get affiliate stats
 */
export function getAffiliateStats(wallet: string): {
  affiliate: Affiliate | null;
  recentCommissions: CommissionRecord[];
  pendingPayouts: PayoutRequest[];
  conversionRate: number;
} {
  const affiliate = getAffiliate(wallet);
  if (!affiliate) {
    return {
      affiliate: null,
      recentCommissions: [],
      pendingPayouts: [],
      conversionRate: 0,
    };
  }

  // Get recent commissions
  const recentCommissions = Array.from(storage.commissions.values())
    .filter(c => c.affiliateWallet === normalizeWallet(wallet))
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 20);

  // Get pending payouts
  const pendingPayouts = Array.from(storage.payouts.values())
    .filter(p => p.affiliateWallet === normalizeWallet(wallet) && p.status === 'pending')
    .sort((a, b) => b.requestedAt - a.requestedAt);

  // Calculate conversion rate
  const conversionRate = affiliate.totalClicks > 0
    ? (affiliate.totalConversions / affiliate.totalClicks) * 100
    : 0;

  return {
    affiliate,
    recentCommissions,
    pendingPayouts,
    conversionRate,
  };
}

// ============================================================================
// REFERRAL TRACKING
// ============================================================================

/**
 * Record a referral click (when someone visits with ?ref=CODE)
 */
export function recordReferralClick(
  code: string,
  refereeId: string,
  metadata?: { ip?: string; userAgent?: string; page?: string }
): { success: boolean; error?: string } {
  const affiliate = getAffiliateByCode(code);

  if (!affiliate) {
    return { success: false, error: 'Invalid referral code' };
  }

  if (affiliate.status !== 'active') {
    return { success: false, error: 'Affiliate account suspended' };
  }

  // Check if user already has attribution
  const existing = storage.attributions.get(refereeId);
  if (existing && existing.expiresAt > Date.now()) {
    // Already attributed, don't override
    return { success: true };
  }

  // Record click
  storage.clicks.push({
    code: code.toUpperCase(),
    ip: metadata?.ip,
    userAgent: metadata?.userAgent,
    page: metadata?.page,
    timestamp: Date.now(),
  });

  // Keep only last 1000 clicks
  if (storage.clicks.length > 1000) {
    storage.clicks.shift();
  }

  // Update affiliate stats
  affiliate.totalClicks += 1;

  // Create attribution
  const attribution: ReferralAttribution = {
    refereeId,
    referrerCode: code.toUpperCase(),
    referrerWallet: affiliate.wallet,
    attributedAt: Date.now(),
    expiresAt: Date.now() + (REFERRAL_CONFIG.ATTRIBUTION_WINDOW_DAYS * 24 * 60 * 60 * 1000),
    converted: false,
    conversionAmount: 0,
    commissionEarned: 0,
  };

  storage.attributions.set(refereeId, attribution);

  return { success: true };
}

/**
 * Get attribution for a user
 */
export function getAttribution(refereeId: string): ReferralAttribution | null {
  const attribution = storage.attributions.get(refereeId);

  if (!attribution) return null;

  // Check if expired
  if (attribution.expiresAt < Date.now()) {
    return null;
  }

  return attribution;
}

/**
 * Check if a wallet has already been referred (anti-fraud)
 */
export function isWalletAlreadyReferred(wallet: string): boolean {
  return storage.walletToReferrer.has(normalizeWallet(wallet));
}

// ============================================================================
// COMMISSION PROCESSING
// ============================================================================

/**
 * Process a payment and credit commission to referrer
 * Call this when a referred user makes a payment
 */
export function processReferralPayment(
  refereeId: string,
  refereeWallet: string,
  paymentTxHash: string,
  paymentAmount: number
): { credited: boolean; commission?: number; referrerWallet?: string; error?: string } {
  const normalizedWallet = normalizeWallet(refereeWallet);

  // Get attribution
  const attribution = getAttribution(refereeId);

  if (!attribution) {
    return { credited: false, error: 'No referral attribution' };
  }

  // Check if wallet already referred by someone else (anti-fraud)
  const existingReferrer = storage.walletToReferrer.get(normalizedWallet);
  if (existingReferrer && existingReferrer !== attribution.referrerWallet) {
    return { credited: false, error: 'Wallet already linked to different referrer' };
  }

  // Check max referrals per wallet
  if (!existingReferrer) {
    // First payment from this wallet - link it
    storage.walletToReferrer.set(normalizedWallet, attribution.referrerWallet);
  }

  // Get referrer affiliate
  const affiliate = storage.affiliates.get(attribution.referrerWallet);
  if (!affiliate || affiliate.status !== 'active') {
    return { credited: false, error: 'Referrer affiliate not active' };
  }

  // Calculate commission
  const commission = paymentAmount * REFERRAL_CONFIG.COMMISSION_RATE;

  // Create commission record
  const commissionRecord: CommissionRecord = {
    id: generateId(),
    affiliateWallet: affiliate.wallet,
    refereeWallet: normalizedWallet,
    paymentTxHash,
    paymentAmount,
    commissionAmount: commission,
    timestamp: Date.now(),
    status: commission > REFERRAL_CONFIG.MANUAL_REVIEW_THRESHOLD ? 'pending' : 'approved',
  };

  storage.commissions.set(commissionRecord.id, commissionRecord);

  // Update attribution
  attribution.refereeWallet = normalizedWallet;
  attribution.converted = true;
  attribution.conversionAmount += paymentAmount;
  attribution.commissionEarned += commission;

  // Update affiliate stats
  if (!existingReferrer) {
    affiliate.totalConversions += 1;
  }
  affiliate.totalEarnings += commission;
  affiliate.pendingPayout += commission;

  return {
    credited: true,
    commission,
    referrerWallet: affiliate.wallet,
  };
}

// ============================================================================
// PAYOUT MANAGEMENT
// ============================================================================

/**
 * Request a payout
 */
export function requestPayout(
  wallet: string
): { success: boolean; payout?: PayoutRequest; error?: string } {
  const affiliate = getAffiliate(wallet);

  if (!affiliate) {
    return { success: false, error: 'Affiliate not found' };
  }

  if (affiliate.status !== 'active') {
    return { success: false, error: 'Account not active' };
  }

  if (affiliate.pendingPayout < REFERRAL_CONFIG.MIN_PAYOUT) {
    return {
      success: false,
      error: `Minimum payout is $${REFERRAL_CONFIG.MIN_PAYOUT} USDC. Current balance: $${affiliate.pendingPayout.toFixed(2)}`,
    };
  }

  // Check for existing pending payout
  const existingPending = Array.from(storage.payouts.values())
    .find(p => p.affiliateWallet === normalizeWallet(wallet) && p.status === 'pending');

  if (existingPending) {
    return { success: false, error: 'You already have a pending payout request' };
  }

  const payout: PayoutRequest = {
    id: generateId(),
    affiliateWallet: normalizeWallet(wallet),
    amount: affiliate.pendingPayout,
    requestedAt: Date.now(),
    status: affiliate.pendingPayout > REFERRAL_CONFIG.MANUAL_REVIEW_THRESHOLD ? 'pending' : 'processing',
  };

  storage.payouts.set(payout.id, payout);

  // Reset pending payout (it's now in the payout request)
  affiliate.pendingPayout = 0;

  return { success: true, payout };
}

/**
 * Mark payout as completed (admin function)
 */
export function completePayout(
  payoutId: string,
  txHash: string
): { success: boolean; error?: string } {
  const payout = storage.payouts.get(payoutId);

  if (!payout) {
    return { success: false, error: 'Payout not found' };
  }

  payout.status = 'completed';
  payout.txHash = txHash;
  payout.processedAt = Date.now();

  // Update affiliate paidOut total
  const affiliate = storage.affiliates.get(payout.affiliateWallet);
  if (affiliate) {
    affiliate.paidOut += payout.amount;
  }

  return { success: true };
}

// ============================================================================
// LEADERBOARD
// ============================================================================

/**
 * Get top affiliates leaderboard
 */
export function getLeaderboard(limit: number = 10): Array<{
  rank: number;
  displayName: string;
  referralCode: string;
  conversions: number;
  earnings: number;
}> {
  const affiliates = Array.from(storage.affiliates.values())
    .filter(a => a.status === 'active' && a.totalConversions > 0)
    .sort((a, b) => b.totalEarnings - a.totalEarnings)
    .slice(0, limit);

  return affiliates.map((a, index) => ({
    rank: index + 1,
    displayName: a.displayName || `${a.wallet.slice(0, 6)}...${a.wallet.slice(-4)}`,
    referralCode: a.referralCode,
    conversions: a.totalConversions,
    earnings: a.totalEarnings,
  }));
}

/**
 * Get overall referral program stats
 */
export function getProgramStats(): {
  totalAffiliates: number;
  totalClicks: number;
  totalConversions: number;
  totalCommissionsPaid: number;
  averageConversionRate: number;
} {
  const affiliates = Array.from(storage.affiliates.values());
  const totalClicks = affiliates.reduce((sum, a) => sum + a.totalClicks, 0);
  const totalConversions = affiliates.reduce((sum, a) => sum + a.totalConversions, 0);
  const totalCommissionsPaid = affiliates.reduce((sum, a) => sum + a.paidOut, 0);

  return {
    totalAffiliates: affiliates.length,
    totalClicks,
    totalConversions,
    totalCommissionsPaid,
    averageConversionRate: totalClicks > 0 ? (totalConversions / totalClicks) * 100 : 0,
  };
}
