#!/usr/bin/env python3
"""Add JavaScript for source analytics to index.html."""

from pathlib import Path

index_path = Path("site/index.html")
content = index_path.read_text(encoding="utf-8")

# The marker to find
old_marker = '''        // Initialize
        fetchAuctions();
    </script>'''

# The new JavaScript to add
new_js = '''        // Initialize
        fetchAuctions();
        fetchSourceAnalytics();

        // Source Analytics - cached data
        let sourceAnalytics = null;

        // Fetch source analytics data
        async function fetchSourceAnalytics() {
            try {
                const response = await fetch('/api/v1/sources.json?t=' + Date.now());
                if (!response.ok) throw new Error('Failed to fetch source analytics');
                const data = await response.json();
                sourceAnalytics = data.data;
                renderSourceTable();
            } catch (err) {
                console.error('Error fetching source analytics:', err);
                const tbody = document.getElementById('source-table-body');
                if (tbody) {
                    tbody.innerHTML = '<tr><td colspan="7" class="py-8 text-center text-white/40">Unable to load source data</td></tr>';
                }
            }
        }

        // Render source comparison table
        function renderSourceTable() {
            if (!sourceAnalytics || !sourceAnalytics.sources) return;

            const tbody = document.getElementById('source-table-body');
            if (!tbody) return;

            let html = '';

            for (const [sourceId, metrics] of Object.entries(sourceAnalytics.sources)) {
                const isJudicial = metrics.source_type === 'judicial';
                const badgeColor = isJudicial ? 'emerald' : (metrics.is_government ? 'blue' : 'amber');
                const badgeText = isJudicial ? 'Judicial' : (metrics.is_government ? 'Estatal' : 'Privada');

                let trustColor = 'text-white/60';
                if (metrics.trust_score >= 80) trustColor = 'text-emerald-400';
                else if (metrics.trust_score >= 60) trustColor = 'text-blue-400';
                else if (metrics.trust_score >= 40) trustColor = 'text-yellow-400';

                let qualityColor = 'text-white/60';
                if (metrics.quality_score >= 80) qualityColor = 'text-emerald-400';
                else if (metrics.quality_score >= 60) qualityColor = 'text-blue-400';
                else if (metrics.quality_score >= 40) qualityColor = 'text-yellow-400';

                const trustBarColor = metrics.trust_score >= 70 ? 'emerald' : metrics.trust_score >= 50 ? 'yellow' : 'red';
                const qualityBarColor = metrics.quality_score >= 70 ? 'emerald' : metrics.quality_score >= 50 ? 'yellow' : 'red';

                html += `
                    <tr class="border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer" onclick="filterBySource('${sourceId}')">
                        <td class="py-4 pr-4">
                            <div class="font-medium text-white">${metrics.source_name}</div>
                        </td>
                        <td class="py-4 px-4 text-center">
                            <span class="inline-flex items-center px-2 py-1 rounded-full text-[10px] font-medium bg-${badgeColor}-500/20 text-${badgeColor}-400 uppercase tracking-wider">
                                ${badgeText}
                            </span>
                        </td>
                        <td class="py-4 px-4 text-center">
                            <div class="flex items-center justify-center gap-2">
                                <div class="w-12 h-1.5 bg-white/10 rounded-full overflow-hidden">
                                    <div class="h-full bg-${trustBarColor}-500 rounded-full" style="width: ${metrics.trust_score}%"></div>
                                </div>
                                <span class="${trustColor} text-sm font-medium">${metrics.trust_score}</span>
                            </div>
                        </td>
                        <td class="py-4 px-4 text-center">
                            <div class="flex items-center justify-center gap-2">
                                <div class="w-12 h-1.5 bg-white/10 rounded-full overflow-hidden">
                                    <div class="h-full bg-${qualityBarColor}-500 rounded-full" style="width: ${metrics.quality_score}%"></div>
                                </div>
                                <span class="${qualityColor} text-sm font-medium">${metrics.quality_score}</span>
                            </div>
                        </td>
                        <td class="py-4 px-4 text-center">
                            <span class="text-white/80">${metrics.total_listings}</span>
                        </td>
                        <td class="py-4 px-4 text-center">
                            <span class="${isJudicial ? 'text-emerald-400' : 'text-white/60'}">${metrics.buyer_commission_pct}%</span>
                        </td>
                        <td class="py-4 pl-4 text-right">
                            <span class="${metrics.iva_included ? 'text-yellow-400' : 'text-emerald-400'}">${metrics.iva_included ? 'Si' : 'No'}</span>
                        </td>
                    </tr>
                `;
            }

            tbody.innerHTML = html;
        }

        // Enhanced source type filter variable
        let currentSourceTypeFilter = null;

        // Filter by source type (judicial, trusted, quality, all)
        function filterBySourceType(type) {
            const sourceSelect = document.getElementById('source-filter');
            if (sourceSelect) sourceSelect.value = '';

            let validSources = [];
            const judicialSources = ['csjn', 'scba', 'cordoba', 'entrerios'];

            if (sourceAnalytics && sourceAnalytics.sources) {
                for (const [sourceId, metrics] of Object.entries(sourceAnalytics.sources)) {
                    if (type === 'judicial' && metrics.source_type === 'judicial') {
                        validSources.push(sourceId);
                    } else if (type === 'trusted' && metrics.trust_score >= 70) {
                        validSources.push(sourceId);
                    } else if (type === 'quality' && metrics.quality_score >= 80) {
                        validSources.push(sourceId);
                    }
                }
            }

            if (validSources.length === 0 && type === 'judicial') {
                validSources = judicialSources;
            }

            if (type === 'all') {
                currentSourceTypeFilter = null;
            } else {
                currentSourceTypeFilter = validSources;
            }

            if (typeof applyFilters === 'function') applyFilters();
            document.getElementById('auctions')?.scrollIntoView({ behavior: 'smooth' });
        }
    </script>'''

if old_marker in content:
    content = content.replace(old_marker, new_js)
    index_path.write_text(content, encoding="utf-8")
    print("Successfully added JavaScript for source analytics!")
else:
    print("Could not find the marker to replace")
