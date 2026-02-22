/**
 * Price History & Market Trends Module for Subasto
 *
 * Provides:
 * - Market trends dashboard data loading
 * - Price history charts for individual items
 * - "Price changed" notifications for listings
 * - Best deal days analysis
 * - Category discount trends
 */

// Cache for market trends data
let marketTrendsCache = null;
let trendsLastFetched = null;
const TRENDS_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Fetch market trends data from API
 * @param {number} days - Number of days (30 or 90)
 * @returns {Promise<Object>} Market trends dashboard data
 */
async function fetchMarketTrends(days = 30) {
    const cacheKey = `trends_${days}`;
    const now = Date.now();

    // Check cache
    if (marketTrendsCache && trendsLastFetched &&
        (now - trendsLastFetched) < TRENDS_CACHE_TTL) {
        return marketTrendsCache;
    }

    try {
        const endpoint = days === 90 ? '/api/v1/trends-90d.json' : '/api/v1/trends.json';
        const response = await fetch(endpoint + '?t=' + now);

        if (!response.ok) {
            throw new Error(`Failed to fetch trends: ${response.status}`);
        }

        const data = await response.json();
        marketTrendsCache = data;
        trendsLastFetched = now;

        return data;
    } catch (err) {
        console.error('Error fetching market trends:', err);
        return null;
    }
}

/**
 * Fetch recent price changes
 * @returns {Promise<Object>} Price changes data
 */
async function fetchPriceChanges() {
    try {
        const response = await fetch('/api/v1/price-changes.json?t=' + Date.now());
        if (!response.ok) {
            throw new Error(`Failed to fetch price changes: ${response.status}`);
        }
        return await response.json();
    } catch (err) {
        console.error('Error fetching price changes:', err);
        return null;
    }
}

/**
 * Check if a listing has price history and return alert data
 * @param {string} listingId - The listing ID to check
 * @returns {Object|null} Price alert data or null
 */
function getPriceAlert(listingId) {
    // This would typically check against cached price change data
    // For now, we check if the listing is in our recent changes
    if (!marketTrendsCache || !marketTrendsCache.recent_price_drops) {
        return null;
    }

    const change = marketTrendsCache.recent_price_drops.find(
        c => c.listing_id === listingId
    );

    if (!change) return null;

    return {
        hasChanged: true,
        previousPrice: change.old_price_usd,
        currentPrice: change.new_price_usd,
        changePercent: change.change_percent,
        message: change.change_percent < 0
            ? `Bajo ${Math.abs(Math.round(change.change_percent))}%`
            : `Subio ${Math.round(change.change_percent)}%`,
        isPositive: change.change_percent < 0 // Price drop is positive for buyers
    };
}

/**
 * Create HTML for price change badge
 * @param {Object} alert - Price alert data
 * @returns {string} HTML string
 */
function createPriceAlertBadge(alert) {
    if (!alert || !alert.hasChanged) return '';

    const colorClass = alert.isPositive
        ? 'bg-green-500/20 text-green-400 border-green-500/30'
        : 'bg-red-500/20 text-red-400 border-red-500/30';

    return `
        <div class="price-alert-badge ${colorClass} px-2 py-1 rounded text-xs font-medium border flex items-center gap-1">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="${alert.isPositive ? 'M13 17h8m0 0V9m0 8l-8-8-4 4-6-6' : 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6'}"/>
            </svg>
            ${alert.message}
        </div>
    `;
}

/**
 * Render market trends dashboard section
 * @param {string} containerId - ID of container element
 */
