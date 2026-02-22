/**
 * Subasto Onboarding Module
 * Shows a welcome modal for first-time users with links to educational guides
 */

(function() {
    'use strict';

    const STORAGE_KEY = 'subasto_onboarding_seen';

    // Create and inject the modal HTML
    function createOnboardingModal() {
        const modalHTML = `
        <div id="onboarding-modal" class="fixed inset-0 z-[100] hidden">
            <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" onclick="SubastoOnboarding.close()"></div>
            <div class="absolute inset-0 flex items-center justify-center p-4">
                <div class="glass rounded-3xl max-w-lg w-full p-8 relative border border-yellow-500/20" style="animation: onboardingFadeIn 0.3s ease-out;">
                    <button onclick="SubastoOnboarding.close()" class="absolute top-4 right-4 text-white/40 hover:text-white transition-colors">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                    <div class="text-center mb-6">
                        <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-yellow-500/20 flex items-center justify-center">
                            <svg class="w-8 h-8 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                            </svg>
                        </div>
                        <h2 class="text-2xl font-display font-medium text-white mb-2">Bienvenido a Subasto!</h2>
                        <p class="text-white/60">Compra bienes al 30-70% del valor de mercado en subastas judiciales y privadas.</p>
                    </div>
                    <div class="space-y-4 mb-8">
                        <div class="flex items-start gap-3 p-3 bg-white/5 rounded-xl">
                            <div class="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                                <span class="text-green-500 font-bold text-sm">1</span>
                            </div>
                            <div>
                                <h4 class="text-white font-medium text-sm">Explora las subastas</h4>
                                <p class="text-white/50 text-xs">Filtra por categoria, precio, y fecha de cierre</p>
                            </div>
                        </div>
                        <div class="flex items-start gap-3 p-3 bg-white/5 rounded-xl">
                            <div class="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                                <span class="text-green-500 font-bold text-sm">2</span>
                            </div>
                            <div>
                                <h4 class="text-white font-medium text-sm">Lee las guias</h4>
                                <p class="text-white/50 text-xs">Aprende como participar, calcular costos, y evitar errores</p>
                            </div>
                        </div>
                        <div class="flex items-start gap-3 p-3 bg-white/5 rounded-xl">
                            <div class="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                                <span class="text-green-500 font-bold text-sm">3</span>
                            </div>
                            <div>
                                <h4 class="text-white font-medium text-sm">Participa con confianza</h4>
                                <p class="text-white/50 text-xs">Con la informacion correcta, comprar en subastas es seguro</p>
                            </div>
                        </div>
                    </div>
                    <div class="flex flex-col sm:flex-row gap-3">
                        <a href="/guides/" class="flex-1 text-center px-6 py-3 bg-yellow-500 hover:bg-yellow-400 text-black font-medium rounded-full transition-colors">
                            Leer Guias Primero
                        </a>
                        <button onclick="SubastoOnboarding.close()" class="flex-1 px-6 py-3 bg-white/10 hover:bg-white/20 text-white font-medium rounded-full transition-colors">
                            Explorar Subastas
                        </button>
                    </div>
                    <label class="flex items-center justify-center gap-2 mt-4 cursor-pointer">
                        <input type="checkbox" id="onboarding-dont-show" class="w-4 h-4 rounded border-white/20">
                        <span class="text-white/40 text-xs">No mostrar de nuevo</span>
                    </label>
                </div>
            </div>
        </div>
        <style>
            @keyframes onboardingFadeIn {
                from { opacity: 0; transform: scale(0.95) translateY(10px); }
                to { opacity: 1; transform: scale(1) translateY(0); }
            }
        </style>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    // Show the onboarding modal
    function showOnboarding() {
        const hasSeenOnboarding = localStorage.getItem(STORAGE_KEY);
        if (!hasSeenOnboarding) {
            setTimeout(() => {
                const modal = document.getElementById('onboarding-modal');
                if (modal) {
                    modal.classList.remove('hidden');
                }
            }, 2500); // Show after 2.5 seconds
        }
    }

    // Close the onboarding modal
    function closeOnboarding() {
        const dontShowAgain = document.getElementById('onboarding-dont-show');
        if (dontShowAgain && dontShowAgain.checked) {
            localStorage.setItem(STORAGE_KEY, 'true');
        }
        const modal = document.getElementById('onboarding-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        createOnboardingModal();
        showOnboarding();
    });

    // Expose API
    window.SubastoOnboarding = {
        show: showOnboarding,
        close: closeOnboarding,
        reset: function() {
            localStorage.removeItem(STORAGE_KEY);
        }
    };

})();
