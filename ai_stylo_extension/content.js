// content.js
// Extract Stylescape items: /catalog/:id + image (decode _next/image) + url
// Works for Next.js SPA pages (MutationObserver)

function decodeNextImageUrl(src) {
  try {
    // Next.js image optimization looks like: /_next/image?url=<ENCODED>&w=...&q=...
    const u = new URL(src, location.origin);
    if (!u.pathname.includes("/_next/image")) return src;

    const encoded = u.searchParams.get("url");
    if (!encoded) return src;

    // encoded may be percent-encoded; decode once
    const decoded = decodeURIComponent(encoded);

    // decoded can be absolute (https://...) or relative (/something)
    if (decoded.startsWith("http://") || decoded.startsWith("https://")) return decoded;
    return new URL(decoded, location.origin).toString();
  } catch (e) {
    return src; // fallback
  }
}

function extractCatalogIdFromHref(href) {
  try {
    // Accept both absolute and relative
    const u = new URL(href, location.origin);
    const m = u.pathname.match(/^\/(uk\/)?catalog\/([^/?#]+)/i);
    if (!m) return null;
    return m[2];
  } catch {
    return null;
  }
}

function findBestImageNearLink(aEl) {
  // Heuristic: check images inside the same card/container
  // 1) inside link
  const imgInLink = aEl.querySelector("img");
  if (imgInLink?.getAttribute("src")) return imgInLink.getAttribute("src");

  // 2) closest card-like container
  const card = aEl.closest("article, li, div, section");
  if (!card) return null;

  // Prefer first visible img with src
  const imgs = Array.from(card.querySelectorAll("img"))
    .map((img) => img.getAttribute("src"))
    .filter(Boolean);

  return imgs[0] || null;
}

function collectItems() {
  const links = Array.from(document.querySelectorAll('a[href*="/catalog/"]'));
  const itemsById = new Map();

  for (const a of links) {
    const href = a.getAttribute("href") || "";
    const id = extractCatalogIdFromHref(href);
    if (!id) continue;

    const absUrl = new URL(href, location.origin).toString();
    const imgSrc = findBestImageNearLink(a);
    const originalImg = imgSrc ? decodeNextImageUrl(imgSrc) : null;

    // Keep the first found, but prefer entries with images
    const prev = itemsById.get(id);
    if (!prev || (!prev.image && originalImg)) {
      itemsById.set(id, {
        merchant: "stylescape",
        id,
        url: absUrl,
        image: originalImg,
      });
    }
  }

  return Array.from(itemsById.values());
}

function sendItems(items) {
  chrome.runtime.sendMessage({
    type: "STYLO_ITEMS_EXTRACTED",
    payload: {
      pageUrl: location.href,
      items,
      ts: Date.now(),
    },
  });
}

let debounceTimer = null;
function scheduleScan() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const items = collectItems();
    if (items.length > 0) {
        sendItems(items);
    }
  }, 350);
}

// Initial scan
scheduleScan();

// SPA / dynamic updates
const mo = new MutationObserver(() => scheduleScan());
mo.observe(document.documentElement, { childList: true, subtree: true });

// Also react to URL changes (Next.js navigation)
let lastHref = location.href;
setInterval(() => {
  if (location.href !== lastHref) {
    lastHref = location.href;
    scheduleScan();
  }
}, 500);