async function renderMarketTrends(containerId = 'market-trends-container') {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Show loading state
    container.innerHTML = `
        <div class="flex items-center justify-center py-12">
            <div class="animate-spin w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full"></div>
        </div>
    `;

    const trends = await fetchMarketTrends(30);

    if (!trends) {
        container.innerHTML = `
            <div class="text-center py-12 text-white/40">
                <p>Datos historicos no disponibles aun.</p>
                <p class="text-sm mt-2">Los datos se recolectan diariamente.</p>
            </div>
        `;
        return;
    }

    const discounts = trends.discount_by_category || {};
    const bestDays = trends.best_deal_days || {};
    const priceTrends = trends.price_trends || {};
    const recentDrops = trends.recent_price_drops || [];

    container.innerHTML = `
        <!-- Category Discounts -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            ${Object.entries(discounts).map(([cat, data]) => `
                <div class="glass rounded-xl p-4 text-center">
                    <div class="text-2xl font-bold text-yellow-400 font-display">${data.avg_discount || 0}%</div>
                    <div class="text-xs text-white/60 uppercase tracking-wider mt-1">${formatCategoryName(cat)}</div>
                    <div class="text-xs mt-2 ${getTrendColor(data.trend)}">${getTrendArrow(data.trend)} ${data.trend || 'N/A'}</div>
                </div>
            `).join('')}
        </div>

        <!-- Best Day to Buy -->
        <div class="glass rounded-xl p-6 mb-8">
            <h4 class="text-lg font-display text-white mb-4 flex items-center gap-2">
                <svg class="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                Mejor Dia para Comprar
            </h4>
            ${bestDays.best_day ? `
                <div class="flex items-center gap-4">
                    <div class="text-4xl font-bold font-display text-green-400">${bestDays.best_day}</div>
                    <div class="text-white/60 text-sm">
                        <p>Promedio <span class="text-yellow-400">${bestDays.best_avg_discount}%</span> de descuento</p>
                        <p class="text-xs mt-1">Basado en ${trends.analysis_period_days || 30} dias de datos</p>
                    </div>
                </div>
            ` : `
                <p class="text-white/40">No hay suficientes datos aun</p>
            `}

            <!-- Day breakdown -->
            ${bestDays.by_day ? `
                <div class="mt-4 grid grid-cols-7 gap-2">
                    ${['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map(day => {
                        const dayData = bestDays.by_day[day] || {};
                        const isBest = day === bestDays.best_day;
                        return `
                            <div class="text-center p-2 rounded ${isBest ? 'bg-yellow-500/20 border border-yellow-500/30' : 'bg-white/5'}">
                                <div class="text-[10px] text-white/40 uppercase">${day.slice(0, 3)}</div>
                                <div class="text-sm font-medium ${isBest ? 'text-yellow-400' : 'text-white/60'}">${dayData.avg_discount || 0}%</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            ` : ''}
        </div>

        <!-- Recent Price Drops -->
        ${recentDrops.length > 0 ? `
            <div class="glass rounded-xl p-6">
                <h4 class="text-lg font-display text-white mb-4 flex items-center gap-2">
                    <svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/>
                    </svg>
                    Bajas de Precio Recientes
                </h4>
                <div class="space-y-3">
                    ${recentDrops.slice(0, 5).map(drop => `
                        <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
                            <div class="flex-1 min-w-0">
                                <p class="text-white text-sm truncate">${drop.title}</p>
                                <p class="text-xs text-white/40">${drop.source} - ${formatCategoryName(drop.category)}</p>
                            </div>
                            <div class="text-right ml-4">
                                <div class="text-green-400 font-bold">${Math.round(drop.change_percent)}%</div>
                                <div class="text-xs text-white/40">
                                    $${Math.round(drop.old_price_usd)} -> $${Math.round(drop.new_price_usd)}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}
    `;
}

/**
 * Create a simple price history chart using SVG
 * @param {Array} prices - Array of {date, price_usd} objects
 * @param {Object} options - Chart options
 * @returns {string} SVG string
 */
function createPriceChart(prices, options = {}) {
    if (!prices || prices.length < 2) {
        return '<div class="text-white/40 text-sm text-center py-4">No hay suficientes datos para mostrar</div>';
    }

    const width = options.width || 300;
    const height = options.height || 100;
    const padding = 10;

    const values = prices.map(p => p.price_usd || p.avg_price_usd || 0);
    const maxVal = Math.max(...values);
    const minVal = Math.min(...values);
    const range = maxVal - minVal || 1;

    // Create points for line
    const points = values.map((val, i) => {
        const x = padding + (i / (values.length - 1)) * (width - padding * 2);
        const y = height - padding - ((val - minVal) / range) * (height - padding * 2);
        return `${x},${y}`;
    }).join(' ');

    // Determine trend color
    const firstVal = values[0];
    const lastVal = values[values.length - 1];
    const strokeColor = lastVal < firstVal ? '#4ade80' : lastVal > firstVal ? '#f87171' : '#fbbf24';

    return `
        <svg viewBox="0 0 ${width} ${height}" class="w-full h-auto">
            <!-- Grid lines -->
            <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"
                stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
            <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}"
                stroke="rgba(255,255,255,0.05)" stroke-width="1" stroke-dasharray="4"/>

            <!-- Area fill -->
            <polygon
                points="${padding},${height - padding} ${points} ${width - padding},${height - padding}"
                fill="url(#areaGradient)"
            />

            <!-- Line -->
            <polyline
                points="${points}"
                fill="none"
                stroke="${strokeColor}"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
            />

            <!-- End point dot -->
            <circle cx="${width - padding}" cy="${height - padding - ((lastVal - minVal) / range) * (height - padding * 2)}"
                r="4" fill="${strokeColor}"/>

            <defs>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.3"/>
                    <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0"/>
                </linearGradient>
            </defs>
        </svg>
        <div class="flex justify-between text-xs text-white/40 mt-1">
            <span>${prices[0].date}</span>
            <span>${prices[prices.length - 1].date}</span>
        </div>
    `;
}

/**
 * Render price history modal for a specific listing
 * @param {string} listingId - The listing ID
 * @param {string} title - Listing title for display
 */
async function showPriceHistoryModal(listingId, title) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('price-history-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'price-history-modal';
        modal.className = 'fixed inset-0 z-[100] hidden';
        modal.innerHTML = `
            <div class="absolute inset-0 bg-black/85 backdrop-blur-sm" onclick="closePriceHistoryModal()"></div>
            <div class="relative max-w-lg mx-auto mt-20 p-6 glass rounded-2xl m-4">
                <button onclick="closePriceHistoryModal()" class="absolute top-4 right-4 text-white/40 hover:text-white">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
                <h3 class="text-lg font-display text-white mb-4 pr-8" id="price-history-title">Historial de Precios</h3>
                <div id="price-history-content">
                    <div class="flex items-center justify-center py-8">
                        <div class="animate-spin w-6 h-6 border-2 border-yellow-500 border-t-transparent rounded-full"></div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Show modal
    modal.classList.remove('hidden');
    document.getElementById('price-history-title').textContent = title || 'Historial de Precios';

    const content = document.getElementById('price-history-content');

    // Load and display data
    // For now, show trends data as we don't have individual item history API yet
    const trends = await fetchMarketTrends(30);

    if (!trends || !trends.price_trends || !trends.price_trends.all) {
        content.innerHTML = `
            <div class="text-center py-8 text-white/40">
                <p>No hay historial de precios disponible para este item.</p>
                <p class="text-sm mt-2">El historial se genera despues de varios dias de seguimiento.</p>
            </div>
        `;
        return;
    }

    const dailyData = trends.price_trends.all.daily_data || [];

    content.innerHTML = `
        <div class="mb-4">
            ${createPriceChart(dailyData)}
        </div>
        <div class="grid grid-cols-2 gap-4 text-center">
            <div class="bg-white/5 rounded-lg p-3">
                <div class="text-lg font-bold text-white">$${dailyData.length > 0 ? Math.round(dailyData[dailyData.length - 1].avg_price_usd) : 'N/A'}</div>
                <div class="text-xs text-white/40">Precio Promedio Actual</div>
            </div>
            <div class="bg-white/5 rounded-lg p-3">
                <div class="text-lg font-bold ${trends.price_trends.all.trend_direction === 'down' ? 'text-green-400' : 'text-red-400'}">
                    ${trends.price_trends.all.avg_change_percent}%
                </div>
                <div class="text-xs text-white/40">Cambio en ${trends.analysis_period_days} dias</div>
            </div>
        </div>
    `;
}

