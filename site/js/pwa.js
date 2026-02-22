/**
 * Subasto.com.ar - PWA Features & Mobile Optimizations
 *
 * Features:
 * - Service Worker registration
 * - Install prompt (Add to Home Screen)
 * - Push notifications
 * - Pull-to-refresh gesture
 * - Swipe actions on cards
 * - Bottom navigation bar
 * - Native-feeling animations
 * - Image lazy loading
 * - Performance optimizations
 */

// ============================================
// PWA STATE
// ============================================
const PWA = {
    deferredPrompt: null,
    isInstalled: false,
    isStandalone: false,
    swRegistration: null,
    pushSubscription: null,
    isIOS: false,
    isAndroid: false,
    isMobile: false,
    supportsTouch: false,
    initialized: false
};

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    detectPlatform();
    registerServiceWorker();
    setupInstallPrompt();
    initMobileOptimizations();
    initPushNotifications();
    initPerformanceOptimizations();
    PWA.initialized = true;
    console.log('[PWA] Initialized', PWA);
});

function detectPlatform() {
    const ua = navigator.userAgent;

    PWA.isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    PWA.isAndroid = /Android/.test(ua);
    PWA.isMobile = PWA.isIOS || PWA.isAndroid || /Mobile|webOS|BlackBerry|Opera Mini|IEMobile/.test(ua);
    PWA.supportsTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    // Check if running as standalone PWA
    PWA.isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
                       window.navigator.standalone === true ||
                       document.referrer.includes('android-app://');

    // Check if already installed
    PWA.isInstalled = PWA.isStandalone || localStorage.getItem('subasto_pwa_installed') === 'true';

    // Add platform classes to body
    document.body.classList.add(PWA.isMobile ? 'is-mobile' : 'is-desktop');
    if (PWA.isIOS) document.body.classList.add('is-ios');
    if (PWA.isAndroid) document.body.classList.add('is-android');
    if (PWA.isStandalone) document.body.classList.add('is-standalone');
}

// ============================================
// SERVICE WORKER REGISTRATION
// ============================================
async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
        console.log('[PWA] Service Workers not supported');
        return;
    }

    try {
        PWA.swRegistration = await navigator.serviceWorker.register('/sw.js', {
            scope: '/'
        });

        console.log('[PWA] Service Worker registered:', PWA.swRegistration.scope);

        // Handle updates
        PWA.swRegistration.addEventListener('updatefound', () => {
            const newWorker = PWA.swRegistration.installing;

            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    // New version available
                    showUpdateAvailable();
                }
            });
        });

        // Listen for messages from SW
        navigator.serviceWorker.addEventListener('message', handleSWMessage);

        // Check for updates periodically
        setInterval(() => {
            PWA.swRegistration.update();
        }, 60 * 60 * 1000); // Every hour

    } catch (error) {
        console.error('[PWA] Service Worker registration failed:', error);
    }
}

function handleSWMessage(event) {
    const { type, payload } = event.data || {};

    switch (type) {
        case 'data-updated':
            // Refresh auction data
            if (typeof fetchAuctions === 'function') {
                fetchAuctions();
            }
            break;

        case 'sync-watchlist':
            // Sync watchlist with server
            console.log('[PWA] Watchlist sync requested');
            break;

        case 'notification-click':
            // Handle notification click data
            if (payload?.auctionId && typeof scrollToAuction === 'function') {
                scrollToAuction(payload.auctionId);
            }
            break;
    }
}

