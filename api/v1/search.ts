import type { VercelRequest, VercelResponse } from "@vercel/node";
import { readFileSync } from "fs";
import { join } from "path";
import { verifyUSDCPayment } from "../lib/verify-payment.js";
import { PAYMENT_WALLET } from "../lib/config.js";

// AI Search pricing
const AI_SEARCH_PRICE = 0.005; // $0.005 USDC per AI-enhanced search

// Simple in-memory cache for used tx hashes
const usedTxHashes = new Set<string>();

// Popular searches (would come from analytics in production)
const POPULAR_SEARCHES = [
  { query: "Toyota Hilux", count: 156, category: "vehicles" },
  { query: "Departamento CABA", count: 134, category: "real_estate" },
  { query: "Ford Ranger", count: 128, category: "vehicles" },
  { query: "Volkswagen Amarok", count: 112, category: "vehicles" },
  { query: "Terreno Cordoba", count: 98, category: "real_estate" },
  { query: "Camioneta 4x4", count: 87, category: "vehicles" },
  { query: "Autoelevador", count: 76, category: "machinery" },
  { query: "Casa Buenos Aires", count: 72, category: "real_estate" },
  { query: "Generador", count: 65, category: "machinery" },
  { query: "Renault Duster", count: 61, category: "vehicles" },
];

// Spanish synonym groups
const SYNONYMS: Record<string, string[]> = {
  auto: ["coche", "vehiculo", "automovil", "carro"],
  camioneta: ["pickup", "4x4", "suv", "utilitario"],
  camion: ["truck", "furgon"],
  moto: ["motocicleta", "scooter"],
  casa: ["vivienda", "hogar", "residencia"],
  departamento: ["depto", "dpto", "apartamento", "piso"],
  terreno: ["lote", "parcela", "predio"],
  local: ["comercio", "negocio", "tienda", "oficina"],
  galpon: ["deposito", "bodega", "nave"],
  tractor: ["maquinaria agricola"],
  generador: ["grupo electrogeno"],
  autoelevador: ["montacargas", "elevador", "forklift"],
};

// Common brand misspellings
const BRAND_CORRECTIONS: Record<string, string> = {
  toyoya: "toyota",
  toytoa: "toyota",
  volkswaguen: "volkswagen",
  volskwagen: "volkswagen",
  folswagen: "volkswagen",
  wolkswagen: "volkswagen",
  peugot: "peugeot",
  peujeot: "peugeot",
  citreon: "citroen",
  renaut: "renault",
  chevroled: "chevrolet",
  chervolet: "chevrolet",
  nissam: "nissan",
  mitshubishi: "mitsubishi",
  hyunday: "hyundai",
  hundai: "hyundai",
  frod: "ford",
  mercedez: "mercedes",
  mersedes: "mercedes",
};

// Category keywords
const CATEGORY_KEYWORDS: Record<string, string[]> = {
  vehicles: [
    "auto", "coche", "vehiculo", "camioneta", "camion", "moto", "pickup",
    "sedan", "suv", "4x4", "ford", "chevrolet", "toyota", "volkswagen",
    "renault", "fiat", "peugeot", "honda", "nissan", "hyundai", "mercedes"
  ],
  real_estate: [
    "casa", "departamento", "depto", "terreno", "lote", "inmueble",
    "propiedad", "local", "oficina", "galpon", "campo", "hectarea"
  ],
  machinery: [
    "maquinaria", "maquina", "tractor", "excavadora", "generador",
    "compresor", "autoelevador", "grua", "industrial", "herramienta"
  ],
  general_goods: [
    "mueble", "electrodomestico", "ropa", "electronico", "computadora",
    "notebook", "celular"
  ],
};

interface SearchFilters {
  category?: string;
  minPrice?: number;
  maxPrice?: number;
  currency: string;
  location?: string;
  source?: string;
  keywords: string[];
  sortBy?: string;
}

interface Listing {
  id: string;
  title: string;
  description?: string;
  category: string;
  base_price: number;
  base_price_usd?: number;
  currency: string;
  source: string;
  source_url: string;
  discount_percent?: number;
  market_typical_usd?: number;
  ends_at?: string;
  images?: string[];
  location?: { province?: string; city?: string };
}

