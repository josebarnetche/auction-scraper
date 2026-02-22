/**
 * Email Unsubscribe API Endpoint
 *
 * GET /api/v1/unsubscribe?token=...
 *
 * Unsubscribes a user using their unique unsubscribe token.
 * No authentication required (token is the auth).
 * GDPR compliant - easy one-click unsubscribe.
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";
import {
  unsubscribeByToken,
  deleteSubscriberData,
  exportSubscriberData,
} from "../lib/subscriber-store.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  const { token, action } = req.query;

  // Validate token
  if (!token || typeof token !== "string") {
    return res.status(400).send(generateErrorPage(
      "Link Invalido",
      "Este link de desuscripcion es invalido."
    ));
  }

  // GET: Show unsubscribe confirmation page or process unsubscribe
  if (req.method === "GET") {
    // If action=confirm, process the unsubscribe
    if (action === "confirm") {
      const subscriber = await unsubscribeByToken(token);

      if (subscriber) {
        return res.status(200).send(generateSuccessPage(
          "Desuscripcion Exitosa",
          `El email <strong>${maskEmail(subscriber.email)}</strong> ha sido removido de nuestra lista.`,
          "Ya no recibiras mas emails de Subasto."
        ));
      } else {
        return res.status(400).send(generateErrorPage(
          "Link Invalido",
          "Este link de desuscripcion es invalido o ya fue usado."
        ));
      }
    }

    // GDPR: Delete all data
    if (action === "delete-data") {
      // First unsubscribe
      const subscriber = await unsubscribeByToken(token);
      if (subscriber) {
        // Then delete all data
        await deleteSubscriberData(subscriber.email);
        return res.status(200).send(generateSuccessPage(
          "Datos Eliminados",
          "Todos tus datos han sido eliminados permanentemente.",
          "Cumplimos con tu derecho al olvido (GDPR Art. 17)."
        ));
      } else {
        return res.status(400).send(generateErrorPage(
          "Error",
          "No se pudo procesar tu solicitud."
        ));
      }
    }

    // GDPR: Export data
    if (action === "export-data") {
      // We need email for this, so redirect to form
      return res.status(200).send(generateDataExportPage(token));
    }

    // Default: Show unsubscribe confirmation page
    return res.status(200).send(generateUnsubscribePage(token));
  }

  // POST: Process data export request
  if (req.method === "POST") {
    let body: any;
    try {
      body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
    } catch {
      return res.status(400).json({ error: "Invalid JSON" });
    }

    if (action === "export-data" && body.email) {
      const data = await exportSubscriberData(body.email);
      if (data) {
        // Return JSON data download
        res.setHeader("Content-Type", "application/json");
        res.setHeader("Content-Disposition", `attachment; filename="subasto-data-export.json"`);
        return res.status(200).json({
          exported_at: new Date().toISOString(),
          data: {
            email: data.email,
            created_at: data.createdAt,
            confirmed_at: data.confirmedAt,
            preferences: data.preferences,
            digest_count: data.digestCount,
            status: data.status,
          },
        });
      }
      return res.status(404).json({ error: "Email not found" });
    }

    return res.status(400).json({ error: "Invalid action" });
  }

  return res.status(405).json({ error: "Method not allowed" });
}

// Helper to mask email for privacy
function maskEmail(email: string): string {
  const [local, domain] = email.split("@");
  if (local.length <= 2) {
    return `${local[0]}***@${domain}`;
  }
  return `${local[0]}***${local.slice(-1)}@${domain}`;
}

// HTML page generators
function generateUnsubscribePage(token: string): string {
  return `
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Desuscribirse - Subasto</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #030303;
      color: #fff;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
      padding: 20px;
    }
    .container {
      text-align: center;
      padding: 40px;
      background: rgba(255,255,255,0.05);
      border-radius: 12px;
      max-width: 500px;
      width: 100%;
    }
    h1 { color: #fff; margin-bottom: 10px; }
    .subtitle { color: #a1a1aa; margin-bottom: 30px; }
    .btn {
      display: inline-block;
      padding: 14px 28px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 600;
      margin: 10px;
      cursor: pointer;
      border: none;
      font-size: 16px;
    }
    .btn-danger {
      background: #dc2626;
      color: white;
    }
    .btn-danger:hover { background: #b91c1c; }
    .btn-secondary {
      background: rgba(255,255,255,0.1);
      color: #a1a1aa;
    }
    .btn-secondary:hover { background: rgba(255,255,255,0.15); }
    .divider {
      border-top: 1px solid rgba(255,255,255,0.1);
      margin: 30px 0;
    }
    .gdpr-links {
      font-size: 14px;
      color: #71717a;
    }
    .gdpr-links a {
      color: #a1a1aa;
      text-decoration: none;
    }
    .gdpr-links a:hover { color: #fff; }
    .icon { font-size: 48px; margin-bottom: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="icon">&#128233;</div>
    <h1>Desuscribirse</h1>
    <p class="subtitle">Lamentamos verte partir</p>

    <p style="color: #a1a1aa; margin-bottom: 30px;">
      Si haces click en el boton, dejaras de recibir nuestros emails de oportunidades de subastas.
    </p>

    <a href="/api/v1/unsubscribe?token=${token}&action=confirm" class="btn btn-danger">
      Desuscribirme
    </a>
    <a href="https://subasto.com.ar" class="btn btn-secondary">
      Volver a Subasto
    </a>

    <div class="divider"></div>

    <div class="gdpr-links">
      <p>Tus derechos de privacidad:</p>
      <a href="/api/v1/unsubscribe?token=${token}&action=export-data">Exportar mis datos</a>
      &nbsp;|&nbsp;
      <a href="/api/v1/unsubscribe?token=${token}&action=delete-data">Eliminar todos mis datos</a>
    </div>
  </div>
</body>
</html>
`;
}

function generateSuccessPage(title: string, message: string, subtitle: string): string {
  return `
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} - Subasto</title>
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
    h1 { color: #22c55e; margin-bottom: 20px; }
    p { color: #a1a1aa; line-height: 1.6; }
    .check { font-size: 64px; margin-bottom: 20px; }
    a { color: #eab308; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <div class="check">&#10003;</div>
    <h1>${title}</h1>
    <p>${message}</p>
    <p style="margin-top: 10px; font-size: 14px;">${subtitle}</p>
    <p style="margin-top: 30px;">
      <a href="https://subasto.com.ar">Volver a Subasto.com.ar</a>
    </p>
  </div>
</body>
</html>
`;
}

function generateErrorPage(title: string, message: string): string {
  return `
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} - Subasto</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #030303;
      color: #fff;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }
    .container { text-align: center; padding: 40px; }
    h1 { color: #ef4444; }
    a { color: #eab308; }
  </style>
</head>
<body>
  <div class="container">
    <h1>${title}</h1>
    <p>${message}</p>
    <p style="margin-top: 20px;"><a href="https://subasto.com.ar">Volver a Subasto</a></p>
  </div>
</body>
</html>
`;
}

function generateDataExportPage(token: string): string {
  return `
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Exportar Datos - Subasto</title>
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
    .container {
      text-align: center;
      padding: 40px;
      background: rgba(255,255,255,0.05);
      border-radius: 12px;
      max-width: 400px;
    }
    h1 { margin-bottom: 20px; }
    input {
      width: 100%;
      padding: 12px;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 8px;
      background: rgba(255,255,255,0.05);
      color: #fff;
      font-size: 16px;
      margin-bottom: 15px;
    }
    button {
      width: 100%;
      padding: 14px;
      background: #eab308;
      color: #000;
      border: none;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
    }
    button:hover { background: #ca9a06; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Exportar Datos</h1>
    <p style="color:#a1a1aa; margin-bottom:20px;">Ingresa tu email para descargar tus datos</p>
    <form action="/api/v1/unsubscribe?token=${token}&action=export-data" method="POST">
      <input type="email" name="email" placeholder="tu@email.com" required>
      <button type="submit">Descargar mis datos</button>
    </form>
  </div>
</body>
</html>
`;
}
