/**
 * Watchlist Module for Subasto.com.ar
 * Allows users to track favorite auctions using localStorage
 * No account required - pure client-side implementation
 */

const Watchlist = (function() {
    'use strict';

    // Constants
    const STORAGE_KEY = 'subasto_watchlist';
    const MAX_ITEMS = 50;
    const WARNING_THRESHOLD = 45;

    // State
    let watchlistItems = [];
    let isOpen = false;
    let currentSort = 'date_added'; // date_added, closing_soon, price_asc, price_desc

    /**
     * Initialize watchlist from localStorage
     */
    function init() {
        loadFromStorage();
        renderWatchlistButton();
        renderWatchlistPanel();
        updateAllHeartIcons();
        startCountdownUpdater();

        // Listen for storage changes (sync across tabs)
        window.addEventListener('storage', (e) => {
            if (e.key === STORAGE_KEY) {
                loadFromStorage();
                updateAllHeartIcons();
                renderWatchlistItems();
                updateWatchlistCount();
            }
        });
    }

    /**
     * Load watchlist from localStorage
     */
    function loadFromStorage() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            watchlistItems = stored ? JSON.parse(stored) : [];
            // Clean up expired items (ended more than 7 days ago)
            const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
            watchlistItems = watchlistItems.filter(item => {
                if (!item.ends_at) return true;
                const endDate = new Date(item.ends_at);
                return endDate > weekAgo;
            });
            saveToStorage();
        } catch (e) {
            console.error('Error loading watchlist:', e);
            watchlistItems = [];
        }
    }

    /**
     * Save watchlist to localStorage
     */
    function saveToStorage() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(watchlistItems));
        } catch (e) {
            console.error('Error saving watchlist:', e);
        }
    }

    /**
     * Check if an item is in the watchlist
     */
    function isInWatchlist(id) {
        return watchlistItems.some(item => item.id === id);
    }

    /**
     * Add item to watchlist
     */
    function addItem(auction) {
        if (isInWatchlist(auction.id)) return false;

        if (watchlistItems.length >= MAX_ITEMS) {
            showNotification('Watchlist llena. Elimina items para agregar mas.', 'error');
            return false;
        }

        const item = {
            id: auction.id,
            title: auction.title,
            base_price: auction.base_price,
            currency: auction.currency,
            ends_at: auction.ends_at,
            starts_at: auction.starts_at,
            source: auction.source,
            source_url: auction.source_url,
            category: auction.category,
            images: auction.images,
            date_added: new Date().toISOString()
        };

        watchlistItems.unshift(item);
        saveToStorage();
        updateWatchlistCount();
        renderWatchlistItems();

        if (watchlistItems.length >= WARNING_THRESHOLD) {
            showNotification(`${MAX_ITEMS - watchlistItems.length} espacios restantes en tu watchlist`, 'warning');
        } else {
            showNotification('Agregado a tu watchlist', 'success');
        }

        // Track event
        if (typeof gtag === 'function') {
            gtag('event', 'add_to_watchlist', {
                'item_id': auction.id,
                'item_category': auction.category
            });
        }

        return true;
    }

    /**
     * Remove item from watchlist
     */
    function removeItem(id) {
        const index = watchlistItems.findIndex(item => item.id === id);
        if (index === -1) return false;

        watchlistItems.splice(index, 1);
        saveToStorage();
        updateWatchlistCount();
        renderWatchlistItems();
        updateHeartIcon(id, false);
        showNotification('Eliminado de tu watchlist', 'info');

        return true;
    }

    /**
     * Toggle item in watchlist
     */
    function toggleItem(auction) {
        if (isInWatchlist(auction.id)) {
            removeItem(auction.id);
            return false;
        } else {
            addItem(auction);
            return true;
        }
    }

    /**
     * Get sorted watchlist items
     */
    function getSortedItems() {
        const items = [...watchlistItems];

        switch (currentSort) {
            case 'closing_soon':
                return items.sort((a, b) => {
                    const aEnd = a.ends_at ? new Date(a.ends_at) : new Date('2099-01-01');
                    const bEnd = b.ends_at ? new Date(b.ends_at) : new Date('2099-01-01');
                    return aEnd - bEnd;
                });
            case 'price_asc':
                return items.sort((a, b) => {
                    const aPrice = toUSD(a.base_price || 0, a.currency);
                    const bPrice = toUSD(b.base_price || 0, b.currency);
                    return aPrice - bPrice;
                });
            case 'price_desc':
                return items.sort((a, b) => {
                    const aPrice = toUSD(a.base_price || 0, a.currency);
                    const bPrice = toUSD(b.base_price || 0, b.currency);
                    return bPrice - aPrice;
                });
            case 'date_added':
            default:
                return items.sort((a, b) => new Date(b.date_added) - new Date(a.date_added));
        }
    }

    /**
     * Convert price to USD (uses global function if available)
     */
    function toUSD(price, currency) {
        if (typeof window.toUSD === 'function') {
            return window.toUSD(price, currency);
        }
        // Fallback
        const BLUE_RATE = window.BLUE_DOLLAR_RATE || 1430;
        return currency === 'USD' ? price : price / BLUE_RATE;
    }

    /**
     * Format price (uses global function if available)
     */
    function formatPriceLocal(price, currency) {
        if (typeof window.formatPrice === 'function') {
            return window.formatPrice(price, currency);
        }
        // Fallback
        const displayCurrency = window.displayCurrency || 'USD';
        const BLUE_RATE = window.BLUE_DOLLAR_RATE || 1430;

        if (displayCurrency === 'ARS') {
            const arsPrice = currency === 'USD' ? price * BLUE_RATE : price;
            return 'ARS ' + arsPrice.toLocaleString('es-AR', { maximumFractionDigits: 0 });
        } else {
            const usdPrice = currency === 'ARS' ? price / BLUE_RATE : price;
            return 'USD ' + usdPrice.toLocaleString('en-US', { maximumFractionDigits: 0 });
        }
    }

    /**
     * Format countdown timer
     */
    function formatCountdownLocal(endDateStr) {
        if (!endDateStr) return null;
        const endDate = new Date(endDateStr);
        const now = new Date();
        const diff = endDate - now;

        if (diff <= 0) return { text: 'Finalizada', expired: true, urgent: false };

        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);

        // Check if closing in 24h
        const closingIn24h = diff <= 24 * 60 * 60 * 1000;

        if (days > 0) {
            return { text: `${days}d ${hours}h`, expired: false, urgent: days <= 1, closingIn24h };
        } else if (hours > 0) {
            return { text: `${hours}h ${minutes}m`, expired: false, urgent: true, closingIn24h };
        } else {
            return { text: `${minutes}m ${seconds}s`, expired: false, urgent: true, closingIn24h };
        }
    }

    /**
     * Check if item is closing in 24h
     */
    function isClosingIn24h(item) {
        if (!item.ends_at) return false;
        const endDate = new Date(item.ends_at);
        const now = new Date();
        const diff = endDate - now;
        return diff > 0 && diff <= 24 * 60 * 60 * 1000;
    }

    /**
     * Get closing in 24h count
     */
    function getClosingIn24hCount() {
        return watchlistItems.filter(isClosingIn24h).length;
    }

    /**
     * Render watchlist button in navigation
     */
    function renderWatchlistButton() {
        // Find the nav element
        const nav = document.querySelector('nav .flex.glass');
        if (!nav) return;

        // Find the currency selector
        const currencyDiv = nav.querySelector('.flex.bg-black\\/30');
        if (!currencyDiv) return;

        // Create watchlist button
        const watchlistBtn = document.createElement('button');
        watchlistBtn.id = 'watchlist-nav-btn';
        watchlistBtn.className = 'relative p-2 text-white/60 hover:text-white transition-colors';
        watchlistBtn.title = 'Mi Watchlist';
        watchlistBtn.onclick = togglePanel;
        watchlistBtn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
            </svg>
            <span id="watchlist-count-badge" class="absolute -top-1 -right-1 w-5 h-5 bg-yellow-500 text-black text-[10px] font-bold rounded-full flex items-center justify-center hidden">0</span>
        `;

        // Insert before currency selector
        currencyDiv.parentNode.insertBefore(watchlistBtn, currencyDiv);

        updateWatchlistCount();
    }

    /**
     * Update watchlist count badge
     */
    function updateWatchlistCount() {
        const badge = document.getElementById('watchlist-count-badge');
        if (!badge) return;

        const count = watchlistItems.length;
        const closingCount = getClosingIn24hCount();

        if (count === 0) {
            badge.classList.add('hidden');
        } else {
            badge.classList.remove('hidden');
            badge.textContent = count;

            // Pulse animation if items closing soon
            if (closingCount > 0) {
                badge.classList.add('animate-pulse', 'bg-red-500');
                badge.classList.remove('bg-yellow-500');
            } else {
                badge.classList.remove('animate-pulse', 'bg-red-500');
                badge.classList.add('bg-yellow-500');
            }
        }
    }

    /**
     * Render watchlist panel (sidebar)
     */
    function renderWatchlistPanel() {
        // Check if panel already exists
        if (document.getElementById('watchlist-panel')) return;

        const panel = document.createElement('div');
        panel.id = 'watchlist-panel';
        panel.className = 'fixed top-0 right-0 w-full md:w-[420px] h-full bg-[#0a0a0a] border-l border-white/10 z-[100] transform translate-x-full transition-transform duration-300 ease-out flex flex-col';
        panel.innerHTML = `
            <!-- Header -->
            <div class="flex items-center justify-between p-4 border-b border-white/10">
                <div class="flex items-center gap-3">
                    <svg class="w-6 h-6 text-yellow-500" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                    </svg>
                    <h2 class="text-lg font-display font-semibold text-white">Mi Watchlist</h2>
                    <span id="watchlist-panel-count" class="text-xs text-white/40">(0 items)</span>
                </div>
                <button onclick="Watchlist.closePanel()" class="p-2 text-white/60 hover:text-white transition-colors">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>

            <!-- Sort & Actions -->
            <div class="flex items-center justify-between p-4 border-b border-white/5 bg-white/[0.02]">
                <div class="flex items-center gap-2">
                    <span class="text-xs text-white/40 uppercase tracking-wider">Ordenar:</span>
                    <select id="watchlist-sort" onchange="Watchlist.setSort(this.value)" class="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-yellow-500/50">
                        <option value="date_added">Agregados</option>
                        <option value="closing_soon">Cierra pronto</option>
                        <option value="price_asc">Precio: menor</option>
                        <option value="price_desc">Precio: mayor</option>
                    </select>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="Watchlist.exportCSV()" class="p-2 text-white/40 hover:text-white transition-colors" title="Exportar CSV">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                        </svg>
                    </button>
                    <button onclick="Watchlist.exportText()" class="p-2 text-white/40 hover:text-white transition-colors" title="Copiar lista">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                        </svg>
                    </button>
                </div>
            </div>

            <!-- Items List -->
            <div id="watchlist-items" class="flex-1 overflow-y-auto p-4 space-y-3">
                <!-- Items rendered here -->
            </div>

            <!-- Footer -->
            <div class="p-4 border-t border-white/10 bg-white/[0.02]">
                <div class="flex items-center justify-between text-xs text-white/40">
                    <span id="watchlist-limit-info">${watchlistItems.length}/${MAX_ITEMS} items</span>
                    <span>Guardado en tu navegador</span>
                </div>
            </div>
        `;

        document.body.appendChild(panel);

        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = 'watchlist-overlay';
        overlay.className = 'fixed inset-0 bg-black/50 z-[99] hidden opacity-0 transition-opacity duration-300';
        overlay.onclick = closePanel;
        document.body.appendChild(overlay);

        renderWatchlistItems();
    }

    /**
     * Render watchlist items
     */
    function renderWatchlistItems() {
        const container = document.getElementById('watchlist-items');
        const countSpan = document.getElementById('watchlist-panel-count');
        const limitInfo = document.getElementById('watchlist-limit-info');

        if (!container) return;

        const items = getSortedItems();

        if (countSpan) {
            countSpan.textContent = `(${items.length} item${items.length !== 1 ? 's' : ''})`;
        }

        if (limitInfo) {
            limitInfo.textContent = `${items.length}/${MAX_ITEMS} items`;
            if (items.length >= WARNING_THRESHOLD) {
                limitInfo.classList.add('text-yellow-500');
            } else {
                limitInfo.classList.remove('text-yellow-500');
            }
        }

        if (items.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <svg class="w-16 h-16 text-white/10 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
                    </svg>
                    <p class="text-white/30 mb-2">Tu watchlist esta vacia</p>
                    <p class="text-white/20 text-sm">Hace clic en el corazon de cualquier subasta para guardarla</p>
                </div>
            `;
            return;
        }

        container.innerHTML = items.map(item => {
            const countdown = formatCountdownLocal(item.ends_at);
            const imageUrl = item.images && item.images.length > 0 ? item.images[0] : '/api/placeholder.svg';
            const closingIn24h = isClosingIn24h(item);
            const categoryClass = `category-${item.category || 'other'}`;

            return `
                <div class="watchlist-item glass rounded-xl p-3 group relative ${closingIn24h ? 'ring-2 ring-yellow-500/50' : ''}">
                    ${closingIn24h ? `
                        <div class="absolute -top-2 -right-2 bg-yellow-500 text-black text-[9px] font-bold px-2 py-0.5 rounded-full animate-pulse">
                            CIERRA EN 24H
                        </div>
                    ` : ''}
                    <div class="flex gap-3">
                        <div class="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 bg-white/5">
                            <img src="${imageUrl}" alt="" class="w-full h-full object-cover" onerror="this.src='/api/placeholder.svg'">
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-start justify-between gap-2">
                                <h4 class="text-white text-sm font-medium line-clamp-2">${item.title}</h4>
                                <div class="flex items-center gap-1 flex-shrink-0">
                                    <button onclick="Watchlist.openInNewTab('${item.source_url}')" class="p-1 text-white/30 hover:text-white transition-colors" title="Abrir">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                        </svg>
                                    </button>
                                    <button onclick="Watchlist.shareItem('${item.id}')" class="p-1 text-white/30 hover:text-white transition-colors" title="Compartir">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/>
                                        </svg>
                                    </button>
                                    <button onclick="Watchlist.removeItem('${item.id}')" class="p-1 text-white/30 hover:text-red-400 transition-colors" title="Eliminar">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            <div class="flex items-center gap-2 mt-1">
                                <span class="category-badge ${categoryClass} text-[8px]">${item.category || 'other'}</span>
                                <span class="source-badge text-[8px]">${item.source}</span>
                            </div>
                            <div class="flex items-center justify-between mt-2">
                                <span class="text-yellow-500 font-display font-bold text-sm">
                                    ${item.base_price > 0 ? formatPriceLocal(item.base_price, item.currency) : 'A consultar'}
                                </span>
                                ${countdown ? `
                                    <span class="text-xs font-mono ${countdown.expired ? 'text-red-400' : countdown.urgent ? 'text-yellow-400' : 'text-green-400'}" data-watchlist-countdown="${item.ends_at || ''}">
                                        ${countdown.text}
                                    </span>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Toggle watchlist panel
     */
    function togglePanel() {
        if (isOpen) {
            closePanel();
        } else {
            openPanel();
        }
    }

    /**
     * Open watchlist panel
     */
    function openPanel() {
        const panel = document.getElementById('watchlist-panel');
        const overlay = document.getElementById('watchlist-overlay');

        if (!panel || !overlay) return;

        isOpen = true;
        panel.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
        setTimeout(() => overlay.classList.add('opacity-100'), 10);
        document.body.classList.add('overflow-hidden');

        renderWatchlistItems();

        // Track event
        if (typeof gtag === 'function') {
            gtag('event', 'view_watchlist', {
                'item_count': watchlistItems.length
            });
        }
    }

    /**
     * Close watchlist panel
     */
    function closePanel() {
        const panel = document.getElementById('watchlist-panel');
        const overlay = document.getElementById('watchlist-overlay');

        if (!panel || !overlay) return;

        isOpen = false;
        panel.classList.add('translate-x-full');
        overlay.classList.remove('opacity-100');
        setTimeout(() => overlay.classList.add('hidden'), 300);
        document.body.classList.remove('overflow-hidden');
    }

    /**
     * Set sort order
     */
    function setSort(sortBy) {
        currentSort = sortBy;
        renderWatchlistItems();
    }

    /**
     * Update all heart icons on auction cards
     */
    function updateAllHeartIcons() {
        document.querySelectorAll('[data-watchlist-id]').forEach(btn => {
            const id = btn.getAttribute('data-watchlist-id');
            updateHeartIcon(id, isInWatchlist(id), btn);
        });
    }

    /**
     * Update single heart icon
     */
    function updateHeartIcon(id, isWatched, btn = null) {
        if (!btn) {
            btn = document.querySelector(`[data-watchlist-id="${id}"]`);
        }
        if (!btn) return;

        const svg = btn.querySelector('svg');
        if (!svg) return;

        if (isWatched) {
            svg.setAttribute('fill', 'currentColor');
            btn.classList.add('text-red-500');
            btn.classList.remove('text-white/30');
        } else {
            svg.setAttribute('fill', 'none');
            btn.classList.remove('text-red-500');
            btn.classList.add('text-white/30');
        }
    }

    /**
     * Start countdown updater for watchlist items
     */
    function startCountdownUpdater() {
        setInterval(() => {
            document.querySelectorAll('[data-watchlist-countdown]').forEach(el => {
                const endDate = el.getAttribute('data-watchlist-countdown');
                if (!endDate) return;
                const countdown = formatCountdownLocal(endDate);
                if (countdown) {
                    el.textContent = countdown.text;
                    el.className = `text-xs font-mono ${countdown.expired ? 'text-red-400' : countdown.urgent ? 'text-yellow-400' : 'text-green-400'}`;
                }
            });
            updateWatchlistCount();
        }, 1000);
    }

    /**
     * Open item in new tab
     */
    function openInNewTab(url) {
        window.open(url, '_blank', 'noopener,noreferrer');
    }

    /**
     * Share item
     */
    function shareItem(id) {
        const item = watchlistItems.find(i => i.id === id);
        if (!item) return;

        const text = `${item.title} - ${formatPriceLocal(item.base_price, item.currency)} en ${item.source.toUpperCase()}`;
        const url = item.source_url;

        if (navigator.share) {
            navigator.share({
                title: item.title,
                text: text,
                url: url
            }).catch(() => {});
        } else {
            // Fallback: copy to clipboard
            navigator.clipboard.writeText(`${text}\n${url}`).then(() => {
                showNotification('Link copiado al portapapeles', 'success');
            }).catch(() => {
                // Final fallback: open share dialog
                window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`, '_blank');
            });
        }
    }

    /**
     * Export watchlist as CSV
     */
    function exportCSV() {
        if (watchlistItems.length === 0) {
            showNotification('Tu watchlist esta vacia', 'info');
            return;
        }

        const headers = ['Titulo', 'Precio', 'Moneda', 'Fuente', 'Categoria', 'Cierra', 'URL'];
        const rows = watchlistItems.map(item => [
            `"${item.title.replace(/"/g, '""')}"`,
            item.base_price || '',
            item.currency || '',
            item.source || '',
            item.category || '',
            item.ends_at || '',
            item.source_url || ''
        ]);

        const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `subasto_watchlist_${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
        URL.revokeObjectURL(url);

        showNotification('Watchlist exportada como CSV', 'success');

        // Track event
        if (typeof gtag === 'function') {
            gtag('event', 'export_watchlist', { 'format': 'csv', 'item_count': watchlistItems.length });
        }
    }

    /**
     * Export watchlist as text (copy to clipboard)
     */
    function exportText() {
        if (watchlistItems.length === 0) {
            showNotification('Tu watchlist esta vacia', 'info');
            return;
        }

        const text = watchlistItems.map((item, i) => {
            const price = item.base_price > 0 ? formatPriceLocal(item.base_price, item.currency) : 'A consultar';
            return `${i + 1}. ${item.title}\n   Precio: ${price}\n   Fuente: ${item.source.toUpperCase()}\n   URL: ${item.source_url}`;
        }).join('\n\n');

        const header = `Mi Watchlist de Subasto.com.ar (${watchlistItems.length} items)\n${'='.repeat(50)}\n\n`;

        navigator.clipboard.writeText(header + text).then(() => {
            showNotification('Watchlist copiada al portapapeles', 'success');
        }).catch(() => {
            showNotification('Error al copiar', 'error');
        });

        // Track event
        if (typeof gtag === 'function') {
            gtag('event', 'export_watchlist', { 'format': 'text', 'item_count': watchlistItems.length });
        }
    }

    /**
     * Show notification toast
     */
    function showNotification(message, type = 'info') {
        // Remove existing notifications
        document.querySelectorAll('.watchlist-notification').forEach(n => n.remove());

        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            info: 'bg-blue-500'
        };

        const notification = document.createElement('div');
        notification.className = `watchlist-notification fixed bottom-4 right-4 ${colors[type]} text-white px-4 py-2 rounded-lg shadow-lg z-[101] transform translate-y-full opacity-0 transition-all duration-300`;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Animate in
        requestAnimationFrame(() => {
            notification.classList.remove('translate-y-full', 'opacity-0');
        });

        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.add('translate-y-full', 'opacity-0');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Generate heart button HTML for auction cards
     */
    function getHeartButtonHTML(auctionId) {
        const isWatched = isInWatchlist(auctionId);
        return `
            <button data-watchlist-id="${auctionId}"
                    class="watchlist-heart-btn absolute top-3 right-3 p-2 rounded-full bg-black/50 hover:bg-black/70 transition-all ${isWatched ? 'text-red-500' : 'text-white/30'} hover:scale-110 z-10"
                    onclick="event.preventDefault(); event.stopPropagation(); Watchlist.handleHeartClick(this);"
                    title="${isWatched ? 'Quitar de watchlist' : 'Agregar a watchlist'}">
                <svg class="w-5 h-5" fill="${isWatched ? 'currentColor' : 'none'}" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
                </svg>
            </button>
        `;
    }

    /**
     * Handle heart button click
     */
    function handleHeartClick(btn) {
        const auctionId = btn.getAttribute('data-watchlist-id');
        if (!auctionId) return;

        // Find the auction data from the global allAuctions array
        const auction = window.allAuctions?.find(a => a.id === auctionId);

        if (!auction) {
            // Try to reconstruct from button's parent card
            const card = btn.closest('.auction-card') || btn.closest('a[href]');
            if (!card) {
                showNotification('Error al procesar subasta', 'error');
                return;
            }

            // Extract data from card - this is a fallback
            const fallbackAuction = {
                id: auctionId,
                title: card.querySelector('h3')?.textContent || 'Sin titulo',
                source_url: card.href || '',
                source: auctionId.split(':')[0] || 'unknown',
                base_price: 0,
                currency: 'ARS',
                category: 'other',
                images: []
            };

            toggleItem(fallbackAuction);
        } else {
            toggleItem(auction);
        }

        // Update button state
        const isWatched = isInWatchlist(auctionId);
        updateHeartIcon(auctionId, isWatched, btn);
    }

    /**
     * Get watchlist items (for external access)
     */
    function getItems() {
        return [...watchlistItems];
    }

    /**
     * Get item count
     */
    function getCount() {
        return watchlistItems.length;
    }

    // Public API
    return {
        init,
        addItem,
        removeItem,
        toggleItem,
        isInWatchlist,
        getItems,
        getCount,
        getClosingIn24hCount,
        openPanel,
        closePanel,
        togglePanel,
        setSort,
        exportCSV,
        exportText,
        openInNewTab,
        shareItem,
        handleHeartClick,
        getHeartButtonHTML,
        updateAllHeartIcons
    };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', Watchlist.init);
} else {
    Watchlist.init();
}
