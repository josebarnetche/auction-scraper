#!/usr/bin/env python3
"""Patch applyFilters to add distance filtering and sorting."""

# Read original file
with open('site/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Update applyFilters to include radius filter
old_filter_setup = '''function applyFilters() {
            const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();
            const minPrice = parseFloat(document.getElementById('min-price').value) || 0;
            const maxPrice = parseFloat(document.getElementById('max-price').value);
            const maxPriceVal = maxPrice >= 500000 ? Infinity : maxPrice;
            const sourceFilter = document.getElementById('source-filter').value;
            const locationFilter = document.getElementById('location-filter').value;
            const sortBy = document.getElementById('sort-filter').value;'''

new_filter_setup = '''function applyFilters() {
            const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();
            const minPrice = parseFloat(document.getElementById('min-price').value) || 0;
            const maxPrice = parseFloat(document.getElementById('max-price').value);
            const maxPriceVal = maxPrice >= 500000 ? Infinity : maxPrice;
            const sourceFilter = document.getElementById('source-filter').value;
            const locationFilter = document.getElementById('location-filter').value;
            const sortBy = document.getElementById('sort-filter').value;
            const radiusFilter = parseFloat(document.getElementById('radius-filter')?.value) || 0;'''

if old_filter_setup in content:
    content = content.replace(old_filter_setup, new_filter_setup)
    print('Added radius filter variable')
else:
    print('Could not find filter setup to patch')

# Add distance filter after location filter
old_location_filter = '''// Location filter
                if (locationFilter && auction.location?.province !== locationFilter) return false;

                return true;'''

new_location_filter = '''// Location filter
                if (locationFilter && auction.location?.province !== locationFilter) return false;

                // Distance filter (if user location is set and radius selected)
                if (radiusFilter > 0 && typeof SubastoLocation !== 'undefined') {
                    const distance = SubastoLocation.getDistanceToAuction(auction);
                    if (distance === null || distance > radiusFilter) return false;
                }

                return true;'''

if old_location_filter in content:
    content = content.replace(old_location_filter, new_location_filter)
    print('Added distance filter')
else:
    print('Could not find location filter to patch')

# Add distance sorting option
old_sort = '''                    case 'ending':
                        const aEnd = a.ends_at ? new Date(a.ends_at) : new Date('2099-01-01');
                        const bEnd = b.ends_at ? new Date(b.ends_at) : new Date('2099-01-01');
                        return aEnd - bEnd;'''

new_sort = '''                    case 'distance':
                        // Sort by distance if location module is available
                        if (typeof SubastoLocation !== 'undefined') {
                            const distA = SubastoLocation.getDistanceToAuction(a) || Infinity;
                            const distB = SubastoLocation.getDistanceToAuction(b) || Infinity;
                            return distA - distB;
                        }
                        return 0;
                    case 'ending':
                        const aEnd = a.ends_at ? new Date(a.ends_at) : new Date('2099-01-01');
                        const bEnd = b.ends_at ? new Date(b.ends_at) : new Date('2099-01-01');
                        return aEnd - bEnd;'''

if old_sort in content:
    content = content.replace(old_sort, new_sort)
    print('Added distance sorting')
else:
    print('Could not find sort section to patch')

# Add map update after render
old_render = '''document.getElementById('results-count').textContent = filteredAuctions.length;
            displayedCount = 12;
            renderAuctions();
        }'''

new_render = '''document.getElementById('results-count').textContent = filteredAuctions.length;
            displayedCount = 12;
            renderAuctions();

            // Update map if visible
            if (typeof SubastoLocation !== 'undefined' && SubastoLocation.isMapVisible()) {
                SubastoLocation.updateMapMarkers(filteredAuctions);
            }
        }'''

if old_render in content:
    content = content.replace(old_render, new_render)
    print('Added map update on filter')
else:
    print('Could not find render section to patch')

# Write back
with open('site/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
