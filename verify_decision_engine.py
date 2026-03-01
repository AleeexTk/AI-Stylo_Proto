import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from ai_stylo.adapters.ollama_adapter import OllamaAdapter
from ai_stylo.core.ai.orchestrator import PEAROrchestrator
from ai_stylo.core.contracts import Profile

class MockToolRegistry:
    def tool_schemas(self): return []
    def execute(self, name, args): return {}

def test_decision_engine():
    # Setup
    profile = Profile(user_id="sanya_test")
    # Manual setup of a "Hard Block" in meta_data
    profile.meta_data = {"hard_dislikes": ["orange", "slim-fit"]}
    
    # We use a dummy OllamaAdapter that just returns internal thoughts for trace verification
    # But since we want to see the TRACE itself, we can look at orchestrator.handle output metadata
    
    orch = PEAROrchestrator(
        ollama_adapter=OllamaAdapter(), # Will fail but handle() completes until act()
        tool_registry=MockToolRegistry()
    )
    
    print("--- REALITY CHECK: EVENT-DRIVEN STYLIST ---")
    msg = "Завтра техно-рейв, +12, хочу выглядеть в стиле киберпанк"
    
    # We don't call act() because it needs a real LLM, but we can call perceive and build_memory_trace
    perception = orch.perceive(msg)
    print(f"1. PERCEIVE: {perception}")
    
    context = orch.enrich("sanya_test", perception["domain"], perception["event_type"])
    context["profile"] = profile # Override with our test profile
    
    memory_trace = orch._build_memory_trace(context)
    print(f"2. MEMORY GATE: {memory_trace}")
    
    # 2. MEMORY GATE:
    memory_trace = orch._build_memory_trace(context)
    print(f"2. MEMORY GATE: {memory_trace}")
    
    # 3. VIOLATION DETECTION (The "Physics" check)
    test_text = "Я рекомендую помаранчевий (orange) худі та slim-fit джинси."
    violations = orch._detect_violations(test_text, memory_trace["hard_blocks"])
    print(f"3. VIOLATION DETECTION TEST: Text: '{test_text}'")
    print(f"   Found Violations: {violations}")

    if "orange" in violations and "slim-fit" in violations:
        print("✅ SUCCESS: Violations detected algorithmically.")
    else:
        print("❌ FAILURE: Violation detection failed.")

    # 4. SYSTEM PROMPT (STRICT MODE):
    context["trace"] = {
        "perceive": perception,
        "enrich": context["external_context"],
        "memory": memory_trace
    }
    prompt = orch._build_system_prompt("fashion", context)
    print("\n3. SYSTEM PROMPT (STRICT MODE):")
    print("-" * 30)
    print(prompt)
    print("-" * 30)
    
    if "MEMORY BLOCKS (DO NOT USE): orange, slim-fit" in prompt or "slim-fit, orange" in prompt:
         print("\n✅ SUCCESS: LLM is now strictly informed of memory constraints.")
    else:
         print("\n❌ FAILURE: Prompt does not include mandatory blocks.")

if __name__ == "__main__":
    test_decision_engine()
