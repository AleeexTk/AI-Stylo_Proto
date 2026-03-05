import { useState } from "react";
import "./index.css";
import StyleAdvisor from "./StyleAdvisor";
import { auth, googleProvider } from "./firebase";
import { signInWithPopup, signOut, type User } from "firebase/auth";

// ─── Types ────────────────────────────────────────────────────────────────────
interface Feature {
  icon: string;
  title: string;
  desc: string;
}

// ─── Data ─────────────────────────────────────────────────────────────────────
const FEATURES: Feature[] = [
  {
    icon: "🧬",
    title: "Style DNA Cloud Sync",
    desc: "Your personal fashion genome syncs from the local AI-Stylo core to the cloud in real time.",
  },
  {
    icon: "🔥",
    title: "Firebase Realtime DB",
    desc: "Firestore-powered catalog and saved outfits — always fresh, always fast.",
  },
  {
    icon: "🤖",
    title: "PEAR Intelligence",
    desc: "The 5-stage PEAR pipeline (Perceive → Enrich → Adapt → Act → Reflect) runs as Firebase Cloud Functions.",
  },
  {
    icon: "🛡️",
    title: "Google Auth",
    desc: "Sign in with Google. Your Style DNA remains encrypted and user-owned in Firestore.",
  },
  {
    icon: "🌐",
    title: "Global Market Catalog",
    desc: "Browse thousands of curated fashion items sourced from the AI-Stylo Agentic DOM Parser.",
  },
  {
    icon: "✨",
    title: "Virtual Try-On (Soon)",
    desc: "Neural warping and MediaPipe pose sync coming to the cloud experience.",
  },
];

