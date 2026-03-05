import { useState, useRef, useCallback } from "react";

interface StyleAnalysis {
  style_description: string;
  colors: string[];
  category: string;
  occasion: string;
  season: string;
  style_tags: string[];
  fit?: string;
}

interface CatalogMatch {
  id: string;
  name: string;
  brand: string;
  category: string;
  color: string;
  price: number | string;
  image_url?: string;
  style?: string;
}

interface RecommendResult {
  style_analysis: StyleAnalysis;
  matches: CatalogMatch[];
  recommendation: string;
}

interface StyleAdvisorProps {
  /** Firebase Cloud Function URL, e.g. https://REGION-PROJECT.cloudfunctions.net/analyze_and_recommend */
  functionUrl?: string;
}

export default function StyleAdvisor({ functionUrl }: StyleAdvisorProps) {
  const [image, setImage] = useState<string | null>(null);
  const [imageB64, setImageB64] = useState<string>("");
  const [mimeType, setMimeType] = useState<string>("image/jpeg");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RecommendResult | null>(null);
  const [error, setError] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = (file: File) => {
    setMimeType(file.type || "image/jpeg");
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setImage(dataUrl);
      // Extract base64 without the data:image/...;base64, prefix
      setImageB64(dataUrl.split(",")[1]);
      setResult(null);
      setError("");
    };
    reader.readAsDataURL(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) processFile(file);
  }, []);

  const analyze = async () => {
    if (!imageB64) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const url = functionUrl || import.meta.env.VITE_FUNCTIONS_URL + "/analyze_and_recommend";
      if (!url || url.includes("undefined")) {
        // Dev mock — shows UI without real backend
        await new Promise((r) => setTimeout(r, 2000));
        setResult(MOCK_RESULT);
        return;
      }

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_b64: imageB64, mime_type: mimeType }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const data: RecommendResult = await res.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="advisor-container">
      {/* Header */}
      <div className="advisor-header">
        <span className="hero-badge advisor-badge">
          🔍 Vision × Embeddings × Firestore
        </span>
        <h2 className="advisor-title">
          <span className="gradient-text">Style DNA Analyzer</span>
        </h2>
        <p>Upload a photo — our AI reads your style and finds matching items from the catalog</p>
      </div>

      {/* Upload Zone */}
      <div
        id="upload-dropzone"
        className={`upload-zone ${isDragging ? "dragging" : "normal"}`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          className="upload-input"
          id="file-upload-input"
          aria-label="Upload outfit photo"
          title="Upload outfit photo"
        />

        {image ? (
          <div className="uploaded-preview-container">
            <img
              src={image}
              alt="Uploaded outfit"
              className="uploaded-image"
            />
            <div>
              <p className="upload-ready-text">✅ Image ready for analysis</p>
              <button
                id="analyze-btn"
                className={`btn btn-primary ${loading ? 'loading-op-70' : ''}`}
                onClick={(e) => { e.stopPropagation(); analyze(); }}
                disabled={loading}
              >
                {loading ? "🔄 Analyzing..." : "🔍 Analyze & Find Matches"}
              </button>
              <br />
              <button
                className="btn btn-ghost remove-btn"
                onClick={(e) => { e.stopPropagation(); setImage(null); setResult(null); }}
              >
                ✕ Remove
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="upload-placeholder-icon">📸</div>
            <p className="upload-placeholder-title">
              Drop your outfit photo here
            </p>
            <p className="upload-placeholder-subtitle">or click to browse · JPG, PNG, WEBP</p>
          </>
        )}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="card loading-container">
          <div className="loading-icon">🧬</div>
          <h3 className="loading-title">Analyzing your style...</h3>
          <p className="loading-subtitle">
            Gemini Vision → Embedding → Firestore Vector Search
          </p>
          <div className="loading-steps">
            {["👁️ Perceiving", "🌿 Enriching", "🧬 Matching"].map((step, i) => (
              <span key={step} className={`loading-step anim-delay-${i}`}>
                {step}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card error-card">
          <p className="error-text">⚠️ {error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="results-container">
          {/* Style Analysis */}
          <div className="card style-analysis-card">
            <h3 className="style-analysis-title">🧬 Style Analysis</h3>
            <p className="style-analysis-desc">
              "{result.style_analysis.style_description}"
            </p>
            <div className="style-tags-container">
              {result.style_analysis.colors?.map((c) => (
                <span key={c} className="style-tag-color">{c}</span>
              ))}
              {result.style_analysis.style_tags?.map((t) => (
                <span key={t} className="style-tag-regular">{t}</span>
              ))}
            </div>
          </div>

          {/* AI Recommendation */}
          <div className="card recommendation-card">
            <div className="recommendation-header">
              <div className="recommendation-icon">✨</div>
              <div>
                <h3 className="recommendation-title">AI-Stylo Recommendation</h3>
                <p className="recommendation-text">{result.recommendation}</p>
              </div>
            </div>
          </div>

          {/* Catalog Matches */}
          {result.matches.length > 0 && (
            <div>
              <h3 className="matches-title">
                🔥 Matched from Catalog <span className="matches-count">({result.matches.length} items)</span>
              </h3>
              <div className="matches-grid">
                {result.matches.map((item) => (
                  <div key={item.id} className="card match-card">
                    {item.image_url ? (
                      <img
                        src={item.image_url}
                        alt={item.name}
                        className="match-image"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    ) : (
                      <div className="match-image-placeholder">
                        👗
                      </div>
                    )}
                    <p className="match-name">{item.name || "Item"}</p>
                    <p className="match-brand">{item.brand}</p>
                    <p className="match-price">
                      {item.price ? `$${item.price}` : ""}
                    </p>
                    <p className="match-color">{item.color}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Dev Mock (no backend needed for UI testing) ────────────────────────────────
const MOCK_RESULT: RecommendResult = {
  style_analysis: {
    style_description: "contemporary minimalist streetwear with monochromatic palette",
    colors: ["charcoal", "off-white", "muted sage"],
    category: "full_outfit",
    occasion: "casual",
    season: "all-season",
    style_tags: ["minimalist", "oversized", "monochrome", "urban", "layered"],
    fit: "relaxed",
  },
  matches: [
    { id: "1", name: "Oversized Cotton Crewneck", brand: "COS", category: "tops", color: "charcoal", price: 89 },
    { id: "2", name: "Wide-Leg Linen Trousers", brand: "Arket", category: "bottoms", color: "sage green", price: 119 },
    { id: "3", name: "Minimal Leather Tote", brand: "& Other Stories", category: "accessories", color: "cream", price: 149 },
    { id: "4", name: "Low-Top Canvas Sneakers", brand: "Common Projects", category: "footwear", color: "white", price: 395 },
    { id: "5", name: "Ribbed Merino Scarf", brand: "Toteme", category: "accessories", color: "oatmeal", price: 175 },
  ],
  recommendation: "Your style radiates effortless, considered minimalism — a masterclass in letting quality speak louder than volume. The items we've matched from our catalog amplify your monochromatic instinct: the oversized COS crewneck and wide-leg Arket linen trousers create that perfect relaxed-yet-intentional silhouette you're clearly drawn to. For a finishing touch, tuck the scarf loosely into the tote and let the clean white sneakers ground the whole look.",
};
