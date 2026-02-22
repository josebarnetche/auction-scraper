/**
 * Subasto.com.ar Internationalization (i18n) System
 * Supports: Spanish (es), English (en), Portuguese (pt)
 *
 * Features:
 * - Auto-detect browser language
 * - URL parameter support (?lang=en)
 * - localStorage persistence
 * - Dynamic content translation
 * - Browser Translation API for listing titles
 * - SEO-friendly hreflang tags
 */

const I18n = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        defaultLang: 'es',
        supportedLangs: ['es', 'en', 'pt'],
        storageKey: 'subasto_language',
        urlParam: 'lang',
        localesPath: '/locales/'
    };

    // Language display names
    const LANG_NAMES = {
        es: { native: 'Espanol', flag: 'AR' },
        en: { native: 'English', flag: 'US' },
        pt: { native: 'Portugues', flag: 'BR' }
    };

    // State
    let currentLang = CONFIG.defaultLang;
    let translations = {};
    let isInitialized = false;
    let onLanguageChangeCallbacks = [];

    /**
     * Get nested translation by dot notation key
     * @param {string} key - Dot notation key (e.g., 'nav.auctions')
     * @param {object} replacements - Optional replacements for placeholders
     * @returns {string} Translated string or key if not found
     */
    function t(key, replacements = {}) {
        const keys = key.split('.');
        let value = translations[currentLang];

        for (const k of keys) {
            if (value && typeof value === 'object' && k in value) {
                value = value[k];
            } else {
                console.warn(`[i18n] Missing translation: ${key} for language: ${currentLang}`);
                return key;
            }
        }

        // Handle array values (e.g., weekdays)
        if (Array.isArray(value)) {
            return value;
        }

        // Replace placeholders like {count}
        if (typeof value === 'string') {
            return value.replace(/\{(\w+)\}/g, (match, placeholder) => {
                return replacements[placeholder] !== undefined ? replacements[placeholder] : match;
            });
        }

        return value;
    }

    /**
     * Detect user's preferred language
     * Priority: URL param > localStorage > browser language > default
     * @returns {string} Language code
     */
    function detectLanguage() {
        // 1. Check URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get(CONFIG.urlParam);
        if (urlLang && CONFIG.supportedLangs.includes(urlLang)) {
            return urlLang;
        }

        // 2. Check localStorage
        const storedLang = localStorage.getItem(CONFIG.storageKey);
        if (storedLang && CONFIG.supportedLangs.includes(storedLang)) {
            return storedLang;
        }

        // 3. Check browser language
        const browserLangs = navigator.languages || [navigator.language || navigator.userLanguage];
        for (const lang of browserLangs) {
            const shortLang = lang.split('-')[0].toLowerCase();
            if (CONFIG.supportedLangs.includes(shortLang)) {
                return shortLang;
            }
        }

        // 4. Default
        return CONFIG.defaultLang;
    }

    /**
     * Load translations for a language
     * @param {string} lang - Language code
     * @returns {Promise<object>} Translations object
     */
    async function loadTranslations(lang) {
        if (translations[lang]) {
            return translations[lang];
        }

        try {
            const response = await fetch(`${CONFIG.localesPath}${lang}.json?v=${Date.now()}`);
            if (!response.ok) {
                throw new Error(`Failed to load ${lang} translations`);
            }
            translations[lang] = await response.json();
            return translations[lang];
        } catch (error) {
            console.error(`[i18n] Error loading translations for ${lang}:`, error);
            // Fallback to default language
            if (lang !== CONFIG.defaultLang) {
                return loadTranslations(CONFIG.defaultLang);
            }
            return {};
        }
    }

    /**
     * Set the current language
     * @param {string} lang - Language code
     * @param {boolean} reload - Whether to reload page (for SEO)
     */
    async function setLanguage(lang, reload = false) {
        if (!CONFIG.supportedLangs.includes(lang)) {
            console.warn(`[i18n] Unsupported language: ${lang}`);
            return;
        }

        // Load translations if not cached
        await loadTranslations(lang);

        currentLang = lang;
        localStorage.setItem(CONFIG.storageKey, lang);

        // Update HTML lang attribute
        document.documentElement.lang = lang;

        // Update URL without reload
        const url = new URL(window.location);
        if (lang !== CONFIG.defaultLang) {
            url.searchParams.set(CONFIG.urlParam, lang);
        } else {
            url.searchParams.delete(CONFIG.urlParam);
        }
        window.history.replaceState({}, '', url);

        // Update meta tags
        updateMetaTags();

        // Update hreflang tags
        updateHreflangTags();

        // Update all translatable elements
        translatePage();

        // Notify callbacks
        onLanguageChangeCallbacks.forEach(cb => cb(lang));

        if (reload) {
            window.location.reload();
        }
    }

    /**
     * Get current language
     * @returns {string} Current language code
     */
    function getLanguage() {
        return currentLang;
    }

    /**
     * Get all supported languages
     * @returns {Array} Array of language codes
     */
    function getSupportedLanguages() {
        return CONFIG.supportedLangs.map(code => ({
            code,
            name: LANG_NAMES[code].native,
            flag: LANG_NAMES[code].flag,
            isCurrent: code === currentLang
        }));
    }

    /**
     * Update meta tags for SEO
     */
    function updateMetaTags() {
        const meta = translations[currentLang]?.meta;
        if (!meta) return;

        // Title
        if (meta.title) {
            document.title = meta.title;
        }

        // Meta description
        const descMeta = document.querySelector('meta[name="description"]');
        if (descMeta && meta.description) {
            descMeta.content = meta.description;
        }

        // Open Graph
        const ogTitle = document.querySelector('meta[property="og:title"]');
        if (ogTitle && meta.title) {
            ogTitle.content = meta.title;
        }

        const ogDesc = document.querySelector('meta[property="og:description"]');
        if (ogDesc && meta.ogDescription) {
            ogDesc.content = meta.ogDescription;
        }

        const ogLocale = document.querySelector('meta[property="og:locale"]');
        if (ogLocale) {
            const localeMap = { es: 'es_AR', en: 'en_US', pt: 'pt_BR' };
            ogLocale.content = localeMap[currentLang] || 'es_AR';
        }

        // Twitter
        const twitterTitle = document.querySelector('meta[name="twitter:title"]');
        if (twitterTitle && meta.title) {
            twitterTitle.content = meta.title;
        }

        const twitterDesc = document.querySelector('meta[name="twitter:description"]');
        if (twitterDesc && meta.twitterDescription) {
            twitterDesc.content = meta.twitterDescription;
        }
    }

    /**
     * Update hreflang tags for SEO
     */
    function updateHreflangTags() {
        // Remove existing hreflang tags
        document.querySelectorAll('link[hreflang]').forEach(el => el.remove());

        const head = document.head;
        const baseUrl = window.location.origin + window.location.pathname;

        // Add hreflang for each supported language
        CONFIG.supportedLangs.forEach(lang => {
            const link = document.createElement('link');
            link.rel = 'alternate';
            link.hreflang = lang === 'es' ? 'es-AR' : (lang === 'pt' ? 'pt-BR' : 'en');
            link.href = lang === CONFIG.defaultLang ? baseUrl : `${baseUrl}?lang=${lang}`;
            head.appendChild(link);
        });

        // Add x-default
        const xDefault = document.createElement('link');
        xDefault.rel = 'alternate';
        xDefault.hreflang = 'x-default';
        xDefault.href = baseUrl;
        head.appendChild(xDefault);
    }

    /**
     * Translate all elements with data-i18n attribute
     */
    function translatePage() {
        // Elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = t(key);

            if (typeof translation === 'string') {
                // Check for specific attribute translations
                const attr = el.getAttribute('data-i18n-attr');
                if (attr) {
                    el.setAttribute(attr, translation);
                } else {
                    el.textContent = translation;
                }
            }
        });

        // Elements with data-i18n-placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = t(key);
        });

        // Elements with data-i18n-title
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.title = t(key);
        });

        // Elements with data-i18n-html (for HTML content)
        document.querySelectorAll('[data-i18n-html]').forEach(el => {
            const key = el.getAttribute('data-i18n-html');
            el.innerHTML = t(key);
        });

        // Update language selector
        updateLanguageSelector();
    }

    /**
     * Update the language selector dropdown
     */
    function updateLanguageSelector() {
        const selector = document.getElementById('language-selector');
        if (!selector) return;

        const currentDisplay = selector.querySelector('.current-lang');
        if (currentDisplay) {
            currentDisplay.textContent = currentLang.toUpperCase();
        }

        // Update active state in dropdown
        selector.querySelectorAll('[data-lang]').forEach(btn => {
            const lang = btn.getAttribute('data-lang');
            if (lang === currentLang) {
                btn.classList.remove('text-white/70');
                btn.classList.add('text-yellow-400');
            } else {
                btn.classList.remove('text-yellow-400');
                btn.classList.add('text-white/70');
            }
        });

        // Close dropdown after selection
        const dropdown = document.getElementById('language-dropdown');
        if (dropdown) {
            dropdown.classList.add('hidden');
        }
    }

    /**
     * Create language selector HTML
     * @returns {string} HTML string for language selector
     */
    function createLanguageSelector() {
        return `
            <div id="language-selector" class="relative">
                <button onclick="I18n.toggleSelector()"
                        class="flex items-center gap-2 px-3 py-2 rounded-full glass text-white/70 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/>
                    </svg>
                    <span class="current-lang text-xs uppercase tracking-wider">${LANG_NAMES[currentLang].native}</span>
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                    </svg>
                </button>
                <div id="language-dropdown" class="hidden absolute top-full right-0 mt-2 glass rounded-xl overflow-hidden min-w-[140px] z-50">
                    ${CONFIG.supportedLangs.map(lang => `
                        <button data-lang="${lang}"
                                onclick="I18n.setLanguage('${lang}')"
                                class="w-full px-4 py-2 text-left text-sm hover:bg-white/10 transition-colors flex items-center gap-2 ${lang === currentLang ? 'text-yellow-400' : 'text-white/70'}">
                            <span class="text-xs">${getFlagEmoji(LANG_NAMES[lang].flag)}</span>
                            <span>${LANG_NAMES[lang].native}</span>
                            ${lang === currentLang ? '<svg class="w-4 h-4 ml-auto" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>' : ''}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Get flag emoji from country code
     * @param {string} countryCode - 2-letter country code
     * @returns {string} Flag emoji
     */
    function getFlagEmoji(countryCode) {
        const codePoints = countryCode
            .toUpperCase()
            .split('')
            .map(char => 127397 + char.charCodeAt(0));
        return String.fromCodePoint(...codePoints);
    }

    /**
     * Toggle language selector dropdown
     */
    function toggleSelector() {
        const dropdown = document.getElementById('language-dropdown');
        if (dropdown) {
            dropdown.classList.toggle('hidden');
        }
    }

    /**
     * Close dropdown when clicking outside
     */
    function setupDropdownClose() {
        document.addEventListener('click', (e) => {
            const selector = document.getElementById('language-selector');
            const dropdown = document.getElementById('language-dropdown');
            if (selector && dropdown && !selector.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });
    }

    /**
     * Translate text using browser's Translation API
     * Falls back to showing original if not supported
     * @param {string} text - Text to translate
     * @param {string} targetLang - Target language code
     * @returns {Promise<string>} Translated text
     */
    async function translateText(text, targetLang = null) {
        targetLang = targetLang || currentLang;

        // If target is Spanish (source language), return original
        if (targetLang === 'es') {
            return text;
        }

        // Check for browser Translation API support
        if ('translation' in self && 'createTranslator' in self.translation) {
            try {
                const translator = await self.translation.createTranslator({
                    sourceLanguage: 'es',
                    targetLanguage: targetLang
                });
                return await translator.translate(text);
            } catch (error) {
                console.warn('[i18n] Browser translation failed:', error);
            }
        }

        // Fallback: Use a simple dictionary for common auction terms
        const commonTerms = {
            en: {
                'vehiculos': 'vehicles',
                'inmuebles': 'real estate',
                'maquinaria': 'machinery',
                'departamento': 'apartment',
                'casa': 'house',
                'auto': 'car',
                'camion': 'truck',
                'terreno': 'land',
                'campo': 'field',
                'oficina': 'office'
            },
            pt: {
                'vehiculos': 'veiculos',
                'inmuebles': 'imoveis',
                'maquinaria': 'maquinario',
                'departamento': 'apartamento',
                'casa': 'casa',
                'auto': 'carro',
                'camion': 'caminhao',
                'terreno': 'terreno',
                'campo': 'campo',
                'oficina': 'escritorio'
            }
        };

        // Return original text with note that translation is not available
        return text;
    }

    /**
     * Create a translate button for auction titles
     * @param {string} originalText - Original text in Spanish
     * @param {HTMLElement} targetElement - Element to update with translation
     * @returns {string} HTML for translate button
     */
    function createTranslateButton(originalText, elementId) {
        if (currentLang === 'es') return '';

        return `
            <button onclick="I18n.translateElement('${elementId}', '${encodeURIComponent(originalText)}')"
                    class="translate-btn text-[10px] text-blue-400 hover:text-blue-300 ml-2 flex items-center gap-1"
                    data-original="${encodeURIComponent(originalText)}"
                    data-translated="false">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"/>
                </svg>
                <span data-i18n="common.translate">${t('common.translate')}</span>
            </button>
        `;
    }

    /**
     * Translate a specific element
     * @param {string} elementId - Element ID
     * @param {string} encodedOriginal - URL-encoded original text
     */
    async function translateElement(elementId, encodedOriginal) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const btn = element.parentElement?.querySelector('.translate-btn');
        const originalText = decodeURIComponent(encodedOriginal);
        const isTranslated = btn?.getAttribute('data-translated') === 'true';

        if (isTranslated) {
            // Show original
            element.textContent = originalText;
            if (btn) {
                btn.setAttribute('data-translated', 'false');
                const btnText = btn.querySelector('span');
                if (btnText) btnText.textContent = t('common.translate');
            }
        } else {
            // Translate
            if (btn) {
                const btnText = btn.querySelector('span');
                if (btnText) btnText.textContent = t('common.translating');
            }

            const translated = await translateText(originalText);

            if (translated !== originalText) {
                element.textContent = translated;
                if (btn) {
                    btn.setAttribute('data-translated', 'true');
                    const btnText = btn.querySelector('span');
                    if (btnText) btnText.textContent = t('common.showOriginal');
                }
            } else {
                // Translation not available
                if (btn) {
                    const btnText = btn.querySelector('span');
                    if (btnText) btnText.textContent = t('common.translationError');
                    setTimeout(() => {
                        if (btnText) btnText.textContent = t('common.translate');
                    }, 2000);
                }
            }
        }
    }

    /**
     * Register callback for language changes
     * @param {Function} callback - Callback function receiving new language code
     */
    function onLanguageChange(callback) {
        if (typeof callback === 'function') {
            onLanguageChangeCallbacks.push(callback);
        }
    }

    /**
     * Inject language selector into the page
     */
    function injectLanguageSelector() {
        // Find the currency selector container
        const currencySelector = document.querySelector('.currency-btn')?.parentElement;
        if (!currencySelector) {
            console.warn('[i18n] Currency selector not found, cannot inject language selector');
            return;
        }

        // Create language selector container
        const langContainer = document.createElement('div');
        langContainer.id = 'language-selector';
        langContainer.className = 'relative';
        langContainer.innerHTML = `
            <button onclick="I18n.toggleSelector()" class="flex items-center gap-1 px-2 sm:px-3 py-1 rounded-full bg-black/30 border border-white/10 text-white/70 hover:text-white transition-colors">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/>
                </svg>
                <span class="current-lang text-[10px] sm:text-xs uppercase tracking-wider hidden sm:inline">${currentLang.toUpperCase()}</span>
                <svg class="w-2.5 h-2.5 hidden sm:block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                </svg>
            </button>
            <div id="language-dropdown" class="hidden absolute top-full right-0 mt-2 glass rounded-xl overflow-hidden min-w-[120px] z-50">
                <button data-lang="es" onclick="I18n.setLanguage('es')" class="lang-option w-full px-3 py-2 text-left text-xs hover:bg-white/10 transition-colors flex items-center gap-2 ${currentLang === 'es' ? 'text-yellow-400' : 'text-white/70'}">
                    <span>ES</span>
                    <span class="text-white/60">Espanol</span>
                </button>
                <button data-lang="en" onclick="I18n.setLanguage('en')" class="lang-option w-full px-3 py-2 text-left text-xs hover:bg-white/10 transition-colors flex items-center gap-2 ${currentLang === 'en' ? 'text-yellow-400' : 'text-white/70'}">
                    <span>EN</span>
                    <span class="text-white/60">English</span>
                </button>
                <button data-lang="pt" onclick="I18n.setLanguage('pt')" class="lang-option w-full px-3 py-2 text-left text-xs hover:bg-white/10 transition-colors flex items-center gap-2 ${currentLang === 'pt' ? 'text-yellow-400' : 'text-white/70'}">
                    <span>PT</span>
                    <span class="text-white/60">Portugues</span>
                </button>
            </div>
        `;

        // Insert after currency selector
        currencySelector.parentElement.insertBefore(langContainer, currencySelector.nextSibling);
    }

    /**
     * Text content mapping for automatic translation
     * Maps original text to translation keys
     */
    const TEXT_MAPPINGS = {
        // Navigation
        'Auctions': 'nav.auctions',
        'Calendar': 'nav.calendar',
        'Dashboard': 'nav.dashboard',
        'Sources': 'nav.sources',
        'API': 'nav.api',
        'Compartir': 'nav.share',
        'Star': 'nav.star',
        'Live': 'common.live',

        // Hero section
        'Live Auctions': 'hero.liveAuctions',
        'Sources': 'hero.sources',
        'Explore Auctions': 'hero.explore',

        // Dashboard
        'Total Auctions': 'dashboard.totalAuctions',
        'Vehicles': 'dashboard.vehicles',
        'Real Estate': 'dashboard.realEstate',
        'Machinery': 'dashboard.machinery',
        'General Goods': 'dashboard.generalGoods',
        'Auctions by Source': 'dashboard.auctionsBySource',
        'Category Distribution': 'dashboard.categoryDistribution',

        // Features
        'Features': 'features.title',
        'Why use Subasto.com.ar': 'features.subtitle',
        'Real-Time Data': 'features.realTimeData',
        'Smart Search': 'features.smartSearch',
        'Price Comparison': 'features.priceComparison',
        'Auction Calendar': 'features.auctionCalendar',

        // Auctions
        'Live Auctions': 'auctions.title',
        'Update': 'auctions.update',
        'Search': 'auctions.search',
        'Price Range': 'auctions.priceRange',
        'No limit': 'auctions.noLimit',
        'Source': 'auctions.source',
        'All Sources': 'auctions.allSources',
        'Location': 'auctions.location',
        'All Locations': 'auctions.allLocations',
        'Sort By': 'auctions.sortBy',
        'Recommended': 'auctions.recommended',
        'Ending Soon': 'auctions.endingSoon',
        'Best Deals': 'auctions.bestDeals',
        'Price: Low to High': 'auctions.priceLowHigh',
        'Price: High to Low': 'auctions.priceHighLow',
        'Newest First': 'auctions.newestFirst',
        'Category:': 'auctions.category',
        'All': 'auctions.all',
        'results': 'auctions.results',
        'Load More Auctions': 'auctions.loadMore',

        // Opportunities
        'Top Opportunities': 'opportunities.title',

        // Sources section
        'Monitored Sources': 'sources.title',
        'Judicial Auctions': 'sources.judicialAuctions',
        'Private Auctions': 'sources.privateAuctions',
        'Daily Updates': 'sources.dailyUpdates',

        // API section
        'API for Agents & Developers': 'api.title',
        'Pricing': 'api.pricing',
        'How It Works': 'api.howItWorks',
        'Technical Details': 'api.technicalDetails',
        'FREE': 'api.free',

        // Footer
        'Support this project': 'footer.supportProject',
        'Developed by': 'footer.developedBy',

        // Categories
        'vehicles': 'categories.vehicles',
        'real_estate': 'categories.real_estate',
        'machinery': 'categories.machinery',
        'general_goods': 'categories.general_goods',
        'other': 'categories.other'
    };

    /**
     * Auto-translate page content based on text mappings
     */
    function autoTranslateContent() {
        // Skip if Spanish (original language)
        if (currentLang === 'es') return;

        // Find and translate text nodes
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        const textNodes = [];
        while (walker.nextNode()) {
            const node = walker.currentNode;
            const text = node.textContent.trim();
            if (text && TEXT_MAPPINGS[text]) {
                textNodes.push({ node, key: TEXT_MAPPINGS[text] });
            }
        }

        // Apply translations
        textNodes.forEach(({ node, key }) => {
            const translation = t(key);
            if (translation && translation !== key) {
                node.textContent = node.textContent.replace(node.textContent.trim(), translation);
            }
        });

        // Translate select options
        document.querySelectorAll('select option').forEach(option => {
            const text = option.textContent.trim();
            if (TEXT_MAPPINGS[text]) {
                const translation = t(TEXT_MAPPINGS[text]);
                if (translation && translation !== TEXT_MAPPINGS[text]) {
                    option.textContent = translation;
                }
            }
        });
    }

    /**
     * Initialize the i18n system
     */
    async function init() {
        if (isInitialized) return;

        // Detect and set initial language
        const detectedLang = detectLanguage();

        // Load translations for detected language
        await loadTranslations(detectedLang);

        // Also preload default language
        if (detectedLang !== CONFIG.defaultLang) {
            loadTranslations(CONFIG.defaultLang);
        }

        currentLang = detectedLang;
        localStorage.setItem(CONFIG.storageKey, detectedLang);

        // Update HTML lang
        document.documentElement.lang = detectedLang;

        // Inject language selector into the page
        injectLanguageSelector();

        // Initial page translation
        updateMetaTags();
        updateHreflangTags();
        translatePage();
        autoTranslateContent();

        // Setup event listeners
        setupDropdownClose();

        // Re-translate on AJAX content updates
        const observer = new MutationObserver((mutations) => {
            let shouldTranslate = false;
            for (const mutation of mutations) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    shouldTranslate = true;
                    break;
                }
            }
            if (shouldTranslate && currentLang !== 'es') {
                // Debounce translations
                clearTimeout(window._i18nTranslateTimeout);
                window._i18nTranslateTimeout = setTimeout(() => {
                    autoTranslateContent();
                }, 100);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        isInitialized = true;
        console.log(`[i18n] Initialized with language: ${currentLang}`);
    }

    // Public API
    return {
        init,
        t,
        setLanguage,
        getLanguage,
        getSupportedLanguages,
        translatePage,
        translateText,
        translateElement,
        createLanguageSelector,
        createTranslateButton,
        toggleSelector,
        onLanguageChange,
        get currentLang() { return currentLang; },
        get isInitialized() { return isInitialized; }
    };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => I18n.init());
} else {
    I18n.init();
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = I18n;
}