function showUpdateAvailable() {
    const banner = document.createElement('div');
    banner.id = 'update-banner';
    banner.className = 'fixed top-20 left-4 right-4 md:left-auto md:right-6 md:w-96 z-[200] glass rounded-2xl p-4 transform transition-all duration-300 -translate-y-full opacity-0';
    banner.innerHTML = `
        <div class="flex items-start gap-4">
            <div class="w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
                <svg class="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
            </div>
            <div class="flex-1">
                <h4 class="text-white font-medium mb-1">Actualizacion disponible</h4>
                <p class="text-white/60 text-sm mb-3">Hay una nueva version de Subasto disponible.</p>
                <div class="flex gap-2">
                    <button onclick="applyUpdate()" class="px-4 py-1.5 bg-yellow-500 text-black rounded-lg text-sm font-medium hover:bg-yellow-400 transition-colors">
                        Actualizar
                    </button>
                    <button onclick="dismissUpdate()" class="px-4 py-1.5 text-white/60 hover:text-white text-sm transition-colors">
                        Despues
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(banner);

    // Animate in
    requestAnimationFrame(() => {
        banner.classList.remove('-translate-y-full', 'opacity-0');
    });
}

function applyUpdate() {
    if (PWA.swRegistration?.waiting) {
        PWA.swRegistration.waiting.postMessage({ type: 'skip-waiting' });
    }
    window.location.reload();
}

function dismissUpdate() {
    const banner = document.getElementById('update-banner');
    if (banner) {
        banner.classList.add('-translate-y-full', 'opacity-0');
        setTimeout(() => banner.remove(), 300);
    }
}

// ============================================
// INSTALL PROMPT (Add to Home Screen)
// ============================================
function setupInstallPrompt() {
    // Capture the install prompt
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        PWA.deferredPrompt = e;
        console.log('[PWA] Install prompt captured');

        // Show install button after a delay
        setTimeout(() => {
            if (!PWA.isInstalled) {
                showInstallPrompt();
            }
        }, 30000); // Show after 30 seconds of use
    });

    // Track when app is installed
    window.addEventListener('appinstalled', () => {
        PWA.isInstalled = true;
        PWA.deferredPrompt = null;
        localStorage.setItem('subasto_pwa_installed', 'true');
        hideInstallPrompt();
        showToast('App instalada correctamente!', 'success');

        // Track event
        if (typeof gtag === 'function') {
            gtag('event', 'pwa_installed');
        }
    });

    // For iOS, show manual instructions
    if (PWA.isIOS && !PWA.isStandalone && !localStorage.getItem('subasto_ios_prompt_dismissed')) {
        setTimeout(() => showIOSInstallPrompt(), 45000);
    }
}

function showInstallPrompt() {
    if (PWA.isInstalled || !PWA.deferredPrompt) return;

    // Don't show if user dismissed recently
    const lastDismissed = localStorage.getItem('subasto_install_dismissed');
    if (lastDismissed && Date.now() - parseInt(lastDismissed) < 7 * 24 * 60 * 60 * 1000) {
        return; // Don't show for 7 days after dismiss
    }

    const prompt = document.createElement('div');
    prompt.id = 'install-prompt';
    prompt.className = 'fixed bottom-24 left-4 right-4 md:bottom-6 md:left-auto md:right-6 md:w-96 z-[150] glass rounded-2xl p-5 transform transition-all duration-500 translate-y-full opacity-0';
    prompt.innerHTML = `
        <div class="flex items-start gap-4">
            <div class="w-14 h-14 rounded-2xl bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" class="w-8 h-8">
                    <g>
                        <rect x="196" y="196" width="120" height="120" fill="none" stroke="#eab308" stroke-width="6" transform="rotate(45 256 256)"/>
                        <circle cx="256" cy="256" r="14" fill="#eab308"/>
                    </g>
                </svg>
            </div>
            <div class="flex-1">
                <h4 class="text-white font-display font-medium text-lg mb-1">Instala Subasto</h4>
                <p class="text-white/60 text-sm mb-4">Accede mas rapido desde tu pantalla de inicio. Sin tienda, sin descargas.</p>
                <div class="flex gap-3">
                    <button onclick="installPWA()" class="flex-1 px-4 py-2.5 bg-yellow-500 text-black rounded-xl font-medium hover:bg-yellow-400 transition-colors flex items-center justify-center gap-2">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                        </svg>
                        Instalar
                    </button>
                    <button onclick="dismissInstallPrompt()" class="px-4 py-2.5 text-white/60 hover:text-white transition-colors">
                        Ahora no
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(prompt);

    // Animate in
    requestAnimationFrame(() => {
        prompt.classList.remove('translate-y-full', 'opacity-0');
    });
}

