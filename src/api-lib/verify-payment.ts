import { createPublicClient, http, parseAbiItem, formatUnits } from "viem";
import { base } from "viem/chains";
import {
  BASE_RPC,
  USDC_ADDRESS,
  USDC_DECIMALS,
  PAYMENT_WALLET,
  TX_MAX_AGE_SECONDS,
} from "./config.js";

const client = createPublicClient({
  chain: base,
  transport: http(BASE_RPC),
});

// ERC20 Transfer event signature
const transferEvent = parseAbiItem(
  "event Transfer(address indexed from, address indexed to, uint256 value)"
);

export interface PaymentVerification {
  valid: boolean;
  error?: string;
  amount?: number;
  from?: string;
  timestamp?: number;
}

export async function verifyUSDCPayment(
  txHash: string,
  requiredAmount: number
): Promise<PaymentVerification> {
  try {
    // Validate tx hash format
    if (!/^0x[a-fA-F0-9]{64}$/.test(txHash)) {
      return { valid: false, error: "Invalid transaction hash format" };
    }

    // Get transaction receipt
    const receipt = await client.getTransactionReceipt({
      hash: txHash as `0x${string}`,
    });

    if (!receipt) {
      return { valid: false, error: "Transaction not found" };
    }

    if (receipt.status !== "success") {
      return { valid: false, error: "Transaction failed" };
    }

    // Get block for timestamp
    const block = await client.getBlock({ blockNumber: receipt.blockNumber });
    const txTimestamp = Number(block.timestamp);
    const now = Math.floor(Date.now() / 1000);

    // Check tx age (anti-replay)
    if (now - txTimestamp > TX_MAX_AGE_SECONDS) {
      return {
        valid: false,
        error: `Transaction too old (max ${TX_MAX_AGE_SECONDS}s)`,
      };
    }

    // Find USDC Transfer event to our wallet
    const transferLogs = receipt.logs.filter(
      (log) =>
        log.address.toLowerCase() === USDC_ADDRESS.toLowerCase() &&
        log.topics[0] ===
          "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" // Transfer event signature
    );

    if (transferLogs.length === 0) {
      return { valid: false, error: "No USDC transfer found in transaction" };
    }

    // Check if any transfer is to our wallet with sufficient amount
    for (const log of transferLogs) {
      // topics[2] is the 'to' address (padded to 32 bytes)
      const toAddress = "0x" + log.topics[2]!.slice(26);

      if (toAddress.toLowerCase() === PAYMENT_WALLET.toLowerCase()) {
        // Decode amount from data
        const amount = BigInt(log.data);
        const amountUSDC = Number(formatUnits(amount, USDC_DECIMALS));

        if (amountUSDC >= requiredAmount) {
          // Decode 'from' address
          const fromAddress = "0x" + log.topics[1]!.slice(26);

          return {
            valid: true,
            amount: amountUSDC,
            from: fromAddress,
            timestamp: txTimestamp,
          };
        } else {
          return {
            valid: false,
            error: `Insufficient amount: paid $${amountUSDC}, required $${requiredAmount}`,
          };
        }
      }
    }

    return {
      valid: false,
      error: `Payment not sent to correct wallet (${PAYMENT_WALLET})`,
    };
  } catch (error) {
    console.error("Payment verification error:", error);
    return {
      valid: false,
      error: "Failed to verify transaction on Base network",
    };
  }
}
