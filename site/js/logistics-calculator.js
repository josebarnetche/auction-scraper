/**
 * Subasto Logistics Calculator
 * Calculates and displays transport/shipping costs for auction items
 */

const SubastoLogistics = (function() {
    'use strict';

    // State
    let transportCosts = null;
    let blueRate = 1200;

    /**
     * Initialize the logistics calculator
     */
    async function init() {
        await loadTransportCosts();
    }

    /**
     * Load transport cost configuration
     */
    async function loadTransportCosts() {
        try {
            const response = await fetch('/api/v1/geocoding.json');
            if (response.ok) {
                const data = await response.json();
                transportCosts = data.transport_costs;
            }
        } catch (e) {
            console.warn('Could not load transport costs:', e);
        }
    }

    /**
     * Set the blue dollar rate for conversions
     */
    function setBlueRate(rate) {
        blueRate = rate;
    }

    /**
     * Calculate total cost including auction price, fees, and transport
     */
    function calculateTotalCost(auction, distanceKm, deliveryOption = 'pickup') {
        if (!auction || !auction.base_price) return null;

        // Get auction cost with fees
        const auctionCost = getAuctionCostWithFees(auction);

        // Get transport cost
        const transportCost = calculateTransportCost(auction.category, distanceKm, deliveryOption);

        // Calculate totals
        const totalARS = auctionCost.total_ars + transportCost.total_ars;
        const totalUSD = Math.round(totalARS / blueRate);

        return {
            auction: auctionCost,
            transport: transportCost,
            total_ars: totalARS,
            total_usd: totalUSD,
            distance_km: distanceKm,
            delivery_option: deliveryOption
        };
    }

    /**
     * Get auction cost with commission and fees
     */
    function getAuctionCostWithFees(auction) {
        const IVA_RATE = 21.0;
        const judicialSources = ['csjn', 'scba', 'cordoba', 'entrerios'];
        const isJudicial = judicialSources.includes(auction.source);

        let baseARS = auction.currency === 'USD'
            ? auction.base_price * blueRate
            : auction.base_price;

        let commission, csjnFee;

        if (isJudicial) {
            commission = 3.0;
            csjnFee = 0.25;
        } else {
            commission = 10.0;
            csjnFee = 0;
        }

        const commissionAmount = baseARS * (commission / 100);
        const ivaAmount = baseARS * (IVA_RATE / 100);
        const feeAmount = baseARS * (csjnFee / 100);

        const totalARS = baseARS + commissionAmount + ivaAmount + feeAmount;

        return {
            base_ars: Math.round(baseARS),
            commission_pct: commission,
            commission_ars: Math.round(commissionAmount),
            iva_pct: IVA_RATE,
            iva_ars: Math.round(ivaAmount),
            csjn_fee_pct: csjnFee,
            csjn_fee_ars: Math.round(feeAmount),
            total_ars: Math.round(totalARS),
            total_usd: Math.round(totalARS / blueRate)
        };
    }

    /**
     * Calculate transport cost based on distance and category
     */
    function calculateTransportCost(category, distanceKm, deliveryOption = 'pickup') {
        if (!transportCosts || !distanceKm || distanceKm <= 0) {
            return {
                total_ars: 0,
                total_usd: 0,
                description: 'Sin transporte',
                breakdown: null
            };
        }

        // Real estate doesn't need transport
        if (category === 'real_estate') {
            return {
                total_ars: 0,
                total_usd: 0,
                description: 'Sin costo de transporte (inmueble)',
                breakdown: null
            };
        }

        const rates = transportCosts.freight_rates[category] || transportCosts.freight_rates.general_goods;

        if (deliveryOption === 'freight') {
            // Professional freight service
            const freightCost = rates.base_fee_ars + (rates.per_km_ars * distanceKm);
            return {
                total_ars: Math.round(freightCost),
                total_usd: Math.round(freightCost / blueRate),
                description: rates.description || 'Flete profesional',
                breakdown: {
                    base_fee_ars: rates.base_fee_ars,
                    per_km_ars: rates.per_km_ars,
                    distance_km: Math.round(distanceKm)
                }
            };
        } else {
            // Self-pickup (fuel + tolls, round trip)
            const fuelCost = (distanceKm / transportCosts.avg_consumption_km_per_liter) * transportCosts.fuel_price_per_liter_ars;
            const tollCost = (distanceKm / 100) * transportCosts.toll_avg_per_100km_ars;
            const totalCost = (fuelCost + tollCost) * 2; // Round trip

            return {
                total_ars: Math.round(totalCost),
                total_usd: Math.round(totalCost / blueRate),
                description: 'Retiro personal (ida y vuelta)',
                breakdown: {
                    fuel_ars: Math.round(fuelCost * 2),
                    tolls_ars: Math.round(tollCost * 2),
                    distance_km: Math.round(distanceKm)
                }
            };
        }
    }

    /**
     * Render the logistics calculator widget
     */
    function renderCalculatorWidget(auction, distanceKm = null) {
        if (!auction) return '';

        const hasDistance = distanceKm !== null && distanceKm > 0;

        // Calculate costs for both options if we have distance
        let pickupCost = null;
        let freightCost = null;
        let auctionCost = null;

        if (hasDistance) {
            auctionCost = getAuctionCostWithFees(auction);
            pickupCost = calculateTransportCost(auction.category, distanceKm, 'pickup');
            freightCost = calculateTransportCost(auction.category, distanceKm, 'freight');
        } else {
            auctionCost = getAuctionCostWithFees(auction);
        }

        const formatARS = (val) => `ARS ${val.toLocaleString('es-AR')}`;
        const formatUSD = (val) => `USD ${val.toLocaleString()}`;

        let html = `
            <div class="transport-cost-card">
                <h4 class="text-white/40 text-xs uppercase tracking-wider mb-4">
                    Costo Total Estimado
                </h4>

                <!-- Auction Cost Breakdown -->
                <div class="space-y-2 mb-4">
                    <div class="total-cost-row">
                        <span class="label">Precio base</span>
                        <span class="value">${formatARS(auctionCost.base_ars)}</span>
                    </div>
                    <div class="total-cost-row">
                        <span class="label">Comision (${auctionCost.commission_pct}%)</span>
                        <span class="value">${formatARS(auctionCost.commission_ars)}</span>
                    </div>
                    <div class="total-cost-row">
                        <span class="label">IVA (${auctionCost.iva_pct}%)</span>
                        <span class="value">${formatARS(auctionCost.iva_ars)}</span>
                    </div>
                    ${auctionCost.csjn_fee_ars > 0 ? `
                    <div class="total-cost-row">
                        <span class="label">Arancel CSJN</span>
                        <span class="value">${formatARS(auctionCost.csjn_fee_ars)}</span>
                    </div>
                    ` : ''}
                    <div class="total-cost-row highlight">
                        <span class="label font-medium">Subtotal Subasta</span>
                        <span class="value auction">${formatARS(auctionCost.total_ars)}</span>
                    </div>
                </div>
        `;

        if (hasDistance && auction.category !== 'real_estate') {
            html += `
                <!-- Transport Options -->
                <div class="space-y-2 mb-4 pt-4 border-t border-white/5">
                    <div class="text-white/40 text-xs uppercase tracking-wider mb-2">
                        Transporte (${Math.round(distanceKm)} km)
                    </div>

                    <div class="transport-option">
                        <div>
                            <span class="transport-option-label">Retiro personal</span>
                            <div class="text-[10px] text-white/30">Combustible + Peajes (ida y vuelta)</div>
                        </div>
                        <span class="transport-option-price pickup">${formatARS(pickupCost.total_ars)}</span>
                    </div>

                    <div class="transport-option">
                        <div>
                            <span class="transport-option-label">Flete profesional</span>
                            <div class="text-[10px] text-white/30">${freightCost.description}</div>
                        </div>
                        <span class="transport-option-price freight">${formatARS(freightCost.total_ars)}</span>
                    </div>
                </div>

                <!-- Total with pickup -->
                <div class="total-cost-row highlight pt-2">
                    <span class="label font-medium text-green-400">Total con retiro</span>
                    <span class="value total">${formatARS(auctionCost.total_ars + pickupCost.total_ars)}</span>
                </div>
                <div class="text-[10px] text-white/30 text-right">
                    ${formatUSD(Math.round((auctionCost.total_ars + pickupCost.total_ars) / blueRate))}
                </div>

                <!-- Total with freight -->
                <div class="total-cost-row pt-2">
                    <span class="label font-medium text-orange-400">Total con flete</span>
                    <span class="value" style="color: #fb923c;">${formatARS(auctionCost.total_ars + freightCost.total_ars)}</span>
                </div>
                <div class="text-[10px] text-white/30 text-right">
                    ${formatUSD(Math.round((auctionCost.total_ars + freightCost.total_ars) / blueRate))}
                </div>
            `;
        } else if (hasDistance && auction.category === 'real_estate') {
            html += `
                <div class="text-white/40 text-xs pt-2">
                    Sin costo de transporte (inmueble)
                </div>
            `;
        } else {
            html += `
                <div class="text-white/30 text-xs pt-2 text-center">
                    <svg class="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                    </svg>
                    Activa tu ubicacion para ver costos de transporte
                </div>
            `;
        }

        html += '</div>';
        return html;
    }

    /**
     * Get a simple transport cost summary for card display
     */
    function getTransportSummary(category, distanceKm) {
        if (!distanceKm || distanceKm <= 0 || category === 'real_estate') {
            return null;
        }

        const pickupCost = calculateTransportCost(category, distanceKm, 'pickup');

        return {
            distance_km: Math.round(distanceKm),
            pickup_ars: pickupCost.total_ars,
            pickup_usd: pickupCost.total_usd
        };
    }

    // Public API
    return {
        init: init,
        setBlueRate: setBlueRate,
        calculateTotalCost: calculateTotalCost,
        calculateTransportCost: calculateTransportCost,
        getAuctionCostWithFees: getAuctionCostWithFees,
        renderCalculatorWidget: renderCalculatorWidget,
        getTransportSummary: getTransportSummary
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    SubastoLogistics.init();
});