interface SearchResult extends Listing {
  relevance_score: number;
  match_reasons: string[];
  highlight_terms: string[];
}

// Normalize text for comparison
function normalizeText(text: string): string {
  if (!text) return "";
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

// Correct common typos
function correctTypos(word: string): string {
  const lower = word.toLowerCase();
  return BRAND_CORRECTIONS[lower] || word;
}

// Expand word with synonyms
function expandSynonyms(word: string): string[] {
  const normalized = normalizeText(word);
  const result = [normalized];

  for (const [key, values] of Object.entries(SYNONYMS)) {
    const keyNorm = normalizeText(key);
    const valuesNorm = values.map(normalizeText);

    if (normalized === keyNorm || valuesNorm.includes(normalized)) {
      result.push(keyNorm, ...valuesNorm);
    }
  }

  return [...new Set(result)];
}

// Detect category from query
function detectCategory(query: string): string | undefined {
  const queryNorm = normalizeText(query);
  let bestCategory: string | undefined;
  let bestScore = 0;

  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    let score = 0;
    for (const keyword of keywords) {
      if (queryNorm.includes(normalizeText(keyword))) {
        score += keyword.length;
      }
    }
    if (score > bestScore) {
      bestScore = score;
      bestCategory = category;
    }
  }

  return bestCategory;
}

// Extract price filters from query
function extractPriceFilters(query: string): { min?: number; max?: number; currency: string } {
  let min: number | undefined;
  let max: number | undefined;
  let currency = "USD";

  // Detect currency
  if (/peso|ars|\$ar/i.test(query)) {
    currency = "ARS";
  }

  // Under/menos de/hasta patterns
  const underMatch = query.match(/(?:under|menos de|hasta|debajo de|max|maximo)\s*\$?\s*([\d,.]+)\s*(?:k|mil)?/i);
  if (underMatch) {
    max = parseFloat(underMatch[1].replace(/[,.]/g, ""));
    if (/k|mil/i.test(underMatch[0])) max *= 1000;
  }

  // Over/mas de/desde patterns
  const overMatch = query.match(/(?:over|mas de|desde|arriba de|min|minimo)\s*\$?\s*([\d,.]+)\s*(?:k|mil)?/i);
  if (overMatch) {
    min = parseFloat(overMatch[1].replace(/[,.]/g, ""));
    if (/k|mil/i.test(overMatch[0])) min *= 1000;
  }

  // Range pattern: $X - $Y
  const rangeMatch = query.match(/\$?\s*([\d,.]+)\s*(?:k|mil)?\s*[-–—a]\s*\$?\s*([\d,.]+)\s*(?:k|mil)?/i);
  if (rangeMatch) {
    min = parseFloat(rangeMatch[1].replace(/[,.]/g, ""));
    max = parseFloat(rangeMatch[2].replace(/[,.]/g, ""));
    if (/k|mil/i.test(rangeMatch[0])) {
      min *= 1000;
      max *= 1000;
    }
  }

  return { min, max, currency };
}

// Parse query into filters
function parseQuery(query: string): SearchFilters {
  const priceFilters = extractPriceFilters(query);
  const category = detectCategory(query);

  // Extract keywords
  const words = query.split(/\s+/);
  const keywords: string[] = [];
  const stopWords = new Set(["de", "en", "con", "para", "por", "y", "o", "un", "una", "el", "la", "los", "las", "a"]);
  const filterWords = new Set(["under", "over", "menos", "mas", "hasta", "desde", "entre", "barato", "caro"]);

  for (const word of words) {
    if (/^[$\d,.]+[km]?$/i.test(word)) continue;
    if (stopWords.has(word.toLowerCase())) continue;
    if (filterWords.has(word.toLowerCase())) continue;

    const corrected = correctTypos(word);
    keywords.push(corrected);
  }

  // Detect sort preference
  let sortBy: string | undefined;
  if (/terminan pronto|ending soon|urgente|rapido/i.test(query)) {
    sortBy = "ending_soon";
  } else if (/descuento|oferta|deal|oportunidad/i.test(query)) {
    sortBy = "discount";
  }

  return {
    category,
    minPrice: priceFilters.min,
    maxPrice: priceFilters.max,
    currency: priceFilters.currency,
    keywords,
    sortBy,
  };
}

