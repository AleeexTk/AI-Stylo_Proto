/**
 * AI-Stylo B2B SDK v1.0
 * Lightweight "Virtual Mirror" integration.
 */
(function() {
    const AS_CONFIG = {
        api_base: "http://localhost:8000/api/v1",
        merchant_id: "demo_merchant_1"
    };

    class AIStyloWidget {
        constructor() {
            this.btn = null;
            this._init();
        }

        _init() {
            console.log("AI-Stylo SDK Initializing...");
            this._createButton();
        }

        _createButton() {
            const btn = document.createElement("button");
            btn.innerHTML = "✨ Virtual Try-On";
            btn.id = "ai-stylo-trigger";
            btn.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: linear-gradient(135deg, #4A90E2, #9013FE);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 30px;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                font-family: 'Inter', sans-serif;
                font-weight: 600;
                z-index: 99999;
                transition: transform 0.2s;
            `;

            btn.onmouseover = () => btn.style.transform = "scale(1.05)";
            btn.onmouseout = () => btn.style.transform = "scale(1)";
            btn.onclick = () => this.openWidget();

            document.body.appendChild(btn);
            this.btn = btn;
        }

        openWidget() {
            alert("✨ AI-Stylo: Opening Virtual Mirror Sync...\n(In Prototype: This will open an iframe or overlay with photo upload)");
            // Future logic:
            // 1. Get current product URL/SKU from page
            // 2. Open overlay with <input type="file" accept="image/*">
            // 3. Send photo to AS_CONFIG.api_base/tryon
        }
    }

    // Auto-init
    window.aiStylo = new AIStyloWidget();
})();
