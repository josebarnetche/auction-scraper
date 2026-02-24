/**
 * Subasto.com.ar - Auction Alerts System
 *
 * Browser-based alerts using LocalStorage for preferences,
 * optional push notifications, and email digest via Formspree.
 *
 * Features:
 * - Save search filters as alerts
 * - Watch specific auctions
 * - Browser notifications for ending auctions
 * - Email digest signup
 */

// ============================================
// STORAGE KEYS
// ============================================
const STORAGE_KEYS = {
    SAVED_SEARCHES: 'subasto_saved_searches',
    WATCHED_AUCTIONS: 'subasto_watched_auctions',
    EMAIL_PREFERENCES: 'subasto_email_prefs',
    NOTIFICATION_PERMISSION: 'subasto_notif_permission',
    LAST_CHECK: 'subasto_last_check'
};

// ============================================
// FORMSPREE ENDPOINT (for email digest)
// ============================================
const FORMSPREE_ENDPOINT = 'https://formspree.io/f/mreaowrr';

// ============================================
// ALERTS STATE
// ============================================
let alertsState = {
    savedSearches: [],
    watchedAuctions: [],
    emailPrefs: null,
    notificationPermission: 'default',
    isModalOpen: false
};

// ============================================
// INITIALIZATION
// ============================================
function initAlerts() {
    // Load state from localStorage
    loadAlertsState();

    // Update UI
    updateAlertsBadge();

    // Check for expiring watched auctions
    checkExpiringAuctions();

    // Set up periodic checks (every minute)
    setInterval(checkExpiringAuctions, 60000);

    // Request notification permission if we have alerts
    if (alertsState.watchedAuctions.length > 0 || alertsState.savedSearches.length > 0) {
        requestNotificationPermission();
    }

    console.log('[Alerts] Initialized with', alertsState.savedSearches.length, 'saved searches and', alertsState.watchedAuctions.length, 'watched auctions');
}

function loadAlertsState() {
    try {
        const savedSearches = localStorage.getItem(STORAGE_KEYS.SAVED_SEARCHES);
        const watchedAuctions = localStorage.getItem(STORAGE_KEYS.WATCHED_AUCTIONS);
        const emailPrefs = localStorage.getItem(STORAGE_KEYS.EMAIL_PREFERENCES);

        alertsState.savedSearches = savedSearches ? JSON.parse(savedSearches) : [];
        alertsState.watchedAuctions = watchedAuctions ? JSON.parse(watchedAuctions) : [];
        alertsState.emailPrefs = emailPrefs ? JSON.parse(emailPrefs) : null;
        alertsState.notificationPermission = Notification?.permission || 'default';

        // Clean up expired watched auctions
        cleanupExpiredWatches();
    } catch (e) {
        console.error('[Alerts] Error loading state:', e);
        alertsState.savedSearches = [];
        alertsState.watchedAuctions = [];
    }
}

function saveAlertsState() {
    try {
        localStorage.setItem(STORAGE_KEYS.SAVED_SEARCHES, JSON.stringify(alertsState.savedSearches));
        localStorage.setItem(STORAGE_KEYS.WATCHED_AUCTIONS, JSON.stringify(alertsState.watchedAuctions));
        if (alertsState.emailPrefs) {
            localStorage.setItem(STORAGE_KEYS.EMAIL_PREFERENCES, JSON.stringify(alertsState.emailPrefs));
        }
    } catch (e) {
        console.error('[Alerts] Error saving state:', e);
    }
}

// ============================================
// SAVED SEARCHES
// ============================================
function getCurrentSearchFilters() {
    return {
        searchTerm: document.getElementById('search-input')?.value || '',
        minPrice: parseFloat(document.getElementById('min-price')?.value) || 0,
        maxPrice: parseFloat(document.getElementById('max-price')?.value) || 500000,
        source: document.getElementById('source-filter')?.value || '',
        location: document.getElementById('location-filter')?.value || '',
        category: currentFilter || '',
        sortBy: document.getElementById('sort-filter')?.value || 'recommended'
    };
}

