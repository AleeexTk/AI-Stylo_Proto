/**
 * AI-Stylo Widget SDK v1.0
 * Integration: <script src=".../sdk.js" data-merchant-id="XYZ"></script>
 */

(function() {
    const script = document.currentScript;
    const merchantId = script.getAttribute('data-merchant-id');
    const apiBase = script.getAttribute('data-api-base') || 'http://localhost:8000';

    console.log(`[AI-Stylo] Initializing for merchant: ${merchantId}`);

    class AIStyloSDK {
        constructor(config) {
            this.merchantId = config.merchantId;
            this.apiBase = config.apiBase;
            this.userId = this._getOrCreateUserId();
        }

        async logEvent(type, payload = {}) {
            payload.user_id = this.userId;
            payload.merchant_id = this.merchantId;
            
            const res = await fetch(`${this.apiBase}/events`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, payload })
            });
            return res.json();
        }

        async getOutfits() {
            const res = await fetch(`${this.apiBase}/outfits/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: this.userId, merchant_id: this.merchantId })
            });
            return res.json();
        }

        _getOrCreateUserId() {
            let id = localStorage.getItem('ai_stylo_user_id');
            if (!id) {
                id = 'user_' + Math.random().toString(36).substr(2, 9);
                localStorage.setItem('ai_stylo_user_id', id);
            }
            return id;
        }
    }

    window.AIStylo = new AIStyloSDK({ merchantId, apiBase });
})();
