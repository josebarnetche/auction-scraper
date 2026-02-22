/**
 * Subasto Location Module
 * Handles geolocation, distance calculations, map display, and logistics estimation
 */

const SubastoLocation = (function() {
    'use strict';

    // State
    let userLocation = null;
    let geocodingData = null;
    let mapInstance = null;
    let markers = [];
    let markerClusterGroup = null;
    let isMapInitialized = false;

    // Constants
    const EARTH_RADIUS_KM = 6371;
    const DEFAULT_CENTER = { lat: -34.6037, lng: -58.3816 }; // Buenos Aires
    const DEFAULT_ZOOM = 5;

    /**
     * Initialize the location module
     */
    async function init() {
        await loadGeocodingData();
        setupEventListeners();
        // Try to load saved location from localStorage
        const savedLocation = localStorage.getItem('subasto_user_location');
        if (savedLocation) {
            try {
                userLocation = JSON.parse(savedLocation);
                updateLocationDisplay();
            } catch (e) {
                console.warn('Could not parse saved location');
            }
        }
    }

    /**
     * Load geocoding data from API
     */
    async function loadGeocodingData() {
        try {
            const response = await fetch('/api/v1/geocoding.json');
            if (response.ok) {
                geocodingData = await response.json();
            }
        } catch (e) {
            console.warn('Could not load geocoding data:', e);
        }
    }

    /**
     * Setup event listeners
     */
    function setupEventListeners() {
        // Listen for location button clicks
        document.addEventListener('click', function(e) {
            if (e.target.closest('#near-me-btn')) {
                requestUserLocation();
            }
            if (e.target.closest('#clear-location-btn')) {
                clearUserLocation();
            }
            if (e.target.closest('#toggle-map-btn')) {
                toggleMapView();
            }
        });

        // Listen for radius filter changes
        const radiusFilter = document.getElementById('radius-filter');
        if (radiusFilter) {
            radiusFilter.addEventListener('change', function() {
                if (typeof applyFilters === 'function') {
                    applyFilters();
                }
            });
        }
    }

    /**
     * Request user's geolocation
     */
    function requestUserLocation() {
        const btn = document.getElementById('near-me-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2" stroke-dasharray="31.4" stroke-dashoffset="10"/></svg> Localizando...';
        }

        if (!navigator.geolocation) {
            showLocationError('Tu navegador no soporta geolocalizacion');
            resetLocationButton();
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                userLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: Date.now()
                };
                localStorage.setItem('subasto_user_location', JSON.stringify(userLocation));
                updateLocationDisplay();
                resetLocationButton();

                // Re-apply filters to sort by distance
                if (typeof applyFilters === 'function') {
                    applyFilters();
                }

                // Update map if visible
                if (isMapInitialized && mapInstance) {
                    addUserMarker();
                    mapInstance.setView([userLocation.lat, userLocation.lng], 8);
                }
            },
            (error) => {
                let message = 'No pudimos obtener tu ubicacion';
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        message = 'Permiso de ubicacion denegado';
                        break;
                    case error.POSITION_UNAVAILABLE:
                        message = 'Ubicacion no disponible';
                        break;
                    case error.TIMEOUT:
                        message = 'Tiempo de espera agotado';
                        break;
                }
                showLocationError(message);
                resetLocationButton();
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000 // 5 minutes cache
            }
        );
    }

    /**
     * Clear user location
     */
    function clearUserLocation() {
        userLocation = null;
        localStorage.removeItem('subasto_user_location');
        updateLocationDisplay();

        // Reset radius filter
        const radiusFilter = document.getElementById('radius-filter');
        if (radiusFilter) {
            radiusFilter.value = '';
        }

        if (typeof applyFilters === 'function') {
            applyFilters();
        }
    }

    /**
     * Update location display in UI
     */
    function updateLocationDisplay() {
        const locationInfo = document.getElementById('location-info');
        const radiusContainer = document.getElementById('radius-filter-container');

        if (userLocation) {
            if (locationInfo) {
                const nearestProvince = findNearestProvince(userLocation.lat, userLocation.lng);
                locationInfo.innerHTML = `
                    <div class="flex items-center gap-2 text-green-400 text-xs">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                        </svg>
                        <span>Cerca de ${nearestProvince}</span>
                        <button id="clear-location-btn" class="text-white/40 hover:text-red-400 ml-2" title="Borrar ubicacion">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>
                `;
            }
            if (radiusContainer) {
                radiusContainer.style.display = 'block';
            }
        } else {
            if (locationInfo) {
                locationInfo.innerHTML = '';
            }
            if (radiusContainer) {
                radiusContainer.style.display = 'none';
            }
        }
    }

    /**
     * Reset location button to default state
     */
    function resetLocationButton() {
        const btn = document.getElementById('near-me-btn');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                </svg>
                ${userLocation ? 'Actualizar' : 'Cerca de mi'}
            `;
        }
    }

    /**
     * Show location error message
     */
    function showLocationError(message) {
        const locationInfo = document.getElementById('location-info');
        if (locationInfo) {
            locationInfo.innerHTML = `
                <div class="flex items-center gap-2 text-red-400 text-xs">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span>${message}</span>
                </div>
            `;
            setTimeout(() => {
                locationInfo.innerHTML = '';
            }, 5000);
        }
    }

    /**
     * Calculate distance between two points using Haversine formula
     */
    function calculateDistance(lat1, lng1, lat2, lng2) {
        const dLat = toRad(lat2 - lat1);
        const dLng = toRad(lng2 - lng1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                  Math.sin(dLng / 2) * Math.sin(dLng / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return EARTH_RADIUS_KM * c;
    }

    function toRad(deg) {
        return deg * (Math.PI / 180);
    }

    /**
     * Get coordinates for an auction listing
     */
    function getAuctionCoordinates(auction) {
        if (!geocodingData) return null;

        // First check if auction has explicit coordinates
        if (auction.lat && auction.lng) {
            return { lat: auction.lat, lng: auction.lng };
        }

        // Try to geocode from location
        const province = normalizeProvinceName(auction.location?.province || '');
        const city = auction.location?.city || '';

        if (province && geocodingData.provinces[province]) {
            const provinceData = geocodingData.provinces[province];
            if (city && provinceData.cities && provinceData.cities[city]) {
                return provinceData.cities[city];
            }
            return { lat: provinceData.lat, lng: provinceData.lng };
        }

        // Fallback to source location
        if (auction.source && geocodingData.source_locations[auction.source]) {
            const sourceLocation = geocodingData.source_locations[auction.source];
            return { lat: sourceLocation.lat, lng: sourceLocation.lng };
        }

        return null;
    }

    /**
     * Normalize province name for lookup
     */
    function normalizeProvinceName(name) {
        if (!name) return '';

        const normalizations = {
            'cordoba': 'Cordoba',
            'cba': 'Cordoba',
            'buenos aires': 'Buenos Aires',
            'ba': 'Buenos Aires',
            'pba': 'Buenos Aires',
            'caba': 'CABA',
            'capital federal': 'CABA',
            'ciudad de buenos aires': 'CABA',
            'entre rios': 'Entre Rios',
            'santa fe': 'Santa Fe',
            'mendoza': 'Mendoza',
            'tucuman': 'Tucuman',
            'salta': 'Salta',
            'chaco': 'Chaco',
            'corrientes': 'Corrientes',
            'misiones': 'Misiones',
            'san juan': 'San Juan',
            'san luis': 'San Luis',
            'la pampa': 'La Pampa',
            'neuquen': 'Neuquen',
            'rio negro': 'Rio Negro',
            'chubut': 'Chubut',
            'santa cruz': 'Santa Cruz',
            'tierra del fuego': 'Tierra del Fuego',
            'jujuy': 'Jujuy',
            'catamarca': 'Catamarca',
            'la rioja': 'La Rioja',
            'santiago del estero': 'Santiago del Estero',
            'formosa': 'Formosa'
        };

        // Remove accents and lowercase for matching
        const normalized = name.toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '');

        return normalizations[normalized] || name;
    }

    /**
     * Find nearest province to given coordinates
     */
    function findNearestProvince(lat, lng) {
        if (!geocodingData) return 'Argentina';

        let nearestProvince = 'Argentina';
        let minDistance = Infinity;

        for (const [name, data] of Object.entries(geocodingData.provinces)) {
            const distance = calculateDistance(lat, lng, data.lat, data.lng);
            if (distance < minDistance) {
                minDistance = distance;
                nearestProvince = data.name || name;
            }
        }

        return nearestProvince;
    }

    /**
     * Get distance from user to auction
     */
    function getDistanceToAuction(auction) {
        if (!userLocation) return null;

        const coords = getAuctionCoordinates(auction);
        if (!coords) return null;

        return calculateDistance(userLocation.lat, userLocation.lng, coords.lat, coords.lng);
    }

    /**
     * Format distance for display
     */
    function formatDistance(km) {
        if (km === null || km === undefined) return '';
        if (km < 1) return 'Menos de 1 km';
        if (km < 10) return `${km.toFixed(1)} km`;
        return `${Math.round(km)} km`;
    }

    /**
     * Calculate transport/logistics cost estimate
     */
    function calculateTransportCost(auction, distanceKm) {
        if (!geocodingData || !geocodingData.transport_costs) return null;
        if (!distanceKm || distanceKm <= 0) return null;

        const costs = geocodingData.transport_costs;
        const category = auction.category || 'general_goods';
        const rates = costs.freight_rates[category] || costs.freight_rates.general_goods;

        // Real estate doesn't need transport
        if (category === 'real_estate') {
            return {
                total_ars: 0,
                description: 'Sin costo de transporte',
                breakdown: null
            };
        }

        // Calculate costs
        const freightCost = rates.base_fee_ars + (rates.per_km_ars * distanceKm);
        const fuelCost = (distanceKm / costs.avg_consumption_km_per_liter) * costs.fuel_price_per_liter_ars;
        const tollCost = (distanceKm / 100) * costs.toll_avg_per_100km_ars;

        // Option 1: Professional freight
        const freightTotal = Math.round(freightCost);

        // Option 2: Self-pickup (just fuel + tolls, round trip)
        const selfPickupTotal = Math.round((fuelCost + tollCost) * 2);

        return {
            freight: {
                total_ars: freightTotal,
                description: rates.description || 'Flete profesional'
            },
            self_pickup: {
                total_ars: selfPickupTotal,
                fuel_ars: Math.round(fuelCost * 2),
                tolls_ars: Math.round(tollCost * 2),
                description: 'Retiro personal (ida y vuelta)'
            },
            distance_km: Math.round(distanceKm),
            category: category
        };
    }

    /**
     * Format transport cost for display
     */
    function formatTransportCost(transportCost, blueRate) {
        if (!transportCost) return '';
        if (transportCost.total_ars === 0) return transportCost.description;

        const formatARS = (val) => `ARS ${val.toLocaleString('es-AR')}`;
        const formatUSD = (val) => `USD ${Math.round(val / blueRate).toLocaleString()}`;

        if (transportCost.freight) {
            return `
                <div class="text-xs space-y-1">
                    <div class="flex justify-between">
                        <span class="text-white/40">Flete (${transportCost.freight.description}):</span>
                        <span class="text-orange-400">${formatARS(transportCost.freight.total_ars)}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-white/40">Retiro personal:</span>
                        <span class="text-green-400">${formatARS(transportCost.self_pickup.total_ars)}</span>
                    </div>
                    <div class="text-white/30 text-[10px]">${transportCost.distance_km} km de distancia</div>
                </div>
            `;
        }

        return '';
    }

    /**
     * Toggle map view visibility
     */
    function toggleMapView() {
        const mapContainer = document.getElementById('map-container');
        const toggleBtn = document.getElementById('toggle-map-btn');

        if (!mapContainer) return;

        const isVisible = !mapContainer.classList.contains('hidden');

        if (isVisible) {
            mapContainer.classList.add('hidden');
            if (toggleBtn) {
                toggleBtn.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
                    </svg>
                    Ver Mapa
                `;
            }
        } else {
            mapContainer.classList.remove('hidden');
            if (toggleBtn) {
                toggleBtn.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
                    </svg>
                    Ver Lista
                `;
            }

            // Initialize map if not already done
            if (!isMapInitialized) {
                setTimeout(() => initMap(), 100);
            } else {
                mapInstance.invalidateSize();
                updateMapMarkers();
            }
        }
    }

    /**
     * Initialize Leaflet map
     */
    function initMap() {
        const mapEl = document.getElementById('auction-map');
        if (!mapEl || isMapInitialized) return;

        // Create map
        mapInstance = L.map('auction-map', {
            center: [DEFAULT_CENTER.lat, DEFAULT_CENTER.lng],
            zoom: DEFAULT_ZOOM,
            zoomControl: true,
            scrollWheelZoom: true
        });

        // Add tile layer (OpenStreetMap)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 18
        }).addTo(mapInstance);

        // Add marker cluster group
        if (typeof L.markerClusterGroup === 'function') {
            markerClusterGroup = L.markerClusterGroup({
                maxClusterRadius: 50,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false,
                iconCreateFunction: function(cluster) {
                    const count = cluster.getChildCount();
                    let size = 'small';
                    if (count > 10) size = 'medium';
                    if (count > 50) size = 'large';
                    return L.divIcon({
                        html: `<div class="cluster-icon cluster-${size}">${count}</div>`,
                        className: 'marker-cluster',
                        iconSize: [40, 40]
                    });
                }
            });
            mapInstance.addLayer(markerClusterGroup);
        }

        isMapInitialized = true;

        // Add user marker if location available
        if (userLocation) {
            addUserMarker();
        }

        // Add auction markers
        updateMapMarkers();
    }

    /**
     * Add user location marker to map
     */
    function addUserMarker() {
        if (!mapInstance || !userLocation) return;

        const userIcon = L.divIcon({
            className: 'user-marker',
            html: `
                <div class="w-6 h-6 bg-blue-500 rounded-full border-2 border-white shadow-lg flex items-center justify-center">
                    <div class="w-2 h-2 bg-white rounded-full"></div>
                </div>
            `,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        L.marker([userLocation.lat, userLocation.lng], { icon: userIcon })
            .addTo(mapInstance)
            .bindPopup('<strong>Tu ubicacion</strong>');
    }

    /**
     * Update map markers based on current filtered auctions
     */
    function updateMapMarkers(auctions) {
        if (!mapInstance) return;

        // Clear existing markers
        if (markerClusterGroup) {
            markerClusterGroup.clearLayers();
        }
        markers.forEach(m => m.remove());
        markers = [];

        // Use global filteredAuctions if not provided
        const auctionsToShow = auctions || (typeof filteredAuctions !== 'undefined' ? filteredAuctions : []);

        // Add markers for each auction
        auctionsToShow.forEach(auction => {
            const coords = getAuctionCoordinates(auction);
            if (!coords) return;

            const categoryColors = {
                vehicles: '#3b82f6',
                real_estate: '#ec4899',
                machinery: '#eab308',
                general_goods: '#22c55e',
                other: '#9ca3af'
            };

            const color = categoryColors[auction.category] || categoryColors.other;
            const distance = userLocation ? formatDistance(getDistanceToAuction(auction)) : '';

            const icon = L.divIcon({
                className: 'auction-marker',
                html: `
                    <div class="w-8 h-8 rounded-full border-2 border-white shadow-lg flex items-center justify-center" style="background-color: ${color}">
                        <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm0 14a6 6 0 110-12 6 6 0 010 12z"/>
                        </svg>
                    </div>
                `,
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            });

            const priceDisplay = auction.base_price > 0
                ? `${auction.currency} ${auction.base_price.toLocaleString()}`
                : 'A consultar';

            const popupContent = `
                <div class="min-w-[200px]">
                    <h4 class="font-medium text-sm mb-1 line-clamp-2">${auction.title}</h4>
                    <div class="text-xs text-gray-600 mb-2">
                        <span class="inline-block px-2 py-0.5 rounded-full text-white text-[10px]" style="background-color: ${color}">${auction.category}</span>
                        <span class="ml-1">${auction.source.toUpperCase()}</span>
                    </div>
                    <div class="text-sm font-bold text-yellow-600 mb-1">${priceDisplay}</div>
                    ${distance ? `<div class="text-xs text-gray-500">${distance} de distancia</div>` : ''}
                    <a href="${auction.source_url}" target="_blank" class="text-blue-500 text-xs hover:underline">Ver subasta</a>
                </div>
            `;

            const marker = L.marker([coords.lat, coords.lng], { icon: icon })
                .bindPopup(popupContent);

            if (markerClusterGroup) {
                markerClusterGroup.addLayer(marker);
            } else {
                marker.addTo(mapInstance);
                markers.push(marker);
            }
        });

        // Fit bounds to show all markers
        if (auctionsToShow.length > 0 && markerClusterGroup) {
            const bounds = markerClusterGroup.getBounds();
            if (bounds.isValid()) {
                mapInstance.fitBounds(bounds, { padding: [50, 50] });
            }
        }
    }

    /**
     * Filter auctions by distance from user
     */
    function filterByDistance(auctions, maxDistanceKm) {
        if (!userLocation || !maxDistanceKm) return auctions;

        return auctions.filter(auction => {
            const distance = getDistanceToAuction(auction);
            return distance !== null && distance <= maxDistanceKm;
        });
    }

    /**
     * Sort auctions by distance from user
     */
    function sortByDistance(auctions) {
        if (!userLocation) return auctions;

        return [...auctions].sort((a, b) => {
            const distA = getDistanceToAuction(a) || Infinity;
            const distB = getDistanceToAuction(b) || Infinity;
            return distA - distB;
        });
    }

    /**
     * Get location badge HTML for auction card
     */
    function getLocationBadge(auction) {
        const distance = getDistanceToAuction(auction);
        const province = auction.location?.province || '';

        if (distance !== null) {
            const formattedDistance = formatDistance(distance);
            const urgencyClass = distance < 50 ? 'bg-green-500/20 text-green-400' :
                                 distance < 200 ? 'bg-yellow-500/20 text-yellow-400' :
                                 'bg-white/10 text-white/60';
            return `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] ${urgencyClass}">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                    </svg>
                    ${formattedDistance}
                </span>
            `;
        } else if (province) {
            return `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-white/10 text-white/60">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                    </svg>
                    ${province}
                </span>
            `;
        }

        return '';
    }

    // Public API
    return {
        init: init,
        requestUserLocation: requestUserLocation,
        clearUserLocation: clearUserLocation,
        getUserLocation: () => userLocation,
        getDistanceToAuction: getDistanceToAuction,
        formatDistance: formatDistance,
        calculateTransportCost: calculateTransportCost,
        formatTransportCost: formatTransportCost,
        getAuctionCoordinates: getAuctionCoordinates,
        filterByDistance: filterByDistance,
        sortByDistance: sortByDistance,
        getLocationBadge: getLocationBadge,
        toggleMapView: toggleMapView,
        updateMapMarkers: updateMapMarkers,
        isMapVisible: () => {
            const mapContainer = document.getElementById('map-container');
            return mapContainer && !mapContainer.classList.contains('hidden');
        }
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    SubastoLocation.init();
});