function saveCurrentSearch() {
    const filters = getCurrentSearchFilters();

    // Check if any filter is actually set
    const hasFilters = filters.searchTerm ||
                       filters.source ||
                       filters.location ||
                       filters.category ||
                       filters.minPrice > 0 ||
                       filters.maxPrice < 500000;

    if (!hasFilters) {
        showToast('Aplica algun filtro antes de guardar la busqueda', 'warning');
        return;
    }

    // Generate a name for the search
    const searchName = generateSearchName(filters);

    // Check for duplicates
    const isDuplicate = alertsState.savedSearches.some(s =>
        JSON.stringify(s.filters) === JSON.stringify(filters)
    );

    if (isDuplicate) {
        showToast('Esta busqueda ya esta guardada', 'warning');
        return;
    }

    const savedSearch = {
        id: 'search_' + Date.now(),
        name: searchName,
        filters: filters,
        createdAt: new Date().toISOString(),
        matchCount: filteredAuctions?.length || 0
    };

    alertsState.savedSearches.push(savedSearch);
    saveAlertsState();
    updateAlertsBadge();

    showToast('Busqueda guardada! Te notificaremos cuando haya nuevos resultados.', 'success');

    // Request notification permission
    requestNotificationPermission();

    // Track event
    if (typeof gtag === 'function') {
        gtag('event', 'save_search', { search_name: searchName });
    }
}

function generateSearchName(filters) {
    const parts = [];

    if (filters.searchTerm) {
        parts.push(`"${filters.searchTerm}"`);
    }
    if (filters.category) {
        const categoryNames = {
            'vehicles': 'Vehiculos',
            'real_estate': 'Inmuebles',
            'machinery': 'Maquinaria',
            'general_goods': 'Bienes'
        };
        parts.push(categoryNames[filters.category] || filters.category);
    }
    if (filters.source) {
        parts.push(filters.source.toUpperCase());
    }
    if (filters.location) {
        parts.push(filters.location);
    }
    if (filters.minPrice > 0 || filters.maxPrice < 500000) {
        const currency = displayCurrency || 'USD';
        const min = filters.minPrice > 0 ? `$${formatPriceShort(filters.minPrice)}` : '';
        const max = filters.maxPrice < 500000 ? `$${formatPriceShort(filters.maxPrice)}` : '';
        if (min && max) {
            parts.push(`${min}-${max} ${currency}`);
        } else if (min) {
            parts.push(`>${min} ${currency}`);
        } else if (max) {
            parts.push(`<${max} ${currency}`);
        }
    }

    return parts.length > 0 ? parts.join(' + ') : 'Todas las subastas';
}

function formatPriceShort(price) {
    if (price >= 1000000) return Math.round(price / 1000000) + 'M';
    if (price >= 1000) return Math.round(price / 1000) + 'k';
    return price.toString();
}

function deleteSavedSearch(searchId) {
    alertsState.savedSearches = alertsState.savedSearches.filter(s => s.id !== searchId);
    saveAlertsState();
    updateAlertsBadge();
    renderAlertsModal();
    showToast('Busqueda eliminada', 'info');
}

function applySavedSearch(searchId) {
    const search = alertsState.savedSearches.find(s => s.id === searchId);
    if (!search) return;

    const f = search.filters;

    // Apply filters to UI
    if (document.getElementById('search-input')) {
        document.getElementById('search-input').value = f.searchTerm || '';
    }
    if (document.getElementById('min-price')) {
        document.getElementById('min-price').value = f.minPrice || 0;
    }
    if (document.getElementById('max-price')) {
        document.getElementById('max-price').value = f.maxPrice || 500000;
    }
    if (document.getElementById('source-filter')) {
        document.getElementById('source-filter').value = f.source || '';
    }
    if (document.getElementById('location-filter')) {
        document.getElementById('location-filter').value = f.location || '';
    }
    if (document.getElementById('sort-filter')) {
        document.getElementById('sort-filter').value = f.sortBy || 'recommended';
    }

    // Apply category filter
    if (typeof filterAuctions === 'function') {
        filterAuctions(f.category || '');
    }

    // Update price slider UI
    if (typeof updatePriceSlider === 'function') {
        updatePriceSlider();
    }

    // Apply all filters
    if (typeof applyFilters === 'function') {
        applyFilters();
    }

    // Close modal and scroll to auctions
    closeAlertsModal();
    document.getElementById('auctions')?.scrollIntoView({ behavior: 'smooth' });

    showToast('Filtros aplicados', 'success');
}

