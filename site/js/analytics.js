/**
 * Subasto Analytics Dashboard
 * Chart rendering and data visualization
 */

// Chart.js global configuration
Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
Chart.defaults.font.family = "'Manrope', sans-serif";

// Color palette matching the site design
const COLORS = {
    primary: '#eab308',      // Yellow
    vehicles: '#60a5fa',     // Blue
    real_estate: '#f472b6',  // Pink
    machinery: '#fbbf24',    // Amber
    general_goods: '#4ade80', // Green
    other: '#d1d5db',        // Gray
    background: 'rgba(255, 255, 255, 0.05)',
    border: 'rgba(255, 255, 255, 0.1)',
    text: 'rgba(255, 255, 255, 0.7)',
    textBright: 'rgba(255, 255, 255, 0.9)'
};

const CATEGORY_LABELS = {
    vehicles: 'Vehiculos',
    real_estate: 'Inmuebles',
    machinery: 'Maquinaria',
    general_goods: 'Bienes Generales',
    other: 'Otros'
};

const SOURCE_LABELS = {
    csjn: 'CSJN',
    scba: 'SCBA',
    cordoba: 'Cordoba',
    entrerios: 'Entre Rios',
    banco_ciudad: 'Banco Ciudad',
    global_remates: 'Global Remates',
    adrian_mercado: 'Adrian Mercado',
    agusti: 'Agusti',
    bidbit: 'BidBit',
    sitiodetiendas: 'Sitio de Tiendas',
    manucha: 'Manucha',
    rematadores: 'Rematadores',
    zarate: 'Zarate',
    delafuente: 'De La Fuente',
    curated: 'Curado'
};

// Global state
let analyticsData = null;
let charts = {};

/**
 * Initialize the analytics dashboard
 */
async function initAnalytics() {
    try {
        showLoading(true);

        // Load analytics data
        const response = await fetch('/api/analytics.json');
        if (!response.ok) {
            throw new Error('Failed to load analytics data');
        }
        analyticsData = await response.json();

        // Update last updated timestamp
        updateTimestamp(analyticsData.generated_at);

        // Render all sections
        renderSummaryCards();
        renderCategoryChart();
        renderSourceChart();
        renderClosingSoon();
        renderBestDeals();
        renderTrending();
        renderInsights();
        renderPriceComparison();

        showLoading(false);

    } catch (error) {
        console.error('Error initializing analytics:', error);
        showError('Error al cargar los datos. Por favor, recarga la pagina.');
    }
}

/**
 * Show/hide loading state
 */
