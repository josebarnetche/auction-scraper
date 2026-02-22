/**
 * Email Subscription API Endpoint
 *
 * POST /api/v1/subscribe
 *
 * Subscribes an email to the daily digest with optional preferences.
 * Implements double opt-in for compliance.
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  createSubscriber,
  confirmSubscriber,
  updatePreferences,
  type SubscriberPreferences,
} from "../lib/subscriber-store.js";

// Simple email validation
function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

// Validate preferences
function validatePreferences(prefs: any): Partial<SubscriberPreferences> {
  const valid: Partial<SubscriberPreferences> = {};

  const validCategories = ["vehicles", "real_estate", "machinery", "general_goods", "other"];
  if (Array.isArray(prefs.categories)) {
    valid.categories = prefs.categories.filter((c: string) => validCategories.includes(c));
  }

  const validProvinces = [
    "Buenos Aires", "CABA", "Cordoba", "Santa Fe", "Mendoza",
    "Tucuman", "Entre Rios", "Salta", "Misiones", "Chaco",
    "Corrientes", "Santiago del Estero", "San Juan", "Jujuy",
    "Rio Negro", "Neuquen", "Formosa", "Chubut", "San Luis",
    "Catamarca", "La Rioja", "La Pampa", "Santa Cruz", "Tierra del Fuego"
  ];
  if (Array.isArray(prefs.provinces)) {
    valid.provinces = prefs.provinces.filter((p: string) => validProvinces.includes(p));
  }

  if (typeof prefs.priceMinUsd === "number" && prefs.priceMinUsd >= 0) {
    valid.priceMinUsd = prefs.priceMinUsd;
  }

  if (typeof prefs.priceMaxUsd === "number" && prefs.priceMaxUsd >= 0) {
    valid.priceMaxUsd = prefs.priceMaxUsd;
  }

  const validFrequencies = ["daily", "weekly", "realtime"];
  if (validFrequencies.includes(prefs.digestFrequency)) {
    valid.digestFrequency = prefs.digestFrequency;
  }

  if (typeof prefs.endingTodayAlerts === "boolean") {
    valid.endingTodayAlerts = prefs.endingTodayAlerts;
  }

  if (typeof prefs.opportunitiesOnly === "boolean") {
    valid.opportunitiesOnly = prefs.opportunitiesOnly;
  }

  return valid;
}

// Rate limiting (simple in-memory)
const subscribeAttempts: Map<string, { count: number; resetAt: number }> = new Map();
const MAX_ATTEMPTS = 5;
const RATE_LIMIT_WINDOW = 3600000; // 1 hour

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const record = subscribeAttempts.get(ip);

  if (!record || now > record.resetAt) {
    subscribeAttempts.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW });
    return true;
  }

  if (record.count >= MAX_ATTEMPTS) {
    return false;
  }

  record.count += 1;
  return true;
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // GET: Confirm subscription (double opt-in)
  if (req.method === "GET") {
    const { token, action } = req.query;

    if (action === "confirm" && typeof token === "string") {
      const subscriber = await confirmSubscriber(token);
      if (subscriber) {
        // Return HTML confirmation page
        return res.status(200).send(`
          <!DOCTYPE html>
          <html lang="es">
          <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Suscripcion Confirmada - Subasto</title>
            <style>
              body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #030303;
                color: #fff;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
              }
              .container {
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                max-width: 500px;
              }
              h1 { color: #eab308; margin-bottom: 20px; }
              p { color: #a1a1aa; line-height: 1.6; }
              .check {
                font-size: 64px;
                margin-bottom: 20px;
              }
              a {
                color: #eab308;
                text-decoration: none;
              }
              a:hover { text-decoration: underline; }
            </style>
          </head>
          <body>
            <div class="container">
              <div class="check">&#10003;</div>
              <h1>Suscripcion Confirmada</h1>
              <p>Tu email <strong>${subscriber.email}</strong> ha sido confirmado.</p>
              <p>Recibiras el digest diario con las mejores oportunidades de subastas.</p>
              <p style="margin-top: 30px;">
                <a href="https://subasto.com.ar">Volver a Subasto.com.ar</a>
              </p>
            </div>
          </body>
          </html>
        `);
      } else {
        return res.status(400).send(`
          <!DOCTYPE html>
          <html lang="es">
          <head>
            <meta charset="UTF-8">
            <title>Error - Subasto</title>
            <style>
              body {
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                background: #030303;
                color: #fff;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
              }
              .container { text-align: center; padding: 40px; }
              h1 { color: #ef4444; }
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Link Invalido</h1>
              <p>Este link de confirmacion es invalido o ya fue usado.</p>
              <p><a href="https://subasto.com.ar" style="color:#eab308;">Volver a Subasto</a></p>
            </div>
          </body>
          </html>
        `);
      }
    }

    return res.status(400).json({
      error: "Invalid request",
      message: "Use POST to subscribe or GET with ?action=confirm&token=...",
    });
  }

  // POST: Create new subscription
  if (req.method === "POST") {
    // Rate limiting
    const ip = (req.headers["x-forwarded-for"] as string)?.split(",")[0] || "unknown";
    if (!checkRateLimit(ip)) {
      return res.status(429).json({
        error: "Too many requests",
        message: "Please wait before subscribing again",
      });
    }

    let body: any;
    try {
      body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
    } catch {
      return res.status(400).json({
        error: "Invalid JSON",
        message: "Request body must be valid JSON",
      });
    }

    const { email, preferences } = body;

    // Validate email
    if (!email || !isValidEmail(email)) {
      return res.status(400).json({
        error: "Invalid email",
        message: "Please provide a valid email address",
      });
    }

    // Validate and sanitize preferences
    const validPrefs = preferences ? validatePreferences(preferences) : {};

    try {
      const { subscriber, isNew } = await createSubscriber(email, validPrefs);

      if (subscriber.status === "active") {
        // Already confirmed - update preferences if provided
        if (Object.keys(validPrefs).length > 0) {
          await updatePreferences(email, validPrefs);
        }
        return res.status(200).json({
          success: true,
          message: "You are already subscribed. Preferences updated.",
          status: "active",
        });
      }

      // Send confirmation email (in production, integrate with email service)
      const confirmUrl = `https://subasto.com.ar/api/v1/subscribe?action=confirm&token=${subscriber.confirmToken}`;

      // Log for now (replace with actual email sending)
      console.log(`[Subscribe] Confirmation email for ${email}: ${confirmUrl}`);

      // TODO: Send actual email using Resend/SendGrid
      // await sendConfirmationEmail(email, confirmUrl);

      return res.status(201).json({
        success: true,
        message: isNew
          ? "Please check your email to confirm your subscription"
          : "Confirmation email resent. Please check your inbox.",
        status: "pending",
        // Only in dev mode, include confirm URL for testing
        ...(process.env.NODE_ENV === "development" && { _debug_confirmUrl: confirmUrl }),
      });
    } catch (error) {
      console.error("Subscription error:", error);
      return res.status(500).json({
        error: "Subscription failed",
        message: "An error occurred. Please try again later.",
      });
    }
  }

  return res.status(405).json({
    error: "Method not allowed",
    message: "Use POST to subscribe",
  });
}
