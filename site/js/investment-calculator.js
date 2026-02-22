/**
 * Investment Calculator Integration for Subasto
 * Integrates the ProfitCalculator with the main auction listings
 *
 * @author Subasto.com.ar
 * @version 1.0.0
 */

(function(global) {
    'use strict';

    // State
    let currentAuction = null;
    let currentScenario = 'expected';
    let calculatorResults = null;

    // Scenario multipliers for estimates
    const SCENARIOS = {
        best: {
            label: 'Mejor Caso',
            transportMultiplier: 0.8,
            repairMultiplier: 0.5,
            resaleMultiplier: 1.1,
            otherMultiplier: 0.7
        },
        expected: {
            label: 'Esperado',
            transportMultiplier: 1.0,
            repairMultiplier: 1.0,
            resaleMultiplier: 1.0,
            otherMultiplier: 1.0
        },
        worst: {
            label: 'Peor Caso',
            transportMultiplier: 1.3,
            repairMultiplier: 2.0,
            resaleMultiplier: 0.85,
            otherMultiplier: 1.5
        }
    };

    // Transport estimates by category and province (in USD)
    const TRANSPORT_ESTIMATES = {
        vehicles: { base: 150, perProvince: 50 },
        real_estate: { base: 0, perProvince: 0 },
        machinery: { base: 500, perProvince: 150 },
        general_goods: { base: 50, perProvince: 20 },
        other: { base: 100, perProvince: 30 }
    };

    // Repair estimates as percentage of base price
    const REPAIR_ESTIMATES = {
        vehicles: { min: 0.05, typical: 0.15, max: 0.30 },
        real_estate: { min: 0.03, typical: 0.10, max: 0.25 },
        machinery: { min: 0.08, typical: 0.20, max: 0.40 },
        general_goods: { min: 0.02, typical: 0.08, max: 0.15 },
        other: { min: 0.05, typical: 0.10, max: 0.20 }
    };

    // Risk levels by category
    const CATEGORY_RISK = {
        vehicles: { level: 'medium', reason: 'Estado mecanico incierto' },
        real_estate: { level: 'low', reason: 'Activo tangible con titulo' },
        machinery: { level: 'high', reason: 'Mercado limitado, estado tecnico variable' },
        general_goods: { level: 'medium', reason: 'Depende del estado y demanda' },
        other: { level: 'high', reason: 'Dificil de evaluar y revender' }
    };

    /**
     * Open the investment calculator modal for an auction
     */
    function openCalculator(auction, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        currentAuction = auction;
        currentScenario = 'expected';

        const modal = document.getElementById('calc-modal');
        if (!modal) {
            console.error('Calculator modal not found');
            return;
        }

        // Populate modal with auction data
        populateCalculator(auction);

        // Show modal
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Calculate initial values
        recalculateInvestment();
    }

    /**
     * Close the calculator modal
     */
    function closeCalculator() {
        const modal = document.getElementById('calc-modal');
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        currentAuction = null;
    }

    /**
     * Populate calculator fields with auction data
     */
    function populateCalculator(auction) {
        // Title
        const titleEl = document.getElementById('calc-auction-title');
        if (titleEl) {
            titleEl.textContent = auction.title ?
                (auction.title.length > 60 ? auction.title.substring(0, 60) + '...' : auction.title) :
                'Subasta sin titulo';
        }

        // Source link
        const sourceLink = document.getElementById('calc-source-link');
        if (sourceLink && auction.source_url) {
            sourceLink.href = auction.source_url;
        }

        // Base price (convert to USD if needed)
        const basePrice = getBasePriceUSD(auction);
        document.getElementById('calc-base-price').value = Math.round(basePrice);
        document.getElementById('calc-currency').textContent = 'USD';

        // Update commission based on source type
        const isJudicial = ['csjn', 'scba', 'cordoba', 'entrerios'].includes(auction.source);
        if (isJudicial) {
            document.getElementById('calc-commission-pct').textContent = '3';
            document.getElementById('calc-fee-pct').textContent = '0.25';
            document.getElementById('calc-fee-row').style.display = '';
        } else {
            document.getElementById('calc-commission-pct').textContent = '10';
            document.getElementById('calc-fee-row').style.display = 'none';
        }

        // Market value
        const marketEl = document.getElementById('calc-market-value');
        const marketSourceEl = document.getElementById('calc-market-source');
        if (auction.market_data && auction.market_data.typical_usd) {
            marketEl.textContent = 'USD ' + auction.market_data.typical_usd.toLocaleString();
            document.getElementById('calc-resale').value = Math.round(auction.market_data.typical_usd * 0.95);
            if (marketSourceEl && auction.market_data.source) {
                marketSourceEl.textContent = 'Fuente: ' + auction.market_data.source;
            }
        } else {
            marketEl.textContent = 'Sin datos';
            // Estimate resale as 130% of base price
            document.getElementById('calc-resale').value = Math.round(basePrice * 1.3);
            if (marketSourceEl) {
                marketSourceEl.textContent = '';
            }
        }

        // Estimate transport based on location
        const transportEstimate = estimateTransport(auction);
        document.getElementById('calc-transport').value = transportEstimate;

        // Estimate repairs based on category
        const repairEstimate = estimateRepairs(auction);
        document.getElementById('calc-repairs').value = repairEstimate;

        // Legal/admin costs
        document.getElementById('calc-legal').value = Math.round(basePrice * 0.02);
        document.getElementById('calc-other').value = 0;

        // Update risk assessment
        updateRiskAssessment(auction.category);

        // Reset scenario tabs
        document.querySelectorAll('.scenario-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.scenario === 'expected');
        });
    }

    /**
     * Get base price in USD
     */
    function getBasePriceUSD(auction) {
        if (!auction.base_price) return 0;
        if (auction.currency === 'USD') return auction.base_price;
        // Use global blue dollar rate
        const rate = window.BLUE_DOLLAR_RATE || 1200;
        return auction.base_price / rate;
    }

    /**
     * Estimate transport cost based on category and location
     */
    function estimateTransport(auction) {
        const category = auction.category || 'other';
        const estimates = TRANSPORT_ESTIMATES[category] || TRANSPORT_ESTIMATES.other;

        // Count provinces away from CABA
        let provinceDistance = 0;
        const location = auction.location;
        if (location && location.province) {
            const remoteProvinces = ['Salta', 'Jujuy', 'Tucuman', 'Misiones', 'Corrientes', 'Chaco', 'Formosa', 'Neuquen', 'Rio Negro', 'Chubut', 'Santa Cruz', 'Tierra del Fuego'];
            const mediumProvinces = ['Cordoba', 'Mendoza', 'Santa Fe', 'Entre Rios', 'San Luis', 'San Juan', 'La Rioja', 'Catamarca', 'Santiago del Estero', 'La Pampa'];

            if (remoteProvinces.some(p => location.province.includes(p))) {
                provinceDistance = 3;
            } else if (mediumProvinces.some(p => location.province.includes(p))) {
                provinceDistance = 2;
            } else if (location.province !== 'CABA' && location.province !== 'Buenos Aires') {
                provinceDistance = 1;
            }
        }

        return Math.round(estimates.base + (estimates.perProvince * provinceDistance));
    }

    /**
     * Estimate repair costs based on category
     */
    function estimateRepairs(auction) {
        const category = auction.category || 'other';
        const basePrice = getBasePriceUSD(auction);
        const estimates = REPAIR_ESTIMATES[category] || REPAIR_ESTIMATES.other;

        // Use typical estimate
        return Math.round(basePrice * estimates.typical);
    }

    /**
     * Update risk assessment display
     */
    function updateRiskAssessment(category) {
        const risk = CATEGORY_RISK[category] || CATEGORY_RISK.other;
        const badge = document.getElementById('calc-risk-badge');
        const levelEl = document.getElementById('calc-risk-level');
        const reasonEl = document.getElementById('calc-risk-reason');

        if (badge) {
            badge.className = 'risk-indicator risk-' + risk.level;
        }
        if (levelEl) {
            levelEl.textContent = risk.level === 'low' ? 'Bajo' :
                                  risk.level === 'medium' ? 'Medio' : 'Alto';
        }
        if (reasonEl) {
            reasonEl.textContent = risk.reason;
        }
    }

    /**
     * Set scenario and recalculate
     */
    function setScenario(scenario) {
        currentScenario = scenario;

        // Update tab styles
        document.querySelectorAll('.scenario-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.scenario === scenario);
        });

        // Recalculate with scenario multipliers
        recalculateInvestment();
    }

    /**
     * Recalculate all investment figures
     */
    function recalculateInvestment() {
        const scenario = SCENARIOS[currentScenario] || SCENARIOS.expected;

        // Get input values
        const basePrice = parseFloat(document.getElementById('calc-base-price').value) || 0;
        const commissionPct = parseFloat(document.getElementById('calc-commission-pct').textContent) || 0;
        const feeRow = document.getElementById('calc-fee-row');
        const feePct = feeRow && feeRow.style.display !== 'none' ?
            parseFloat(document.getElementById('calc-fee-pct').textContent) || 0 : 0;
        const ivaPct = 21;

        let transport = parseFloat(document.getElementById('calc-transport').value) || 0;
        let repairs = parseFloat(document.getElementById('calc-repairs').value) || 0;
        let legal = parseFloat(document.getElementById('calc-legal').value) || 0;
        let other = parseFloat(document.getElementById('calc-other').value) || 0;
        let resale = parseFloat(document.getElementById('calc-resale').value) || 0;

        // Apply scenario multipliers
        transport = Math.round(transport * scenario.transportMultiplier);
        repairs = Math.round(repairs * scenario.repairMultiplier);
        other = Math.round(other * scenario.otherMultiplier);
        resale = Math.round(resale * scenario.resaleMultiplier);

        // Calculate acquisition costs
        const commission = basePrice * (commissionPct / 100);
        const fee = basePrice * (feePct / 100);
        const iva = basePrice * (ivaPct / 100);
        const acquisitionTotal = basePrice + commission + fee + iva;

        // Update display
        document.getElementById('calc-commission').textContent = '$' + Math.round(commission).toLocaleString();
        document.getElementById('calc-fee').textContent = '$' + Math.round(fee).toLocaleString();
        document.getElementById('calc-iva').textContent = '$' + Math.round(iva).toLocaleString();
        document.getElementById('calc-acquisition-total').textContent = 'USD ' + Math.round(acquisitionTotal).toLocaleString();

        // Calculate total investment
        const totalInvestment = acquisitionTotal + transport + repairs + legal + other;

        // Update summary
        document.getElementById('calc-summary-acquisition').textContent = 'USD ' + Math.round(acquisitionTotal).toLocaleString();
        document.getElementById('calc-summary-transport').textContent = 'USD ' + transport.toLocaleString();
        document.getElementById('calc-summary-repairs').textContent = 'USD ' + repairs.toLocaleString();
        document.getElementById('calc-summary-legal').textContent = 'USD ' + legal.toLocaleString();
        document.getElementById('calc-summary-other').textContent = 'USD ' + other.toLocaleString();
        document.getElementById('calc-total-investment').textContent = 'USD ' + Math.round(totalInvestment).toLocaleString();

        // Calculate profit
        const profit = resale - totalInvestment;
        const roi = totalInvestment > 0 ? (profit / totalInvestment) * 100 : 0;
        const breakeven = totalInvestment;

        // Update profit display
        document.getElementById('calc-summary-resale').textContent = 'USD ' + resale.toLocaleString();
        document.getElementById('calc-summary-investment').textContent = 'USD ' + Math.round(totalInvestment).toLocaleString();

        const profitEl = document.getElementById('calc-profit');
        profitEl.textContent = (profit >= 0 ? '+' : '') + 'USD ' + Math.round(profit).toLocaleString();
        profitEl.className = 'font-display font-bold text-xl ' + (profit >= 0 ? 'profit-positive' : 'profit-negative');

        const roiEl = document.getElementById('calc-roi');
        roiEl.textContent = (roi >= 0 ? '+' : '') + roi.toFixed(1) + '%';
        roiEl.className = 'font-bold text-lg ' + (roi >= 0 ? 'profit-positive' : 'profit-negative');

        document.getElementById('calc-breakeven').textContent = 'USD ' + Math.round(breakeven).toLocaleString();

        // Store results for export
        calculatorResults = {
            auction: currentAuction,
            scenario: currentScenario,
            basePrice,
            commission,
            fee,
            iva,
            acquisitionTotal,
            transport,
            repairs,
            legal,
            other,
            totalInvestment,
            resale,
            profit,
            roi,
            breakeven
        };
    }

    /**
     * Apply quick estimate for transport or repairs
     */
    function applyQuickEstimate(type) {
        if (!currentAuction) return;

        if (type === 'transport') {
            const estimate = estimateTransport(currentAuction);
            document.getElementById('calc-transport').value = estimate;
        } else if (type === 'repairs') {
            const estimate = estimateRepairs(currentAuction);
            document.getElementById('calc-repairs').value = estimate;
        }

        recalculateInvestment();
    }

    /**
     * Export calculator as PDF
     */
    function exportCalculatorPDF() {
        if (!calculatorResults) {
            alert('Calcula primero para exportar');
            return;
        }

        const r = calculatorResults;
        const html = `
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Analisis de Inversion - Subasto.com.ar</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; color: #1f2937; padding: 40px; max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #eab308; padding-bottom: 20px; }
        .logo { font-size: 28px; font-weight: bold; color: #eab308; }
        .date { color: #6b7280; font-size: 12px; margin-top: 5px; }
        .title { font-size: 16px; color: #374151; margin-top: 10px; }
        h2 { font-size: 16px; margin: 20px 0 10px; color: #374151; border-left: 4px solid #eab308; padding-left: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0 20px; }
        th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        .amount { text-align: right; font-family: monospace; }
        .total { background: #fef3c7; font-weight: bold; }
        .profit { font-size: 24px; text-align: center; padding: 20px; margin: 20px 0; border-radius: 8px; }
        .profit.positive { background: #d1fae5; color: #065f46; }
        .profit.negative { background: #fee2e2; color: #991b1b; }
        .scenario { text-align: center; padding: 10px; background: #f3f4f6; border-radius: 4px; margin-bottom: 20px; }
        .footer { margin-top: 40px; text-align: center; color: #9ca3af; font-size: 11px; }
        @media print { body { padding: 20px; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">SUBASTO</div>
        <div>Analisis de Inversion</div>
        <div class="date">Generado: ${new Date().toLocaleDateString('es-AR')} ${new Date().toLocaleTimeString('es-AR')}</div>
        <div class="title">${r.auction ? r.auction.title : 'Subasta'}</div>
    </div>

    <div class="scenario">Escenario: <strong>${SCENARIOS[r.scenario].label}</strong></div>

    <h2>Costos de Adquisicion</h2>
    <table>
        <tr><td>Precio Base</td><td class="amount">USD ${r.basePrice.toLocaleString()}</td></tr>
        <tr><td>Comision</td><td class="amount">USD ${Math.round(r.commission).toLocaleString()}</td></tr>
        <tr><td>Arancel</td><td class="amount">USD ${Math.round(r.fee).toLocaleString()}</td></tr>
        <tr><td>IVA (21%)</td><td class="amount">USD ${Math.round(r.iva).toLocaleString()}</td></tr>
        <tr class="total"><td>Subtotal Adquisicion</td><td class="amount">USD ${Math.round(r.acquisitionTotal).toLocaleString()}</td></tr>
    </table>

    <h2>Costos Adicionales</h2>
    <table>
        <tr><td>Transporte</td><td class="amount">USD ${r.transport.toLocaleString()}</td></tr>
        <tr><td>Reparaciones</td><td class="amount">USD ${r.repairs.toLocaleString()}</td></tr>
        <tr><td>Tramites/Legal</td><td class="amount">USD ${r.legal.toLocaleString()}</td></tr>
        <tr><td>Otros</td><td class="amount">USD ${r.other.toLocaleString()}</td></tr>
    </table>

    <h2>Resumen</h2>
    <table>
        <tr class="total"><td>INVERSION TOTAL</td><td class="amount">USD ${Math.round(r.totalInvestment).toLocaleString()}</td></tr>
        <tr><td>Precio de Reventa Est.</td><td class="amount">USD ${r.resale.toLocaleString()}</td></tr>
        <tr><td>Precio Break-Even</td><td class="amount">USD ${Math.round(r.breakeven).toLocaleString()}</td></tr>
    </table>

    <div class="profit ${r.profit >= 0 ? 'positive' : 'negative'}">
        <div>GANANCIA POTENCIAL</div>
        <div style="font-size: 32px; font-weight: bold;">${r.profit >= 0 ? '+' : ''}USD ${Math.round(r.profit).toLocaleString()}</div>
        <div style="margin-top: 10px;">ROI: ${r.roi >= 0 ? '+' : ''}${r.roi.toFixed(1)}%</div>
    </div>

    <div class="footer">
        <p>Este analisis es una estimacion. Verificar condiciones antes de ofertar.</p>
        <p>Generado por Subasto.com.ar - El agregador de subastas de Argentina</p>
    </div>
</body>
</html>`;

        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const printWindow = window.open(url, '_blank');
        if (printWindow) {
            printWindow.onload = function() {
                printWindow.print();
            };
        }
    }

    /**
     * Export calculator as image (screenshot)
     */
    function exportCalculatorImage() {
        const modalContent = document.querySelector('.calc-modal-content');
        if (!modalContent) {
            alert('No se puede capturar la imagen');
            return;
        }

        // Use html2canvas if available
        if (typeof html2canvas !== 'undefined') {
            html2canvas(modalContent, {
                backgroundColor: '#1a1a1a',
                scale: 2
            }).then(canvas => {
                const link = document.createElement('a');
                link.download = 'analisis-inversion-subasto.png';
                link.href = canvas.toDataURL();
                link.click();
            });
        } else {
            // Fallback: copy data to clipboard as text
            if (calculatorResults) {
                const r = calculatorResults;
                const text = `Analisis de Inversion - Subasto.com.ar
${r.auction ? r.auction.title : 'Subasta'}
Escenario: ${SCENARIOS[r.scenario].label}

Inversion Total: USD ${Math.round(r.totalInvestment).toLocaleString()}
Precio Reventa: USD ${r.resale.toLocaleString()}
Ganancia: ${r.profit >= 0 ? '+' : ''}USD ${Math.round(r.profit).toLocaleString()}
ROI: ${r.roi >= 0 ? '+' : ''}${r.roi.toFixed(1)}%

subasto.com.ar`;

                navigator.clipboard.writeText(text).then(() => {
                    alert('Datos copiados al portapapeles');
                }).catch(() => {
                    alert('Para capturar imagen, usa la funcion de captura de tu navegador');
                });
            }
        }
    }

    /**
     * Calculate quick ROI for an auction (for badge display)
     */
    function calculateQuickROI(auction) {
        if (!auction.base_price || auction.base_price === 0) return null;

        const basePrice = getBasePriceUSD(auction);
        const marketValue = auction.market_data ?
            (auction.market_data.typical_usd || auction.market_data.market_price_usd) : null;

        if (!marketValue) return null;

        // Quick estimate: acquisition costs ~25% of base, resale at 95% of market
        const estimatedCosts = basePrice * 1.25;
        const estimatedResale = marketValue * 0.95;
        const profit = estimatedResale - estimatedCosts;
        const roi = (profit / estimatedCosts) * 100;

        return {
            roi: Math.round(roi),
            profit: Math.round(profit),
            isPositive: roi > 0
        };
    }

    /**
     * Get risk level for an auction category
     */
    function getRiskLevel(category) {
        return CATEGORY_RISK[category] || CATEGORY_RISK.other;
    }

    /**
     * Generate HTML for ROI badge
     */
    function generateROIBadge(auction) {
        const roiData = calculateQuickROI(auction);
        if (!roiData) return '';

        const badgeClass = roiData.roi >= 20 ? 'positive' :
                          roiData.roi >= 0 ? 'neutral' : 'negative';

        return `<span class="roi-badge ${badgeClass}" title="ROI estimado">
            ${roiData.roi >= 0 ? '+' : ''}${roiData.roi}% ROI
        </span>`;
    }

    /**
     * Generate HTML for risk indicator
     */
    function generateRiskIndicator(category) {
        const risk = getRiskLevel(category);
        return `<span class="risk-indicator risk-${risk.level}" title="${risk.reason}">
            ${risk.level === 'low' ? 'Bajo' : risk.level === 'medium' ? 'Medio' : 'Alto'} Riesgo
        </span>`;
    }

    /**
     * Generate calculator button HTML
     */
    function generateCalcButton(auctionId) {
        return `<button class="calc-btn" onclick="InvestmentCalculator.openByIndex(${auctionId})" title="Calcular inversion">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
            </svg>
            Calcular
        </button>`;
    }

    /**
     * Open calculator by auction index (from allAuctions array)
     */
    function openByIndex(index) {
        if (window.allAuctions && window.allAuctions[index]) {
            openCalculator(window.allAuctions[index]);
        }
    }

    // Close on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeCalculator();
        }
    });

    // Export to global scope
    global.InvestmentCalculator = {
        open: openCalculator,
        openByIndex: openByIndex,
        close: closeCalculator,
        setScenario: setScenario,
        recalculate: recalculateInvestment,
        applyQuickEstimate: applyQuickEstimate,
        exportPDF: exportCalculatorPDF,
        exportImage: exportCalculatorImage,
        calculateQuickROI: calculateQuickROI,
        getRiskLevel: getRiskLevel,
        generateROIBadge: generateROIBadge,
        generateRiskIndicator: generateRiskIndicator,
        generateCalcButton: generateCalcButton
    };

    // Also expose these functions globally for onclick handlers
    global.openCalculator = openCalculator;
    global.closeCalculator = closeCalculator;
    global.setScenario = setScenario;
    global.recalculateInvestment = recalculateInvestment;
    global.applyQuickEstimate = applyQuickEstimate;
    global.exportCalculatorPDF = exportCalculatorPDF;
    global.exportCalculatorImage = exportCalculatorImage;

})(typeof window !== 'undefined' ? window : global);
