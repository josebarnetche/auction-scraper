#!/usr/bin/env python3
"""Patch the Sources section in index.html with enhanced analytics."""

from pathlib import Path

# Read the current file
index_path = Path("site/index.html")
content = index_path.read_text(encoding="utf-8")

# Define the old section to replace
old_section = '''    <!-- SOURCES SECTION -->
    <section class="py-20 px-4 md:px-6 bg-black/70 border-t border-white/5 relative z-10" id="sources">
        <div class="max-w-[1400px] mx-auto">
            <div class="text-center mb-16">
                <h2 class="text-3xl md:text-5xl font-display font-medium text-white tracking-tight mb-4">Monitored Sources</h2>
                <p class="text-yellow-400/80">Aggregating from judicial and private auction platforms</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="glass rounded-2xl p-8 text-center hover:bg-white/5 transition-colors">
                    <div class="w-16 h-16 rounded-full bg-yellow-500/10 flex items-center justify-center mx-auto mb-6">
                        <svg class="w-8 h-8 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
                        </svg>
                    </div>
                    <h3 class="text-xl font-display font-medium text-white mb-2">Judicial Auctions</h3>
                    <p class="text-white/60 text-sm mb-4">Court-ordered auctions from CSJN, SCBA, Córdoba & Entre Ríos</p>
                    <div class="text-yellow-500 text-xs uppercase tracking-wider">4 Sources</div>
                </div>

                <div class="glass rounded-2xl p-8 text-center hover:bg-white/5 transition-colors">
                    <div class="w-16 h-16 rounded-full bg-blue-500/10 flex items-center justify-center mx-auto mb-6">
                        <svg class="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                        </svg>
                    </div>
                    <h3 class="text-xl font-display font-medium text-white mb-2">Private Auctions</h3>
                    <p class="text-white/60 text-sm mb-4">Banco Ciudad, Agusti, Global Remates, Adrián Mercado & more</p>
                    <div class="text-blue-400 text-xs uppercase tracking-wider">10 Sources</div>
                </div>

                <div class="glass rounded-2xl p-8 text-center hover:bg-white/5 transition-colors">
                    <div class="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-6">
                        <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                    </div>
                    <h3 class="text-xl font-display font-medium text-white mb-2">Daily Updates</h3>
                    <p class="text-white/60 text-sm mb-4">Data refreshed automatically at midnight Argentina time</p>
                    <div class="text-green-400 text-xs uppercase tracking-wider">00:00 GMT-3</div>
                </div>
            </div>
        </div>
    </section>'''

