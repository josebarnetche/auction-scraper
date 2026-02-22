/**
 * Advanced Search Modal for Subasto.com.ar
 *
 * Provides a full-featured search interface with:
 * - Natural language query builder
 * - Filter selection UI
 * - Price range slider
 * - Category selection
 * - Location picker
 * - Source selection
 * - Sort options
 */

(function() {
    'use strict';

    let isOpen = false;
    let modalElement = null;

    const CATEGORIES = [
        { id: 'vehicles', name: 'Vehiculos', icon: 'M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z M13 16V4h-3v12m8 0V4h-3v8' },
        { id: 'real_estate', name: 'Inmuebles', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
        { id: 'machinery', name: 'Maquinaria', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
        { id: 'general_goods', name: 'Bienes Generales', icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' },
    ];

    const SOURCES = [
        { id: 'csjn', name: 'CSJN', type: 'judicial' },
        { id: 'scba', name: 'SCBA', type: 'judicial' },
        { id: 'cordoba', name: 'Cordoba', type: 'judicial' },
        { id: 'entrerios', name: 'Entre Rios', type: 'judicial' },
        { id: 'banco_ciudad', name: 'Banco Ciudad', type: 'private' },
        { id: 'adrian_mercado', name: 'Adrian Mercado', type: 'private' },
        { id: 'agusti', name: 'Agusti', type: 'private' },
        { id: 'global_remates', name: 'Global Remates', type: 'private' },
        { id: 'bidbit', name: 'BidBit', type: 'private' },
    ];

    const PROVINCES = [
        'Buenos Aires', 'CABA', 'Cordoba', 'Santa Fe', 'Mendoza',
        'Tucuman', 'Entre Rios', 'Salta', 'Misiones', 'Chaco',
        'Corrientes', 'Santiago del Estero', 'San Juan', 'Jujuy',
        'Rio Negro', 'Neuquen', 'Formosa', 'Chubut', 'San Luis',
        'Catamarca', 'La Rioja', 'La Pampa', 'Santa Cruz', 'Tierra del Fuego'
    ];

    const SORT_OPTIONS = [
        { id: 'relevance', name: 'Relevancia' },
        { id: 'ending_soon', name: 'Terminan pronto' },
        { id: 'discount', name: 'Mayor descuento' },
        { id: 'price_asc', name: 'Precio: menor a mayor' },
        { id: 'price_desc', name: 'Precio: mayor a menor' },
        { id: 'newest', name: 'Mas recientes' },
    ];

    // Filter state
    let filters = {
        query: '',
        category: null,
        minPrice: 0,
        maxPrice: 500000,
        currency: 'USD',
        location: null,
        sources: [],
        sortBy: 'relevance',
        intent: null,
    };

    /**
     * Create and show the modal
     */
    function openModal() {
        if (isOpen) return;

        // Reset filters to current search state
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            filters.query = searchInput.value;
        }

        createModal();
        isOpen = true;
        document.body.style.overflow = 'hidden';
    }

    /**
     * Close the modal
     */
    function closeModal() {
        if (!isOpen || !modalElement) return;

        modalElement.classList.add('modal-closing');
        setTimeout(() => {
            modalElement.remove();
            modalElement = null;
            isOpen = false;
            document.body.style.overflow = '';
        }, 200);
    }

    /**
     * Create the modal DOM structure
     */
    function createModal() {
        modalElement = document.createElement('div');
        modalElement.className = 'advanced-search-modal fixed inset-0 z-[100] flex items-center justify-center p-4';
        modalElement.innerHTML = `
            <div class="modal-backdrop absolute inset-0 bg-black/80 backdrop-blur-sm" onclick="AdvancedSearch.close()"></div>
            <div class="modal-content relative w-full max-w-4xl max-h-[90vh] bg-[#0a0a0a] rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
                <!-- Header -->
                <div class="flex items-center justify-between p-6 border-b border-white/10">
                    <div>
                        <h2 class="text-2xl font-display font-medium text-white">Busqueda Avanzada</h2>
                        <p class="text-sm text-white/40 mt-1">Utiliza filtros para encontrar exactamente lo que buscas</p>
                    </div>
                    <button onclick="AdvancedSearch.close()" class="p-2 text-white/40 hover:text-white transition-colors">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>

                <!-- Body -->
                <div class="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
                    <!-- Natural Language Input -->
                    <div class="mb-8">
                        <label class="block text-sm font-medium text-white/60 mb-2">
                            Describe lo que buscas en tus propias palabras
                        </label>
                        <textarea
                            id="adv-query"
                            class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-yellow-500/50 resize-none"
                            rows="2"
                            placeholder='Ejemplo: "Toyota Hilux 4x4 en buen estado, menos de 20000 dolares, en Cordoba o Buenos Aires"'
                        >${escapeHtml(filters.query)}</textarea>
                        <div class="mt-2 flex flex-wrap gap-2">
                            <span class="text-xs text-white/30">Sugerencias:</span>
                            <button type="button" class="text-xs text-yellow-400 hover:text-yellow-300" onclick="AdvancedSearch.setQuery('camioneta pickup 4x4 barata')">pickup 4x4 barata</button>
                            <button type="button" class="text-xs text-yellow-400 hover:text-yellow-300" onclick="AdvancedSearch.setQuery('departamento 2 ambientes CABA inversion')">depto inversion CABA</button>
                            <button type="button" class="text-xs text-yellow-400 hover:text-yellow-300" onclick="AdvancedSearch.setQuery('tractor agricola oportunidad')">tractor oportunidad</button>
                        </div>
                    </div>

                    <!-- Categories -->
                    <div class="mb-8">
                        <label class="block text-sm font-medium text-white/60 mb-3">Categoria</label>
                        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            <button type="button" class="category-btn ${!filters.category ? 'active' : ''}" data-category="" onclick="AdvancedSearch.setCategory(null)">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/>
                                </svg>
                                <span>Todas</span>
                            </button>
                            ${CATEGORIES.map(cat => `
                                <button type="button" class="category-btn ${filters.category === cat.id ? 'active' : ''}" data-category="${cat.id}" onclick="AdvancedSearch.setCategory('${cat.id}')">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${cat.icon}"/>
                                    </svg>
                                    <span>${cat.name}</span>
                                </button>
                            `).join('')}
                        </div>
                    </div>

                    <!-- Price Range -->
                    <div class="mb-8">
                        <div class="flex items-center justify-between mb-3">
                            <label class="text-sm font-medium text-white/60">Rango de precio</label>
                            <div class="flex bg-black/30 rounded-full p-0.5 border border-white/10">
                                <button type="button" class="currency-btn px-3 py-1 text-xs font-medium rounded-full ${filters.currency === 'USD' ? 'bg-yellow-500 text-black' : 'text-white/60'}"
                                        onclick="AdvancedSearch.setCurrency('USD')">USD</button>
                                <button type="button" class="currency-btn px-3 py-1 text-xs font-medium rounded-full ${filters.currency === 'ARS' ? 'bg-yellow-500 text-black' : 'text-white/60'}"
                                        onclick="AdvancedSearch.setCurrency('ARS')">ARS</button>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs text-white/40 mb-1 block">Minimo</label>
                                <input type="number" id="adv-min-price" value="${filters.minPrice}"
                                       class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-yellow-500/50"
                                       placeholder="0" onchange="AdvancedSearch.updatePrice()">
                            </div>
                            <div>
                                <label class="text-xs text-white/40 mb-1 block">Maximo</label>
                                <input type="number" id="adv-max-price" value="${filters.maxPrice === 500000 ? '' : filters.maxPrice}"
                                       class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-yellow-500/50"
                                       placeholder="Sin limite" onchange="AdvancedSearch.updatePrice()">
                            </div>
                        </div>
                        <div class="flex flex-wrap gap-2 mt-3">
                            <button type="button" class="price-preset px-3 py-1 text-xs rounded-full bg-white/5 text-white/60 hover:bg-white/10" onclick="AdvancedSearch.setPriceRange(0, 5000)">Hasta $5k</button>
                            <button type="button" class="price-preset px-3 py-1 text-xs rounded-full bg-white/5 text-white/60 hover:bg-white/10" onclick="AdvancedSearch.setPriceRange(0, 10000)">Hasta $10k</button>
                            <button type="button" class="price-preset px-3 py-1 text-xs rounded-full bg-white/5 text-white/60 hover:bg-white/10" onclick="AdvancedSearch.setPriceRange(10000, 25000)">$10k - $25k</button>
                            <button type="button" class="price-preset px-3 py-1 text-xs rounded-full bg-white/5 text-white/60 hover:bg-white/10" onclick="AdvancedSearch.setPriceRange(25000, 50000)">$25k - $50k</button>
                            <button type="button" class="price-preset px-3 py-1 text-xs rounded-full bg-white/5 text-white/60 hover:bg-white/10" onclick="AdvancedSearch.setPriceRange(50000, null)">$50k+</button>
                        </div>
                    </div>

                    <!-- Location -->
                    <div class="mb-8">
                        <label class="block text-sm font-medium text-white/60 mb-3">Ubicacion</label>
                        <select id="adv-location" class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-yellow-500/50"
                                onchange="AdvancedSearch.setLocation(this.value)">
                            <option value="" class="bg-[#1a1a1a]">Todas las ubicaciones</option>
                            ${PROVINCES.map(p => `
                                <option value="${p}" class="bg-[#1a1a1a]" ${filters.location === p ? 'selected' : ''}>${p}</option>
                            `).join('')}
                        </select>
                    </div>

                    <!-- Sources -->
                    <div class="mb-8">
                        <label class="block text-sm font-medium text-white/60 mb-3">Fuentes</label>
                        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                            ${SOURCES.map(source => `
                                <label class="source-checkbox flex items-center gap-2 p-2 rounded-lg hover:bg-white/5 cursor-pointer">
                                    <input type="checkbox" value="${source.id}" ${filters.sources.includes(source.id) ? 'checked' : ''}
                                           class="w-4 h-4 rounded border-white/20 bg-white/5 text-yellow-500 focus:ring-yellow-500/50"
                                           onchange="AdvancedSearch.toggleSource('${source.id}')">
                                    <span class="text-sm text-white/80">${source.name}</span>
                                    <span class="text-xs px-1.5 py-0.5 rounded ${source.type === 'judicial' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'}">${source.type}</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>

                    <!-- Sort -->
                    <div class="mb-8">
                        <label class="block text-sm font-medium text-white/60 mb-3">Ordenar por</label>
                        <div class="flex flex-wrap gap-2">
                            ${SORT_OPTIONS.map(opt => `
                                <button type="button" class="sort-btn px-4 py-2 text-sm rounded-lg ${filters.sortBy === opt.id ? 'bg-yellow-500 text-black' : 'bg-white/5 text-white/60 hover:bg-white/10'}"
                                        onclick="AdvancedSearch.setSortBy('${opt.id}')">${opt.name}</button>
                            `).join('')}
                        </div>
                    </div>

                    <!-- Intent (optional) -->
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-white/60 mb-3">Proposito de compra (opcional)</label>
                        <div class="flex flex-wrap gap-2">
                            <button type="button" class="intent-btn px-4 py-2 text-sm rounded-lg ${!filters.intent ? 'bg-white/10 text-white' : 'bg-white/5 text-white/60 hover:bg-white/10'}"
                                    onclick="AdvancedSearch.setIntent(null)">Cualquiera</button>
                            <button type="button" class="intent-btn px-4 py-2 text-sm rounded-lg ${filters.intent === 'investment' ? 'bg-yellow-500 text-black' : 'bg-white/5 text-white/60 hover:bg-white/10'}"
                                    onclick="AdvancedSearch.setIntent('investment')">Inversion</button>
                            <button type="button" class="intent-btn px-4 py-2 text-sm rounded-lg ${filters.intent === 'flip' ? 'bg-yellow-500 text-black' : 'bg-white/5 text-white/60 hover:bg-white/10'}"
                                    onclick="AdvancedSearch.setIntent('flip')">Reventa</button>
                            <button type="button" class="intent-btn px-4 py-2 text-sm rounded-lg ${filters.intent === 'personal' ? 'bg-yellow-500 text-black' : 'bg-white/5 text-white/60 hover:bg-white/10'}"
                                    onclick="AdvancedSearch.setIntent('personal')">Uso personal</button>
                            <button type="button" class="intent-btn px-4 py-2 text-sm rounded-lg ${filters.intent === 'business' ? 'bg-yellow-500 text-black' : 'bg-white/5 text-white/60 hover:bg-white/10'}"
                                    onclick="AdvancedSearch.setIntent('business')">Negocio</button>
                        </div>
                    </div>
                </div>

                <!-- Footer -->
                <div class="flex items-center justify-between p-6 border-t border-white/10 bg-black/30">
                    <button type="button" onclick="AdvancedSearch.reset()" class="text-white/40 hover:text-white transition-colors">
                        Limpiar filtros
                    </button>
                    <div class="flex gap-3">
                        <button type="button" onclick="AdvancedSearch.close()" class="px-6 py-2 rounded-lg border border-white/10 text-white/60 hover:text-white hover:border-white/30 transition-colors">
                            Cancelar
                        </button>
                        <button type="button" onclick="AdvancedSearch.apply()" class="px-6 py-2 rounded-lg bg-yellow-500 text-black font-medium hover:bg-yellow-400 transition-colors">
                            Buscar
                        </button>
                    </div>
                </div>
            </div>
        `;

        injectModalStyles();
        document.body.appendChild(modalElement);

        // Focus query input
        setTimeout(() => {
            const queryInput = document.getElementById('adv-query');
            if (queryInput) queryInput.focus();
        }, 100);
    }

    /**
     * Set query text
     */
    function setQuery(query) {
        filters.query = query;
        const input = document.getElementById('adv-query');
        if (input) input.value = query;
    }

    /**
     * Set category filter
     */
    function setCategory(category) {
        filters.category = category;
        updateCategoryButtons();
    }

    /**
     * Update category button states
     */
    function updateCategoryButtons() {
        const buttons = modalElement.querySelectorAll('.category-btn');
        buttons.forEach(btn => {
            const cat = btn.dataset.category;
            if ((cat === '' && !filters.category) || cat === filters.category) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    /**
     * Set currency
     */
    function setCurrency(currency) {
        filters.currency = currency;
        const buttons = modalElement.querySelectorAll('.currency-btn');
        buttons.forEach(btn => {
            if (btn.textContent.trim() === currency) {
                btn.classList.add('bg-yellow-500', 'text-black');
                btn.classList.remove('text-white/60');
            } else {
                btn.classList.remove('bg-yellow-500', 'text-black');
                btn.classList.add('text-white/60');
            }
        });
    }

    /**
     * Update price from inputs
     */
    function updatePrice() {
        const minInput = document.getElementById('adv-min-price');
        const maxInput = document.getElementById('adv-max-price');

        filters.minPrice = parseFloat(minInput.value) || 0;
        filters.maxPrice = parseFloat(maxInput.value) || 500000;
    }

    /**
     * Set price range
     */
    function setPriceRange(min, max) {
        filters.minPrice = min;
        filters.maxPrice = max || 500000;

        const minInput = document.getElementById('adv-min-price');
        const maxInput = document.getElementById('adv-max-price');

        if (minInput) minInput.value = min;
        if (maxInput) maxInput.value = max || '';
    }

    /**
     * Set location
     */
    function setLocation(location) {
        filters.location = location || null;
    }

    /**
     * Toggle source selection
     */
    function toggleSource(sourceId) {
        const index = filters.sources.indexOf(sourceId);
        if (index > -1) {
            filters.sources.splice(index, 1);
        } else {
            filters.sources.push(sourceId);
        }
    }

    /**
     * Set sort option
     */
    function setSortBy(sortBy) {
        filters.sortBy = sortBy;
        const buttons = modalElement.querySelectorAll('.sort-btn');
        buttons.forEach(btn => {
            if (btn.textContent.trim() === SORT_OPTIONS.find(o => o.id === sortBy)?.name) {
                btn.classList.add('bg-yellow-500', 'text-black');
                btn.classList.remove('bg-white/5', 'text-white/60');
            } else {
                btn.classList.remove('bg-yellow-500', 'text-black');
                btn.classList.add('bg-white/5', 'text-white/60');
            }
        });
    }

    /**
     * Set intent
     */
    function setIntent(intent) {
        filters.intent = intent;
        const buttons = modalElement.querySelectorAll('.intent-btn');
        buttons.forEach(btn => {
            const btnIntent = btn.onclick.toString().match(/'([^']+)'/)?.[1] || null;
            if (btnIntent === intent || (!btnIntent && !intent)) {
                btn.classList.add(intent ? 'bg-yellow-500' : 'bg-white/10');
                btn.classList.add(intent ? 'text-black' : 'text-white');
                btn.classList.remove('bg-white/5', 'text-white/60');
            } else {
                btn.classList.remove('bg-yellow-500', 'bg-white/10', 'text-black', 'text-white');
                btn.classList.add('bg-white/5', 'text-white/60');
            }
        });
    }

    /**
     * Reset all filters
     */
    function reset() {
        filters = {
            query: '',
            category: null,
            minPrice: 0,
            maxPrice: 500000,
            currency: 'USD',
            location: null,
            sources: [],
            sortBy: 'relevance',
            intent: null,
        };

        // Recreate modal with reset state
        closeModal();
        setTimeout(openModal, 250);
    }

    /**
     * Apply filters and search
     */
    function apply() {
        // Get query from textarea
        const queryInput = document.getElementById('adv-query');
        if (queryInput) {
            filters.query = queryInput.value;
        }

        // Update the main search input
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.value = filters.query;
        }

        // Update price range sliders
        const minPriceSlider = document.getElementById('min-price');
        const maxPriceSlider = document.getElementById('max-price');
        if (minPriceSlider) minPriceSlider.value = filters.minPrice;
        if (maxPriceSlider) maxPriceSlider.value = filters.maxPrice === 500000 ? 500000 : filters.maxPrice;

        // Update source filter
        const sourceFilter = document.getElementById('source-filter');
        if (sourceFilter && filters.sources.length === 1) {
            sourceFilter.value = filters.sources[0];
        }

        // Update location filter
        const locationFilter = document.getElementById('location-filter');
        if (locationFilter && filters.location) {
            locationFilter.value = filters.location;
        }

        // Update sort filter
        const sortFilter = document.getElementById('sort-filter');
        if (sortFilter) {
            const sortMap = {
                'relevance': 'recommended',
                'ending_soon': 'ending',
                'discount': 'discount',
                'price_asc': 'price-asc',
                'price_desc': 'price-desc',
                'newest': 'newest',
            };
            sortFilter.value = sortMap[filters.sortBy] || 'recommended';
        }

        // Update category filter buttons
        if (filters.category) {
            const filterBtns = document.querySelectorAll('.filter-btn');
            filterBtns.forEach(btn => {
                if (btn.dataset.filter === filters.category) {
                    btn.click();
                }
            });
        }

        // Close modal
        closeModal();

        // Trigger filter application
        if (typeof window.applyFilters === 'function') {
            window.applyFilters();
        }

        // Scroll to auctions section
        const auctionsSection = document.getElementById('auctions');
        if (auctionsSection) {
            auctionsSection.scrollIntoView({ behavior: 'smooth' });
        }
    }

    /**
     * Inject modal-specific styles
     */
    function injectModalStyles() {
        if (document.getElementById('advanced-search-modal-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'advanced-search-modal-styles';
        styles.textContent = `
            .advanced-search-modal {
                animation: fadeIn 0.2s ease;
            }

            .advanced-search-modal.modal-closing {
                animation: fadeOut 0.2s ease;
            }

            .advanced-search-modal .modal-content {
                animation: slideUp 0.3s ease;
            }

            .advanced-search-modal.modal-closing .modal-content {
                animation: slideDown 0.2s ease;
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }

            @keyframes slideUp {
                from { transform: translateY(20px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }

            @keyframes slideDown {
                from { transform: translateY(0); opacity: 1; }
                to { transform: translateY(20px); opacity: 0; }
            }

            .category-btn {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 0.5rem;
                padding: 1rem;
                border-radius: 0.75rem;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.6);
                transition: all 0.2s;
            }

            .category-btn:hover {
                background: rgba(255, 255, 255, 0.05);
                color: white;
            }

            .category-btn.active {
                background: rgba(234, 179, 8, 0.1);
                border-color: rgba(234, 179, 8, 0.3);
                color: #eab308;
            }

            .source-checkbox input[type="checkbox"] {
                appearance: none;
                -webkit-appearance: none;
                width: 1rem;
                height: 1rem;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 0.25rem;
                background: rgba(255, 255, 255, 0.05);
            }

            .source-checkbox input[type="checkbox"]:checked {
                background: #eab308;
                border-color: #eab308;
            }

            .source-checkbox input[type="checkbox"]:checked::after {
                content: '';
                display: block;
                width: 0.5rem;
                height: 0.5rem;
                margin: 0.2rem auto;
                border: solid black;
                border-width: 0 2px 2px 0;
                transform: rotate(45deg);
            }
        `;
        document.head.appendChild(styles);
    }

    // Utility function
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Export public API
    window.AdvancedSearch = {
        open: openModal,
        close: closeModal,
        setQuery,
        setCategory,
        setCurrency,
        updatePrice,
        setPriceRange,
        setLocation,
        toggleSource,
        setSortBy,
        setIntent,
        reset,
        apply,
    };

})();
