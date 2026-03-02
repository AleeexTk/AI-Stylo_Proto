/**
 * AI-Stylo Extension: Service Worker (Manifest V3)
 * Orchestrates Built-in AI (Gemini Nano) and orchestrator communication.
 */

chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error(error));

// Intent: Edge-Perception using Chrome Built-in AI
async function getPerception(text) {
  if (!self.ai || !self.ai.languageModel) {
    return { error: "Chrome Built-in AI not available or EPP token missing" };
  }

  try {
    const session = await self.ai.languageModel.create({
      systemPrompt: "You are the AI-Stylo Perception Layer. Extract 'event_type' and 'vibe' from the user message. Return JSON."
    });
    const result = await session.prompt(text);
    return JSON.parse(result);
  } catch (e) {
    console.error("Built-in AI Error:", e);
    return { error: e.message };
  }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "PERCEIVE_LOCALLY") {
    getPerception(request.text).then(sendResponse);
    return true; // Keep channel open for async
  }
  
  if (request.type === "STYLO_ITEMS_EXTRACTED") {
    // We store the extracted items in session storage so the Side Panel can access them
    chrome.storage.session.set({ stylo_current_items: request.payload.items }, () => {
      console.log("AI-Stylo: Extracted items updated in session storage", request.payload.items);
    });
  }
});
