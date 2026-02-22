#!/usr/bin/env python3
"""Patch index.html to add location-based features UI."""

import re

# Read original file
with open('site/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old and new filter sections
old_filters = '''<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <!-- Source Filter -->
                    <div>
                        <label class="text-xs uppercase tracking-wider text-white/40 mb-2 block">Source</label>
                        <select id="source-filter" class="w-full bg-[#1a1a1a] border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50" onchange="applyFilters()">
                            <option value="" class="bg-[#1a1a1a] text-white">All Sources</option>
                        </select>
                    </div>
                    <!-- Location Filter -->
                    <div>
                        <label class="text-xs uppercase tracking-wider text-white/40 mb-2 block">Location</label>
                        <select id="location-filter" class="w-full bg-[#1a1a1a] border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50" onchange="applyFilters()">
                            <option value="" class="bg-[#1a1a1a] text-white">All Locations</option>
                        </select>
                    </div>
                    <!-- Sort -->
                    <div>
                        <label class="text-xs uppercase tracking-wider text-white/40 mb-2 block">Sort By</label>
                        <select id="sort-filter" class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50" onchange="applyFilters()">
                            <option value="recommended" selected>Recommended</option>
                            <option value="ending">Ending Soon</option>
                            <option value="discount">Best Deals</option>
                            <option value="price-asc">Price: Low to High</option>
                            <option value="price-desc">Price: High to Low</option>
                            <option value="newest">Newest First</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- TOP OPPORTUNITIES SECTION -->'''

new_filters = '''<div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <!-- Source Filter -->
                    <div>
                        <label class="text-xs uppercase tracking-wider text-white/40 mb-2 block">Source</label>
                        <select id="source-filter" class="w-full bg-[#1a1a1a] border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50" onchange="applyFilters()">
                            <option value="" class="bg-[#1a1a1a] text-white">All Sources</option>
                        </select>
                    </div>
                    <!-- Province Filter -->
                    <div>
                        <label class="text-xs uppercase tracking-wider text-white/40 mb-2 block">Province</label>
                        <select id="location-filter" class="w-full bg-[#1a1a1a] border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50" onchange="applyFilters()">
                            <option value="" class="bg-[#1a1a1a] text-white">All Provinces</option>
                        </select>
                    </div>
                    <!-- Radius Filter (appears when location is set) -->
                    <div id="radius-filter-container" style="display: none;">
                        <label class="text-xs uppercase tracking-wider text-white/40 mb-2 block">Distance</label>
                        <select id="radius-filter" class="w-full bg-[#1a1a1a] border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50" onchange="applyFilters()">
                            <option value="">Any distance</option>
                            <option value="50">Within 50 km</option>
                            <option value="100">Within 100 km</option>
                            <option value="200">Within 200 km</option>
                            <option value="500">Within 500 km</option>
                            <option value="1000">Within 1000 km</option>
                        </select>
                    </div>
                    <!-- Sort -->
                    <div>
                        <label class="text-xs uppercase tracking-wider text-white/40 mb-2 block">Sort By</label>
                        <select id="sort-filter" class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50" onchange="applyFilters()">
                            <option value="recommended" selected>Recommended</option>
                            <option value="distance">Nearest First</option>
                            <option value="ending">Ending Soon</option>
                            <option value="discount">Best Deals</option>
                            <option value="price-asc">Price: Low to High</option>
                            <option value="price-desc">Price: High to Low</option>
                            <option value="newest">Newest First</option>
                        </select>
                    </div>
                </div>
                <!-- Location Controls Row -->
                <div class="flex flex-wrap items-center gap-4 mt-4 pt-4 border-t border-white/5">
                    <button id="near-me-btn" class="glass rounded-full px-4 py-2 text-xs uppercase tracking-wider text-yellow-400 hover:text-white transition-all flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                        </svg>
                        Cerca de mi
                    </button>
                    <button id="toggle-map-btn" class="glass rounded-full px-4 py-2 text-xs uppercase tracking-wider text-yellow-400 hover:text-white transition-all flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
                        </svg>
                        Ver Mapa
                    </button>
                    <div id="location-info" class="flex-1"></div>
                </div>
            </div>

            <!-- Map Container (hidden by default) -->
            <div id="map-container" class="mb-8 hidden">
                <div class="glass rounded-2xl p-4">
                    <div id="auction-map" class="rounded-xl"></div>
                    <div class="flex flex-wrap gap-4 mt-4 justify-center">
                        <div class="flex items-center gap-2 text-xs text-white/60">
                            <span class="w-3 h-3 rounded-full bg-blue-500"></span> Vehicles
                        </div>
                        <div class="flex items-center gap-2 text-xs text-white/60">
                            <span class="w-3 h-3 rounded-full bg-pink-500"></span> Real Estate
                        </div>
                        <div class="flex items-center gap-2 text-xs text-white/60">
                            <span class="w-3 h-3 rounded-full bg-yellow-500"></span> Machinery
                        </div>
                        <div class="flex items-center gap-2 text-xs text-white/60">
                            <span class="w-3 h-3 rounded-full bg-green-500"></span> General Goods
                        </div>
                    </div>
                </div>
            </div>

            <!-- TOP OPPORTUNITIES SECTION -->'''

if old_filters in content:
    content = content.replace(old_filters, new_filters)
    print('Filter section updated successfully')
else:
    print('Could not find filter section to replace')

# Write back
with open('site/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
