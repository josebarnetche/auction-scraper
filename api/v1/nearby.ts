import type { VercelRequest, VercelResponse } from '@vercel/node';
import { readFileSync } from 'fs';
import { join } from 'path';

// Earth radius in kilometers
const EARTH_RADIUS_KM = 6371;

interface GeocodingData {
  provinces: Record<string, {
    name: string;
    lat: number;
    lng: number;
    cities?: Record<string, { lat: number; lng: number }>;
  }>;
  source_locations: Record<string, {
    province: string;
    city: string;
    lat: number;
    lng: number;
  }>;
  transport_costs: {
    fuel_price_per_liter_ars: number;
    avg_consumption_km_per_liter: number;
    toll_avg_per_100km_ars: number;
    freight_rates: Record<string, {
      per_km_ars: number;
      base_fee_ars: number;
      description?: string;
    }>;
  };
}

interface Auction {
  id: string;
  title: string;
  source: string;
  source_url: string;
  category: string;
  base_price: number;
  currency: string;
  location?: {
    province?: string;
    city?: string;
  };
  ends_at?: string;
  images?: string[];
}

interface NearbyResult extends Auction {
  distance_km: number;
  transport_estimate?: {
    freight_ars: number;
    self_pickup_ars: number;
  };
  coordinates?: {
    lat: number;
    lng: number;
  };
}

// Calculate distance between two points using Haversine formula
function calculateDistance(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const toRad = (deg: number) => deg * (Math.PI / 180);

  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);

  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return EARTH_RADIUS_KM * c;
}

// Normalize province name for lookup
function normalizeProvinceName(name: string): string {
  if (!name) return '';

  const normalizations: Record<string, string> = {
    'cordoba': 'Cordoba',
    'cba': 'Cordoba',
    'buenos aires': 'Buenos Aires',
    'ba': 'Buenos Aires',
    'pba': 'Buenos Aires',
    'caba': 'CABA',
    'capital federal': 'CABA',
    'ciudad de buenos aires': 'CABA',
    'entre rios': 'Entre Rios',
    'santa fe': 'Santa Fe',
    'mendoza': 'Mendoza',
    'tucuman': 'Tucuman',
    'salta': 'Salta'
  };

  const normalized = name.toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  return normalizations[normalized] || name;
}

// Get coordinates for an auction
function getAuctionCoordinates(
  auction: Auction,
  geocoding: GeocodingData
): { lat: number; lng: number } | null {
  // Try to geocode from location
  const province = normalizeProvinceName(auction.location?.province || '');
  const city = auction.location?.city || '';

  if (province && geocoding.provinces[province]) {
    const provinceData = geocoding.provinces[province];
    if (city && provinceData.cities && provinceData.cities[city]) {
      return provinceData.cities[city];
    }
    return { lat: provinceData.lat, lng: provinceData.lng };
  }

  // Fallback to source location
  if (auction.source && geocoding.source_locations[auction.source]) {
    const sourceLocation = geocoding.source_locations[auction.source];
    return { lat: sourceLocation.lat, lng: sourceLocation.lng };
  }

  return null;
}

// Calculate transport cost estimate
function calculateTransportCost(
  distanceKm: number,
  category: string,
  geocoding: GeocodingData
): { freight_ars: number; self_pickup_ars: number } | null {
  if (!geocoding.transport_costs || distanceKm <= 0) return null;

  const costs = geocoding.transport_costs;
  const rates = costs.freight_rates[category] || costs.freight_rates.general_goods;

  // Real estate doesn't need transport
  if (category === 'real_estate') {
    return { freight_ars: 0, self_pickup_ars: 0 };
  }

  // Professional freight
  const freightCost = rates.base_fee_ars + (rates.per_km_ars * distanceKm);

  // Self-pickup (fuel + tolls, round trip)
  const fuelCost = (distanceKm / costs.avg_consumption_km_per_liter) * costs.fuel_price_per_liter_ars;
  const tollCost = (distanceKm / 100) * costs.toll_avg_per_100km_ars;
  const selfPickupCost = (fuelCost + tollCost) * 2;

  return {
    freight_ars: Math.round(freightCost),
    self_pickup_ars: Math.round(selfPickupCost)
  };
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Parse query parameters
    const lat = parseFloat(req.query.lat as string);
    const lng = parseFloat(req.query.lng as string);
    const radius = parseFloat(req.query.radius as string) || 100; // Default 100km
    const limit = parseInt(req.query.limit as string) || 50;
    const category = req.query.category as string || '';
    const includeTransport = req.query.transport !== 'false';

    // Validate coordinates
    if (isNaN(lat) || isNaN(lng)) {
      return res.status(400).json({
        error: 'Invalid coordinates',
        message: 'Please provide valid lat and lng query parameters'
      });
    }

    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      return res.status(400).json({
        error: 'Coordinates out of range',
        message: 'lat must be between -90 and 90, lng between -180 and 180'
      });
    }

    // Load data
    const listingsPath = join(process.cwd(), 'site', 'api', 'listings.json');
    const geocodingPath = join(process.cwd(), 'site', 'api', 'v1', 'geocoding.json');

    let listingsData: { listings: Auction[] };
    let geocodingData: GeocodingData;

    try {
      listingsData = JSON.parse(readFileSync(listingsPath, 'utf-8'));
      geocodingData = JSON.parse(readFileSync(geocodingPath, 'utf-8'));
    } catch (e) {
      return res.status(500).json({
        error: 'Data not available',
        message: 'Could not load auction or geocoding data'
      });
    }

    const auctions = listingsData.listings || [];

    // Find nearby auctions
    const nearbyAuctions: NearbyResult[] = [];

    for (const auction of auctions) {
      // Category filter
      if (category && auction.category !== category) continue;

      // Get auction coordinates
      const coords = getAuctionCoordinates(auction, geocodingData);
      if (!coords) continue;

      // Calculate distance
      const distance = calculateDistance(lat, lng, coords.lat, coords.lng);

      // Check if within radius
      if (distance > radius) continue;

      // Build result
      const result: NearbyResult = {
        ...auction,
        distance_km: Math.round(distance * 10) / 10,
        coordinates: coords
      };

      // Add transport estimate if requested
      if (includeTransport && distance > 0) {
        const transport = calculateTransportCost(distance, auction.category, geocodingData);
        if (transport) {
          result.transport_estimate = transport;
        }
      }

      nearbyAuctions.push(result);
    }

    // Sort by distance
    nearbyAuctions.sort((a, b) => a.distance_km - b.distance_km);

    // Apply limit
    const results = nearbyAuctions.slice(0, limit);

    // Build response
    const response = {
      success: true,
      query: {
        lat,
        lng,
        radius_km: radius,
        category: category || 'all',
        include_transport: includeTransport
      },
      total_found: nearbyAuctions.length,
      results_returned: results.length,
      results,
      _meta: {
        generated_at: new Date().toISOString(),
        api_version: '1.0'
      }
    };

    // Cache for 5 minutes
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');

    return res.status(200).json(response);

  } catch (error) {
    console.error('Nearby API error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}