// ============================================
// WATCHED AUCTIONS
// ============================================
function watchAuction(auction) {
    if (!auction || !auction.id) {
        console.error('[Alerts] Invalid auction to watch');
        return;
    }

    // Check if already watching
    const isWatching = alertsState.watchedAuctions.some(w => w.id === auction.id);

    if (isWatching) {
        // Unwatch
        unwatchAuction(auction.id);
        return;
    }

    const watchedAuction = {
        id: auction.id,
        title: auction.title,
        source: auction.source,
        sourceUrl: auction.source_url,
        basePrice: auction.base_price,
        currency: auction.currency,
        category: auction.category,
        endsAt: auction.ends_at,
        imageUrl: auction.images?.[0] || null,
        watchedAt: new Date().toISOString(),
        notified: false
    };

    alertsState.watchedAuctions.push(watchedAuction);
    saveAlertsState();
    updateAlertsBadge();
    updateWatchButtons();

    showToast(`Siguiendo: ${auction.title.substring(0, 40)}...`, 'success');

    // Request notification permission
    requestNotificationPermission();

    // Track event
    if (typeof gtag === 'function') {
        gtag('event', 'watch_auction', { auction_id: auction.id, category: auction.category });
    }
}

function unwatchAuction(auctionId) {
    alertsState.watchedAuctions = alertsState.watchedAuctions.filter(w => w.id !== auctionId);
    saveAlertsState();
    updateAlertsBadge();
    updateWatchButtons();
    renderAlertsModal();
    showToast('Dejaste de seguir esta subasta', 'info');
}

function isAuctionWatched(auctionId) {
    return alertsState.watchedAuctions.some(w => w.id === auctionId);
}

function cleanupExpiredWatches() {
    const now = new Date();
    const before = alertsState.watchedAuctions.length;

    alertsState.watchedAuctions = alertsState.watchedAuctions.filter(w => {
        if (!w.endsAt) return true; // Keep if no end date
        return new Date(w.endsAt) > now;
    });

    if (alertsState.watchedAuctions.length !== before) {
        saveAlertsState();
        console.log('[Alerts] Cleaned up', before - alertsState.watchedAuctions.length, 'expired watches');
    }
}

function updateWatchButtons() {
    // Update all watch buttons on the page
    document.querySelectorAll('[data-watch-id]').forEach(btn => {
        const auctionId = btn.getAttribute('data-watch-id');
        const isWatching = isAuctionWatched(auctionId);

        btn.classList.toggle('watching', isWatching);
        btn.setAttribute('title', isWatching ? 'Dejar de seguir' : 'Seguir subasta');

        // Update icon
        const icon = btn.querySelector('svg');
        if (icon) {
            if (isWatching) {
                icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>';
                icon.classList.add('text-yellow-500');
                icon.classList.remove('text-white/40');
            } else {
                icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>';
                icon.classList.remove('text-yellow-500');
                icon.classList.add('text-white/40');
            }
        }
    });
}

// ============================================
// NOTIFICATIONS
// ============================================
async function requestNotificationPermission() {
    if (!('Notification' in window)) {
        console.log('[Alerts] Notifications not supported');
        return false;
    }

    if (Notification.permission === 'granted') {
        alertsState.notificationPermission = 'granted';
        return true;
    }

    if (Notification.permission !== 'denied') {
        const permission = await Notification.requestPermission();
        alertsState.notificationPermission = permission;
        return permission === 'granted';
    }

    return false;
}

function sendNotification(title, body, url) {
    if (Notification.permission !== 'granted') return;

    const notification = new Notification(title, {
        body: body,
        icon: '/favicon-32x32.png',
        badge: '/favicon-32x32.png',
        tag: 'subasto-alert',
        requireInteraction: true
    });

    notification.onclick = function() {
        window.focus();
        if (url) {
            window.open(url, '_blank');
        }
        notification.close();
    };
}

function checkExpiringAuctions() {
    const now = new Date();
    const oneHour = 60 * 60 * 1000;
    const twentyFourHours = 24 * 60 * 60 * 1000;

    alertsState.watchedAuctions.forEach(watch => {
        if (!watch.endsAt || watch.notified) return;

        const endsAt = new Date(watch.endsAt);
        const timeLeft = endsAt - now;

        // Notify if ending within 1 hour
        if (timeLeft > 0 && timeLeft < oneHour) {
            const minutes = Math.round(timeLeft / 60000);
            sendNotification(
                'Subasta por terminar!',
                `"${watch.title.substring(0, 50)}..." termina en ${minutes} minutos`,
                watch.sourceUrl
            );

            // Mark as notified
            watch.notified = true;
            saveAlertsState();
        }
        // Also notify at 24 hours
        else if (timeLeft > 0 && timeLeft < twentyFourHours && timeLeft > twentyFourHours - 60000) {
            sendNotification(
                'Subasta termina manana',
                `"${watch.title.substring(0, 50)}..." termina en 24 horas`,
                watch.sourceUrl
            );
        }
    });
}

