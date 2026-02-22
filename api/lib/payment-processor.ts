/**
 * Payment Processor for Subasto API
 *
 * Handles payment verification, credit management, AND referral attribution
 * in a unified flow. Use this instead of calling credit-manager directly
 * when processing payments from users.
 *
 * Flow:
 * 1. Verify USDC payment on-chain
 * 2. Credit the user's account (credits or subscription)
 * 3. Check for referral attribution
 * 4. Credit referrer if applicable (10% commission)
 */

import { verifyUSDCPayment, PaymentVerification } from "./verify-payment.js";
import {
  addCredits,
  activateSubscription,
  isTxUsed,
  calculateCreditsForAmount,
  getSubscriptionForAmount,
  CreditAccount,
} from "./credit-manager.js";
import {
  processReferralPayment,
  getAttribution,
  REFERRAL_CONFIG,
} from "./referral-tracker.js";

export interface PaymentResult {
  success: boolean;
  error?: string;

  // Payment details
  payment?: {
    txHash: string;
    amount: number;
    from: string;
  };

  // What was purchased
  purchase?: {
    type: "credits" | "subscription";
    credits?: number;
    bonus?: number;
    subscriptionTier?: string;
    expiresAt?: string;
  };

  // Account state after purchase
  account?: CreditAccount;

  // Referral info
  referral?: {
    credited: boolean;
    referrerWallet?: string;
    commission?: number;
    message?: string;
  };
}

/**
 * Process a payment with full referral integration
 *
 * @param txHash - Transaction hash of USDC payment
 * @param userId - User's localStorage ID (from SubastoReferral.getUserId())
 * @param requiredAmount - Minimum expected payment amount
 */
export async function processPayment(
  txHash: string,
  userId: string | undefined,
  requiredAmount: number = 0.01
): Promise<PaymentResult> {
  // 1. Check if tx already used
  if (isTxUsed(txHash)) {
    return {
      success: false,
      error: "Transaction already used",
    };
  }

  // 2. Verify payment on-chain
  const verification = await verifyUSDCPayment(txHash, requiredAmount);

  if (!verification.valid) {
    return {
      success: false,
      error: verification.error,
    };
  }

  const payerWallet = verification.from!;
  const amount = verification.amount!;

  // 3. Determine what was purchased (credits or subscription)
  const subscription = getSubscriptionForAmount(amount);
  const creditPackage = calculateCreditsForAmount(amount);

  let purchase: PaymentResult["purchase"];
  let account: CreditAccount;

  if (subscription) {
    // Subscription purchase
    account = activateSubscription(
      payerWallet,
      txHash,
      subscription.tier,
      amount
    );

    purchase = {
      type: "subscription",
      subscriptionTier: subscription.tier,
      expiresAt: account.subscriptionExpiresAt
        ? new Date(account.subscriptionExpiresAt).toISOString()
        : undefined,
    };
  } else if (creditPackage) {
    // Credit purchase
    account = addCredits(
      payerWallet,
      txHash,
      creditPackage.packageId,
      creditPackage.credits,
      amount
    );

    purchase = {
      type: "credits",
      credits: creditPackage.credits,
      bonus: creditPackage.bonus,
    };
  } else {
    // Fallback - minimum payment for single request (legacy mode)
    account = addCredits(payerWallet, txHash, "single", 1, amount);
    purchase = {
      type: "credits",
      credits: 1,
      bonus: 0,
    };
  }

  // 4. Process referral if user has attribution
  let referral: PaymentResult["referral"] = { credited: false };

  if (userId) {
    const attribution = getAttribution(userId);

    if (attribution) {
      const referralResult = processReferralPayment(
        userId,
        payerWallet,
        txHash,
        amount
      );

      if (referralResult.credited) {
        referral = {
          credited: true,
          referrerWallet: referralResult.referrerWallet,
          commission: referralResult.commission,
          message: `Referrer earned $${referralResult.commission?.toFixed(2)} commission`,
        };
      } else {
        referral = {
          credited: false,
          message: referralResult.error,
        };
      }
    }
  }

  return {
    success: true,
    payment: {
      txHash,
      amount,
      from: payerWallet,
    },
    purchase,
    account,
    referral,
  };
}

/**
 * Process a simple per-request payment (legacy mode)
 * Used for endpoints that don't use the credit system
 */
export async function processLegacyPayment(
  txHash: string,
  userId: string | undefined,
  requiredAmount: number
): Promise<{
  valid: boolean;
  error?: string;
  amount?: number;
  from?: string;
  referralCredited?: boolean;
}> {
  // Verify payment
  const verification = await verifyUSDCPayment(txHash, requiredAmount);

  if (!verification.valid) {
    return { valid: false, error: verification.error };
  }

  // Process referral if applicable
  let referralCredited = false;
  if (userId && verification.from) {
    const result = processReferralPayment(
      userId,
      verification.from,
      txHash,
      verification.amount!
    );
    referralCredited = result.credited;
  }

  return {
    valid: true,
    amount: verification.amount,
    from: verification.from,
    referralCredited,
  };
}

/**
 * Get referral info to include in API responses
 * Helps users understand their referral status
 */
export function getReferralInfo(userId: string | undefined): {
  hasReferral: boolean;
  referrerCode?: string;
  expiresIn?: string;
  commissionRate: string;
} {
  if (!userId) {
    return {
      hasReferral: false,
      commissionRate: `${REFERRAL_CONFIG.COMMISSION_RATE * 100}%`,
    };
  }

  const attribution = getAttribution(userId);

  if (!attribution) {
    return {
      hasReferral: false,
      commissionRate: `${REFERRAL_CONFIG.COMMISSION_RATE * 100}%`,
    };
  }

  const daysRemaining = Math.ceil(
    (attribution.expiresAt - Date.now()) / (24 * 60 * 60 * 1000)
  );

  return {
    hasReferral: true,
    referrerCode: attribution.referrerCode,
    expiresIn: `${daysRemaining} days`,
    commissionRate: `${REFERRAL_CONFIG.COMMISSION_RATE * 100}%`,
  };
}
