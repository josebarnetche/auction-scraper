/**
 * API Stats & Monitoring Endpoint
 *
 * GET /api/v1/stats - Get API usage statistics
 * GET /api/v1/stats?dashboard=true - Get full dashboard data
 * GET /api/v1/stats?date=2024-01-15 - Get stats for specific date
 * GET /api/v1/stats?alerts=true - Get recent security alerts
 *
 * Protected with admin API key (STATS_API_KEY env var)
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getRequestLogger } from "../lib/request-logger.js";
import { getAbusePrevention } from "../lib/abuse-prevention.js";
import { getRateLimiter, getClientIP } from "../lib/rate-limiter.js";

// Admin API key for accessing stats
const STATS_API_KEY = process.env.STATS_API_KEY;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
    return res.status(200).end();
  }

  // Check authentication
  const authHeader = req.headers.authorization;
  const providedKey = authHeader?.replace("Bearer ", "");

  if (!STATS_API_KEY) {
    // If no key configured, only allow in development
    if (process.env.NODE_ENV === "production") {
      return res.status(503).json({
        error: "Stats endpoint not configured",
        message: "Set STATS_API_KEY environment variable",
      });
    }
  } else if (providedKey !== STATS_API_KEY) {
    return res.status(401).json({
      error: "Unauthorized",
      message: "Invalid or missing API key",
    });
  }

  const requestLogger = getRequestLogger();
  const abusePrevention = getAbusePrevention();
  const rateLimiter = getRateLimiter();

  try {
    const { dashboard, date, alerts, errors, requests } = req.query;

    // Get security alerts
    if (alerts === "true") {
      const recentAlerts = await abusePrevention.getRecentAlerts(100);
      return res.status(200).json({
        success: true,
        alerts: recentAlerts,
      });
    }

    // Get recent errors
    if (errors === "true") {
      const recentErrors = await requestLogger.getRecentErrors(100);
      return res.status(200).json({
        success: true,
        errors: recentErrors,
      });
    }

    // Get recent requests
    if (requests === "true") {
      const count = parseInt(req.query.count as string) || 100;
      const recentRequests = await requestLogger.getRecentRequests(count);
      return res.status(200).json({
        success: true,
        requests: recentRequests,
      });
    }

    // Get full dashboard
    if (dashboard === "true") {
      const dashboardData = await requestLogger.getDashboard(date as string);

      // Add security alerts to dashboard
      const recentAlerts = await abusePrevention.getRecentAlerts(10);

      return res.status(200).json({
        success: true,
        dashboard: {
          ...dashboardData,
          security: {
            recentAlerts,
            alertCount: recentAlerts.length,
          },
        },
      });
    }

    // Default: Get basic stats for a date
    const stats = await requestLogger.getStats(date as string);

    return res.status(200).json({
      success: true,
      date: date || new Date().toISOString().split("T")[0],
      stats,
      _links: {
        dashboard: "/api/v1/stats?dashboard=true",
        alerts: "/api/v1/stats?alerts=true",
        errors: "/api/v1/stats?errors=true",
        requests: "/api/v1/stats?requests=true",
      },
    });
  } catch (error) {
    console.error("Stats endpoint error:", error);
    return res.status(500).json({
      error: "Internal error",
      message: "Failed to fetch stats",
    });
  }
}