function showLoading(show) {
    const loader = document.getElementById('loading-overlay');
    if (loader) {
        loader.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Show error message
 */
function showError(message) {
    const container = document.getElementById('error-container');
    if (container) {
        container.innerHTML = `
            <div class="glass rounded-xl p-6 text-center">
                <svg class="w-12 h-12 mx-auto mb-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                </svg>
                <p class="text-white/70">${message}</p>
            </div>
        `;
        container.style.display = 'block';
    }
    showLoading(false);
}

/**
 * Update the last updated timestamp
 */
function updateTimestamp(isoDate) {
    const el = document.getElementById('last-updated');
    if (el && isoDate) {
        const date = new Date(isoDate);
        const options = {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        };
        el.textContent = `Actualizado: ${date.toLocaleDateString('es-AR', options)}`;
    }
}

/**
 * Render summary cards
 */
function renderSummaryCards() {
    const summary = analyticsData.summary;

    document.getElementById('total-listings').textContent = summary.total_listings.toLocaleString('es-AR');
    document.getElementById('total-sources').textContent = summary.total_sources;
    document.getElementById('total-opportunities').textContent = summary.opportunity_count;

    // Format total value
    const totalValue = summary.total_value_usd;
    let valueText;
    if (totalValue >= 1000000) {
        valueText = `$${(totalValue / 1000000).toFixed(1)}M`;
    } else if (totalValue >= 1000) {
        valueText = `$${(totalValue / 1000).toFixed(0)}K`;
    } else {
        valueText = `$${totalValue.toFixed(0)}`;
    }
    document.getElementById('total-value').textContent = valueText;
}

/**
 * Render category pie chart
 */
function renderCategoryChart() {
    const ctx = document.getElementById('category-chart');
    if (!ctx) return;

    const categories = analyticsData.by_category;
    const labels = [];
    const data = [];
    const colors = [];

    for (const [key, stats] of Object.entries(categories)) {
        labels.push(CATEGORY_LABELS[key] || key);
        data.push(stats.count);
        colors.push(COLORS[key] || COLORS.other);
    }

    if (charts.category) {
        charts.category.destroy();
    }

    charts.category = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderColor: 'rgba(3, 3, 3, 0.8)',
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 15,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.raw / total) * 100).toFixed(1);
                            return `${context.label}: ${context.raw} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render source bar chart
 */
function renderSourceChart() {
    const ctx = document.getElementById('source-chart');
    if (!ctx) return;

    const sources = analyticsData.by_source;
    const sortedSources = Object.entries(sources)
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 10);  // Top 10

    const labels = sortedSources.map(([key]) => SOURCE_LABELS[key] || key);
    const data = sortedSources.map(([, stats]) => stats.count);
    const colors = sortedSources.map(([, stats]) =>
        stats.source_type === 'judicial' ? '#60a5fa' : '#fbbf24'
    );

    if (charts.source) {
        charts.source.destroy();
    }

    charts.source = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Listings',
                data: data,
                backgroundColor: colors,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const source = sortedSources[context.dataIndex];
                            const type = source[1].source_type === 'judicial' ? 'Judicial' : 'Privado';
                            return `${context.raw} listings (${type})`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

/**
 * Render closing soon section
 */
function renderClosingSoon() {
    const container = document.getElementById('closing-soon-list');
    if (!container) return;

    const closingSoon = analyticsData.closing_this_week || [];

    if (closingSoon.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8 text-white/50">
                <p>No hay subastas cerrando esta semana</p>
            </div>
        `;
        return;
    }

    const html = closingSoon.slice(0, 8).map(item => {
        const timeLeft = item.days_left > 0
            ? `${item.days_left} dias`
            : `${item.hours_left} horas`;

        const urgencyClass = item.days_left === 0
            ? 'text-red-400 bg-red-400/10'
            : item.days_left <= 2
                ? 'text-yellow-400 bg-yellow-400/10'
                : 'text-green-400 bg-green-400/10';

        const discountBadge = item.discount_percent > 0
            ? `<span class="text-xs px-2 py-0.5 rounded bg-green-400/10 text-green-400">${item.discount_percent.toFixed(0)}% off</span>`
            : '';

        return `
            <a href="${item.source_url}" target="_blank" class="block glass rounded-lg p-3 hover:bg-white/10 transition-colors">
                <div class="flex justify-between items-start gap-2">
                    <div class="flex-1 min-w-0">
                        <h4 class="text-sm font-medium text-white truncate">${item.title}</h4>
                        <div class="flex items-center gap-2 mt-1">
                            <span class="text-xs text-white/50 uppercase">${item.source}</span>
                            <span class="category-badge category-${item.category}">${CATEGORY_LABELS[item.category] || item.category}</span>
                            ${discountBadge}
                        </div>
                    </div>
                    <div class="flex flex-col items-end">
                        <span class="text-xs px-2 py-0.5 rounded ${urgencyClass}">${timeLeft}</span>
                        ${item.base_price_usd > 0 ? `<span class="text-xs text-white/50 mt-1">$${item.base_price_usd.toLocaleString('es-AR')}</span>` : ''}
                    </div>
                </div>
            </a>
        `;
    }).join('');

    container.innerHTML = html;
}

/**
 * Render best deals section
 */