// Calculate string similarity
function similarity(a: string, b: string): number {
  if (a === b) return 1;
  if (a.length === 0 || b.length === 0) return 0;

  const longer = a.length > b.length ? a : b;
  const shorter = a.length > b.length ? b : a;

  if (longer.includes(shorter)) return shorter.length / longer.length;

  // Simple character match ratio
  let matches = 0;
  for (let i = 0; i < shorter.length; i++) {
    if (longer[i] === shorter[i]) matches++;
  }
  return matches / longer.length;
}

// Score a listing
function scoreListing(
  listing: Listing,
  filters: SearchFilters,
  expandedKeywords: string[],
  blueDollarRate: number
): { score: number; reasons: string[]; highlights: string[] } {
  let score = 0;
  const reasons: string[] = [];
  const highlights: string[] = [];

  const titleNorm = normalizeText(listing.title);
  const descNorm = normalizeText(listing.description || "");
  const allText = `${titleNorm} ${descNorm}`;

  // Category filter
  if (filters.category && listing.category !== filters.category) {
    return { score: 0, reasons: [], highlights: [] };
  }
  if (filters.category) {
    score += 10;
    reasons.push(`category:${filters.category}`);
  }

  // Source filter
  if (filters.source && listing.source !== filters.source) {
    return { score: 0, reasons: [], highlights: [] };
  }

  // Price filters
  let priceUsd = listing.base_price_usd || 0;
  if (!priceUsd && listing.base_price) {
    priceUsd = listing.currency === "ARS"
      ? listing.base_price / blueDollarRate
      : listing.base_price;
  }

  if (filters.minPrice !== undefined) {
    const filterPrice = filters.currency === "ARS"
      ? filters.minPrice / blueDollarRate
      : filters.minPrice;
    if (priceUsd < filterPrice) {
      return { score: 0, reasons: [], highlights: [] };
    }
    score += 5;
  }

  if (filters.maxPrice !== undefined) {
    const filterPrice = filters.currency === "ARS"
      ? filters.maxPrice / blueDollarRate
      : filters.maxPrice;
    if (priceUsd > filterPrice) {
      return { score: 0, reasons: [], highlights: [] };
    }
    score += 5;
    reasons.push(`price_under:${filters.maxPrice}`);
  }

  // Keyword matching
  for (const keyword of expandedKeywords) {
    if (!keyword) continue;

    if (titleNorm.includes(keyword)) {
      score += 30;
      highlights.push(keyword);
      if (!reasons.includes(`keyword:${keyword}`)) {
        reasons.push(`keyword:${keyword}`);
      }
    } else if (allText.includes(keyword)) {
      score += 10;
      highlights.push(keyword);
      if (!reasons.includes(`keyword:${keyword}`)) {
        reasons.push(`keyword:${keyword}`);
      }
    } else if (keyword.length > 3) {
      // Fuzzy match
      for (const word of titleNorm.split(/\s+/)) {
        if (similarity(keyword, word) > 0.8) {
          score += 15;
          highlights.push(word);
          reasons.push(`fuzzy:${keyword}~${word}`);
          break;
        }
      }
    }
  }

  // Bonus for high discount
  if ((listing.discount_percent || 0) > 30) {
    score += 20;
    reasons.push("high_discount");
  }

  return { score, reasons, highlights: [...new Set(highlights)] };
}

// Get typo corrections
function getTypoCorrections(query: string): Record<string, string> {
  const corrections: Record<string, string> = {};
  for (const word of query.split(/\s+/)) {
    const corrected = correctTypos(word);
    if (corrected.toLowerCase() !== word.toLowerCase()) {
      corrections[word] = corrected;
    }
  }
  return corrections;
}

// Generate "did you mean" suggestion
function getDidYouMean(query: string): string | null {
  const corrections = getTypoCorrections(query);
  if (Object.keys(corrections).length === 0) return null;

  let corrected = query;
  for (const [original, fixed] of Object.entries(corrections)) {
    corrected = corrected.replace(new RegExp(`\\b${original}\\b`, "gi"), fixed);
  }

  return corrected.toLowerCase() !== query.toLowerCase() ? corrected : null;
}

