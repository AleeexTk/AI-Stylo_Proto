# 📗 StyleScape Integration Guide (for Sergey)

This document outlines the steps to integrate the AI-Stylo Cloud/Firebase modules into the active StyleScape platform.

## 1. Cloud Infrastructure (Firebase)

The project is hosted on the Firebase project `ai-stylo-styleskape`.

### Required Steps

- **Deploy Functions**: Run `firebase deploy --only functions` from the `AI-Stylo-Firebase` directory.
- **Firestore Collections**:
  - `catalog`: Primary collection with product metadata and `embedding` vectors.
  - `user_designs`: Storage for AI-generated collection blueprints.
- **Vector Index**: **CRITICAL** - You must create a vector index in the Firebase Console:
  - Collection: `catalog`
  - Field: `embedding`
  - Distance Measure: `COSINE`
  - Dimension: `768` (Standard for `text-embedding-004`)

## 2. API Endpoints

The backend (`functions/main.py`) exposes these primary endpoints:

| Endpoint | Method | Key Feature |
| :--- | :--- | :--- |
| `/analyze_and_recommend` | `POST` | Core PEAR Pipeline. Takes image B64 -> returns analysis + catalog matches. |
| `/stylescape/design_collection` | `POST` | **AI Designer**. Text idea -> Full capsule blueprint (prompt, name, tags). |
| `/stylescape/checkout_generated_look`| `POST` | **Visual Checkout**. Generated image -> `buy_manifest` with real products. |

## 3. Frontend Integration (`web/src/`)

The React components use a **Hybrid PEAR** approach:

1. **VITE_FUNCTIONS_URL**: If set, the components prioritize calling the Cloud Functions.
2. **Local Fallback**: If the cloud is unavailable, it uses the browser-side Gemini API (`VITE_GEMINI_API_KEY`) to perform analysis.

### Required Env Variables

```env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_PROJECT_ID=ai-stylo-styleskape
VITE_FUNCTIONS_URL=https://europe-west3-ai-stylo-styleskape.cloudfunctions.net
VITE_GEMINI_API_KEY=...
```

## 4. Maintenance

- **Catalog Update**: Use `seed_catalog.py` to push new items from JSON to Firestore with computed embeddings.
- **DNA Sync**: User taste vectors (`Profile`) are stored in Firestore to enable cross-device consistency.

---
*Created for the StyleScape Engineering Team.*
