/**
 * Subasto Profit Calculator
 * Calculate potential profit from auction purchases in Argentina
 *
 * @author Subasto.com.ar
 * @version 1.0.0
 */

(function(global) {
    'use strict';

    // =========================================================================
    // CONSTANTS & PRESETS
    // =========================================================================

    const TAX_RATES = {
        IVA: 0.21,              // 21% IVA on base price
        INGRESOS_BRUTOS: 0.035, // ~3.5% average across provinces
        SELLOS: 0.01            // 1% stamp tax on contracts
    };

    const CATEGORY_PRESETS = {
        vehicles: {
            label: 'Vehiculos',
            icon: '🚗',
            commissionMin: 0.03,      // 3% auction commission
            commissionMax: 0.06,      // 6% max
            defaultCommission: 0.05,  // 5% typical
            typicalMargin: 0.25,      // 25% typical resale margin
            sellingFees: {
                mercadolibre: 0.13,   // 13% MercadoLibre fee
                kavak: 0.08,          // 8% Kavak-style
                private: 0.02         // 2% advertising
            },
            repairCosts: {
                new: 0,
                used: 0.05,           // 5% of price
                needs_repair: 0.20    // 20% of price
            },
            transportBase: 15000,     // Base transport ARS
            transportPerKm: 150,      // Per km ARS
            additionalCosts: {
                vtv: 8500,            // VTV inspection
                patentamiento: 0.015, // 1.5% of value
                seguro_mes: 35000,    // Monthly insurance
                gestor: 25000         // Administrative fees
            }
        },
        real_estate: {
            label: 'Inmuebles',
            icon: '🏠',
            commissionMin: 0.02,
            commissionMax: 0.04,
            defaultCommission: 0.03,
            typicalMargin: 0.30,
            sellingFees: {
                inmobiliaria: 0.04,   // 4% real estate agent
                zonaprop: 0.02,       // 2% listing fees
                private: 0.01
            },
            repairCosts: {
                new: 0,
                used: 0.08,
                needs_repair: 0.25
            },
            transportBase: 0,
            transportPerKm: 0,
            additionalCosts: {
                escribano: 0.02,      // 2% notary fees
                impuesto_sellos: 0.035, // 3.5% stamp tax
                certificados: 50000,  // Various certificates
                expensas_meses: 3,    // Months of expenses to budget
                expensa_promedio: 45000
            }
        },
        machinery: {
            label: 'Maquinaria',
            icon: '🏭',
            commissionMin: 0.04,
            commissionMax: 0.10,
            defaultCommission: 0.06,
            typicalMargin: 0.35,
            sellingFees: {
                marketplace: 0.08,
                dealer: 0.12,
                private: 0.03
            },
            repairCosts: {
                new: 0,
                used: 0.10,
                needs_repair: 0.30
            },
            transportBase: 50000,
            transportPerKm: 500,
            additionalCosts: {
                instalacion: 0.05,    // 5% installation
                testing: 0.02,        // 2% testing/calibration
                capacitacion: 100000, // Training
                permisos: 75000       // Permits/licenses
            }
        },
        general_goods: {
            label: 'Bienes Generales',
            icon: '📦',
            commissionMin: 0.05,
            commissionMax: 0.10,
            defaultCommission: 0.08,
            typicalMargin: 0.40,
            sellingFees: {
                mercadolibre: 0.15,
                wholesale: 0.05,
                private: 0.02
            },
            repairCosts: {
                new: 0,
                used: 0.03,
                needs_repair: 0.15
            },
            transportBase: 5000,
            transportPerKm: 50,
            additionalCosts: {
                almacenamiento_mes: 20000,
                embalaje: 0.02,
                seguro_mercaderia: 0.01
            }
        }
    };

    const ARGENTINA_DISTANCES = {
        'CABA': { lat: -34.6037, lng: -58.3816 },
        'Buenos Aires': { lat: -34.9215, lng: -57.9545 },
        'Cordoba': { lat: -31.4201, lng: -64.1888 },
        'Rosario': { lat: -32.9468, lng: -60.6393 },
        'Mendoza': { lat: -32.8895, lng: -68.8458 },
        'Tucuman': { lat: -26.8083, lng: -65.2176 },
        'Salta': { lat: -24.7821, lng: -65.4232 },
        'Santa Fe': { lat: -31.6107, lng: -60.6973 },
        'Mar del Plata': { lat: -38.0055, lng: -57.5426 },
        'Neuquen': { lat: -38.9516, lng: -68.0591 },
        'Bahia Blanca': { lat: -38.7196, lng: -62.2724 },
        'Resistencia': { lat: -27.4606, lng: -58.9839 },
        'Posadas': { lat: -27.3621, lng: -55.8969 },
        'San Juan': { lat: -31.5375, lng: -68.5364 },
        'Corrientes': { lat: -27.4692, lng: -58.8306 }
    };

    // =========================================================================
    // CALCULATOR CLASS
    // =========================================================================

    class ProfitCalculator {
        constructor(options = {}) {
            this.options = {
                currency: 'ARS',
                locale: 'es-AR',
                ...options
            };
            this.results = null;
        }

        /**
         * Calculate profit from auction purchase
         */
        calculate(params) {
            const {
                basePrice,
                category,
                condition = 'used',
                resalePrice,
                originLocation = 'CABA',
                destinationLocation = 'CABA',
                customCommission = null,
                sellingChannel = null,
                includeIVA = true,
                monthsToSell = 2
            } = params;

            const preset = CATEGORY_PRESETS[category];
            if (!preset) {
                throw new Error(`Invalid category: ${category}`);
            }

            // Commission rate
            const commissionRate = customCommission !== null
                ? customCommission
                : preset.defaultCommission;

            // ========== ACQUISITION COSTS ==========

            // Base auction price
            const auctionPrice = basePrice;

            // IVA (21% on base price)
            const ivaAmount = includeIVA ? basePrice * TAX_RATES.IVA : 0;

            // Auction commission
            const commissionAmount = basePrice * commissionRate;

            // Calculate distance and transport
            const distance = this._calculateDistance(originLocation, destinationLocation);
            const transportCost = preset.transportBase + (distance * preset.transportPerKm);

            // Repair/refurbishment costs
            const repairRate = preset.repairCosts[condition] || 0;
            const repairCost = basePrice * repairRate;

            // Category-specific additional costs
            const additionalCosts = this._calculateAdditionalCosts(preset, basePrice, monthsToSell);

            // Total acquisition cost
            const totalAcquisitionCost = auctionPrice + ivaAmount + commissionAmount +
                                         transportCost + repairCost + additionalCosts.total;

            // ========== SELLING COSTS ==========

            // Determine selling channel and fees
            const channelKey = sellingChannel || Object.keys(preset.sellingFees)[0];
            const sellingFeeRate = preset.sellingFees[channelKey] || 0.10;
            const sellingFees = resalePrice * sellingFeeRate;

            // ========== PROFIT CALCULATIONS ==========

            // Total investment
            const totalInvestment = totalAcquisitionCost;

            // Gross profit (before selling fees)
            const grossProfit = resalePrice - totalInvestment;

            // Net profit (after selling fees)
            const netProfit = grossProfit - sellingFees;

            // ROI percentage
            const roi = totalInvestment > 0 ? (netProfit / totalInvestment) * 100 : 0;

            // Break-even price (minimum resale to not lose money)
            const breakEvenPrice = totalInvestment / (1 - sellingFeeRate);

            // Margin percentage
            const marginPercent = resalePrice > 0 ? (netProfit / resalePrice) * 100 : 0;

            // ========== BUILD RESULTS ==========

            this.results = {
                input: {
                    basePrice,
                    category,
                    categoryLabel: preset.label,
                    condition,
                    resalePrice,
                    originLocation,
                    destinationLocation,
                    distance: Math.round(distance),
                    commissionRate,
                    sellingChannel: channelKey,
                    sellingFeeRate,
                    monthsToSell
                },
                acquisition: {
                    auctionPrice,
                    ivaAmount,
                    ivaRate: TAX_RATES.IVA,
                    commissionAmount,
                    commissionRate,
                    transportCost,
                    repairCost,
                    repairRate,
                    additionalCosts: additionalCosts.breakdown,
                    additionalCostsTotal: additionalCosts.total,
                    totalAcquisitionCost
                },
                selling: {
                    channel: channelKey,
                    feeRate: sellingFeeRate,
                    fees: sellingFees
                },
                profit: {
                    totalInvestment,
                    grossProfit,
                    netProfit,
                    roi,
                    breakEvenPrice,
                    marginPercent,
                    isProfitable: netProfit > 0
                },
                summary: {
                    verdict: this._getVerdict(roi),
                    riskLevel: this._getRiskLevel(marginPercent, condition),
                    suggestedMinResale: Math.ceil(breakEvenPrice * 1.15), // 15% buffer
                    expectedROI: preset.typicalMargin * 100
                }
            };

            return this.results;
        }

        /**
         * Calculate distance between two Argentine cities
         */
        _calculateDistance(origin, destination) {
            const originCoords = ARGENTINA_DISTANCES[origin];
            const destCoords = ARGENTINA_DISTANCES[destination];

            if (!originCoords || !destCoords) {
                return 100; // Default 100km
            }

            // Haversine formula
            const R = 6371; // Earth radius in km
            const dLat = this._toRad(destCoords.lat - originCoords.lat);
            const dLng = this._toRad(destCoords.lng - originCoords.lng);
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                      Math.cos(this._toRad(originCoords.lat)) *
                      Math.cos(this._toRad(destCoords.lat)) *
                      Math.sin(dLng/2) * Math.sin(dLng/2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

            return R * c;
        }

        _toRad(deg) {
            return deg * (Math.PI / 180);
        }

        /**
         * Calculate category-specific additional costs
         */
        _calculateAdditionalCosts(preset, basePrice, monthsToSell) {
            const breakdown = {};
            let total = 0;

            for (const [key, value] of Object.entries(preset.additionalCosts)) {
                let cost;
                if (typeof value === 'number' && value < 1) {
                    // It's a percentage
                    cost = basePrice * value;
                } else if (key.includes('mes') || key.includes('meses')) {
                    // Monthly cost - multiply by months
                    const months = preset.additionalCosts[key.replace('_mes', '_meses')] || monthsToSell;
                    cost = value * (typeof months === 'number' && months > 1 ? months : monthsToSell);
                } else {
                    cost = value;
                }
                breakdown[key] = cost;
                total += cost;
            }

            return { breakdown, total };
        }

        /**
         * Get verdict based on ROI
         */
        _getVerdict(roi) {
            if (roi >= 50) return { level: 'excellent', label: 'Excelente oportunidad', color: '#22c55e' };
            if (roi >= 25) return { level: 'good', label: 'Buena oportunidad', color: '#84cc16' };
            if (roi >= 10) return { level: 'moderate', label: 'Oportunidad moderada', color: '#eab308' };
            if (roi >= 0) return { level: 'marginal', label: 'Ganancia marginal', color: '#f97316' };
            return { level: 'loss', label: 'Operacion a perdida', color: '#ef4444' };
        }

        /**
         * Get risk level
         */
        _getRiskLevel(marginPercent, condition) {
            let riskScore = 0;

            if (marginPercent < 10) riskScore += 2;
            else if (marginPercent < 20) riskScore += 1;

            if (condition === 'needs_repair') riskScore += 2;
            else if (condition === 'used') riskScore += 1;

            if (riskScore >= 3) return { level: 'high', label: 'Alto', color: '#ef4444' };
            if (riskScore >= 2) return { level: 'medium', label: 'Medio', color: '#f97316' };
            return { level: 'low', label: 'Bajo', color: '#22c55e' };
        }

        /**
         * Format currency for display
         */
        formatCurrency(amount) {
            return new Intl.NumberFormat(this.options.locale, {
                style: 'currency',
                currency: this.options.currency,
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            }).format(amount);
        }

        /**
         * Format percentage
         */
        formatPercent(value) {
            return new Intl.NumberFormat(this.options.locale, {
                style: 'percent',
                minimumFractionDigits: 1,
                maximumFractionDigits: 1
            }).format(value / 100);
        }

        /**
         * Generate shareable URL with parameters
         */
        generateShareUrl(baseUrl = 'https://subasto.com.ar/widgets/calculator.html') {
            if (!this.results) return baseUrl;

            const params = new URLSearchParams({
                bp: this.results.input.basePrice,
                cat: this.results.input.category,
                cond: this.results.input.condition,
                rp: this.results.input.resalePrice,
                from: this.results.input.originLocation,
                to: this.results.input.destinationLocation,
                ch: this.results.input.sellingChannel
            });

            return `${baseUrl}?${params.toString()}`;
        }

        /**
         * Parse URL parameters to prefill calculator
         */
        static parseUrlParams(url = window.location.href) {
            const params = new URL(url).searchParams;
            return {
                basePrice: parseFloat(params.get('bp')) || null,
                category: params.get('cat') || 'vehicles',
                condition: params.get('cond') || 'used',
                resalePrice: parseFloat(params.get('rp')) || null,
                originLocation: params.get('from') || 'CABA',
                destinationLocation: params.get('to') || 'CABA',
                sellingChannel: params.get('ch') || null
            };
        }

        /**
         * Get available categories
         */
        static getCategories() {
            return Object.entries(CATEGORY_PRESETS).map(([key, value]) => ({
                id: key,
                label: value.label,
                icon: value.icon,
                typicalMargin: value.typicalMargin,
                commissionRange: `${value.commissionMin * 100}% - ${value.commissionMax * 100}%`
            }));
        }

        /**
         * Get available locations
         */
        static getLocations() {
            return Object.keys(ARGENTINA_DISTANCES);
        }

        /**
         * Get selling channels for a category
         */
        static getSellingChannels(category) {
            const preset = CATEGORY_PRESETS[category];
            if (!preset) return [];

            return Object.entries(preset.sellingFees).map(([key, rate]) => ({
                id: key,
                label: key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' '),
                feeRate: rate,
                feePercent: `${(rate * 100).toFixed(0)}%`
            }));
        }

        /**
         * Get condition options
         */
        static getConditions() {
            return [
                { id: 'new', label: 'Nuevo', icon: '✨' },
                { id: 'used', label: 'Usado (buen estado)', icon: '👍' },
                { id: 'needs_repair', label: 'Necesita reparacion', icon: '🔧' }
            ];
        }

        /**
         * Generate PDF content (returns HTML string for printing)
         */
        generatePDFContent() {
            if (!this.results) return '';

            const r = this.results;
            const fmt = (n) => this.formatCurrency(n);

            return `
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Analisis de Rentabilidad - Subasto.com.ar</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; color: #1f2937; padding: 40px; max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #eab308; padding-bottom: 20px; }
        .logo { font-size: 28px; font-weight: bold; color: #eab308; }
        .date { color: #6b7280; font-size: 12px; margin-top: 5px; }
        h1 { font-size: 20px; margin: 20px 0 10px; color: #374151; }
        .section { margin-bottom: 25px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f9fafb; font-weight: 600; }
        .amount { text-align: right; font-family: monospace; }
        .total-row { background: #fef3c7; font-weight: bold; }
        .profit-positive { color: #059669; }
        .profit-negative { color: #dc2626; }
        .verdict { padding: 15px; border-radius: 8px; text-align: center; margin: 20px 0; }
        .verdict-excellent { background: #d1fae5; color: #065f46; }
        .verdict-good { background: #ecfccb; color: #3f6212; }
        .verdict-moderate { background: #fef3c7; color: #92400e; }
        .verdict-marginal { background: #ffedd5; color: #9a3412; }
        .verdict-loss { background: #fee2e2; color: #991b1b; }
        .footer { margin-top: 40px; text-align: center; color: #9ca3af; font-size: 11px; border-top: 1px solid #e5e7eb; padding-top: 20px; }
        @media print { body { padding: 20px; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">SUBASTO</div>
        <div>Analisis de Rentabilidad</div>
        <div class="date">Generado: ${new Date().toLocaleDateString('es-AR')} ${new Date().toLocaleTimeString('es-AR')}</div>
    </div>

    <div class="section">
        <h1>Datos de la Operacion</h1>
        <table>
            <tr><td>Categoria</td><td>${r.input.categoryLabel}</td></tr>
            <tr><td>Condicion</td><td>${r.input.condition === 'new' ? 'Nuevo' : r.input.condition === 'used' ? 'Usado' : 'Necesita reparacion'}</td></tr>
            <tr><td>Origen</td><td>${r.input.originLocation}</td></tr>
            <tr><td>Destino</td><td>${r.input.destinationLocation} (${r.input.distance} km)</td></tr>
            <tr><td>Canal de venta</td><td>${r.input.sellingChannel}</td></tr>
        </table>
    </div>

    <div class="section">
        <h1>Costos de Adquisicion</h1>
        <table>
            <tr><td>Precio base subasta</td><td class="amount">${fmt(r.acquisition.auctionPrice)}</td></tr>
            <tr><td>IVA (${(r.acquisition.ivaRate * 100).toFixed(0)}%)</td><td class="amount">${fmt(r.acquisition.ivaAmount)}</td></tr>
            <tr><td>Comision (${(r.acquisition.commissionRate * 100).toFixed(0)}%)</td><td class="amount">${fmt(r.acquisition.commissionAmount)}</td></tr>
            <tr><td>Transporte</td><td class="amount">${fmt(r.acquisition.transportCost)}</td></tr>
            <tr><td>Reparacion/Acondicionamiento</td><td class="amount">${fmt(r.acquisition.repairCost)}</td></tr>
            <tr><td>Otros costos</td><td class="amount">${fmt(r.acquisition.additionalCostsTotal)}</td></tr>
            <tr class="total-row"><td>TOTAL ADQUISICION</td><td class="amount">${fmt(r.acquisition.totalAcquisitionCost)}</td></tr>
        </table>
    </div>

    <div class="section">
        <h1>Costos de Venta</h1>
        <table>
            <tr><td>Precio de venta estimado</td><td class="amount">${fmt(r.input.resalePrice)}</td></tr>
            <tr><td>Comision ${r.selling.channel} (${(r.selling.feeRate * 100).toFixed(0)}%)</td><td class="amount">${fmt(r.selling.fees)}</td></tr>
        </table>
    </div>

    <div class="section">
        <h1>Resultado</h1>
        <table>
            <tr><td>Inversion total</td><td class="amount">${fmt(r.profit.totalInvestment)}</td></tr>
            <tr><td>Ganancia bruta</td><td class="amount">${fmt(r.profit.grossProfit)}</td></tr>
            <tr class="total-row"><td>GANANCIA NETA</td><td class="amount ${r.profit.isProfitable ? 'profit-positive' : 'profit-negative'}">${fmt(r.profit.netProfit)}</td></tr>
            <tr><td>ROI</td><td class="amount">${r.profit.roi.toFixed(1)}%</td></tr>
            <tr><td>Precio de equilibrio</td><td class="amount">${fmt(r.profit.breakEvenPrice)}</td></tr>
        </table>
    </div>

    <div class="verdict verdict-${r.summary.verdict.level}">
        <strong>${r.summary.verdict.label}</strong>
        <br>
        Riesgo: ${r.summary.riskLevel.label} | Venta minima sugerida: ${fmt(r.summary.suggestedMinResale)}
    </div>

    <div class="footer">
        <p>Este analisis es una estimacion y no constituye asesoramiento financiero.</p>
        <p>Generado por Subasto.com.ar - El agregador de subastas de Argentina</p>
    </div>
</body>
</html>`;
        }
    }

    // =========================================================================
    // UI CONTROLLER (for widget)
    // =========================================================================

    class CalculatorUI {
        constructor(containerId, options = {}) {
            this.container = document.getElementById(containerId);
            this.calculator = new ProfitCalculator(options);
            this.onCalculate = options.onCalculate || null;

            if (this.container) {
                this.init();
            }
        }

        init() {
            this._bindEvents();
            this._loadFromUrl();
        }

        _bindEvents() {
            // Form inputs
            const form = this.container.querySelector('#calculator-form');
            if (form) {
                form.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.calculate();
                });

                form.addEventListener('input', () => {
                    this._debounce(() => this.calculate(), 300);
                });
            }

            // Category change
            const categorySelect = this.container.querySelector('#calc-category');
            if (categorySelect) {
                categorySelect.addEventListener('change', () => {
                    this._updateSellingChannels();
                    this.calculate();
                });
            }

            // Export buttons
            const pdfBtn = this.container.querySelector('#export-pdf');
            if (pdfBtn) {
                pdfBtn.addEventListener('click', () => this.exportPDF());
            }

            const shareBtn = this.container.querySelector('#share-link');
            if (shareBtn) {
                shareBtn.addEventListener('click', () => this.shareLink());
            }

            const printBtn = this.container.querySelector('#print-btn');
            if (printBtn) {
                printBtn.addEventListener('click', () => this.print());
            }
        }

        _debounceTimer = null;
        _debounce(fn, delay) {
            clearTimeout(this._debounceTimer);
            this._debounceTimer = setTimeout(fn, delay);
        }

        _loadFromUrl() {
            try {
                const params = ProfitCalculator.parseUrlParams();
                if (params.basePrice) {
                    this._setFieldValue('calc-base-price', params.basePrice);
                    this._setFieldValue('calc-category', params.category);
                    this._setFieldValue('calc-condition', params.condition);
                    this._setFieldValue('calc-resale-price', params.resalePrice);
                    this._setFieldValue('calc-origin', params.originLocation);
                    this._setFieldValue('calc-destination', params.destinationLocation);

                    this._updateSellingChannels();
                    if (params.sellingChannel) {
                        this._setFieldValue('calc-channel', params.sellingChannel);
                    }

                    setTimeout(() => this.calculate(), 100);
                }
            } catch (e) {
                console.log('No URL params to load');
            }
        }

        _setFieldValue(id, value) {
            const field = this.container.querySelector(`#${id}`);
            if (field && value !== null) {
                field.value = value;
            }
        }

        _getFieldValue(id) {
            const field = this.container.querySelector(`#${id}`);
            return field ? field.value : null;
        }

        _updateSellingChannels() {
            const category = this._getFieldValue('calc-category');
            const channelSelect = this.container.querySelector('#calc-channel');

            if (!channelSelect) return;

            const channels = ProfitCalculator.getSellingChannels(category);
            channelSelect.innerHTML = channels.map(ch =>
                `<option value="${ch.id}">${ch.label} (${ch.feePercent})</option>`
            ).join('');
        }

        calculate() {
            const basePrice = parseFloat(this._getFieldValue('calc-base-price')) || 0;
            const resalePrice = parseFloat(this._getFieldValue('calc-resale-price')) || 0;

            if (basePrice <= 0) {
                this._showPlaceholder();
                return;
            }

            try {
                const results = this.calculator.calculate({
                    basePrice,
                    category: this._getFieldValue('calc-category') || 'vehicles',
                    condition: this._getFieldValue('calc-condition') || 'used',
                    resalePrice: resalePrice || basePrice * 1.3,
                    originLocation: this._getFieldValue('calc-origin') || 'CABA',
                    destinationLocation: this._getFieldValue('calc-destination') || 'CABA',
                    sellingChannel: this._getFieldValue('calc-channel') || null
                });

                this._renderResults(results);

                if (this.onCalculate) {
                    this.onCalculate(results);
                }
            } catch (e) {
                console.error('Calculation error:', e);
            }
        }

        _showPlaceholder() {
            const resultsContainer = this.container.querySelector('#calculator-results');
            if (resultsContainer) {
                resultsContainer.innerHTML = `
                    <div class="text-center py-8 text-gray-400">
                        <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                        </svg>
                        <p>Ingresa el precio base para calcular</p>
                    </div>
                `;
            }
        }

        _renderResults(results) {
            const resultsContainer = this.container.querySelector('#calculator-results');
            if (!resultsContainer) return;

            const r = results;
            const fmt = (n) => this.calculator.formatCurrency(n);
            const verdictClass = {
                'excellent': 'from-green-500/20 to-green-600/10 border-green-500/30',
                'good': 'from-lime-500/20 to-lime-600/10 border-lime-500/30',
                'moderate': 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30',
                'marginal': 'from-orange-500/20 to-orange-600/10 border-orange-500/30',
                'loss': 'from-red-500/20 to-red-600/10 border-red-500/30'
            }[r.summary.verdict.level];

            resultsContainer.innerHTML = `
                <!-- Verdict Banner -->
                <div class="bg-gradient-to-r ${verdictClass} border rounded-xl p-4 mb-6">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-lg font-bold" style="color: ${r.summary.verdict.color}">${r.summary.verdict.label}</div>
                            <div class="text-sm text-gray-400">Riesgo: <span style="color: ${r.summary.riskLevel.color}">${r.summary.riskLevel.label}</span></div>
                        </div>
                        <div class="text-right">
                            <div class="text-3xl font-bold ${r.profit.isProfitable ? 'text-green-400' : 'text-red-400'}">${r.profit.roi.toFixed(1)}%</div>
                            <div class="text-xs text-gray-400">ROI</div>
                        </div>
                    </div>
                </div>

                <!-- Key Metrics -->
                <div class="grid grid-cols-2 gap-3 mb-6">
                    <div class="bg-white/5 rounded-lg p-3">
                        <div class="text-xs text-gray-400 mb-1">Inversion Total</div>
                        <div class="text-lg font-semibold text-white">${fmt(r.profit.totalInvestment)}</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-3">
                        <div class="text-xs text-gray-400 mb-1">Ganancia Neta</div>
                        <div class="text-lg font-semibold ${r.profit.isProfitable ? 'text-green-400' : 'text-red-400'}">${fmt(r.profit.netProfit)}</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-3">
                        <div class="text-xs text-gray-400 mb-1">Precio Equilibrio</div>
                        <div class="text-lg font-semibold text-yellow-400">${fmt(r.profit.breakEvenPrice)}</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-3">
                        <div class="text-xs text-gray-400 mb-1">Venta Sugerida</div>
                        <div class="text-lg font-semibold text-blue-400">${fmt(r.summary.suggestedMinResale)}</div>
                    </div>
                </div>

                <!-- Cost Breakdown -->
                <div class="space-y-2 mb-6">
                    <h4 class="text-sm font-medium text-gray-300 mb-2">Desglose de Costos</h4>

                    <div class="flex justify-between text-sm">
                        <span class="text-gray-400">Precio subasta</span>
                        <span class="text-white">${fmt(r.acquisition.auctionPrice)}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-400">+ IVA (21%)</span>
                        <span class="text-white">${fmt(r.acquisition.ivaAmount)}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-400">+ Comision (${(r.acquisition.commissionRate * 100).toFixed(0)}%)</span>
                        <span class="text-white">${fmt(r.acquisition.commissionAmount)}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-400">+ Transporte (${r.input.distance} km)</span>
                        <span class="text-white">${fmt(r.acquisition.transportCost)}</span>
                    </div>
                    ${r.acquisition.repairCost > 0 ? `
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-400">+ Reparacion</span>
                        <span class="text-white">${fmt(r.acquisition.repairCost)}</span>
                    </div>
                    ` : ''}
                    ${r.acquisition.additionalCostsTotal > 0 ? `
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-400">+ Otros costos</span>
                        <span class="text-white">${fmt(r.acquisition.additionalCostsTotal)}</span>
                    </div>
                    ` : ''}
                    <div class="border-t border-white/10 pt-2 flex justify-between text-sm font-medium">
                        <span class="text-gray-300">Total adquisicion</span>
                        <span class="text-yellow-400">${fmt(r.acquisition.totalAcquisitionCost)}</span>
                    </div>

                    <div class="flex justify-between text-sm mt-3">
                        <span class="text-gray-400">Precio venta</span>
                        <span class="text-white">${fmt(r.input.resalePrice)}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-400">- Comision venta (${(r.selling.feeRate * 100).toFixed(0)}%)</span>
                        <span class="text-red-400">-${fmt(r.selling.fees)}</span>
                    </div>

                    <div class="border-t border-white/10 pt-2 flex justify-between font-bold">
                        <span class="text-white">GANANCIA NETA</span>
                        <span class="${r.profit.isProfitable ? 'text-green-400' : 'text-red-400'}">${fmt(r.profit.netProfit)}</span>
                    </div>
                </div>

                <!-- Export Actions -->
                <div class="flex gap-2 pt-4 border-t border-white/10">
                    <button id="export-pdf" class="flex-1 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 rounded-lg py-2 px-3 text-sm font-medium transition-colors flex items-center justify-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        PDF
                    </button>
                    <button id="share-link" class="flex-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg py-2 px-3 text-sm font-medium transition-colors flex items-center justify-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path>
                        </svg>
                        Compartir
                    </button>
                    <button id="print-btn" class="bg-gray-500/20 hover:bg-gray-500/30 text-gray-400 rounded-lg py-2 px-3 text-sm font-medium transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path>
                        </svg>
                    </button>
                </div>
            `;

            // Rebind export events
            this._bindExportEvents();
        }

        _bindExportEvents() {
            const pdfBtn = this.container.querySelector('#export-pdf');
            if (pdfBtn) {
                pdfBtn.addEventListener('click', () => this.exportPDF());
            }

            const shareBtn = this.container.querySelector('#share-link');
            if (shareBtn) {
                shareBtn.addEventListener('click', () => this.shareLink());
            }

            const printBtn = this.container.querySelector('#print-btn');
            if (printBtn) {
                printBtn.addEventListener('click', () => this.print());
            }
        }

        exportPDF() {
            const pdfContent = this.calculator.generatePDFContent();
            const blob = new Blob([pdfContent], { type: 'text/html' });
            const url = URL.createObjectURL(blob);

            const printWindow = window.open(url, '_blank');
            printWindow.onload = function() {
                printWindow.print();
            };
        }

        print() {
            const pdfContent = this.calculator.generatePDFContent();
            const printWindow = window.open('', '_blank');
            printWindow.document.write(pdfContent);
            printWindow.document.close();
            printWindow.print();
        }

        shareLink() {
            const url = this.calculator.generateShareUrl();

            if (navigator.share) {
                navigator.share({
                    title: 'Calculadora de Rentabilidad - Subasto',
                    text: 'Analiza la rentabilidad de esta oportunidad de subasta',
                    url: url
                });
            } else if (navigator.clipboard) {
                navigator.clipboard.writeText(url).then(() => {
                    this._showToast('Link copiado al portapapeles');
                });
            } else {
                prompt('Copia este link:', url);
            }
        }

        _showToast(message) {
            const toast = document.createElement('div');
            toast.className = 'fixed bottom-4 left-1/2 transform -translate-x-1/2 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-50 animate-fade-in';
            toast.textContent = message;
            document.body.appendChild(toast);

            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
    }

    // =========================================================================
    // EXPORTS
    // =========================================================================

    // Export to global scope for use in browsers
    global.SubastoCalculator = {
        ProfitCalculator,
        CalculatorUI,
        CATEGORY_PRESETS,
        TAX_RATES
    };

    // Export for module systems
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { ProfitCalculator, CalculatorUI, CATEGORY_PRESETS, TAX_RATES };
    }

})(typeof window !== 'undefined' ? window : global);