function renderBestDeals() {
    const container = document.getElementById('best-deals-list');
    if (!container) return;

    const deals = analyticsData.best_deals || [];

    if (deals.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8 text-white/50">
                <p>No hay ofertas destacadas disponibles</p>
            </div>
        `;
        return;
    }

    const html = deals.slice(0, 8).map((item, index) => {
        const image = item.images?.[0] || '/api/placeholder.svg';
        const rank = index + 1;

        return `
            <a href="${item.source_url}" target="_blank" class="flex gap-3 glass rounded-lg p-3 hover:bg-white/10 transition-colors">
                <div class="relative flex-shrink-0">
                    <img src="${image}" alt="" class="w-16 h-16 object-cover rounded-lg bg-white/5" onerror="this.src='/api/placeholder.svg'">
                    <span class="absolute -top-1 -left-1 w-5 h-5 bg-yellow-500 text-black text-xs font-bold rounded-full flex items-center justify-center">${rank}</span>
                </div>
                <div class="flex-1 min-w-0">
                    <h4 class="text-sm font-medium text-white truncate">${item.title}</h4>
                    <div class="flex items-center gap-2 mt-1">
                        <span class="text-xs text-white/50 uppercase">${item.source}</span>
                        <span class="category-badge category-${item.category}">${CATEGORY_LABELS[item.category] || item.category}</span>
                    </div>
                    <div class="flex items-center gap-2 mt-1">
                        <span class="text-green-400 font-bold">${item.discount_percent.toFixed(0)}% OFF</span>
                        <span class="text-xs text-white/40 line-through">$${item.market_price_usd?.toLocaleString('es-AR') || '?'}</span>
                        <span class="text-xs text-white">$${item.base_price_usd?.toLocaleString('es-AR') || '?'}</span>
                    </div>
                </div>
            </a>
        `;
    }).join('');

    container.innerHTML = html;
}

/**
 * Render trending/hot items section
 */
function renderTrending() {
    const container = document.getElementById('trending-list');
    if (!container) return;

    const trending = analyticsData.trending || [];

    if (trending.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8 text-white/50">
                <p>No hay items trending esta semana</p>
            </div>
        `;
        return;
    }

    const signalLabels = {
        nuevo: 'Nuevo',
        alta_calidad: 'Alta Calidad',
        gran_descuento: 'Gran Descuento',
        buen_descuento: 'Buen Descuento',
        premium: 'Premium',
        top_oportunidad: 'Top',
        cierra_pronto: 'Cierra Pronto',
        judicial: 'Judicial'
    };

    const html = trending.slice(0, 6).map(item => {
        const signals = (item.signals || []).slice(0, 3).map(s =>
            `<span class="text-xs px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-400">${signalLabels[s] || s}</span>`
        ).join('');

        return `
            <a href="${item.source_url}" target="_blank" class="block glass rounded-lg p-4 hover:bg-white/10 transition-colors">
                <div class="flex justify-between items-start">
                    <h4 class="text-sm font-medium text-white flex-1">${item.title}</h4>
                    <span class="text-yellow-500 font-bold ml-2">${item.trending_score}</span>
                </div>
                <div class="flex items-center gap-2 mt-2 flex-wrap">
                    <span class="category-badge category-${item.category}">${CATEGORY_LABELS[item.category] || item.category}</span>
                    ${signals}
                </div>
                ${item.discount_percent ? `<p class="text-green-400 text-sm mt-2">${item.discount_percent.toFixed(0)}% descuento</p>` : ''}
            </a>
        `;
    }).join('');

    container.innerHTML = html;
}

/**
 * Render insights section
 */
function renderInsights() {
    const insights = analyticsData.insights || {};

    // Best day for deals
    const bestDay = insights.best_day_for_deals;
    if (bestDay) {
        const el = document.getElementById('insight-best-day');
        if (el) {
            el.innerHTML = `
                <div class="flex items-center gap-3 mb-3">
                    <div class="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
                        <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                        </svg>
                    </div>
                    <div>
                        <h4 class="text-sm font-medium text-white">Mejor Dia para Ofertas</h4>
                        <p class="text-2xl font-bold text-yellow-500">${bestDay.best_day}</p>
                    </div>
                </div>
                <p class="text-sm text-white/60">${bestDay.insight}</p>
            `;
        }
    }

    // Most undervalued category
    const undervalued = insights.most_undervalued_category;
    if (undervalued && undervalued.category) {
        const el = document.getElementById('insight-undervalued');
        if (el) {
            el.innerHTML = `
                <div class="flex items-center gap-3 mb-3">
                    <div class="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                        <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                        </svg>
                    </div>
                    <div>
                        <h4 class="text-sm font-medium text-white">Categoria mas Subvaluada</h4>
                        <p class="text-2xl font-bold text-yellow-500">${undervalued.category_label}</p>
                    </div>
                </div>
                <p class="text-sm text-white/60">${undervalued.opportunity_ratio}% de oportunidades con ${undervalued.avg_discount}% descuento promedio</p>
            `;
        }
    }

    // Price comparison
    const priceComp = insights.price_comparison?.overall;
    if (priceComp) {
        const el = document.getElementById('insight-savings');
        if (el) {
            el.innerHTML = `
                <div class="flex items-center gap-3 mb-3">
                    <div class="w-10 h-10 rounded-full bg-pink-500/20 flex items-center justify-center">
                        <svg class="w-5 h-5 text-pink-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                    </div>
                    <div>
                        <h4 class="text-sm font-medium text-white">Ahorro vs Retail</h4>
                        <p class="text-2xl font-bold text-yellow-500">${priceComp.avg_savings_percent}%</p>
                    </div>
                </div>
                <p class="text-sm text-white/60">${priceComp.insight}</p>
            `;
        }
    }
}

/**
 * Render price comparison chart
 */