// Get autocomplete suggestions
function getSuggestions(
  prefix: string,
  listings: Listing[],
  limit: number = 10
): Array<{ text: string; type: string; category?: string }> {
  if (prefix.length < 2) return [];

  const prefixNorm = normalizeText(prefix);
  const suggestions: Array<{ text: string; type: string; category?: string; priority: number }> = [];
  const seen = new Set<string>();

  // Check listings
  for (const listing of listings.slice(0, 500)) {
    const title = listing.title;
    const titleNorm = normalizeText(title);

    if (titleNorm.includes(prefixNorm)) {
      const words = title.split(/\s+/);
      for (let i = 0; i < words.length; i++) {
        if (normalizeText(words[i]).includes(prefixNorm)) {
          const phrase = words.slice(i, i + 3).join(" ");
          const key = phrase.toLowerCase();
          if (!seen.has(key)) {
            seen.add(key);
            suggestions.push({
              text: phrase,
              type: "listing",
              category: listing.category,
              priority: titleNorm.startsWith(prefixNorm) ? 0 : 1,
            });
          }
          break;
        }
      }
    }

    if (suggestions.length >= limit * 2) break;
  }

  // Add common searches
  const commonSearches = [
    { text: "Toyota Hilux", category: "vehicles" },
    { text: "Ford Ranger", category: "vehicles" },
    { text: "Volkswagen Amarok", category: "vehicles" },
    { text: "Departamento", category: "real_estate" },
    { text: "Casa", category: "real_estate" },
    { text: "Terreno", category: "real_estate" },
    { text: "Tractor", category: "machinery" },
    { text: "Camioneta", category: "vehicles" },
    { text: "Generador", category: "machinery" },
  ];

  for (const { text, category } of commonSearches) {
    if (normalizeText(text).includes(prefixNorm) && !seen.has(text.toLowerCase())) {
      seen.add(text.toLowerCase());
      suggestions.push({ text, type: "common", category, priority: 2 });
    }
  }

  // Sort and return
  suggestions.sort((a, b) => a.priority - b.priority);
  return suggestions.slice(0, limit).map(({ text, type, category }) => ({ text, type, category }));
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  const action = req.query.action as string || "search";
  const query = (req.query.q as string || "").trim();

  // Load listings
  let listingsData: any;
  try {
    const listingsPath = join(process.cwd(), "site", "api", "listings.json");
    listingsData = JSON.parse(readFileSync(listingsPath, "utf-8"));
  } catch (error) {
    console.error("Error loading listings:", error);
    return res.status(500).json({ error: "Failed to load listings" });
  }

  const listings: Listing[] = listingsData.listings || [];
  const blueDollarRate: number = listingsData.blue_dollar_rate || 1200;

  // Handle different actions
  switch (action) {
    case "suggestions": {
      // Free: autocomplete suggestions
      const suggestions = getSuggestions(query, listings, 10);
      return res.status(200).json({
        success: true,
        suggestions,
        prefix: query,
      });
    }

    case "popular": {
      // Free: popular searches
      return res.status(200).json({
        success: true,
        popular: POPULAR_SEARCHES,
      });
    }

    case "did_you_mean": {
      // Free: typo correction suggestion
      const suggestion = getDidYouMean(query);
      return res.status(200).json({
        success: true,
        original: query,
        suggestion,
        corrections: getTypoCorrections(query),
      });
    }

    case "search":
    default: {
      // Check if AI-enhanced search (paid) or basic search (free)
      const aiEnhanced = req.query.ai === "true";
      const txHash = req.query.tx as string;

      if (aiEnhanced) {
        // Verify payment for AI search
        if (!txHash) {
          return res.status(402).json({
            error: "Payment required for AI-enhanced search",
            message: "Include ?tx=YOUR_TX_HASH with USDC payment on Base",
            price: AI_SEARCH_PRICE,
            currency: "USDC",
            wallet: PAYMENT_WALLET,
            hint: "Use action=search without ai=true for free basic search",
          });
        }

        if (usedTxHashes.has(txHash.toLowerCase())) {
          return res.status(400).json({
            error: "Transaction already used",
            message: "Each transaction can only be used once",
          });
        }

        const verification = await verifyUSDCPayment(txHash, AI_SEARCH_PRICE);
        if (!verification.valid) {
          return res.status(402).json({
            error: "Payment verification failed",
            message: verification.error,
            required: AI_SEARCH_PRICE,
          });
        }

        usedTxHashes.add(txHash.toLowerCase());
      }

      if (!query) {
        return res.status(400).json({
          error: "Missing query parameter",
          message: "Provide search query with ?q=YOUR_QUERY",
        });
      }

      // Parse query and filters
      const filters = parseQuery(query);

      // Apply query param overrides
      if (req.query.category) {
        filters.category = req.query.category as string;
      }
      if (req.query.source) {
        filters.source = req.query.source as string;
      }
      if (req.query.min_price) {
        filters.minPrice = parseFloat(req.query.min_price as string);
      }
      if (req.query.max_price) {
        filters.maxPrice = parseFloat(req.query.max_price as string);
      }
      if (req.query.sort) {
        filters.sortBy = req.query.sort as string;
      }

      // Expand keywords with synonyms
      const expandedKeywords: string[] = [];
      for (const keyword of filters.keywords) {
        expandedKeywords.push(...expandSynonyms(keyword));
      }

      // Score all listings
      const scoredResults: Array<{
        listing: Listing;
        score: number;
        reasons: string[];
        highlights: string[];
      }> = [];

      for (const listing of listings) {
        const { score, reasons, highlights } = scoreListing(
          listing,
          filters,
          expandedKeywords,
          blueDollarRate
        );

        if (score > 0) {
          scoredResults.push({ listing, score, reasons, highlights });
        }
      }

      // Sort results
      if (filters.sortBy === "ending_soon") {
        scoredResults.sort((a, b) => {
          const aEnd = a.listing.ends_at || "9999";
          const bEnd = b.listing.ends_at || "9999";
          return aEnd.localeCompare(bEnd) || b.score - a.score;
        });
      } else if (filters.sortBy === "discount") {
        scoredResults.sort((a, b) =>
          (b.listing.discount_percent || 0) - (a.listing.discount_percent || 0)
        );
      } else if (filters.sortBy === "price_asc") {
        scoredResults.sort((a, b) =>
          (a.listing.base_price_usd || 0) - (b.listing.base_price_usd || 0)
        );
      } else if (filters.sortBy === "price_desc") {
        scoredResults.sort((a, b) =>
          (b.listing.base_price_usd || 0) - (a.listing.base_price_usd || 0)
        );
      } else {
        // Default: sort by relevance score
        scoredResults.sort((a, b) => b.score - a.score);
      }

      // Pagination
      const offset = parseInt(req.query.offset as string) || 0;
      const limit = Math.min(parseInt(req.query.limit as string) || 50, 100);
      const paginatedResults = scoredResults.slice(offset, offset + limit);

      // Build response
      const results: SearchResult[] = paginatedResults.map(({ listing, score, reasons, highlights }) => ({
        ...listing,
        relevance_score: score,
        match_reasons: reasons,
        highlight_terms: highlights,
      }));

      // Generate suggestions for refinement
      const categoryCounts: Record<string, number> = {};
      const sourceCounts: Record<string, number> = {};
      for (const { listing } of scoredResults.slice(0, 100)) {
        categoryCounts[listing.category] = (categoryCounts[listing.category] || 0) + 1;
        sourceCounts[listing.source] = (sourceCounts[listing.source] || 0) + 1;
      }

      const didYouMean = getDidYouMean(query);

      return res.status(200).json({
        success: true,
        query,
        ai_enhanced: aiEnhanced,
        filters: {
          category: filters.category,
          min_price: filters.minPrice,
          max_price: filters.maxPrice,
          currency: filters.currency,
          location: filters.location,
          source: filters.source,
          sort_by: filters.sortBy,
          keywords: filters.keywords,
          expanded_keywords: [...new Set(expandedKeywords)],
        },
        did_you_mean: didYouMean,
        typo_corrections: getTypoCorrections(query),
        results,
        pagination: {
          total: scoredResults.length,
          offset,
          limit,
          has_more: offset + limit < scoredResults.length,
        },
        facets: {
          categories: Object.entries(categoryCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5),
          sources: Object.entries(sourceCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5),
        },
      });
    }
  }
}