async function installPWA() {
    if (!PWA.deferredPrompt) {
        console.log('[PWA] No install prompt available');
        return;
    }

    PWA.deferredPrompt.prompt();
    const { outcome } = await PWA.deferredPrompt.userChoice;

    console.log('[PWA] Install outcome:', outcome);

    if (outcome === 'accepted') {
        PWA.deferredPrompt = null;
    }

    hideInstallPrompt();
}

function dismissInstallPrompt() {
    localStorage.setItem('subasto_install_dismissed', Date.now().toString());
    hideInstallPrompt();
}

function hideInstallPrompt() {
    const prompt = document.getElementById('install-prompt');
    if (prompt) {
        prompt.classList.add('translate-y-full', 'opacity-0');
        setTimeout(() => prompt.remove(), 500);
    }
}

function showIOSInstallPrompt() {
    const prompt = document.createElement('div');
    prompt.id = 'ios-install-prompt';
    prompt.className = 'fixed bottom-20 left-4 right-4 z-[150] glass rounded-2xl p-5 transform transition-all duration-500 translate-y-full opacity-0';
    prompt.innerHTML = `
        <button onclick="dismissIOSPrompt()" class="absolute top-3 right-3 w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center">
            <svg class="w-5 h-5 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
        </button>
        <div class="text-center">
            <h4 class="text-white font-display font-medium text-lg mb-3">Agrega a tu pantalla de inicio</h4>
            <p class="text-white/60 text-sm mb-4">Para una mejor experiencia, agrega Subasto a tu pantalla de inicio:</p>
            <div class="flex items-center justify-center gap-2 text-white/80 text-sm">
                <span>Toca</span>
                <svg class="w-6 h-6 text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M16 5l-1.42 1.42-1.59-1.59V16h-1.98V4.83L9.42 6.42 8 5l4-4 4 4zm4 5v11c0 1.1-.9 2-2 2H6a2 2 0 01-2-2V10c0-1.11.89-2 2-2h3v2H6v11h12V10h-3V8h3a2 2 0 012 2z"/>
                </svg>
                <span>y luego "Agregar a pantalla de inicio"</span>
            </div>
        </div>
    `;

    document.body.appendChild(prompt);

    requestAnimationFrame(() => {
        prompt.classList.remove('translate-y-full', 'opacity-0');
    });
}

function dismissIOSPrompt() {
    localStorage.setItem('subasto_ios_prompt_dismissed', 'true');
    const prompt = document.getElementById('ios-install-prompt');
    if (prompt) {
        prompt.classList.add('translate-y-full', 'opacity-0');
        setTimeout(() => prompt.remove(), 500);
    }
}

// ============================================
// PUSH NOTIFICATIONS
// ============================================
async function initPushNotifications() {
    if (!('PushManager' in window) || !PWA.swRegistration) {
        console.log('[PWA] Push notifications not supported');
        return;
    }

    try {
        PWA.pushSubscription = await PWA.swRegistration.pushManager.getSubscription();

        if (PWA.pushSubscription) {
            console.log('[PWA] Already subscribed to push');
        }
    } catch (error) {
        console.error('[PWA] Error checking push subscription:', error);
    }
}

async function subscribeToPush() {
    if (!PWA.swRegistration) {
        console.error('[PWA] No service worker registration');
        return false;
    }

    try {
        // Request notification permission
        const permission = await Notification.requestPermission();

        if (permission !== 'granted') {
            console.log('[PWA] Notification permission denied');
            return false;
        }

        // Subscribe to push (you would need a VAPID key for production)
        // For now, we just use local notifications via the existing alerts system
        console.log('[PWA] Push notifications enabled (local mode)');

        // Track event
        if (typeof gtag === 'function') {
            gtag('event', 'push_enabled');
        }

        return true;
    } catch (error) {
        console.error('[PWA] Push subscription failed:', error);
        return false;
    }
}