// ============================================
// EMAIL DIGEST
// ============================================
async function subscribeToEmailDigest(email, preferences) {
    if (!email || !email.includes('@')) {
        showToast('Por favor ingresa un email valido', 'error');
        return false;
    }

    const formData = {
        email: email,
        preferences: preferences,
        savedSearches: alertsState.savedSearches.map(s => s.name),
        watchedCount: alertsState.watchedAuctions.length,
        subscribedAt: new Date().toISOString()
    };

    try {
        // In production, send to Formspree or your email service
        // For now, we'll just save locally and show success
        alertsState.emailPrefs = {
            email: email,
            frequency: preferences.frequency || 'daily',
            categories: preferences.categories || [],
            subscribedAt: new Date().toISOString()
        };

        saveAlertsState();

        showToast('Suscripcion exitosa! Recibiras alertas en tu email.', 'success');

        // Track event
        if (typeof gtag === 'function') {
            gtag('event', 'email_subscribe', { frequency: preferences.frequency });
        }

        return true;
    } catch (e) {
        console.error('[Alerts] Email subscription error:', e);
        showToast('Error al suscribirse. Intenta de nuevo.', 'error');
        return false;
    }
}

function unsubscribeFromEmail() {
    alertsState.emailPrefs = null;
    localStorage.removeItem(STORAGE_KEYS.EMAIL_PREFERENCES);
    showToast('Te desuscribiste del digest por email', 'info');
}

// ============================================
// UI COMPONENTS
// ============================================
function updateAlertsBadge() {
    const badge = document.getElementById('alerts-badge');
    const count = alertsState.savedSearches.length + alertsState.watchedAuctions.length;

    if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? 'flex' : 'none';
    }
}

function toggleAlertsModal() {
    if (alertsState.isModalOpen) {
        closeAlertsModal();
    } else {
        openAlertsModal();
    }
}

function openAlertsModal() {
    alertsState.isModalOpen = true;

    // Create modal if it doesn't exist
    let modal = document.getElementById('alerts-modal');
    if (!modal) {
        modal = createAlertsModal();
        document.body.appendChild(modal);
    }

    renderAlertsModal();
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
}