function renderPriceComparison() {
    const ctx = document.getElementById('price-comparison-chart');
    if (!ctx) return;

    const comparison = analyticsData.insights?.price_comparison?.by_category || {};
    const categories = Object.keys(comparison);

    if (categories.length === 0) return;

    const labels = categories.map(c => CATEGORY_LABELS[c] || c);
    const auctionPrices = categories.map(c => comparison[c].avg_auction_price_usd);
    const marketPrices = categories.map(c => comparison[c].avg_market_price_usd);

    if (charts.priceComparison) {
        charts.priceComparison.destroy();
    }

    charts.priceComparison = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Precio Subasta',
                    data: auctionPrices,
                    backgroundColor: '#4ade80',
                    borderRadius: 6
                },
                {
                    label: 'Precio Mercado',
                    data: marketPrices,
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: $${context.raw.toLocaleString('es-AR')} USD`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + (value / 1000).toFixed(0) + 'K';
                        }
                    }
                }
            }
        }
    });
}

/**
 * Export chart as image
 */
function exportChart(chartId, filename) {
    const chart = charts[chartId];
    if (!chart) {
        console.error('Chart not found:', chartId);
        return;
    }

    const link = document.createElement('a');
    link.download = `subasto-${filename}-${new Date().toISOString().split('T')[0]}.png`;
    link.href = chart.toBase64Image();
    link.click();
}

/**
 * Export data as CSV
 */
function exportCSV(dataType) {
    let csvContent = '';
    let filename = '';

    switch (dataType) {
        case 'categories':
            csvContent = 'Categoria,Cantidad,Valor Total USD,Precio Promedio USD,Oportunidades,Descuento Promedio\n';
            for (const [cat, stats] of Object.entries(analyticsData.by_category)) {
                csvContent += `"${CATEGORY_LABELS[cat] || cat}",${stats.count},${stats.total_value_usd},${stats.avg_price_usd},${stats.opportunities},${stats.avg_discount_percent}\n`;
            }
            filename = 'categorias';
            break;

        case 'sources':
            csvContent = 'Fuente,Tipo,Cantidad,Valor Total USD,Oportunidades\n';
            for (const [source, stats] of Object.entries(analyticsData.by_source)) {
                csvContent += `"${SOURCE_LABELS[source] || source}",${stats.source_type},${stats.count},${stats.total_value_usd},${stats.opportunities}\n`;
            }
            filename = 'fuentes';
            break;

        case 'deals':
            csvContent = 'Titulo,Categoria,Fuente,Precio Subasta USD,Precio Mercado USD,Descuento %,URL\n';
            for (const deal of analyticsData.best_deals || []) {
                csvContent += `"${deal.title.replace(/"/g, '""')}","${CATEGORY_LABELS[deal.category] || deal.category}","${deal.source}",${deal.base_price_usd},${deal.market_price_usd || ''},${deal.discount_percent},"${deal.source_url}"\n`;
            }
            filename = 'mejores-ofertas';
            break;

        case 'closing':
            csvContent = 'Titulo,Categoria,Fuente,Precio USD,Cierra En,Descuento %,URL\n';
            for (const item of analyticsData.closing_this_week || []) {
                const timeLeft = item.days_left > 0 ? `${item.days_left} dias` : `${item.hours_left} horas`;
                csvContent += `"${item.title.replace(/"/g, '""')}","${CATEGORY_LABELS[item.category] || item.category}","${item.source}",${item.base_price_usd},"${timeLeft}",${item.discount_percent || ''},"${item.source_url}"\n`;
            }
            filename = 'cierran-pronto';
            break;

        default:
            console.error('Unknown data type:', dataType);
            return;
    }

    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `subasto-${filename}-${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
}

/**
 * Generate embed code for a chart
 */
function generateEmbedCode(chartId) {
    const embedUrl = `${window.location.origin}/analytics.html?embed=${chartId}`;
    const embedCode = `<iframe src="${embedUrl}" width="600" height="400" frameborder="0" style="border-radius: 12px;"></iframe>`;

    // Copy to clipboard
    navigator.clipboard.writeText(embedCode).then(() => {
        showToast('Codigo de embed copiado al portapapeles');
    }).catch(err => {
        console.error('Failed to copy:', err);
        prompt('Copia este codigo:', embedCode);
    });
}

/**
 * Show toast notification
 */
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 glass px-4 py-2 rounded-lg text-white text-sm z-50 animate-fade-in';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initAnalytics);

// Handle embed mode
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.has('embed')) {
    document.body.classList.add('embed-mode');
}
