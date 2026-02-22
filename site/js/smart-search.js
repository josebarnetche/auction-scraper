/**
 * Smart Search Module for Subasto.com.ar
 *
 * Features:
 * - Natural language query understanding
 * - Autocomplete suggestions
 * - Voice search (Web Speech API)
 * - Recent searches (localStorage)
 * - Popular searches display
 * - "Did you mean?" suggestions
 * - Advanced search modal
 * - Filter extraction from queries
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        API_BASE: '/api/v1/search',
        SUGGESTIONS_DEBOUNCE: 150,
        MIN_QUERY_LENGTH: 2,
        MAX_RECENT_SEARCHES: 10,
        STORAGE_KEY: 'subasto_recent_searches',
        VOICE_LANG: 'es-AR',
    };

    // Spanish synonyms for client-side expansion
    const SYNONYMS = {
        auto: ['coche', 'vehiculo', 'automovil', 'carro'],
        camioneta: ['pickup', '4x4', 'suv', 'utilitario'],
        camion: ['truck', 'furgon'],
        moto: ['motocicleta', 'scooter'],
        casa: ['vivienda', 'hogar', 'residencia'],
        departamento: ['depto', 'dpto', 'apartamento', 'piso'],
        terreno: ['lote', 'parcela', 'predio'],
        local: ['comercio', 'negocio', 'tienda', 'oficina'],
        galpon: ['deposito', 'bodega', 'nave'],
    };

    // Brand typo corrections
    const BRAND_CORRECTIONS = {
        toyoya: 'toyota',
        volkswaguen: 'volkswagen',
        volskwagen: 'volkswagen',
        peugot: 'peugeot',
        renaut: 'renault',
        chevroled: 'chevrolet',
        hyunday: 'hyundai',
        mercedez: 'mercedes',
    };

    // State
    let state = {
        suggestions: [],
        recentSearches: [],
        popularSearches: [],
        showSuggestions: false,
        selectedIndex: -1,
        isVoiceActive: false,
        recognition: null,
        lastQuery: '',
        didYouMean: null,
    };

    // DOM Elements (cached after init)
    let elements = {};

    /**
     * Initialize the smart search module
     */
    function init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setupSmartSearch);
        } else {
            setupSmartSearch();
        }
    }

    /**
     * Set up smart search components
     */
    function setupSmartSearch() {
        // Check if search input exists
        const searchInput = document.getElementById('search-input');
        if (!searchInput) {
            console.warn('Smart Search: search-input element not found');
            return;
        }

        // Enhance the search area
        enhanceSearchInput(searchInput);

        // Add Advanced Search button to category filters
        addAdvancedSearchButton();

        // Load recent searches from localStorage
        loadRecentSearches();

        // Fetch popular searches
        fetchPopularSearches();

        // Initialize voice search if available
        initVoiceSearch();

        console.log('Smart Search initialized');
    }

    /**
     * Enhance the existing search input with smart features
     */
    function enhanceSearchInput(input) {
        // Store reference
        elements.searchInput = input;

        // Create wrapper container
        const wrapper = document.createElement('div');
        wrapper.className = 'smart-search-wrapper relative';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        // Add voice search button
        const voiceBtn = createVoiceButton();
        wrapper.appendChild(voiceBtn);
        elements.voiceBtn = voiceBtn;

        // Create suggestions dropdown
        const dropdown = createSuggestionsDropdown();
        wrapper.appendChild(dropdown);
        elements.dropdown = dropdown;

        // Create "Did you mean?" container
        const didYouMeanContainer = createDidYouMeanContainer();
        wrapper.parentNode.insertBefore(didYouMeanContainer, wrapper.nextSibling);
        elements.didYouMean = didYouMeanContainer;

        // Add event listeners
        setupEventListeners(input);

        // Update input placeholder
        input.placeholder = 'Buscar: "Toyota Hilux barato", "departamento CABA", "camioneta menos de 10k"...';

        // Add styles
        injectStyles();
    }

    /**
     * Add Advanced Search button to category filters row
     */
    function addAdvancedSearchButton() {
        // Find the category filters container (the flex div with filter-btn buttons)
        const resultsCount = document.getElementById('results-count');
        if (!resultsCount) return;

        const resultsSpan = resultsCount.closest('span');
        if (!resultsSpan) return;

        // Check if button already exists
        if (document.getElementById('smart-search-btn')) return;

        // Create the button
        const btn = document.createElement('button');
        btn.id = 'smart-search-btn';
        btn.className = 'glass rounded-full px-4 py-2 text-xs uppercase tracking-wider text-yellow-400 hover:text-white hover:bg-yellow-500/10 transition-all flex items-center gap-2 border border-yellow-500/30';
        btn.onclick = function() {
            if (typeof window.AdvancedSearch !== 'undefined') {
                window.AdvancedSearch.open();
            } else {
                console.warn('AdvancedSearch not loaded');
            }
        };
        btn.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/>
            </svg>
            <span class="hidden sm:inline">Busqueda Inteligente</span>
            <span class="sm:hidden">AI</span>
        `;

        // Insert before the results span
        resultsSpan.parentNode.insertBefore(btn, resultsSpan);
    }

    /**
     * Create voice search button
     */
    function createVoiceButton() {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'voice-search-btn absolute right-10 top-1/2 -translate-y-1/2 p-2 text-white/40 hover:text-yellow-400 transition-colors';
        btn.title = 'Buscar por voz';
        btn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/>
            </svg>
        `;
        btn.addEventListener('click', toggleVoiceSearch);
        return btn;
    }

    /**
     * Create suggestions dropdown
     */
    function createSuggestionsDropdown() {
        const dropdown = document.createElement('div');
        dropdown.className = 'smart-search-dropdown absolute top-full left-0 right-0 mt-2 bg-[#1a1a1a] border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden';
        dropdown.style.display = 'none';
        return dropdown;
    }

    /**
     * Create "Did you mean?" container
     */
    function createDidYouMeanContainer() {
        const container = document.createElement('div');
        container.className = 'did-you-mean-container mt-2 hidden';
        return container;
    }

    /**
     * Set up event listeners
     */
    function setupEventListeners(input) {
        // Input events
        input.addEventListener('input', debounce(handleInput, CONFIG.SUGGESTIONS_DEBOUNCE));
        input.addEventListener('focus', handleFocus);
        input.addEventListener('blur', handleBlur);
        input.addEventListener('keydown', handleKeydown);

        // Form submit
        const form = input.closest('form');
        if (form) {
            form.addEventListener('submit', handleSubmit);
        }

        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!elements.dropdown.contains(e.target) && e.target !== input) {
                hideSuggestions();
            }
        });
    }

    /**
     * Handle input changes
     */
    async function handleInput(e) {
        const query = e.target.value.trim();
        state.lastQuery = query;

        if (query.length < CONFIG.MIN_QUERY_LENGTH) {
            showRecentAndPopular();
            return;
        }

        // Client-side typo correction
        const correctedQuery = correctTypos(query);
        if (correctedQuery !== query) {
            state.didYouMean = correctedQuery;
            showDidYouMean(correctedQuery);
        } else {
            hideDidYouMean();
        }

        // Fetch suggestions from API
        try {
            const response = await fetch(`${CONFIG.API_BASE}?action=suggestions&q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success && data.suggestions) {
                state.suggestions = data.suggestions;
                renderSuggestions(data.suggestions, query);
            }
        } catch (error) {
            console.error('Error fetching suggestions:', error);
            // Fallback to client-side suggestions
            const localSuggestions = getLocalSuggestions(query);
            renderSuggestions(localSuggestions, query);
        }
    }

    /**
     * Handle input focus
     */
    function handleFocus() {
        if (elements.searchInput.value.length < CONFIG.MIN_QUERY_LENGTH) {
            showRecentAndPopular();
        } else if (state.suggestions.length > 0) {
            showSuggestions();
        }
    }

    /**
     * Handle input blur
     */
    function handleBlur(e) {
        // Delay to allow click on suggestions
        setTimeout(() => {
            if (!elements.dropdown.contains(document.activeElement)) {
                hideSuggestions();
            }
        }, 150);
    }

    /**
     * Handle keyboard navigation
     */
    function handleKeydown(e) {
        const items = elements.dropdown.querySelectorAll('.suggestion-item');
        const maxIndex = items.length - 1;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                state.selectedIndex = Math.min(state.selectedIndex + 1, maxIndex);
                updateSelection(items);
                break;
            case 'ArrowUp':
                e.preventDefault();
                state.selectedIndex = Math.max(state.selectedIndex - 1, -1);
                updateSelection(items);
                break;
            case 'Enter':
                if (state.selectedIndex >= 0 && items[state.selectedIndex]) {
                    e.preventDefault();
                    selectSuggestion(items[state.selectedIndex].dataset.value);
                }
                break;
            case 'Escape':
                hideSuggestions();
                break;
        }
    }

    /**
     * Handle form submit
     */
    function handleSubmit(e) {
        const query = elements.searchInput.value.trim();
        if (query) {
            saveRecentSearch(query);
        }
        hideSuggestions();
    }

    /**
     * Update keyboard selection highlight
     */
    function updateSelection(items) {
        items.forEach((item, index) => {
            if (index === state.selectedIndex) {
                item.classList.add('bg-white/10');
            } else {
                item.classList.remove('bg-white/10');
            }
        });

        // Scroll into view
        if (state.selectedIndex >= 0 && items[state.selectedIndex]) {
            items[state.selectedIndex].scrollIntoView({ block: 'nearest' });
        }
    }

    /**
     * Show recent searches and popular searches
     */
    function showRecentAndPopular() {
        let html = '';

        // Recent searches section
        if (state.recentSearches.length > 0) {
            html += `
                <div class="p-3 border-b border-white/5">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs uppercase tracking-wider text-white/40">Busquedas recientes</span>
                        <button onclick="window.SmartSearch.clearRecentSearches()" class="text-xs text-red-400 hover:text-red-300">Limpiar</button>
                    </div>
                    ${state.recentSearches.map(search => `
                        <div class="suggestion-item flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-white/5 rounded-lg"
                             data-value="${escapeHtml(search)}" onclick="window.SmartSearch.selectSuggestion('${escapeHtml(search)}')">
                            <svg class="w-4 h-4 text-white/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            <span class="text-white/80">${escapeHtml(search)}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        // Popular searches section
        if (state.popularSearches.length > 0) {
            html += `
                <div class="p-3">
                    <span class="text-xs uppercase tracking-wider text-white/40 block mb-2">Busquedas populares</span>
                    <div class="flex flex-wrap gap-2">
                        ${state.popularSearches.slice(0, 8).map(item => `
                            <button class="suggestion-chip px-3 py-1.5 text-sm rounded-full bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition-colors"
                                    data-value="${escapeHtml(item.query)}" onclick="window.SmartSearch.selectSuggestion('${escapeHtml(item.query)}')">
                                ${escapeHtml(item.query)}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Example searches
        if (html === '') {
            html = `
                <div class="p-4">
                    <span class="text-xs uppercase tracking-wider text-white/40 block mb-3">Ejemplos de busqueda inteligente</span>
                    <div class="space-y-2 text-sm">
                        <div class="example-search p-2 rounded-lg hover:bg-white/5 cursor-pointer" onclick="window.SmartSearch.selectSuggestion('Toyota Hilux menos de 15000')">
                            <span class="text-yellow-400">"Toyota Hilux menos de 15000"</span>
                            <span class="text-white/40 text-xs ml-2">- Vehiculo + precio maximo</span>
                        </div>
                        <div class="example-search p-2 rounded-lg hover:bg-white/5 cursor-pointer" onclick="window.SmartSearch.selectSuggestion('departamento CABA inversion')">
                            <span class="text-yellow-400">"departamento CABA inversion"</span>
                            <span class="text-white/40 text-xs ml-2">- Inmueble + ubicacion + intent</span>
                        </div>
                        <div class="example-search p-2 rounded-lg hover:bg-white/5 cursor-pointer" onclick="window.SmartSearch.selectSuggestion('camioneta 4x4 barata')">
                            <span class="text-yellow-400">"camioneta 4x4 barata"</span>
                            <span class="text-white/40 text-xs ml-2">- Sinonimos expandidos automaticamente</span>
                        </div>
                    </div>
                </div>
            `;
        }

        elements.dropdown.innerHTML = html;
        showSuggestions();
    }

    /**
     * Render autocomplete suggestions
     */
    function renderSuggestions(suggestions, query) {
        if (suggestions.length === 0) {
            elements.dropdown.innerHTML = `
                <div class="p-4 text-center">
                    <span class="text-white/40">No se encontraron sugerencias para "${escapeHtml(query)}"</span>
                </div>
            `;
            showSuggestions();
            return;
        }

        const html = suggestions.map((suggestion, index) => {
            const text = suggestion.text || suggestion;
            const type = suggestion.type || 'listing';
            const category = suggestion.category;

            const categoryBadge = category ?
                `<span class="category-badge category-${category} text-[9px]">${category}</span>` : '';

            const icon = type === 'common' ?
                `<svg class="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                </svg>` :
                `<svg class="w-4 h-4 text-white/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>`;

            // Highlight matching parts
            const highlightedText = highlightMatch(text, query);

            return `
                <div class="suggestion-item flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-white/5 ${index === state.selectedIndex ? 'bg-white/10' : ''}"
                     data-value="${escapeHtml(text)}" onclick="window.SmartSearch.selectSuggestion('${escapeHtml(text)}')">
                    ${icon}
                    <span class="flex-1 text-white/80">${highlightedText}</span>
                    ${categoryBadge}
                </div>
            `;
        }).join('');

        elements.dropdown.innerHTML = html;
        state.selectedIndex = -1;
        showSuggestions();
    }

    /**
     * Select a suggestion
     */
    function selectSuggestion(value) {
        elements.searchInput.value = value;
        saveRecentSearch(value);
        hideSuggestions();

        // Trigger the existing applyFilters function
        if (typeof window.applyFilters === 'function') {
            window.applyFilters();
        } else {
            // Dispatch input event to trigger any listeners
            elements.searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }

    /**
     * Show suggestions dropdown
     */
    function showSuggestions() {
        elements.dropdown.style.display = 'block';
        state.showSuggestions = true;
    }

    /**
     * Hide suggestions dropdown
     */
    function hideSuggestions() {
        elements.dropdown.style.display = 'none';
        state.showSuggestions = false;
        state.selectedIndex = -1;
    }

    /**
     * Show "Did you mean?" suggestion
     */
    function showDidYouMean(correctedQuery) {
        elements.didYouMean.innerHTML = `
            <div class="flex items-center gap-2 text-sm">
                <span class="text-white/40">Quizas quisiste decir:</span>
                <button class="text-yellow-400 hover:text-yellow-300 underline" onclick="window.SmartSearch.selectSuggestion('${escapeHtml(correctedQuery)}')">
                    ${escapeHtml(correctedQuery)}
                </button>
            </div>
        `;
        elements.didYouMean.classList.remove('hidden');
    }

    /**
     * Hide "Did you mean?" suggestion
     */
    function hideDidYouMean() {
        elements.didYouMean.classList.add('hidden');
    }

    /**
     * Correct common typos
     */
    function correctTypos(query) {
        const words = query.split(/\s+/);
        const corrected = words.map(word => {
            const lower = word.toLowerCase();
            return BRAND_CORRECTIONS[lower] || word;
        });
        return corrected.join(' ');
    }

    /**
     * Get local suggestions (fallback)
     */
    function getLocalSuggestions(query) {
        const queryLower = query.toLowerCase();
        const suggestions = [];

        // Check recent searches
        state.recentSearches.forEach(search => {
            if (search.toLowerCase().includes(queryLower)) {
                suggestions.push({ text: search, type: 'recent' });
            }
        });

        // Check popular searches
        state.popularSearches.forEach(item => {
            if (item.query.toLowerCase().includes(queryLower)) {
                suggestions.push({ text: item.query, type: 'popular', category: item.category });
            }
        });

        return suggestions.slice(0, 10);
    }

    /**
     * Highlight matching text
     */
    function highlightMatch(text, query) {
        if (!query) return escapeHtml(text);

        const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
        return escapeHtml(text).replace(regex, '<mark class="bg-yellow-500/30 text-yellow-300 px-0.5 rounded">$1</mark>');
    }

    /**
     * Initialize voice search
     */
    function initVoiceSearch() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            // Hide voice button if not supported
            if (elements.voiceBtn) {
                elements.voiceBtn.style.display = 'none';
            }
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        state.recognition = new SpeechRecognition();
        state.recognition.lang = CONFIG.VOICE_LANG;
        state.recognition.continuous = false;
        state.recognition.interimResults = true;

        state.recognition.onstart = () => {
            state.isVoiceActive = true;
            elements.voiceBtn.classList.add('voice-active');
            elements.searchInput.placeholder = 'Escuchando...';
        };

        state.recognition.onend = () => {
            state.isVoiceActive = false;
            elements.voiceBtn.classList.remove('voice-active');
            elements.searchInput.placeholder = 'Buscar: "Toyota Hilux barato", "departamento CABA"...';
        };

        state.recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');

            elements.searchInput.value = transcript;

            if (event.results[0].isFinal) {
                saveRecentSearch(transcript);
                if (typeof window.applyFilters === 'function') {
                    window.applyFilters();
                }
            }
        };

        state.recognition.onerror = (event) => {
            console.error('Voice recognition error:', event.error);
            state.isVoiceActive = false;
            elements.voiceBtn.classList.remove('voice-active');
        };
    }

    /**
     * Toggle voice search
     */
    function toggleVoiceSearch() {
        if (!state.recognition) return;

        if (state.isVoiceActive) {
            state.recognition.stop();
        } else {
            state.recognition.start();
        }
    }

    /**
     * Load recent searches from localStorage
     */
    function loadRecentSearches() {
        try {
            const stored = localStorage.getItem(CONFIG.STORAGE_KEY);
            if (stored) {
                state.recentSearches = JSON.parse(stored);
            }
        } catch (e) {
            console.error('Error loading recent searches:', e);
        }
    }

    /**
     * Save recent search to localStorage
     */
    function saveRecentSearch(query) {
        if (!query.trim()) return;

        // Remove if already exists
        state.recentSearches = state.recentSearches.filter(s => s.toLowerCase() !== query.toLowerCase());

        // Add to beginning
        state.recentSearches.unshift(query.trim());

        // Limit size
        state.recentSearches = state.recentSearches.slice(0, CONFIG.MAX_RECENT_SEARCHES);

        // Save to localStorage
        try {
            localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(state.recentSearches));
        } catch (e) {
            console.error('Error saving recent searches:', e);
        }
    }

    /**
     * Clear recent searches
     */
    function clearRecentSearches() {
        state.recentSearches = [];
        try {
            localStorage.removeItem(CONFIG.STORAGE_KEY);
        } catch (e) {
            console.error('Error clearing recent searches:', e);
        }
        showRecentAndPopular();
    }

    /**
     * Fetch popular searches from API
     */
    async function fetchPopularSearches() {
        try {
            const response = await fetch(`${CONFIG.API_BASE}?action=popular`);
            const data = await response.json();
            if (data.success && data.popular) {
                state.popularSearches = data.popular;
            }
        } catch (error) {
            console.error('Error fetching popular searches:', error);
            // Use fallback data
            state.popularSearches = [
                { query: 'Toyota Hilux', count: 156, category: 'vehicles' },
                { query: 'Departamento CABA', count: 134, category: 'real_estate' },
                { query: 'Ford Ranger', count: 128, category: 'vehicles' },
                { query: 'Terreno Cordoba', count: 98, category: 'real_estate' },
                { query: 'Camioneta 4x4', count: 87, category: 'vehicles' },
            ];
        }
    }

    /**
     * Inject CSS styles
     */
    function injectStyles() {
        if (document.getElementById('smart-search-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'smart-search-styles';
        styles.textContent = `
            .smart-search-wrapper {
                position: relative;
            }

            .smart-search-dropdown {
                max-height: 400px;
                overflow-y: auto;
            }

            .smart-search-dropdown::-webkit-scrollbar {
                width: 6px;
            }

            .smart-search-dropdown::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.05);
            }

            .smart-search-dropdown::-webkit-scrollbar-thumb {
                background: rgba(234, 179, 8, 0.3);
                border-radius: 3px;
            }

            .smart-search-dropdown::-webkit-scrollbar-thumb:hover {
                background: rgba(234, 179, 8, 0.5);
            }

            .voice-search-btn.voice-active {
                color: #ef4444;
                animation: pulse-voice 1s infinite;
            }

            @keyframes pulse-voice {
                0%, 100% {
                    transform: translateY(-50%) scale(1);
                }
                50% {
                    transform: translateY(-50%) scale(1.1);
                }
            }

            .suggestion-item:hover {
                background: rgba(255, 255, 255, 0.05);
            }

            .suggestion-chip {
                transition: all 0.2s ease;
            }

            .suggestion-chip:hover {
                transform: translateY(-1px);
            }

            .did-you-mean-container {
                animation: fadeIn 0.2s ease;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-5px); }
                to { opacity: 1; transform: translateY(0); }
            }

            /* Adjust existing search input padding for voice button */
            #search-input {
                padding-right: 70px !important;
            }
        `;
        document.head.appendChild(styles);
    }

    // Utility functions
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // Export public API
    window.SmartSearch = {
        init,
        selectSuggestion,
        clearRecentSearches,
        toggleVoiceSearch,
        showAdvancedSearch: function() {
            // Could open an advanced search modal
            console.log('Advanced search not yet implemented');
        }
    };

    // Auto-initialize
    init();

})();
