/**
 * Subasto Referral Tracking System
 *
 * Handles:
 * - Detecting ?ref=CODE in URL
 * - Storing referral attribution in localStorage
 * - Sending referral data with API calls
 * - Managing the Share & Earn UI
 *
 * Usage:
 * Include this script in your HTML:
 * <script src="/js/referral.js"></script>
 *
 * The script auto-initializes on DOMContentLoaded.
 */

(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    API_BASE: '/api/v1/referral',
    STORAGE_KEY: 'subasto_referral',
    USER_ID_KEY: 'subasto_user_id',
    ATTRIBUTION_DAYS: 30,
    BASE_URL: 'https://subasto.com.ar',
  };

  // ============================================================================
  // USER ID MANAGEMENT
  // ============================================================================

  /**
   * Get or create a unique user ID for this browser
   */
  function getUserId() {
    let userId = localStorage.getItem(CONFIG.USER_ID_KEY);
    if (!userId) {
      userId = 'u_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 10);
      localStorage.setItem(CONFIG.USER_ID_KEY, userId);
    }
    return userId;
  }

  // ============================================================================
  // REFERRAL STORAGE
  // ============================================================================

  /**
   * Get stored referral data
   */
  function getReferralData() {
    try {
      const data = localStorage.getItem(CONFIG.STORAGE_KEY);
      if (!data) return null;

      const parsed = JSON.parse(data);

      // Check if expired
      if (parsed.expiresAt && Date.now() > parsed.expiresAt) {
        localStorage.removeItem(CONFIG.STORAGE_KEY);
        return null;
      }

      return parsed;
    } catch (e) {
      console.warn('Failed to parse referral data:', e);
      return null;
    }
  }

  /**
   * Store referral data
   */
  function setReferralData(code, referrerName) {
    const data = {
      code: code.toUpperCase(),
      referrerName: referrerName || null,
      attributedAt: Date.now(),
      expiresAt: Date.now() + (CONFIG.ATTRIBUTION_DAYS * 24 * 60 * 60 * 1000),
    };
    localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(data));
    return data;
  }

  /**
   * Get referral code (for sending with API requests)
   */
  function getReferralCode() {
    const data = getReferralData();
    return data ? data.code : null;
  }

  // ============================================================================
  // REFERRAL DETECTION & TRACKING
  // ============================================================================

  /**
   * Check URL for referral code and track it
   */
  async function checkAndTrackReferral() {
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = urlParams.get('ref');

    if (!refCode) return;

    // Already have this referral stored?
    const existing = getReferralData();
    if (existing && existing.code === refCode.toUpperCase()) {
      // Already tracked this referral
      cleanUrl();
      return;
    }

    // Track the referral click
    try {
      const response = await fetch(`${CONFIG.API_BASE}/track`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          code: refCode,
          userId: getUserId(),
          page: window.location.pathname,
          userAgent: navigator.userAgent,
        }),
      });

      const result = await response.json();

      if (result.success && result.attributed) {
        // Store the referral
        setReferralData(refCode, result.referrer);
        console.log(`Referral tracked: ${refCode} (${result.referrer})`);

        // Show toast notification
        showReferralToast(result.referrer);
      }
    } catch (error) {
      console.warn('Failed to track referral:', error);
      // Store locally anyway - we'll try to sync later
      setReferralData(refCode, null);
    }

    // Clean URL (remove ref param)
    cleanUrl();
  }

  /**
   * Remove ref param from URL without reload
   */
  function cleanUrl() {
    const url = new URL(window.location.href);
    url.searchParams.delete('ref');
    window.history.replaceState({}, '', url.toString());
  }

  /**
   * Show a toast notification for referral
   */
  function showReferralToast(referrerName) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-yellow-500/90 text-black px-4 py-3 rounded-lg shadow-lg z-50 transform translate-y-20 opacity-0 transition-all duration-300';
    toast.innerHTML = `
      <div class="flex items-center gap-3">
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
          <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd"/>
        </svg>
        <div>
          <div class="font-semibold">Referido por ${referrerName || 'un amigo'}</div>
          <div class="text-xs opacity-80">Tu referente gana 10% de tus pagos API</div>
        </div>
      </div>
    `;

    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
      toast.classList.remove('translate-y-20', 'opacity-0');
    });

    // Remove after 5 seconds
    setTimeout(() => {
      toast.classList.add('translate-y-20', 'opacity-0');
      setTimeout(() => toast.remove(), 300);
    }, 5000);
  }

  // ============================================================================
  // SHARE & EARN UI
  // ============================================================================

  /**
   * Initialize the Share & Earn section (if present)
   */
  function initShareAndEarnUI() {
    const container = document.getElementById('share-and-earn');
    if (!container) return;

    // Check if user is an affiliate
    const affiliateWallet = localStorage.getItem('subasto_affiliate_wallet');

    if (affiliateWallet) {
      renderAffiliateStats(container, affiliateWallet);
    } else {
      renderJoinProgram(container);
    }
  }

  /**
   * Render "Join the program" UI
   */
  function renderJoinProgram(container) {
    container.innerHTML = `
      <div class="glass rounded-2xl p-6 md:p-8">
        <div class="flex items-center gap-3 mb-6">
          <div class="w-12 h-12 rounded-xl bg-yellow-500/20 flex items-center justify-center">
            <svg class="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <div>
            <h3 class="text-xl font-display font-bold text-white">Comparte y Gana</h3>
            <p class="text-white/60 text-sm">Gana 10% de los pagos API de tus referidos</p>
          </div>
        </div>

        <div class="grid gap-4 mb-6">
          <div class="flex items-center gap-3 text-white/80">
            <div class="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-yellow-500 font-bold text-sm">1</div>
            <span>Conecta tu wallet para recibir pagos</span>
          </div>
          <div class="flex items-center gap-3 text-white/80">
            <div class="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-yellow-500 font-bold text-sm">2</div>
            <span>Obtene tu link de referido unico</span>
          </div>
          <div class="flex items-center gap-3 text-white/80">
            <div class="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-yellow-500 font-bold text-sm">3</div>
            <span>Gana USDC cuando tus referidos paguen</span>
          </div>
        </div>

        <div class="space-y-3">
          <input
            type="text"
            id="affiliate-wallet-input"
            placeholder="Tu wallet (0x...)"
            class="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/40 focus:outline-none focus:border-yellow-500/50"
          >
          <input
            type="text"
            id="affiliate-name-input"
            placeholder="Tu nombre o marca (opcional)"
            class="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/40 focus:outline-none focus:border-yellow-500/50"
            maxlength="30"
          >
          <button
            id="join-affiliate-btn"
            class="w-full py-3 bg-yellow-500 hover:bg-yellow-400 text-black font-semibold rounded-xl transition-colors"
          >
            Unirme al Programa
          </button>
        </div>

        <p class="text-white/40 text-xs mt-4 text-center">
          Minimo $1 USDC para retirar. Pagos en Base network.
        </p>
      </div>
    `;

    // Add event listener
    const joinBtn = document.getElementById('join-affiliate-btn');
    if (joinBtn) {
      joinBtn.addEventListener('click', handleJoinAffiliate);
    }
  }

  /**
   * Handle joining affiliate program
   */
  async function handleJoinAffiliate() {
    const walletInput = document.getElementById('affiliate-wallet-input');
    const nameInput = document.getElementById('affiliate-name-input');
    const joinBtn = document.getElementById('join-affiliate-btn');

    const wallet = walletInput.value.trim();
    const displayName = nameInput.value.trim();

    if (!wallet || !/^0x[a-fA-F0-9]{40}$/.test(wallet)) {
      alert('Ingresa una direccion wallet valida (0x...)');
      return;
    }

    joinBtn.disabled = true;
    joinBtn.textContent = 'Registrando...';

    try {
      const response = await fetch(`${CONFIG.API_BASE}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          wallet,
          displayName: displayName || undefined,
        }),
      });

      const result = await response.json();

      if (result.success) {
        // Store wallet locally
        localStorage.setItem('subasto_affiliate_wallet', wallet);
        localStorage.setItem('subasto_affiliate_code', result.affiliate.referralCode);

        // Re-render with stats
        const container = document.getElementById('share-and-earn');
        renderAffiliateStats(container, wallet);

        // Show success toast
        showSuccessToast('Bienvenido al programa de afiliados!');
      } else {
        alert(result.error || result.message || 'Error al registrarse');
      }
    } catch (error) {
      console.error('Failed to join affiliate program:', error);
      alert('Error de conexion. Intenta de nuevo.');
    } finally {
      joinBtn.disabled = false;
      joinBtn.textContent = 'Unirme al Programa';
    }
  }

  /**
   * Render affiliate stats dashboard
   */
  async function renderAffiliateStats(container, wallet) {
    // Show loading state
    container.innerHTML = `
      <div class="glass rounded-2xl p-6 md:p-8">
        <div class="flex items-center justify-center py-8">
          <div class="animate-spin w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full"></div>
        </div>
      </div>
    `;

    try {
      const response = await fetch(`${CONFIG.API_BASE}/stats?wallet=${encodeURIComponent(wallet)}`);
      const result = await response.json();

      if (!result.success) {
        // Not registered - show join UI
        localStorage.removeItem('subasto_affiliate_wallet');
        renderJoinProgram(container);
        return;
      }

      const { affiliate, stats, recentCommissions } = result;

      container.innerHTML = `
        <div class="glass rounded-2xl p-6 md:p-8">
          <div class="flex items-center justify-between mb-6">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-yellow-500/20 flex items-center justify-center">
                <svg class="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
              </div>
              <div>
                <h3 class="text-xl font-display font-bold text-white">Tu Panel de Afiliado</h3>
                <p class="text-white/60 text-sm">${affiliate.displayName || affiliate.wallet.slice(0, 10) + '...'}</p>
              </div>
            </div>
            <button id="logout-affiliate" class="text-white/40 hover:text-white/60 text-sm">
              Salir
            </button>
          </div>

          <!-- Stats Grid -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white/5 rounded-xl p-4">
              <div class="text-white/60 text-xs uppercase tracking-wider mb-1">Clicks</div>
              <div class="text-2xl font-display font-bold text-white">${stats.totalClicks}</div>
            </div>
            <div class="bg-white/5 rounded-xl p-4">
              <div class="text-white/60 text-xs uppercase tracking-wider mb-1">Conversiones</div>
              <div class="text-2xl font-display font-bold text-white">${stats.totalConversions}</div>
            </div>
            <div class="bg-white/5 rounded-xl p-4">
              <div class="text-white/60 text-xs uppercase tracking-wider mb-1">Ganancias</div>
              <div class="text-2xl font-display font-bold text-yellow-500">${stats.totalEarnings.formatted}</div>
            </div>
            <div class="bg-white/5 rounded-xl p-4">
              <div class="text-white/60 text-xs uppercase tracking-wider mb-1">Conversion</div>
              <div class="text-2xl font-display font-bold text-white">${stats.conversionRate}</div>
            </div>
          </div>

          <!-- Referral Link -->
          <div class="bg-white/5 rounded-xl p-4 mb-6">
            <div class="text-white/60 text-xs uppercase tracking-wider mb-2">Tu Link de Referido</div>
            <div class="flex items-center gap-2">
              <input
                type="text"
                readonly
                value="${affiliate.referralUrl}"
                class="flex-1 px-3 py-2 bg-white/10 border border-white/10 rounded-lg text-white text-sm font-mono"
                id="referral-link-input"
              >
              <button
                id="copy-referral-link"
                class="px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black font-semibold rounded-lg text-sm transition-colors"
              >
                Copiar
              </button>
            </div>
            <div class="flex gap-2 mt-3">
              <button id="share-twitter" class="flex-1 py-2 bg-[#1DA1F2]/20 hover:bg-[#1DA1F2]/30 text-[#1DA1F2] rounded-lg text-sm transition-colors">
                Twitter/X
              </button>
              <button id="share-whatsapp" class="flex-1 py-2 bg-[#25D366]/20 hover:bg-[#25D366]/30 text-[#25D366] rounded-lg text-sm transition-colors">
                WhatsApp
              </button>
              <button id="share-telegram" class="flex-1 py-2 bg-[#0088cc]/20 hover:bg-[#0088cc]/30 text-[#0088cc] rounded-lg text-sm transition-colors">
                Telegram
              </button>
            </div>
          </div>

          <!-- Pending Payout -->
          <div class="bg-gradient-to-r from-yellow-500/20 to-yellow-600/10 rounded-xl p-4 mb-6">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-white/60 text-xs uppercase tracking-wider mb-1">Saldo Pendiente</div>
                <div class="text-3xl font-display font-bold text-yellow-500">${stats.pendingPayout.formatted}</div>
                ${stats.pendingPayout.canWithdraw
                  ? '<div class="text-green-400 text-xs mt-1">Disponible para retirar</div>'
                  : `<div class="text-white/40 text-xs mt-1">Minimo $${stats.pendingPayout.minPayout} para retirar</div>`
                }
              </div>
              <button
                id="request-payout"
                class="px-6 py-3 bg-yellow-500 hover:bg-yellow-400 disabled:bg-white/10 disabled:text-white/40 text-black font-semibold rounded-xl transition-colors"
                ${stats.pendingPayout.canWithdraw ? '' : 'disabled'}
              >
                Retirar
              </button>
            </div>
          </div>

          <!-- Recent Commissions -->
          ${recentCommissions.length > 0 ? `
            <div>
              <div class="text-white/60 text-xs uppercase tracking-wider mb-3">Comisiones Recientes</div>
              <div class="space-y-2 max-h-48 overflow-y-auto">
                ${recentCommissions.map(c => `
                  <div class="flex items-center justify-between py-2 border-b border-white/5">
                    <div class="text-white/60 text-sm">${c.refereeWallet}</div>
                    <div class="text-yellow-500 font-semibold">+$${c.commissionAmount.toFixed(2)}</div>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : `
            <div class="text-center text-white/40 py-4">
              <p>Todavia no tenes comisiones</p>
              <p class="text-sm">Comparte tu link para empezar a ganar!</p>
            </div>
          `}
        </div>
      `;

      // Add event listeners
      setupAffiliateEventListeners(affiliate, wallet);

    } catch (error) {
      console.error('Failed to load affiliate stats:', error);
      container.innerHTML = `
        <div class="glass rounded-2xl p-6 text-center">
          <p class="text-red-400 mb-4">Error al cargar estadisticas</p>
          <button onclick="location.reload()" class="text-yellow-500 hover:underline">Reintentar</button>
        </div>
      `;
    }
  }

  /**
   * Setup event listeners for affiliate dashboard
   */
  function setupAffiliateEventListeners(affiliate, wallet) {
    // Copy link
    const copyBtn = document.getElementById('copy-referral-link');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        const input = document.getElementById('referral-link-input');
        navigator.clipboard.writeText(input.value);
        copyBtn.textContent = 'Copiado!';
        setTimeout(() => copyBtn.textContent = 'Copiar', 2000);
      });
    }

    // Social shares
    const shareText = 'Descubri subastas judiciales en Argentina - activos al 30-70% del valor de mercado!';
    const shareUrl = affiliate.referralUrl;

    document.getElementById('share-twitter')?.addEventListener('click', () => {
      window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`, '_blank');
    });

    document.getElementById('share-whatsapp')?.addEventListener('click', () => {
      window.open(`https://wa.me/?text=${encodeURIComponent(shareText + ' ' + shareUrl)}`, '_blank');
    });

    document.getElementById('share-telegram')?.addEventListener('click', () => {
      window.open(`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`, '_blank');
    });

    // Request payout
    document.getElementById('request-payout')?.addEventListener('click', async () => {
      const btn = document.getElementById('request-payout');
      btn.disabled = true;
      btn.textContent = 'Procesando...';

      try {
        const response = await fetch(`${CONFIG.API_BASE}/stats`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ wallet, action: 'payout' }),
        });

        const result = await response.json();

        if (result.success) {
          showSuccessToast('Solicitud de retiro enviada!');
          // Refresh stats
          const container = document.getElementById('share-and-earn');
          renderAffiliateStats(container, wallet);
        } else {
          alert(result.error || result.message);
          btn.disabled = false;
          btn.textContent = 'Retirar';
        }
      } catch (error) {
        alert('Error al procesar solicitud');
        btn.disabled = false;
        btn.textContent = 'Retirar';
      }
    });

    // Logout
    document.getElementById('logout-affiliate')?.addEventListener('click', () => {
      localStorage.removeItem('subasto_affiliate_wallet');
      localStorage.removeItem('subasto_affiliate_code');
      const container = document.getElementById('share-and-earn');
      renderJoinProgram(container);
    });
  }

  /**
   * Show success toast
   */
  function showSuccessToast(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-green-500/90 text-white px-4 py-3 rounded-lg shadow-lg z-50 transform translate-y-20 opacity-0 transition-all duration-300';
    toast.innerHTML = `
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
        <span>${message}</span>
      </div>
    `;

    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.remove('translate-y-20', 'opacity-0'));
    setTimeout(() => {
      toast.classList.add('translate-y-20', 'opacity-0');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ============================================================================
  // LEADERBOARD
  // ============================================================================

  /**
   * Initialize leaderboard (if present)
   */
  async function initLeaderboard() {
    const container = document.getElementById('referral-leaderboard');
    if (!container) return;

    try {
      const response = await fetch(`${CONFIG.API_BASE}/leaderboard?limit=10`);
      const result = await response.json();

      if (!result.success || result.leaderboard.length === 0) {
        container.innerHTML = `
          <div class="text-center text-white/40 py-8">
            <p>Se el primero en el leaderboard!</p>
            <p class="text-sm">Unete al programa de afiliados arriba.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <div class="glass rounded-2xl overflow-hidden">
          <div class="px-6 py-4 border-b border-white/10">
            <h3 class="font-display font-bold text-white">Top Afiliados</h3>
          </div>
          <div class="divide-y divide-white/5">
            ${result.leaderboard.map((entry, index) => `
              <div class="flex items-center justify-between px-6 py-3 hover:bg-white/5 transition-colors">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
                    index === 0 ? 'bg-yellow-500 text-black' :
                    index === 1 ? 'bg-gray-400 text-black' :
                    index === 2 ? 'bg-amber-700 text-white' :
                    'bg-white/10 text-white/60'
                  }">
                    ${entry.rank}
                  </div>
                  <span class="text-white">${entry.displayName}</span>
                </div>
                <div class="text-right">
                  <div class="text-yellow-500 font-semibold">${entry.earnings.formatted}</div>
                  <div class="text-white/40 text-xs">${entry.conversions} referidos</div>
                </div>
              </div>
            `).join('')}
          </div>
          <div class="px-6 py-4 bg-white/5 text-center">
            <p class="text-white/60 text-sm">
              ${result.programStats.totalReferrals} referidos totales ·
              ${result.programStats.totalCommissionsPaid.formatted} pagados
            </p>
          </div>
        </div>
      `;
    } catch (error) {
      console.error('Failed to load leaderboard:', error);
    }
  }

  // ============================================================================
  // PUBLIC API (for use by other scripts)
  // ============================================================================

  window.SubastoReferral = {
    /**
     * Get the current referral code (for sending with API requests)
     */
    getCode: getReferralCode,

    /**
     * Get the full referral data
     */
    getData: getReferralData,

    /**
     * Get user ID
     */
    getUserId: getUserId,

    /**
     * Check if user was referred
     */
    isReferred: () => !!getReferralData(),

    /**
     * Manually trigger referral check (useful for SPAs)
     */
    checkReferral: checkAndTrackReferral,
  };

  // ============================================================================
  // INITIALIZATION
  // ============================================================================

  function init() {
    // Check for referral in URL
    checkAndTrackReferral();

    // Initialize UI components
    initShareAndEarnUI();
    initLeaderboard();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
