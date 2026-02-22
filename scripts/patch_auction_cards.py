#!/usr/bin/env python3
"""Patch renderAuctions to add location badges and transport costs."""

# Read original file
with open('site/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add logistics-calculator.js script
if 'logistics-calculator.js' not in content:
    old_scripts = '''    <!-- Location Features -->
    <script src="/js/location.js"></script>
</body>'''

    new_scripts = '''    <!-- Location Features -->
    <script src="/js/location.js"></script>
    <script src="/js/logistics-calculator.js"></script>
</body>'''

    if old_scripts in content:
        content = content.replace(old_scripts, new_scripts)
        print('Added logistics-calculator.js')
    else:
        print('Could not find location scripts section')

# Patch the card rendering to include location badge
# Find the category badge and add location badge after it
old_badges = '''<div class="absolute top-3 left-3 flex gap-1">
                                <span class="category-badge category-${auction.category}">${auction.category}</span>
                                ${auction.visibility === 'search_only' ? '<span class="search-only-badge">BUSQUEDA</span>' : ''}
                            </div>'''

new_badges = '''<div class="absolute top-3 left-3 flex gap-1 flex-wrap">
                                <span class="category-badge category-${auction.category}">${auction.category}</span>
                                ${auction.visibility === 'search_only' ? '<span class="search-only-badge">BUSQUEDA</span>' : ''}
                                ${typeof SubastoLocation !== 'undefined' ? SubastoLocation.getLocationBadge(auction) : ''}
                            </div>'''

if old_badges in content:
    content = content.replace(old_badges, new_badges)
    print('Added location badge to auction cards')
else:
    print('Could not find badges section to patch')

# Write back
with open('site/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