// Schedule local notification for ending auctions
function scheduleAuctionReminder(auction, minutesBefore = 60) {
    if (Notification.permission !== 'granted') return;

    const endTime = new Date(auction.ends_at).getTime();
    const notifyTime = endTime - (minutesBefore * 60 * 1000);
    const now = Date.now();

    if (notifyTime > now) {
        const delay = notifyTime - now;

        setTimeout(() => {
            if (document.hidden) { // Only notify if app is in background
                new Notification('Subasta por terminar', {
                    body: `"${auction.title.substring(0, 50)}..." termina en ${minutesBefore} minutos`,
                    icon: '/favicon-32x32.png',
                    tag: `auction-${auction.id}`,
                    data: { auctionId: auction.id, url: auction.source_url }
                });
            }
        }, delay);
    }
}

// ============================================
// MOBILE OPTIMIZATIONS
// ============================================
function initMobileOptimizations() {
    if (!PWA.isMobile) return;

    initPullToRefresh();
    initSwipeActions();
    initBottomNavigation();
    initHapticFeedback();
    optimizeScrolling();
    handleSafeAreas();
}

// Pull-to-refresh gesture
function initPullToRefresh() {
    let startY = 0;
    let currentY = 0;
    let isPulling = false;
    let refreshTriggered = false;

    const threshold = 80;
    const maxPull = 120;

    // Create pull indicator
    const indicator = document.createElement('div');
    indicator.id = 'pull-indicator';
    indicator.className = 'fixed top-0 left-0 right-0 h-16 flex items-center justify-center z-[100] pointer-events-none opacity-0 transition-opacity';
    indicator.innerHTML = `
        <div class="pull-spinner w-8 h-8 rounded-full border-2 border-yellow-500/30 border-t-yellow-500"></div>
    `;
    document.body.appendChild(indicator);

    // Add spinning animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes pull-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .pull-spinning { animation: pull-spin 0.8s linear infinite; }
        .pull-indicator-pulling .pull-spinner { transform: scale(0.8); }
        .pull-indicator-ready .pull-spinner { transform: scale(1); border-color: #eab308 !important; }
    `;
    document.head.appendChild(style);

    document.addEventListener('touchstart', (e) => {
        if (window.scrollY === 0) {
            startY = e.touches[0].pageY;
            isPulling = true;
        }
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (!isPulling || window.scrollY > 0) {
            isPulling = false;
            return;
        }

        currentY = e.touches[0].pageY;
        const pullDistance = Math.min(currentY - startY, maxPull);

        if (pullDistance > 0) {
            indicator.style.opacity = Math.min(pullDistance / threshold, 1);
            indicator.style.transform = `translateY(${pullDistance - 64}px)`;

            if (pullDistance >= threshold) {
                indicator.classList.add('pull-indicator-ready');
                indicator.classList.remove('pull-indicator-pulling');
                refreshTriggered = true;
            } else {
                indicator.classList.add('pull-indicator-pulling');
                indicator.classList.remove('pull-indicator-ready');
                refreshTriggered = false;
            }
        }
    }, { passive: true });

    document.addEventListener('touchend', async () => {
        if (refreshTriggered) {
            indicator.querySelector('.pull-spinner').classList.add('pull-spinning');

            // Perform refresh
            if (typeof refreshAuctions === 'function') {
                await refreshAuctions();
            } else if (typeof fetchAuctions === 'function') {
                await fetchAuctions();
            }

            showToast('Datos actualizados', 'success');
        }

        // Reset
        indicator.style.opacity = '0';
        indicator.style.transform = 'translateY(-64px)';
        indicator.classList.remove('pull-indicator-ready', 'pull-indicator-pulling');
        indicator.querySelector('.pull-spinner').classList.remove('pull-spinning');

        isPulling = false;
        refreshTriggered = false;
    }, { passive: true });
}

// Swipe actions on cards
function initSwipeActions() {
    // This will be applied to auction cards after they're rendered
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.classList?.contains('auction-card')) {
                    makeSwipeable(node);
                }
            });
        });
    });

    const grid = document.getElementById('auctions-grid');
    if (grid) {
        observer.observe(grid, { childList: true });

        // Apply to existing cards
        grid.querySelectorAll('.auction-card').forEach(makeSwipeable);
    }
}

function makeSwipeable(card) {
    if (card.dataset.swipeable) return;
    card.dataset.swipeable = 'true';

    let startX = 0;
    let currentX = 0;
    let startTime = 0;

    const actionThreshold = 80;
    const maxSwipe = 100;

    // Create swipe action indicators
    const leftAction = document.createElement('div');
    leftAction.className = 'swipe-action swipe-action-left absolute inset-y-0 left-0 w-20 flex items-center justify-center bg-yellow-500 rounded-l-2xl opacity-0 -z-10';
    leftAction.innerHTML = `
        <svg class="w-6 h-6 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
        </svg>
    `;

    const rightAction = document.createElement('div');
    rightAction.className = 'swipe-action swipe-action-right absolute inset-y-0 right-0 w-20 flex items-center justify-center bg-blue-500 rounded-r-2xl opacity-0 -z-10';
    rightAction.innerHTML = `
        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/>
        </svg>
    `;

    card.style.position = 'relative';
    card.appendChild(leftAction);
    card.appendChild(rightAction);

    card.addEventListener('touchstart', (e) => {
        startX = e.touches[0].pageX;
        startTime = Date.now();
        card.style.transition = 'none';
    }, { passive: true });

    card.addEventListener('touchmove', (e) => {
        currentX = e.touches[0].pageX;
        const deltaX = Math.max(-maxSwipe, Math.min(maxSwipe, currentX - startX));

        card.style.transform = `translateX(${deltaX}px)`;

        // Show appropriate action
        if (deltaX > 20) {
            leftAction.style.opacity = Math.min(deltaX / actionThreshold, 1);
            rightAction.style.opacity = '0';
        } else if (deltaX < -20) {
            rightAction.style.opacity = Math.min(Math.abs(deltaX) / actionThreshold, 1);
            leftAction.style.opacity = '0';
        }
    }, { passive: true });

    card.addEventListener('touchend', () => {
        const deltaX = currentX - startX;
        const velocity = Math.abs(deltaX) / (Date.now() - startTime);

        card.style.transition = 'transform 0.3s ease';
        card.style.transform = 'translateX(0)';
        leftAction.style.opacity = '0';
        rightAction.style.opacity = '0';

        // Trigger action if threshold reached
        if (deltaX > actionThreshold || (deltaX > 40 && velocity > 0.5)) {
            // Swipe right: Watch auction
            triggerSwipeWatch(card);
        } else if (deltaX < -actionThreshold || (deltaX < -40 && velocity > 0.5)) {
            // Swipe left: Share
            triggerSwipeShare(card);
        }
    }, { passive: true });
}

function triggerSwipeWatch(card) {
    const link = card.querySelector('a[href]');
    if (link) {
        const auctionId = link.href.split('/').pop() || link.getAttribute('data-auction-id');
        if (typeof watchAuctionById === 'function') {
            watchAuctionById(auctionId);
            triggerHaptic('success');
        }
    }
}

function triggerSwipeShare(card) {
    const link = card.querySelector('a[href]');
    const title = card.querySelector('h3')?.textContent || 'Subasta';

    if (navigator.share && link) {
        navigator.share({
            title: title,
            text: 'Mira esta subasta en Subasto.com.ar',
            url: link.href
        }).then(() => {
            triggerHaptic('success');
        }).catch(() => {});
    }
}

// Bottom navigation bar
function initBottomNavigation() {
    // Only show on mobile in standalone mode
    if (!PWA.isStandalone && !PWA.isMobile) return;

    const nav = document.createElement('nav');
    nav.id = 'bottom-nav';
    nav.className = 'fixed bottom-0 left-0 right-0 z-[100] glass border-t border-white/10 safe-area-bottom';
    nav.innerHTML = `
        <div class="flex items-center justify-around h-16 max-w-lg mx-auto">
            <a href="#" onclick="scrollToSection('auctions'); return false;" class="bottom-nav-item flex flex-col items-center justify-center gap-1 flex-1 py-2 text-yellow-500" data-section="auctions">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
                </svg>
                <span class="text-[10px] uppercase tracking-wider">Subastas</span>
            </a>
            <a href="#" onclick="scrollToSection('calendar'); return false;" class="bottom-nav-item flex flex-col items-center justify-center gap-1 flex-1 py-2 text-white/50" data-section="calendar">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                <span class="text-[10px] uppercase tracking-wider">Calendario</span>
            </a>
            <a href="#" onclick="scrollToSection('dashboard'); return false;" class="bottom-nav-item flex flex-col items-center justify-center gap-1 flex-1 py-2 text-white/50" data-section="dashboard">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
                <span class="text-[10px] uppercase tracking-wider">Dashboard</span>
            </a>
            <button onclick="openAlertsFromNav()" class="bottom-nav-item flex flex-col items-center justify-center gap-1 flex-1 py-2 text-white/50 relative" data-section="alerts">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
                </svg>
                <span class="text-[10px] uppercase tracking-wider">Alertas</span>
                <span id="bottom-nav-badge" class="absolute -top-1 right-1/4 w-4 h-4 bg-yellow-500 text-black text-[9px] font-bold rounded-full flex items-center justify-center hidden">0</span>
            </button>
        </div>
    `;

    document.body.appendChild(nav);

    // Add padding to body for bottom nav
    document.body.style.paddingBottom = '80px';

    // Update active state on scroll
    updateBottomNavActive();
    window.addEventListener('scroll', throttle(updateBottomNavActive, 100));

    // Update badge
    updateBottomNavBadge();
}

function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
        updateBottomNavItem(sectionId);
        triggerHaptic('light');
    }
}

function updateBottomNavActive() {
    const sections = ['auctions', 'calendar', 'dashboard'];
    const scrollPos = window.scrollY + window.innerHeight / 2;

    let activeSection = 'auctions';

    for (const id of sections) {
        const section = document.getElementById(id);
        if (section) {
            const rect = section.getBoundingClientRect();
            const sectionTop = rect.top + window.scrollY;
            const sectionBottom = sectionTop + rect.height;

            if (scrollPos >= sectionTop && scrollPos < sectionBottom) {
                activeSection = id;
                break;
            }
        }
    }

    updateBottomNavItem(activeSection);
}

function updateBottomNavItem(activeSection) {
    document.querySelectorAll('.bottom-nav-item').forEach(item => {
        const section = item.dataset.section;
        if (section === activeSection) {
            item.classList.remove('text-white/50');
            item.classList.add('text-yellow-500');
        } else {
            item.classList.add('text-white/50');
            item.classList.remove('text-yellow-500');
        }
    });
}

function updateBottomNavBadge() {
    const badge = document.getElementById('bottom-nav-badge');
    if (!badge) return;

    // Get count from alerts system
    const watchedCount = JSON.parse(localStorage.getItem('subasto_watched_auctions') || '[]').length;
    const savedCount = JSON.parse(localStorage.getItem('subasto_saved_searches') || '[]').length;
    const total = watchedCount + savedCount;

    if (total > 0) {
        badge.textContent = total > 9 ? '9+' : total;
        badge.classList.remove('hidden');
    } else {
        badge.classList.add('hidden');
    }
}

function openAlertsFromNav() {
    if (typeof toggleAlertsModal === 'function') {
        toggleAlertsModal();
    } else if (typeof SubastoAlerts?.toggleAlertsModal === 'function') {
        SubastoAlerts.toggleAlertsModal();
    }
    triggerHaptic('medium');
}

// Haptic feedback
function initHapticFeedback() {
    if (!('vibrate' in navigator)) return;

    // Add haptic to all buttons
    document.addEventListener('click', (e) => {
        if (e.target.closest('button') || e.target.closest('a')) {
            triggerHaptic('light');
        }
    });
}

function triggerHaptic(style = 'light') {
    if (!('vibrate' in navigator)) return;

    const patterns = {
        light: [10],
        medium: [20],
        heavy: [40],
        success: [10, 50, 10],
        warning: [30, 50, 30],
        error: [50, 30, 50, 30, 50]
    };

    navigator.vibrate(patterns[style] || patterns.light);
}

// Optimize scrolling
function optimizeScrolling() {
    // Disable rubber-band effect on iOS
    if (PWA.isIOS) {
        document.body.style.overscrollBehavior = 'none';
    }

    // Add momentum scrolling hints
    document.querySelectorAll('.overflow-auto, .overflow-y-auto').forEach(el => {
        el.style.webkitOverflowScrolling = 'touch';
    });
}

// Handle safe areas (notch, home indicator)
function handleSafeAreas() {
    // Add CSS for safe areas
    const style = document.createElement('style');
    style.textContent = `
        .safe-area-top { padding-top: env(safe-area-inset-top); }
        .safe-area-bottom { padding-bottom: env(safe-area-inset-bottom); }
        .safe-area-left { padding-left: env(safe-area-inset-left); }
        .safe-area-right { padding-right: env(safe-area-inset-right); }

        /* Standalone PWA adjustments */
        .is-standalone nav.fixed { padding-top: calc(1rem + env(safe-area-inset-top)); }
        .is-standalone #bottom-nav { padding-bottom: env(safe-area-inset-bottom); }

        /* iOS notch handling */
        .is-ios.is-standalone body { padding-top: env(safe-area-inset-top); }
    `;
    document.head.appendChild(style);
}

// ============================================
// PERFORMANCE OPTIMIZATIONS
// ============================================
function initPerformanceOptimizations() {
    initLazyLoading();
    initSkeletonLoading();
    prefetchCriticalResources();
}

// Lazy load images
function initLazyLoading() {
    // Use native lazy loading with IntersectionObserver fallback
    if ('loading' in HTMLImageElement.prototype) {
        document.querySelectorAll('img[data-src]').forEach(img => {
            img.src = img.dataset.src;
            img.loading = 'lazy';
        });
    } else {
        // Fallback for older browsers
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                    }
                    imageObserver.unobserve(img);
                }
            });
        }, { rootMargin: '50px' });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
}

// Skeleton loading states
function initSkeletonLoading() {
    // Add skeleton animation styles
    const style = document.createElement('style');
    style.textContent = `
        .skeleton {
            background: linear-gradient(90deg, rgba(255,255,255,0.05) 25%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0.05) 75%);
            background-size: 200% 100%;
            animation: skeleton-shimmer 1.5s infinite;
        }
        @keyframes skeleton-shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
    `;
    document.head.appendChild(style);
}

// Show skeleton grid
function showSkeletonGrid(count = 8) {
    const grid = document.getElementById('auctions-grid');
    if (!grid) return;

    grid.innerHTML = Array(count).fill().map(() => `
        <div class="glass rounded-2xl overflow-hidden">
            <div class="aspect-[4/3] skeleton"></div>
            <div class="p-4 space-y-3">
                <div class="h-4 skeleton rounded w-3/4"></div>
                <div class="h-3 skeleton rounded w-1/2"></div>
                <div class="h-6 skeleton rounded w-1/3"></div>
            </div>
        </div>
    `).join('');
}

// Prefetch critical resources
function prefetchCriticalResources() {
    const resources = [
        '/api/listings.json'
    ];

    resources.forEach(url => {
        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = url;
        document.head.appendChild(link);
    });
}

// ============================================
// UTILITIES
// ============================================
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

function showToast(message, type = 'info') {
    // Use existing toast function if available
    if (typeof SubastoAlerts?.showToast === 'function') {
        SubastoAlerts.showToast(message, type);
        return;
    }

    // Fallback toast implementation
    const toast = document.createElement('div');
    toast.className = `fixed bottom-24 left-1/2 -translate-x-1/2 z-[200] px-6 py-3 rounded-full shadow-lg font-medium text-sm transform transition-all duration-300 translate-y-10 opacity-0 ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        type === 'warning' ? 'bg-yellow-500 text-black' :
        'bg-blue-500 text-white'
    }`;
    toast.textContent = message;

    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-10', 'opacity-0');
    });

    setTimeout(() => {
        toast.classList.add('translate-y-10', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// EXPORTS
// ============================================
window.SubastoPWA = {
    install: installPWA,
    subscribeToPush,
    scheduleReminder: scheduleAuctionReminder,
    triggerHaptic,
    showSkeleton: showSkeletonGrid,
    showToast,
    get isInstalled() { return PWA.isInstalled; },
    get isStandalone() { return PWA.isStandalone; },
    get isMobile() { return PWA.isMobile; }
};

console.log('[PWA] Module loaded');