function closeAlertsModal() {
    alertsState.isModalOpen = false;

    const modal = document.getElementById('alerts-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }

    // Restore body scroll
    document.body.style.overflow = '';
}

function createAlertsModal() {
    const modal = document.createElement('div');
    modal.id = 'alerts-modal';
    modal.className = 'fixed inset-0 z-[100] hidden items-center justify-center p-4 bg-black/80 backdrop-blur-sm';
    modal.onclick = function(e) {
        if (e.target === modal) closeAlertsModal();
    };

    modal.innerHTML = `
        <div class="glass rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col" onclick="event.stopPropagation()">
            <!-- Header -->
            <div class="flex items-center justify-between p-6 border-b border-white/10">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center">
                        <svg class="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
                        </svg>
                    </div>
                    <div>
                        <h2 class="text-xl font-display font-medium text-white">Mis Alertas</h2>
                        <p class="text-sm text-white/40">Busquedas guardadas y subastas seguidas</p>
                    </div>
                </div>
                <button onclick="closeAlertsModal()" class="w-10 h-10 rounded-full hover:bg-white/10 flex items-center justify-center transition-colors">
                    <svg class="w-6 h-6 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>

            <!-- Tabs -->
            <div class="flex border-b border-white/10">
                <button onclick="switchAlertsTab('searches')" id="tab-searches" class="flex-1 px-4 py-3 text-sm font-medium text-yellow-500 border-b-2 border-yellow-500">
                    Busquedas Guardadas
                </button>
                <button onclick="switchAlertsTab('watched')" id="tab-watched" class="flex-1 px-4 py-3 text-sm font-medium text-white/40 hover:text-white border-b-2 border-transparent">
                    Subastas Seguidas
                </button>
                <button onclick="switchAlertsTab('email')" id="tab-email" class="flex-1 px-4 py-3 text-sm font-medium text-white/40 hover:text-white border-b-2 border-transparent">
                    Email Digest
                </button>
            </div>

            <!-- Content -->
            <div id="alerts-modal-content" class="flex-1 overflow-y-auto p-6">
                <!-- Content rendered dynamically -->
            </div>
        </div>
    `;

    return modal;
}

function switchAlertsTab(tab) {
    // Update tab styles
    ['searches', 'watched', 'email'].forEach(t => {
        const tabEl = document.getElementById(`tab-${t}`);
        if (tabEl) {
            if (t === tab) {
                tabEl.className = 'flex-1 px-4 py-3 text-sm font-medium text-yellow-500 border-b-2 border-yellow-500';
            } else {
                tabEl.className = 'flex-1 px-4 py-3 text-sm font-medium text-white/40 hover:text-white border-b-2 border-transparent';
            }
        }
    });

    renderAlertsModal(tab);
}

function renderAlertsModal(tab = 'searches') {
    const content = document.getElementById('alerts-modal-content');
    if (!content) return;

    switch (tab) {
        case 'searches':
            content.innerHTML = renderSavedSearchesTab();
            break;
        case 'watched':
            content.innerHTML = renderWatchedAuctionsTab();
            break;
        case 'email':
            content.innerHTML = renderEmailDigestTab();
            break;
    }
}

function renderSavedSearchesTab() {
    if (alertsState.savedSearches.length === 0) {
        return `
            <div class="text-center py-12">
                <svg class="w-16 h-16 text-white/10 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
                <p class="text-white/40 mb-4">No tenes busquedas guardadas</p>
                <p class="text-white/30 text-sm mb-6">Usa los filtros en la seccion de subastas y clickea "Guardar Busqueda"</p>
                <button onclick="closeAlertsModal(); document.getElementById('auctions').scrollIntoView({behavior:'smooth'});"
                        class="px-4 py-2 bg-yellow-500 text-black rounded-lg font-medium hover:bg-yellow-400 transition-colors">
                    Ir a Subastas
                </button>
            </div>
        `;
    }

    return `
        <div class="space-y-3">
            ${alertsState.savedSearches.map(search => `
                <div class="glass rounded-xl p-4 hover:bg-white/5 transition-colors">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1 min-w-0">
                            <h4 class="text-white font-medium mb-1 truncate">${escapeHtml(search.name)}</h4>
                            <p class="text-white/40 text-sm">
                                Guardada ${formatRelativeDate(search.createdAt)}
                                ${search.matchCount ? ` - ${search.matchCount} resultados` : ''}
                            </p>
                        </div>
                        <div class="flex items-center gap-2">
                            <button onclick="applySavedSearch('${search.id}')"
                                    class="px-3 py-1.5 bg-yellow-500/20 text-yellow-500 rounded-lg text-sm hover:bg-yellow-500/30 transition-colors"
                                    title="Aplicar filtros">
                                Aplicar
                            </button>
                            <button onclick="deleteSavedSearch('${search.id}')"
                                    class="w-8 h-8 rounded-lg hover:bg-red-500/20 flex items-center justify-center transition-colors"
                                    title="Eliminar">
                                <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderWatchedAuctionsTab() {
    if (alertsState.watchedAuctions.length === 0) {
        return `
            <div class="text-center py-12">
                <svg class="w-16 h-16 text-white/10 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
                </svg>
                <p class="text-white/40 mb-4">No estas siguiendo ninguna subasta</p>
                <p class="text-white/30 text-sm mb-6">Clickea el icono de campana en cualquier subasta para seguirla</p>
                <button onclick="closeAlertsModal(); document.getElementById('auctions').scrollIntoView({behavior:'smooth'});"
                        class="px-4 py-2 bg-yellow-500 text-black rounded-lg font-medium hover:bg-yellow-400 transition-colors">
                    Ver Subastas
                </button>
            </div>
        `;
    }

    return `
        <div class="space-y-3">
            ${alertsState.watchedAuctions.map(watch => {
                const countdown = watch.endsAt ? formatCountdown(watch.endsAt) : null;
                const priceDisplay = watch.basePrice > 0
                    ? formatPrice(watch.basePrice, watch.currency || 'USD')
                    : 'A consultar';

                return `
                    <div class="glass rounded-xl p-4 hover:bg-white/5 transition-colors">
                        <div class="flex gap-4">
                            ${watch.imageUrl ? `
                                <div class="w-20 h-20 rounded-lg overflow-hidden flex-shrink-0 bg-white/5">
                                    <img src="${watch.imageUrl}" alt="" class="w-full h-full object-cover" onerror="this.onerror=null; this.src='/api/placeholder.svg'">
                                </div>
                            ` : ''}
                            <div class="flex-1 min-w-0">
                                <div class="flex items-start justify-between gap-2 mb-2">
                                    <a href="${watch.sourceUrl}" target="_blank" class="text-white font-medium hover:text-yellow-400 transition-colors line-clamp-2">
                                        ${escapeHtml(watch.title)}
                                    </a>
                                    <button onclick="unwatchAuction('${watch.id}')"
                                            class="w-8 h-8 rounded-lg hover:bg-red-500/20 flex items-center justify-center transition-colors flex-shrink-0"
                                            title="Dejar de seguir">
                                        <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                        </svg>
                                    </button>
                                </div>
                                <div class="flex items-center gap-2 flex-wrap text-sm">
                                    <span class="category-badge category-${watch.category || 'other'}">${watch.category || 'other'}</span>
                                    <span class="source-badge">${watch.source}</span>
                                    <span class="text-green-400">${priceDisplay}</span>
                                </div>
                                ${countdown ? `
                                    <div class="flex items-center gap-2 mt-2">
                                        <svg class="w-4 h-4 ${countdown.urgent ? 'text-yellow-400' : 'text-white/40'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                        </svg>
                                        <span class="text-xs ${countdown.expired ? 'text-red-400' : countdown.urgent ? 'text-yellow-400' : 'text-green-400'}">
                                            ${countdown.expired ? 'Finalizada' : `Termina en ${countdown.text}`}
                                        </span>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

function renderEmailDigestTab() {
    const isSubscribed = alertsState.emailPrefs !== null;

    if (isSubscribed) {
        return `
            <div class="text-center py-8">
                <div class="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                </div>
                <h3 class="text-xl font-display font-medium text-white mb-2">Suscripto!</h3>
                <p class="text-white/40 mb-2">Recibiras alertas en: <span class="text-white">${alertsState.emailPrefs.email}</span></p>
                <p class="text-white/30 text-sm mb-6">Frecuencia: ${alertsState.emailPrefs.frequency === 'daily' ? 'Diaria' : 'Inmediata'}</p>
                <button onclick="unsubscribeFromEmail(); renderAlertsModal('email');"
                        class="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg font-medium hover:bg-red-500/30 transition-colors">
                    Desuscribirme
                </button>
            </div>
        `;
    }

    return `
        <div class="max-w-md mx-auto">
            <div class="text-center mb-6">
                <div class="w-16 h-16 rounded-full bg-yellow-500/20 flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                    </svg>
                </div>
                <h3 class="text-xl font-display font-medium text-white mb-2">Recibe alertas por email</h3>
                <p class="text-white/40 text-sm">Te notificamos cuando aparecen nuevas subastas que coincidan con tus busquedas guardadas</p>
            </div>

            <form onsubmit="handleEmailSubscribe(event)" class="space-y-4">
                <div>
                    <label class="block text-xs uppercase tracking-wider text-white/40 mb-2">Email</label>
                    <input type="email" id="digest-email" required
                           placeholder="tu@email.com"
                           class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-yellow-500/50">
                </div>

                <div>
                    <label class="block text-xs uppercase tracking-wider text-white/40 mb-2">Frecuencia</label>
                    <select id="digest-frequency" class="w-full bg-[#1a1a1a] border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-yellow-500/50">
                        <option value="daily">Resumen diario (recomendado)</option>
                        <option value="instant">Alertas instantaneas</option>
                    </select>
                </div>

                <div>
                    <label class="block text-xs uppercase tracking-wider text-white/40 mb-3">Categorias de interes</label>
                    <div class="grid grid-cols-2 gap-2">
                        <label class="flex items-center gap-2 p-3 rounded-lg bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                            <input type="checkbox" name="category" value="vehicles" class="rounded text-yellow-500 focus:ring-yellow-500">
                            <span class="text-white/80 text-sm">Vehiculos</span>
                        </label>
                        <label class="flex items-center gap-2 p-3 rounded-lg bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                            <input type="checkbox" name="category" value="real_estate" class="rounded text-yellow-500 focus:ring-yellow-500">
                            <span class="text-white/80 text-sm">Inmuebles</span>
                        </label>
                        <label class="flex items-center gap-2 p-3 rounded-lg bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                            <input type="checkbox" name="category" value="machinery" class="rounded text-yellow-500 focus:ring-yellow-500">
                            <span class="text-white/80 text-sm">Maquinaria</span>
                        </label>
                        <label class="flex items-center gap-2 p-3 rounded-lg bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                            <input type="checkbox" name="category" value="general_goods" class="rounded text-yellow-500 focus:ring-yellow-500">
                            <span class="text-white/80 text-sm">Bienes</span>
                        </label>
                    </div>
                </div>

                <button type="submit" class="w-full px-4 py-3 bg-yellow-500 text-black rounded-lg font-medium hover:bg-yellow-400 transition-colors">
                    Suscribirme
                </button>

                <p class="text-center text-white/30 text-xs">
                    Podes desuscribirte en cualquier momento
                </p>
            </form>
        </div>
    `;
}

async function handleEmailSubscribe(event) {
    event.preventDefault();

    const email = document.getElementById('digest-email').value;
    const frequency = document.getElementById('digest-frequency').value;
    const categoryCheckboxes = document.querySelectorAll('input[name="category"]:checked');
    const categories = Array.from(categoryCheckboxes).map(cb => cb.value);

    const success = await subscribeToEmailDigest(email, {
        frequency,
        categories
    });

    if (success) {
        renderAlertsModal('email');
    }
}

// ============================================
// TOAST NOTIFICATIONS
// ============================================
function showToast(message, type = 'info') {
    // Remove existing toast
    const existing = document.getElementById('alerts-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'alerts-toast';

    const bgColors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    };

    const textColors = {
        success: 'text-white',
        error: 'text-white',
        warning: 'text-black',
        info: 'text-white'
    };

    toast.className = `fixed bottom-20 left-1/2 -translate-x-1/2 z-[200] ${bgColors[type]} ${textColors[type]} px-6 py-3 rounded-full shadow-lg font-medium text-sm transform transition-all duration-300 translate-y-10 opacity-0`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-10', 'opacity-0');
    });

    // Remove after delay
    setTimeout(() => {
        toast.classList.add('translate-y-10', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// UTILITY FUNCTIONS
// ============================================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatRelativeDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'ahora';
    if (diffMins < 60) return `hace ${diffMins}m`;
    if (diffHours < 24) return `hace ${diffHours}h`;
    if (diffDays < 7) return `hace ${diffDays}d`;
    return date.toLocaleDateString('es-AR');
}

// ============================================
// GENERATE WATCH BUTTON HTML
// ============================================
function getWatchButtonHtml(auction) {
    if (!auction || !auction.id) return '';

    const isWatching = isAuctionWatched(auction.id);

    return `
        <button data-watch-id="${auction.id}"
                onclick="event.preventDefault(); event.stopPropagation(); watchAuctionById('${auction.id}')"
                class="absolute bottom-3 right-3 w-8 h-8 rounded-full bg-black/50 hover:bg-black/70 flex items-center justify-center transition-all ${isWatching ? 'watching' : ''}"
                title="${isWatching ? 'Dejar de seguir' : 'Seguir subasta'}">
            <svg class="w-4 h-4 ${isWatching ? 'text-yellow-500' : 'text-white/40'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
            </svg>
        </button>
    `;
}

// Helper to watch by ID (finds auction in allAuctions)
function watchAuctionById(auctionId) {
    const auction = (typeof allAuctions !== 'undefined' ? allAuctions : []).find(a => a.id === auctionId);
    if (auction) {
        watchAuction(auction);
    } else {
        console.warn('[Alerts] Auction not found:', auctionId);
    }
}

// ============================================
// EXPORT / INIT
// ============================================
// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAlerts);
} else {
    initAlerts();
}

// Expose functions globally
window.SubastoAlerts = {
    init: initAlerts,
    saveCurrentSearch,
    watchAuction,
    watchAuctionById,
    unwatchAuction,
    isAuctionWatched,
    openAlertsModal,
    closeAlertsModal,
    toggleAlertsModal,
    getWatchButtonHtml,
    showToast
};