// ─── Components ───────────────────────────────────────────────────────────────
function Navbar({ onLogin, onAdvisor, activeTab, user, onSignOut }: {
  onLogin: () => void;
  onAdvisor: () => void;
  activeTab: string;
  user: User | null;
  onSignOut: () => void;
}) {
  return (
    <nav className="navbar">
      <div className="container">
        <a href="#" className="navbar-logo">
          <div className="logo-icon">🧬</div>
          <span className="logo-text">
            AI-Stylo <span className="gradient-text">Cloud</span>
          </span>
        </a>
        <div className="navbar-links">
          <a href="#features" className={`nav-link ${activeTab === 'advisor' ? 'hidden' : ''}`}>Features</a>
          <a href="#sync" className={`nav-link ${activeTab === 'advisor' ? 'hidden' : ''}`}>Sync</a>
          <button
            id="nav-advisor-btn"
            className={`btn nav-btn ${activeTab === 'advisor' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={onAdvisor}
          >
            🔍 Style Advisor
          </button>
          {user ? (
            <div className="user-menu">
              <img src={user.photoURL || ''} alt={user.displayName || 'User'} className="user-avatar" />
              <button id="nav-signout-btn" className="btn btn-ghost signout-btn" onClick={onSignOut}>Sign Out</button>
            </div>
          ) : (
            <button id="nav-signin-btn" className="btn btn-primary nav-btn" onClick={onLogin}>
              Sign In
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}

function Hero({ onLogin }: { onLogin: () => void }) {
  return (
    <section className="hero">
      {/* Background orbs */}
      <div className="hero-bg-orb orb-purple" />
      <div className="hero-bg-orb orb-pink" />
      <div className="hero-bg-orb orb-cyan" />

      <div className="container">
        <div className="hero-content">
          <div className="hero-badge">
            <span>🔥</span> Powered by Firebase + EvoPyramid PEAR Architecture
          </div>

          <h1 className="hero-title">
            Your Style DNA,{" "}
            <span className="shimmer-text">Now in the Cloud</span>
          </h1>

          <p className="hero-subtitle">
            AI-Stylo Firebase is the autonomous cloud twin of your local Fashion OS.
            It syncs your personal Style DNA to Firebase, bringing your AI-powered
            wardrobe to any device, anywhere.
          </p>

          <div className="hero-actions">
            <button id="hero-getstarted-btn" className="btn btn-primary" onClick={onLogin}>
              🚀 Get Started Free
            </button>
            <a
              href="https://github.com/AleeexTk/AI-Stylo_Proto"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost"
            >
              ⭐ View on GitHub
            </a>
          </div>

          <div className="status-strip">
            <div className="status-item">
              <div className="status-dot" />
              Firebase Connected
            </div>
            <div className="status-item">
              <div className="status-dot status-dot-purple" />
              PEAR Pipeline Active
            </div>
            <div className="status-item">
              <div className="status-dot status-dot-cyan" />
              Style DNA Sync Ready
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="section features-section">
      <div className="container">
        <p className="section-label">What's Inside</p>
        <h2 className="section-title gradient-text">Cloud-Native Fashion Intelligence</h2>
        <p className="section-subtitle">
          Everything you love about AI-Stylo, now scalable, shareable, and always online.
        </p>
        <div className="features-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="card feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p className="feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function SyncSection() {
  return (
    <section id="sync" className="section">
      <div className="container">
        <div className="card sync-card">
          <div className="sync-grid">
            <div>
              <p className="section-label">The Bridge</p>
              <h2 className="sync-title">
                Local AI Core ↔ <span className="gradient-text">Firebase Cloud</span>
              </h2>
              <p className="sync-desc">
                The <strong className="text-primary">Sync Connector</strong> is the
                only bridge between your private local SQLite database and the Firebase cloud.
                Your raw Style DNA never leaves your machine — only the curated, anonymized snapshot
                you choose to share gets pushed to Firestore.
              </p>
              <div className="sync-list">
                {[
                  "🔒 Local SQLite → Firestore (one-way sync)",
                  "🌍 Global Market Catalog from JSON → Firestore",
                  "⚡ Python firebase-admin CLI tool",
                  "🚫 No direct ai_stylo/ imports from cloud code",
                ].map((item) => (
                  <div key={item} className="sync-list-item">
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="sync-terminal-wrapper">
              <div className="card sync-terminal-block">
                <div className="term-line-green">$ python sync_connector.py</div>
                <div className="term-line-muted">
                  --catalog{" "}
                  <span className="term-comment"># Push catalog to Firestore</span>
                </div>
                <div className="term-line-muted-mt">
                  --dna --user-id alex{" "}
                  <span className="term-comment"># Sync Style DNA</span>
                </div>
                <div className="term-line-purple-mt">
                  [SYNC] ✅ Catalog synced: 247 items
                </div>
                <div className="term-line-purple">
                  [SYNC] ✅ Style DNA synced for 'alex'
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function AuthModal({ onClose, onLogin }: { onClose: () => void; onLogin: () => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError("");
    try {
      await signInWithPopup(auth, googleProvider);
      onLogin();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Auth error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="auth-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="card auth-card auth-modal-card">
        <button
          onClick={onClose}
          className="auth-close-btn"
        >
          ✕
        </button>
        <div className="auth-header-sec">
          <div className="auth-icon">🧬</div>
          <h2 className="auth-title">Welcome to AI-Stylo</h2>
          <p className="auth-subtitle">Sign in to access your Style DNA in the cloud</p>
        </div>

        <button id="google-signin-btn" className="btn google-btn" onClick={handleGoogleLogin} disabled={loading}>
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" />
            <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z" />
            <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.55 0 9s.348 2.825.957 4.039l3.007-2.332z" />
            <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z" />
          </svg>
          Continue with Google
        </button>

        {error && <p className="auth-error">{error}</p>}

        <div className="divider">or</div>

        <div className="auth-footer">
          📖 First time here?{" "}
          <a href="#sync" onClick={onClose} className="auth-link">
            Learn how to sync your local Style DNA →
          </a>
        </div>
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
function App() {
  const [showAuth, setShowAuth] = useState(false);
  const [activeTab, setActiveTab] = useState<'home' | 'advisor'>('home');
  const [user, setUser] = useState<User | null>(null);

  const handleSignOut = async () => {
    await signOut(auth);
    setUser(null);
  };

  return (
    <>
      <Navbar
        onLogin={() => setShowAuth(true)}
        onAdvisor={() => setActiveTab(activeTab === 'advisor' ? 'home' : 'advisor')}
        activeTab={activeTab}
        user={user}
        onSignOut={handleSignOut}
      />

      {activeTab === 'home' ? (
        <>
          <Hero onLogin={() => setShowAuth(true)} />
          <Features />
          <SyncSection />
        </>
      ) : (
        <div className="advisor-page">
          <StyleAdvisor />
        </div>
      )}

      <footer className="footer">
        <div className="container">
          <p>
            🧬 AI-Stylo Firebase · Built with ❤️ by <span className="gradient-text">AleeexTk & SergeyJohnvikovich</span>
          </p>
          <p className="footer-subtext">
            Autonomous cloud twin of AI-Stylo — the Personal Fashion OS
          </p>
        </div>
      </footer>

      {showAuth && <AuthModal onClose={() => setShowAuth(false)} onLogin={() => setUser(auth.currentUser)} />}
    </>
  );
}

export default App;
