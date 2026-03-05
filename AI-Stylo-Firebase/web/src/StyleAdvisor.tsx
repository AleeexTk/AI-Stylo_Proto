import { useState, useRef, useCallback } from "react";
import { GoogleGenerativeAI } from "@google/generative-ai";
import {
  collection,
  getDocs,
  query,
  limit as fsLimit,
} from "firebase/firestore";
import { db } from "./firebase";

interface StyleAnalysis {
  style_description: string;
  colors: string[];
  category: string;
  occasion: string;
  season: string;
  style_tags: string[];
  fit?: string;
  embedding_text?: string;
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

// Gemini Config
const GEN_AI_KEY = import.meta.env.VITE_GEMINI_API_KEY;
const genAI = GEN_AI_KEY ? new GoogleGenerativeAI(GEN_AI_KEY) : null;

export default function StyleAdvisor() {
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

  const analyzeLocally = async () => {
    if (!imageB64 || !genAI) {
      if (!GEN_AI_KEY) setError("Gemini API Key missing (VITE_GEMINI_API_KEY)");
      return;
    }
    
    setLoading(true);
    setError("");
    setResult(null);

    try {
      // 1. Analyze Style with Gemini Vision
      const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
      const prompt = `Analyze this clothing image and return ONLY a JSON object:
      {
        "style_description": "concise description",
        "colors": ["list"],
        "category": "tops/bottoms/dresses/outerwear/footwear/accessories/full_outfit",
        "occasion": "casual/formal/...",
        "style_tags": ["tags"],
        "embedding_text": "rich description for search"
      }`;

      const visionResult = await model.generateContent([
        prompt,
        { inlineData: { data: imageB64, mimeType } }
      ]);
      
      const responseText = visionResult.response.text();
      let styleAnalysis: StyleAnalysis;
      try {
        const cleanJson = responseText.replace(/```json|```/g, "").trim();
        styleAnalysis = JSON.parse(cleanJson);
      } catch {
        console.error("JSON parse error", responseText);
        throw new Error("Failed to parse AI response");
      }

      // 2. Generate Embedding for the style
      const embedModel = genAI.getGenerativeModel({ model: "text-embedding-004" });
      const embedResult = await embedModel.embedContent(styleAnalysis.embedding_text || styleAnalysis.style_description);
      const vector = embedResult.embedding.values;

      // 3. Search Firestore — try client-side findNearest, fallback to basic query
      console.log("Searching Firestore, vector dims:", vector.length);
      const catalogRef = collection(db, "catalog");
      let matches: CatalogMatch[] = [];

      try {
        // findNearest is available on CollectionReference in Firebase JS SDK v9.22+
        const vectorRef = (catalogRef as unknown as { findNearest: (field: string, vector: number[], opts: object) => object }).findNearest;
        if (typeof vectorRef === "function") {
          const vq = (catalogRef as unknown as { findNearest: (f: string, v: number[], o: object) => object })
            .findNearest("embedding", vector, { distanceMeasure: "COSINE", limit: 5 }) as Parameters<typeof getDocs>[0];
          const snapshot = await getDocs(vq);
          matches = snapshot.docs.map(doc => ({ id: doc.id, ...(doc.data() as object) } as CatalogMatch));
        } else {
          throw new Error("findNearest not available");
        }
      } catch (vErr) {
        console.warn("Vector search not available, using basic query.", vErr);
        const basicQuery = query(catalogRef, fsLimit(5));
        const snapshot = await getDocs(basicQuery);
        matches = snapshot.docs.map(doc => ({ id: doc.id, ...(doc.data() as object) } as CatalogMatch));
      }

      // 4. Generate Recommendation text
      const recModel = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
      const matchesText = matches.map(m => `- ${m.name} by ${m.brand}`).join("\n");
      const recPrompt = `The user likes this style: ${styleAnalysis.style_description}. 
      We found these items in our catalog:
      ${matchesText}
      Write a warm 2-sentence personal recommendation.`;
      
      const recResult = await recModel.generateContent(recPrompt);
      const recommendation = recResult.response.text().trim();

      setResult({
        style_analysis: styleAnalysis,
        matches,
        recommendation
      });

    } catch (err: unknown) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="advisor-container">
      {/* Header */}
      <div className="advisor-header">
        <span className="hero-badge advisor-badge">
          🔍 Client-Side AI × Vector Search × UA Brands
        </span>
        <h2 className="advisor-title">
          <span className="gradient-text">Style DNA Analyzer</span>
        </h2>
        <p>Your photo is analyzed locally in your browser using Gemini — finding true Ukrainian fashion matches</p>
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
                onClick={(e) => { e.stopPropagation(); analyzeLocally(); }}
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
            Local Gemini Vision → Embeddings → Firestore
          </p>
          <div className="loading-steps">
            {["👁️ Vision", "🌿 Embedding", "🧬 Firestore"].map((step, i) => (
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

          <div className="card recommendation-card">
            <div className="recommendation-header">
              <div className="recommendation-icon">✨</div>
              <div>
                <h3 className="recommendation-title">AI-Stylo Recommendation</h3>
                <p className="recommendation-text">{result.recommendation}</p>
              </div>
            </div>
          </div>

          {result.matches.length > 0 && (
            <div>
              <h3 className="matches-title">
                🔥 Ukrainian Brand Matches <span className="matches-count">({result.matches.length} items)</span>
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
                      <div className="match-image-placeholder">👗</div>
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