# Define the new enhanced section
new_section = '''    <!-- SOURCES SECTION -->
    <section class="py-20 px-4 md:px-6 bg-black/70 border-t border-white/5 relative z-10" id="sources">
        <div class="max-w-[1400px] mx-auto">
            <div class="text-center mb-16">
                <h2 class="text-3xl md:text-5xl font-display font-medium text-white tracking-tight mb-4">Source Analytics</h2>
                <p class="text-yellow-400/80">Compare auction houses by trust, quality, and fees</p>
            </div>

            <!-- Source Type Cards -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
                <div class="glass rounded-2xl p-8 text-center hover:bg-white/5 transition-colors border border-emerald-500/20">
                    <div class="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-6">
                        <svg class="w-8 h-8 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"/>
                        </svg>
                    </div>
                    <h3 class="text-xl font-display font-medium text-white mb-2">Judicial Auctions</h3>
                    <p class="text-white/60 text-sm mb-4">Government-operated. Highest trust. 3% fees.</p>
                    <div class="flex items-center justify-center gap-2">
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-[10px] font-medium bg-emerald-500/20 text-emerald-400 uppercase tracking-wider">Recommended</span>
                        <span class="text-emerald-400 text-xs">4 Sources</span>
                    </div>
                </div>

                <div class="glass rounded-2xl p-8 text-center hover:bg-white/5 transition-colors">
                    <div class="w-16 h-16 rounded-full bg-blue-500/10 flex items-center justify-center mx-auto mb-6">
                        <svg class="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                        </svg>
                    </div>
                    <h3 class="text-xl font-display font-medium text-white mb-2">Private Auctions</h3>
                    <p class="text-white/60 text-sm mb-4">Commercial operators. 10-15% fees + IVA.</p>
                    <div class="flex items-center justify-center gap-2">
                        <span class="text-blue-400 text-xs uppercase tracking-wider">10 Sources</span>
                    </div>
                </div>

                <div class="glass rounded-2xl p-8 text-center hover:bg-white/5 transition-colors">
                    <div class="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-6">
                        <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                    </div>
                    <h3 class="text-xl font-display font-medium text-white mb-2">Daily Updates</h3>
                    <p class="text-white/60 text-sm mb-4">All sources scraped every 24 hours automatically.</p>
                    <div class="text-green-400 text-xs uppercase tracking-wider">00:00 GMT-3</div>
                </div>
            </div>

            <!-- WHY JUDICIAL EXPLAINER -->
            <div class="glass rounded-2xl p-8 mb-16 border border-emerald-500/20 bg-emerald-500/5">
                <div class="flex flex-col md:flex-row items-start gap-8">
                    <div class="flex-shrink-0">
                        <div class="w-20 h-20 rounded-full bg-emerald-500/20 flex items-center justify-center">
                            <svg class="w-10 h-10 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                            </svg>
                        </div>
                    </div>
                    <div class="flex-1">
                        <h3 class="text-2xl font-display font-medium text-white mb-4">Por que elegir subastas judiciales?</h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                            <div class="flex items-start gap-3">
                                <svg class="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                </svg>
                                <div>
                                    <div class="text-white font-medium text-sm">Seguridad Juridica</div>
                                    <div class="text-white/50 text-xs">Supervisadas por el Poder Judicial</div>
                                </div>
                            </div>
                            <div class="flex items-start gap-3">
                                <svg class="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                </svg>
                                <div>
                                    <div class="text-white font-medium text-sm">Menores Comisiones</div>
                                    <div class="text-white/50 text-xs">3% vs 10-15% en privadas</div>
                                </div>
                            </div>
                            <div class="flex items-start gap-3">
                                <svg class="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                </svg>
                                <div>
                                    <div class="text-white font-medium text-sm">Titulos Claros</div>
                                    <div class="text-white/50 text-xs">Sin gravamenes ocultos</div>
                                </div>
                            </div>
                            <div class="flex items-start gap-3">
                                <svg class="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                </svg>
                                <div>
                                    <div class="text-white font-medium text-sm">Precios Justos</div>
                                    <div class="text-white/50 text-xs">Tasaciones por peritos judiciales</div>
                                </div>
                            </div>
                            <div class="flex items-start gap-3">
                                <svg class="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                </svg>
                                <div>
                                    <div class="text-white font-medium text-sm">Sin IVA</div>
                                    <div class="text-white/50 text-xs">Para compradores particulares</div>
                                </div>
                            </div>
                            <div class="flex items-start gap-3">
                                <svg class="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                </svg>
                                <div>
                                    <div class="text-white font-medium text-sm">Proceso Transparente</div>
                                    <div class="text-white/50 text-xs">Expediente publico disponible</div>
                                </div>
                            </div>
                        </div>
                        <a href="#auctions" onclick="filterBySourceType('judicial')" class="inline-flex items-center gap-2 text-emerald-400 hover:text-white text-sm font-medium transition-colors">
                            Ver subastas judiciales
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/>
                            </svg>
                        </a>
                    </div>
                </div>
            </div>

            <!-- SOURCE COMPARISON TABLE -->
            <div class="glass rounded-2xl p-6 md:p-8 overflow-hidden">
                <h3 class="text-xl font-display font-medium text-white mb-6 flex items-center gap-3">
                    <svg class="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    Source Comparison
                </h3>
                <div class="overflow-x-auto -mx-6 md:-mx-8 px-6 md:px-8">
                    <table class="w-full min-w-[800px]" id="source-comparison-table">
                        <thead>
                            <tr class="text-left text-xs uppercase tracking-wider text-white/40 border-b border-white/10">
                                <th class="pb-4 pr-4">Source</th>
                                <th class="pb-4 px-4 text-center">Type</th>
                                <th class="pb-4 px-4 text-center">Trust</th>
                                <th class="pb-4 px-4 text-center">Quality</th>
                                <th class="pb-4 px-4 text-center">Listings</th>
                                <th class="pb-4 px-4 text-center">Commission</th>
                                <th class="pb-4 pl-4 text-right">IVA</th>
                            </tr>
                        </thead>
                        <tbody id="source-table-body">
                            <!-- Populated by JavaScript -->
                            <tr><td colspan="7" class="py-8 text-center text-white/40">Loading source analytics...</td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="mt-6 pt-6 border-t border-white/10 flex items-center justify-between">
                    <div class="text-xs text-white/40">
                        Trust Score: Government backing + years operating + transparency
                    </div>
                    <a href="/api/v1/sources.json" target="_blank" class="text-xs text-yellow-500 hover:text-white transition-colors flex items-center gap-1">
                        API: /api/v1/sources
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                        </svg>
                    </a>
                </div>
            </div>

            <!-- FILTER BY SOURCE QUALITY -->
            <div class="mt-8 glass rounded-2xl p-6">
                <h4 class="text-sm font-medium text-white/60 uppercase tracking-wider mb-4">Filter by Source Quality</h4>
                <div class="flex flex-wrap gap-3" id="source-quality-filters">
                    <button onclick="filterBySourceType('all')" class="source-quality-btn px-4 py-2 rounded-full text-sm font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 hover:bg-yellow-500/30 transition-colors">
                        All Sources
                    </button>
                    <button onclick="filterBySourceType('judicial')" class="source-quality-btn px-4 py-2 rounded-full text-sm font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors">
                        Judicial Only (3% fees)
                    </button>
                    <button onclick="filterBySourceType('trusted')" class="source-quality-btn px-4 py-2 rounded-full text-sm font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors">
                        High Trust (70+)
                    </button>
                    <button onclick="filterBySourceType('quality')" class="source-quality-btn px-4 py-2 rounded-full text-sm font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 hover:bg-purple-500/20 transition-colors">
                        High Quality (80+)
                    </button>
                </div>
            </div>
        </div>
    </section>'''

# Perform the replacement
if old_section in content:
    content = content.replace(old_section, new_section)
    index_path.write_text(content, encoding="utf-8")
    print("Successfully patched the Sources section!")
else:
    print("Could not find the old section to replace. The file may have been modified.")
    print("Looking for partial match...")
    if "Monitored Sources" in content:
        print("Found 'Monitored Sources' - section exists but may have different formatting")
    else:
        print("Section appears to be already updated or missing")
