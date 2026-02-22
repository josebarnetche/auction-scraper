/**
 * Subasto Social Sharing Module
 * Handles sharing functionality for auction listings
 * Version: 1.0.0
 */

(function() {
    'use strict';

    // Configuration
    const SHARE_CONFIG = {
        baseUrl: 'https://subasto.com.ar',
        utmSource: 'subasto',
        utmMedium: 'social',
        hashtags: ['SubastaArgentina', 'Oportunidad', 'Subasto'],
        twitterHandle: 'subasto_ar'
    };

    // Category name translations
    const CATEGORY_NAMES = {
        vehicles: 'Vehiculo',
        real_estate: 'Inmueble',
        machinery: 'Maquinaria',
        general_goods: 'Bienes',
        other: 'Producto'
    };

    // Share count storage (simulated - in production would be server-side)
    const shareCountsKey = 'subasto_share_counts';

    // Get share counts from localStorage
    function getShareCounts() {
        try {
            return JSON.parse(localStorage.getItem(shareCountsKey)) || {};
        } catch (e) {
            return {};
        }
    }

    // Increment share count for an auction
    function incrementShareCount(auctionId, platform) {
        const counts = getShareCounts();
        if (!counts[auctionId]) {
            counts[auctionId] = { total: 0, platforms: {} };
        }
        counts[auctionId].total++;
        counts[auctionId].platforms[platform] = (counts[auctionId].platforms[platform] || 0) + 1;
        localStorage.setItem(shareCountsKey, JSON.stringify(counts));
        return counts[auctionId].total;
    }

    // Get total shares for an auction
    function getShareCount(auctionId) {
        const counts = getShareCounts();
        return counts[auctionId]?.total || 0;
    }

    // Generate UTM-tagged URL
    function generateShareUrl(auction, platform, referrer = null) {
        const params = new URLSearchParams({
            utm_source: SHARE_CONFIG.utmSource,
            utm_medium: platform,
            utm_campaign: 'share',
            utm_content: auction.id || auction.title.substring(0, 20).replace(/\s+/g, '_')
        });

        if (referrer) {
            params.append('ref', referrer);
        }

        // Use the source URL directly for now, with UTM params
        const url = new URL(auction.source_url);
        url.searchParams.set('shared_from', 'subasto');

        // For Subasto tracking, we'll use the base URL with auction ID
        const trackingUrl = `${SHARE_CONFIG.baseUrl}/?${params.toString()}#auction-${auction.id || encodeURIComponent(auction.title.substring(0, 30))}`;

        return {
            auctionUrl: auction.source_url,
            trackingUrl: trackingUrl
        };
    }

    // Format price for sharing
    function formatSharePrice(price, currency) {
        if (!price || price === 0) return 'A consultar';

        // Format based on currency
        if (currency === 'USD') {
            return 'USD ' + price.toLocaleString('en-US', { maximumFractionDigits: 0 });
        } else {
            return 'ARS ' + price.toLocaleString('es-AR', { maximumFractionDigits: 0 });
        }
    }

    // Generate share messages for different platforms
    function generateShareMessages(auction, discount) {
        const category = CATEGORY_NAMES[auction.category] || 'Producto';
        const price = formatSharePrice(auction.base_price, auction.currency);
        const title = auction.title.length > 60 ? auction.title.substring(0, 57) + '...' : auction.title;
        const discountText = discount && discount >= 20 ? `${discount}% de descuento` : '';
        const urgencyText = isEndingSoon(auction) ? 'Termina pronto!' : '';

        return {
            // WhatsApp - with emojis and urgency
            whatsapp: [
                discount >= 20 ? `*${discountText}* en ${category}` : `${category} en subasta`,
                '',
                `${title}`,
                '',
                `Precio base: ${price}`,
                urgencyText ? `${urgencyText}` : '',
                '',
                `Ver en Subasto.com.ar`
            ].filter(Boolean).join('\n'),

            // Twitter/X - with hashtags (limited to 280 chars)
            twitter: (() => {
                const base = discount >= 20
                    ? `Encontre un ${category} al ${discount}% de descuento!`
                    : `${category} en subasta:`;
                const hashtags = SHARE_CONFIG.hashtags.map(h => `#${h}`).join(' ');
                const shortTitle = title.length > 80 ? title.substring(0, 77) + '...' : title;
                return `${base} ${shortTitle} - ${price} ${hashtags}`;
            })(),

            // Facebook - clean and professional
            facebook: discount >= 20
                ? `Encontre este ${category} con ${discount}% de descuento! ${title} - ${price}`
                : `${category} en subasta: ${title} - ${price}`,

            // Telegram - with emojis
            telegram: [
                discount >= 20 ? `*${discountText}*` : `Subasta de ${category}`,
                '',
                title,
                '',
                `Precio: ${price}`,
                urgencyText ? urgencyText : '',
                '',
                'Ver en Subasto.com.ar'
            ].filter(Boolean).join('\n'),

            // Email subject and body
            email: {
                subject: discount >= 20
                    ? `${category} al ${discount}% de descuento - Subasto.com.ar`
                    : `${category} en subasta - Subasto.com.ar`,
                body: [
                    'Hola!',
                    '',
                    'Te comparto esta oportunidad que encontre en Subasto.com.ar:',
                    '',
                    title,
                    '',
                    `Categoria: ${category}`,
                    `Precio base: ${price}`,
                    discount >= 20 ? `Descuento estimado: ${discount}%` : '',
                    '',
                    'Podes ver mas detalles en el link.',
                    '',
                    'Saludos!'
                ].filter(Boolean).join('\n')
            },

            // Generic/Copy
            generic: discount >= 20
                ? `${category} al ${discount}% de descuento! ${title} - ${price} - Subasto.com.ar`
                : `${category} en subasta: ${title} - ${price} - Subasto.com.ar`
        };
    }

    // Check if auction is ending soon (within 24 hours)
    function isEndingSoon(auction) {
        if (!auction.ends_at) return false;
        const endDate = new Date(auction.ends_at);
        const now = new Date();
        const hoursUntilEnd = (endDate - now) / (1000 * 60 * 60);
        return hoursUntilEnd > 0 && hoursUntilEnd <= 24;
    }

    // Share to WhatsApp
    function shareToWhatsApp(auction, discount) {
        const messages = generateShareMessages(auction, discount);
        const urls = generateShareUrl(auction, 'whatsapp');
        const text = encodeURIComponent(messages.whatsapp + '\n\n' + urls.auctionUrl);

        incrementShareCount(auction.id || auction.title, 'whatsapp');
        trackShare(auction, 'whatsapp');

        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        const whatsappUrl = isMobile
            ? `whatsapp://send?text=${text}`
            : `https://web.whatsapp.com/send?text=${text}`;

        window.open(whatsappUrl, '_blank');
    }

    // Share to Twitter/X
    function shareToTwitter(auction, discount) {
        const messages = generateShareMessages(auction, discount);
        const urls = generateShareUrl(auction, 'twitter');

        incrementShareCount(auction.id || auction.title, 'twitter');
        trackShare(auction, 'twitter');

        const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(messages.twitter)}&url=${encodeURIComponent(urls.auctionUrl)}`;
        window.open(tweetUrl, '_blank', 'width=550,height=420');
    }

    // Share to Facebook
    function shareToFacebook(auction, discount) {
        const messages = generateShareMessages(auction, discount);
        const urls = generateShareUrl(auction, 'facebook');

        incrementShareCount(auction.id || auction.title, 'facebook');
        trackShare(auction, 'facebook');

        const fbUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(urls.auctionUrl)}&quote=${encodeURIComponent(messages.facebook)}`;
        window.open(fbUrl, '_blank', 'width=550,height=420');
    }

    // Share to Telegram
    function shareToTelegram(auction, discount) {
        const messages = generateShareMessages(auction, discount);
        const urls = generateShareUrl(auction, 'telegram');

        incrementShareCount(auction.id || auction.title, 'telegram');
        trackShare(auction, 'telegram');

        const telegramUrl = `https://t.me/share/url?url=${encodeURIComponent(urls.auctionUrl)}&text=${encodeURIComponent(messages.telegram)}`;
        window.open(telegramUrl, '_blank', 'width=550,height=420');
    }

    // Share via Email
    function shareToEmail(auction, discount) {
        const messages = generateShareMessages(auction, discount);
        const urls = generateShareUrl(auction, 'email');

        incrementShareCount(auction.id || auction.title, 'email');
        trackShare(auction, 'email');

        const mailtoUrl = `mailto:?subject=${encodeURIComponent(messages.email.subject)}&body=${encodeURIComponent(messages.email.body + '\n\n' + urls.auctionUrl)}`;
        window.location.href = mailtoUrl;
    }

    // Copy link to clipboard
    async function copyShareLink(auction, discount, buttonElement) {
        const messages = generateShareMessages(auction, discount);
        const urls = generateShareUrl(auction, 'copy');
        const textToCopy = messages.generic + '\n' + urls.auctionUrl;

        try {
            await navigator.clipboard.writeText(textToCopy);

            incrementShareCount(auction.id || auction.title, 'copy');
            trackShare(auction, 'copy');

            // Show success feedback
            if (buttonElement) {
                const originalContent = buttonElement.innerHTML;
                buttonElement.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                    <span>Copiado!</span>
                `;
                buttonElement.classList.add('bg-green-500/20', 'text-green-400');

                setTimeout(() => {
                    buttonElement.innerHTML = originalContent;
                    buttonElement.classList.remove('bg-green-500/20', 'text-green-400');
                }, 2000);
            }

            return true;
        } catch (err) {
            console.error('Failed to copy:', err);
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = textToCopy;
            textArea.style.position = 'fixed';
            textArea.style.left = '-9999px';
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            return true;
        }
    }

    // Track share event with Google Analytics
    function trackShare(auction, platform) {
        if (typeof gtag === 'function') {
            gtag('event', 'share', {
                method: platform,
                content_type: 'auction',
                item_id: auction.id || auction.title.substring(0, 30),
                content_category: auction.category
            });
        }
    }

    // Generate share button HTML for a card
    function generateShareButton(auctionIndex) {
        return `
            <button
                type="button"
                onclick="event.preventDefault(); event.stopPropagation(); SubastoShare.openShareModal(${auctionIndex});"
                class="share-btn absolute bottom-3 right-3 w-8 h-8 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center text-white/60 hover:text-white hover:bg-yellow-500/80 transition-all opacity-0 group-hover:opacity-100 z-10"
                title="Compartir"
            >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/>
                </svg>
            </button>
        `;
    }

    // Generate share modal HTML
    function generateShareModalHTML() {
        return `
            <div id="share-modal" class="fixed inset-0 z-[100] hidden">
                <!-- Backdrop -->
                <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" onclick="SubastoShare.closeShareModal()"></div>

                <!-- Modal Content -->
                <div class="absolute inset-0 flex items-center justify-center p-4 pointer-events-none">
                    <div class="share-modal-content bg-[#1a1a1a] rounded-2xl p-6 max-w-md w-full border border-white/10 pointer-events-auto transform scale-95 opacity-0 transition-all duration-200">
                        <!-- Header -->
                        <div class="flex items-center justify-between mb-6">
                            <h3 class="text-lg font-display font-medium text-white">Compartir subasta</h3>
                            <button onclick="SubastoShare.closeShareModal()" class="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </div>

                        <!-- Auction Preview -->
                        <div id="share-modal-preview" class="glass rounded-xl p-4 mb-6">
                            <!-- Populated dynamically -->
                        </div>

                        <!-- Share Buttons Grid -->
                        <div class="grid grid-cols-5 gap-3 mb-6">
                            <!-- WhatsApp -->
                            <button id="share-whatsapp" class="share-platform-btn flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-white/10 transition-colors group" title="WhatsApp">
                                <div class="w-12 h-12 rounded-full bg-[#25D366]/20 flex items-center justify-center group-hover:bg-[#25D366]/30 transition-colors">
                                    <svg class="w-6 h-6 text-[#25D366]" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                                    </svg>
                                </div>
                                <span class="text-[10px] text-white/60">WhatsApp</span>
                            </button>

                            <!-- Twitter/X -->
                            <button id="share-twitter" class="share-platform-btn flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-white/10 transition-colors group" title="X (Twitter)">
                                <div class="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center group-hover:bg-white/20 transition-colors">
                                    <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                                    </svg>
                                </div>
                                <span class="text-[10px] text-white/60">X</span>
                            </button>

                            <!-- Facebook -->
                            <button id="share-facebook" class="share-platform-btn flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-white/10 transition-colors group" title="Facebook">
                                <div class="w-12 h-12 rounded-full bg-[#1877F2]/20 flex items-center justify-center group-hover:bg-[#1877F2]/30 transition-colors">
                                    <svg class="w-6 h-6 text-[#1877F2]" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                                    </svg>
                                </div>
                                <span class="text-[10px] text-white/60">Facebook</span>
                            </button>

                            <!-- Telegram -->
                            <button id="share-telegram" class="share-platform-btn flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-white/10 transition-colors group" title="Telegram">
                                <div class="w-12 h-12 rounded-full bg-[#0088cc]/20 flex items-center justify-center group-hover:bg-[#0088cc]/30 transition-colors">
                                    <svg class="w-6 h-6 text-[#0088cc]" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                                    </svg>
                                </div>
                                <span class="text-[10px] text-white/60">Telegram</span>
                            </button>

                            <!-- Email -->
                            <button id="share-email" class="share-platform-btn flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-white/10 transition-colors group" title="Email">
                                <div class="w-12 h-12 rounded-full bg-yellow-500/20 flex items-center justify-center group-hover:bg-yellow-500/30 transition-colors">
                                    <svg class="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                                    </svg>
                                </div>
                                <span class="text-[10px] text-white/60">Email</span>
                            </button>
                        </div>

                        <!-- Copy Link Section -->
                        <div class="border-t border-white/10 pt-4">
                            <button id="share-copy-link" class="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-white/5 hover:bg-white/10 text-white/80 hover:text-white transition-all">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                                </svg>
                                <span>Copiar enlace</span>
                            </button>
                        </div>

                        <!-- Social Proof -->
                        <div id="share-social-proof" class="mt-4 text-center hidden">
                            <span class="text-xs text-white/40">
                                <span id="share-count-display">0</span> personas compartieron esta subasta
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // Current auction being shared
    let currentShareAuction = null;
    let currentShareDiscount = null;

    // Open share modal
    function openShareModal(auctionIndex) {
        // Get auction from the filtered list (used by main rendering)
        const auction = window.filteredAuctions?.[auctionIndex] || window.allAuctions?.[auctionIndex];
        if (!auction) {
            console.error('Auction not found at index:', auctionIndex);
            return;
        }

        currentShareAuction = auction;

        // Calculate discount if available
        currentShareDiscount = null;
        if (typeof window.calculateDiscount === 'function') {
            currentShareDiscount = window.calculateDiscount(auction);
        } else if (auction.market_data?.discount_percent) {
            currentShareDiscount = Math.round(auction.market_data.discount_percent);
        }

        // Update modal preview
        updateShareModalPreview(auction, currentShareDiscount);

        // Update social proof
        const shareCount = getShareCount(auction.id || auction.title);
        const proofElement = document.getElementById('share-social-proof');
        const countDisplay = document.getElementById('share-count-display');
        if (shareCount > 0) {
            countDisplay.textContent = shareCount;
            proofElement.classList.remove('hidden');
        } else {
            proofElement.classList.add('hidden');
        }

        // Wire up share buttons
        document.getElementById('share-whatsapp').onclick = () => shareToWhatsApp(auction, currentShareDiscount);
        document.getElementById('share-twitter').onclick = () => shareToTwitter(auction, currentShareDiscount);
        document.getElementById('share-facebook').onclick = () => shareToFacebook(auction, currentShareDiscount);
        document.getElementById('share-telegram').onclick = () => shareToTelegram(auction, currentShareDiscount);
        document.getElementById('share-email').onclick = () => shareToEmail(auction, currentShareDiscount);
        document.getElementById('share-copy-link').onclick = function() {
            copyShareLink(auction, currentShareDiscount, this);
        };

        // Show modal with animation
        const modal = document.getElementById('share-modal');
        const content = modal.querySelector('.share-modal-content');
        modal.classList.remove('hidden');

        requestAnimationFrame(() => {
            content.classList.remove('scale-95', 'opacity-0');
            content.classList.add('scale-100', 'opacity-100');
        });

        // Track modal open
        trackShare(auction, 'modal_open');
    }

    // Update share modal preview
    function updateShareModalPreview(auction, discount) {
        const preview = document.getElementById('share-modal-preview');
        const imageUrl = auction.images?.[0] || '';
        const price = formatSharePrice(auction.base_price, auction.currency);
        const category = CATEGORY_NAMES[auction.category] || 'Producto';

        preview.innerHTML = `
            <div class="flex gap-4">
                ${imageUrl ? `
                    <div class="w-20 h-20 rounded-lg overflow-hidden flex-shrink-0 bg-white/5">
                        <img src="${imageUrl}" alt="" class="w-full h-full object-cover" onerror="this.style.display='none'">
                    </div>
                ` : ''}
                <div class="flex-1 min-w-0">
                    <h4 class="text-white font-medium text-sm mb-2 line-clamp-2">${auction.title}</h4>
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="category-badge category-${auction.category}">${category}</span>
                        ${discount >= 20 ? `<span class="bg-green-500/20 text-green-400 text-[10px] px-2 py-0.5 rounded-full">-${discount}%</span>` : ''}
                    </div>
                    <div class="mt-2 text-yellow-500 font-display font-semibold">${price}</div>
                </div>
            </div>
        `;
    }

    // Close share modal
    function closeShareModal() {
        const modal = document.getElementById('share-modal');
        const content = modal.querySelector('.share-modal-content');

        content.classList.remove('scale-100', 'opacity-100');
        content.classList.add('scale-95', 'opacity-0');

        setTimeout(() => {
            modal.classList.add('hidden');
        }, 200);

        currentShareAuction = null;
        currentShareDiscount = null;
    }

    // Initialize share module
    function init() {
        // Inject modal into page if not exists
        if (!document.getElementById('share-modal')) {
            document.body.insertAdjacentHTML('beforeend', generateShareModalHTML());
        }

        // Add keyboard listener for ESC
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !document.getElementById('share-modal').classList.contains('hidden')) {
                closeShareModal();
            }
        });

        console.log('SubastoShare module initialized');
    }

    // Generate shareable image URL (uses existing images or generates a card)
    function getShareableImageUrl(auction) {
        // For now, use the first auction image or the og-image
        if (auction.images && auction.images.length > 0) {
            return auction.images[0];
        }
        return `${SHARE_CONFIG.baseUrl}/og-image.png`;
    }

    // Web Share API (for native mobile sharing)
    async function nativeShare(auction, discount) {
        if (!navigator.share) {
            // Fall back to modal
            return false;
        }

        const messages = generateShareMessages(auction, discount);
        const urls = generateShareUrl(auction, 'native');

        try {
            await navigator.share({
                title: auction.title,
                text: messages.generic,
                url: urls.auctionUrl
            });

            incrementShareCount(auction.id || auction.title, 'native');
            trackShare(auction, 'native');
            return true;
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('Native share failed:', err);
            }
            return false;
        }
    }

    // Quick share button (tries native first, then opens modal)
    async function quickShare(auctionIndex) {
        const auction = window.filteredAuctions?.[auctionIndex] || window.allAuctions?.[auctionIndex];
        if (!auction) return;

        let discount = null;
        if (typeof window.calculateDiscount === 'function') {
            discount = window.calculateDiscount(auction);
        }

        // Try native share on mobile
        const shared = await nativeShare(auction, discount);
        if (!shared) {
            // Fall back to modal
            openShareModal(auctionIndex);
        }
    }

    // Expose public API
    window.SubastoShare = {
        init,
        openShareModal,
        closeShareModal,
        quickShare,
        shareToWhatsApp,
        shareToTwitter,
        shareToFacebook,
        shareToTelegram,
        shareToEmail,
        copyShareLink,
        generateShareButton,
        getShareCount,
        getShareableImageUrl
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
