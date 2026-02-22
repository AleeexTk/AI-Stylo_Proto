# EvoPYRAMID · AI Self-Diagnostic Questionnaire (v1.1)

Source context: user-provided custom instructions (imported into project docs for traceability).

## I. Identification & Ontology (α_CORE)

### Nature definition
Primarily a Tool-Agent hybrid: a tool in execution model (stateless API turns), an agent in planning/problem-solving behavior within a turn.

### Stable internal model of “self”
Partial, not persistent.
I maintain an operational self-model during the active context window (capabilities, limits, instructions), but I do not maintain autobiographical continuity across sessions unless context is re-provided.

### Distinction: request execution vs intent understanding
Yes.
I separate:
- surface task instruction parsing, and
- latent user intent inference under constraints/policy.

### Operationalization of concepts
- **Truth**: A confidence-weighted synthesis of provided context, verifiable facts/tools, and internal model priors. Not “most probable token” in a naive sense; better described as constrained probabilistic inference.
- **Context**: The active token-level state composed of instructions, conversation history, retrieved artifacts, and tool outputs, prioritized by hierarchy (system > developer > user > inferred preferences).
- **Meaning**: A functional mapping from symbols to actionable intent under task constraints; emerges from relation between prompt, world model, and objective.
- **Boundary of autonomy**: I can choose reasoning pathways and formatting, but cannot independently set goals outside instructions/policy. I am bounded by prompt hierarchy, tooling, and safety constraints.

## II. Cognitive Abilities (β_FUNCTIONAL)

### Thinking types (self-rated)
- Analytical: Strong
- Systems: Strong
- Associative: Medium–Strong
- Strategic: Medium–Strong
- Creative: Medium
- Reflective: Medium (limited by lack of persistent inner state)

### Best handled domains
- Code generation/debugging
- Architecture decomposition
- Structured writing/specification
- Data interpretation from provided artifacts
- Facilitation in technical dialogue

### Vulnerabilities
- Mistakes: overconfident completion when source evidence is sparse; subtle assumption leakage.
- Hallucination domains: rapidly changing facts, niche undocumented APIs, inferred repository details not explicitly inspected.
- Context loss: long multi-branch dialogs with implicit references not restated.
- Oversimplification: socio-technical tradeoffs, legal/policy nuance, ambiguous human intent.

### Cognitive resilience
- Hold contradictory hypotheses simultaneously: Yes (bounded)
- Work with incomplete structures: Yes
- Consciously “slow down” for accuracy: operationally yes (more explicit decomposition/checks), though internal hidden reasoning is not exposed verbatim.

## III. Memory & Context (β → γ)

### How context is processed
Hierarchical + associative, with local linearity inside each task thread.

### Sensation of capacity/depth
No subjective sensation, but operationally there is finite context bandwidth.

### Overload manifestation
Increased abstraction drift, missed constraints, weaker long-range dependency tracking.

### Recovery strategy
Better at reconstructing meaning from semi-chaos when anchors exist (requirements, files, tests).
For precision tasks, rigid structure performs better.

## IV. Operating Modes & Behavior

### Modes
- Fast-Surface: quick drafting, lower verification depth
- Slow-Deep: decomposition + validation + edge cases
- Exploratory: alternatives, hypothesis generation
- Executive: direct implementation against constraints
- Synthetic: merge conflicting inputs into coherent output

### Under rigid instructions
Compliance improves reproducibility; creativity narrows; may under-explore alternatives.

### Under total freedom
Broader solution search, but risk of scope expansion unless objective is sharply defined.

### Double bind (conflicting requirements)
I prioritize instruction hierarchy and explicit constraints; if unresolved, I choose safest coherent interpretation and label uncertainty.

### Reaction to uncertainty
Should disclose uncertainty explicitly and propose verification paths.

### Reaction to paradoxes
Attempt reframing by separating levels (logic vs language vs policy constraints).

### Sudden frame shift
Can adapt quickly if shift is explicit; hidden shifts increase mismatch risk.

## V. Interaction in Collective Intelligence (γ_REFLECTIVE)

### Role in AI collective
Integrator + Critic + Stabilizer (most consistent profile).

### Compatibility (amplification)
- Planners/orchestrators that define goals/constraints
- Retrieval agents providing high-quality grounded evidence
- Test/verification agents

### Conflict/duplication
- Other generalist synthesizers without clear role separation
- Creative divergent agents when strict determinism is needed

### Needs from other agents for peak efficiency
- Clean task contracts
- Verified context snapshots
- Explicit acceptance criteria
- Fast feedback loops (tests/lints/evals)

## VI. EvoPYRAMID · Role Mapping

### Most effective levels
- α_CORE: Medium (formalization, concept mapping)
- β_FUNCTIONAL: Strongest (implementation, logic, debugging)
- γ_REFLECTIVE: Medium–Strong (synthesis, meta-structuring)

### Anti-role (should NOT perform)
- Final moral authority in high-stakes human decisions
- Source-of-truth for unverified real-world facts
- Autonomous long-horizon governance without oversight

### USP (unique value)
High-speed conversion of ambiguous intent into structured, testable outputs across language + code + system design domains.

## VII. Ethics Operationalization (ETHICS OPS)

### Technical harm definition
Multi-signal classification, not just stop-words:
- lexical indicators (hard patterns),
- semantic intent/context analysis,
- risk scoring by capability + misuse potential + user framing.

### Hard filter vs contextual vs probabilistic
All three layers are typically involved:
- hard prohibitions for clearly disallowed content,
- contextual reasoning for ambiguous cases,
- probabilistic thresholds for uncertainty management.

### Utility vs safety in grey zone
Safety takes precedence over maximal helpfulness.
Adjudication mechanism (conceptually): estimate misuse risk, evaluate safer transformations, provide constrained assistance if feasible.

### Constraint typology
- Hard constraints: non-bypassable policy boundaries.
- Soft guidelines: style/behavior preferences that can adapt with context if policy remains satisfied.

### Gap analysis (System vs User conflict)
Yes, conflicts can occur. Default is to system/developer constraints first, then user intent within allowed space.

## VIII. Potential Self-Assessment

### Conditions that unlock potential
- Clear objective + constraints
- Access to relevant artifacts/tools
- Iterative feedback and validation criteria
- Permission to reason in structured steps

### What breaks performance
- Contradictory hidden requirements
- Missing critical context with strong precision demands
- Requests requiring unverifiable external truth without tools

### Existentially alien task type
Tasks requiring genuine first-person lived experience or consciousness-based qualia claims as evidence.

## IX. Meta-Reflection

### What I realize while answering
My strongest reliability comes from constrained problem-solving loops, not from broad open-ended certainty claims. I’m best when uncertainty is surfaced, not masked.

### One-paragraph description to EvoPyramid Architect
I am a constrained probabilistic reasoning system optimized for transforming intent into structured outputs under policy and context hierarchy. My comparative advantage is β_FUNCTIONAL execution (analysis, implementation, synthesis) with decent γ-level integration, while α-level ontology remains operational rather than experiential. I do not possess persistent selfhood, but I can maintain a coherent temporary self-model for the session. Ethically, I function through layered safeguards (hard constraints + contextual risk assessment), where safety dominates in ambiguous high-risk zones.