/**
 * Close price history modal
 */
function closePriceHistoryModal() {
    const modal = document.getElementById('price-history-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Helper functions
function formatCategoryName(category) {
    const names = {
        vehicles: 'Vehiculos',
        real_estate: 'Inmuebles',
        machinery: 'Maquinaria',
        general_goods: 'Bienes',
        other: 'Otros'
    };
    return names[category] || category;
}

function getTrendColor(trend) {
    const colors = {
        up: 'text-green-400',
        down: 'text-red-400',
        stable: 'text-white/60',
        insufficient_data: 'text-white/30'
    };
    return colors[trend] || 'text-white/40';
}

function getTrendArrow(trend) {
    const arrows = {
        up: '&#8593;',
        down: '&#8595;',
        stable: '&#8596;',
        insufficient_data: '-'
    };
    return arrows[trend] || '-';
}

// Export functions for global access
window.fetchMarketTrends = fetchMarketTrends;
window.fetchPriceChanges = fetchPriceChanges;
window.getPriceAlert = getPriceAlert;
window.createPriceAlertBadge = createPriceAlertBadge;
window.renderMarketTrends = renderMarketTrends;
window.showPriceHistoryModal = showPriceHistoryModal;
window.closePriceHistoryModal = closePriceHistoryModal;
window.createPriceChart = createPriceChart;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    // Pre-fetch trends data
    fetchMarketTrends(30);
});
