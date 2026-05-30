"""
MediAssist Role 3 — pipeline orchestrator.

Composes every component in Role 3 (Query Planner → Provider → Gatekeeper →
Auditor → Calibrator → Strategist) into a single function:
    run_mediassist_pipeline(symptoms, retrieved_chunks) -> DiagnosticResponse

Failure handling: every stage substitutes FALLBACK_RESPONSE on failure. The
function NEVER raises, NEVER returns None. This is the patient-safety property.

What changed vs the prototype:
    * Provider is constructed once via the lru_cache in factory.get_llm_provider
      instead of per request — saves 50-200 ms per call.
    * The blocking health-check before generation has been removed. Health is
      verified at FastAPI startup; per-request, if the model is genuinely down
      we let provider.generate() raise and catch it below.
    * SYSTEM_PROMPT is the same — both Ollama JSON mode and OpenAI JSON mode
      still benefit from the schema-in-prompt because the providers enforce
      *parseability*, not *schema compliance*.
"""

from typing import List

from role3_llm.calibration import calibrate_probabilities
from role3_llm.factory import get_llm_provider
from role3_llm.parser import FALLBACK_RESPONSE
from role3_llm.token_counter import count_tokens
from role3_llm.validation.auditor import audit_grounding
from role3_llm.validation.gatekeeper import gatekeeper_check
from role3_llm.validation.sanitizer import sanitize_response
from role3_llm.validation.strategist import strategist_check
from shared.schemas import DiagnosisItem, DiagnosticResponse


# Input-token ceiling. mistral:7b-instruct has 8k context; gpt-4o-mini has
# 128k; llama3.2:3b has 128k. 7000 is the safe lower bound that works for
# every supported model. We reserve ~512 tokens for the LLM's output (see the
# max_tokens cap on provider.generate below).
MAX_INPUT_TOKENS = 7000


SYSTEM_PROMPT = """You are a clinical decision support assistant for \
Tanzanian healthcare facilities.

Your task: receive patient symptoms and excerpts from the Tanzania \
Standard Treatment Guidelines (STG), then produce a structured \
differential diagnosis.

Rules (follow ALL of them — output that breaks any rule is rejected):
- Reason ONLY from the provided STG excerpts. Do not use general medical \
knowledge from your training data.
- List the TOP 1 to 3 diagnoses, ranked by likelihood (rank 1 = most likely). \
Include a diagnosis ONLY if you can support it with a quote from the excerpts. \
Do NOT invent a candidate you cannot ground — omit it instead.
- Every diagnosis MUST have a non-empty `reasoning` (one concise sentence, \
about 20 words) AND a non-empty `evidence` field containing a SHORT exact \
quote copied verbatim from the excerpts (at most ~15 words; copy exactly, do \
NOT paraphrase, never leave it empty).
- The `probability` values across all listed diagnoses MUST add up to exactly 100.
- `follow_up_questions` MUST contain at least 2 questions and `recommended_tests` \
at least 1 test. Neither list may be empty.

Respond with ONLY valid JSON in this exact schema:

{
  "diagnoses": [
    {
      "rank": 1,
      "condition": "Disease name",
      "probability": 70,
      "reasoning": "One concise sentence on why these symptoms suggest this.",
      "evidence": "A short exact quote copied verbatim from the excerpts.",
      "source_section": "Section name from the STG"
    }
  ],
  "follow_up_questions": ["Question 1", "Question 2"],
  "recommended_tests": ["Test 1", "Test 2"],
  "confidence_overall": "low" | "medium" | "high"
}

Do NOT include markdown code fences, explanations, or any text outside \
the JSON object."""


def assemble_messages(symptoms: str, guidelines_text: str) -> List[dict]:
    user_message = (
        f"Patient symptoms: {symptoms}\n\n"
        f"Relevant STG excerpts:\n{guidelines_text}\n\n"
        f"Provide a ranked differential diagnosis in the required JSON format."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def _calibrate(response: DiagnosticResponse) -> DiagnosticResponse:
    diagnosis_dicts = [diagnosis.model_dump() for diagnosis in response.diagnoses]
    calibrated_dicts = calibrate_probabilities(diagnosis_dicts)
    return response.model_copy(
        update={"diagnoses": [DiagnosisItem(**d) for d in calibrated_dicts]}
    )


def run_mediassist_pipeline(
    symptoms: str,
    retrieved_chunks: List[str],
) -> DiagnosticResponse:
    # 1. Query Planner
    guidelines_text = "\n\n".join(retrieved_chunks)
    messages = assemble_messages(symptoms, guidelines_text)

    # 2. Token budget
    token_count = count_tokens(messages)
    if token_count > MAX_INPUT_TOKENS:
        print(
            f"[Pipeline] Token count {token_count} exceeds budget "
            f"{MAX_INPUT_TOKENS} — returning fallback."
        )
        return FALLBACK_RESPONSE

    # 3. LLM generation (provider is cached; health was checked at startup)
    provider = get_llm_provider()
    print(
        f"[Pipeline] Sending {token_count} tokens to "
        f"{provider.get_provider_name()}..."
    )
    try:
        # Cap output at 512 tokens: a concise top-3 differential fits well under
        # this, and on CPU the generation time is ~linear in tokens produced, so
        # the cap directly bounds worst-case latency.
        raw_text = provider.generate(messages, max_tokens=512)
    except Exception as exc:
        print(
            f"[Pipeline] {provider.get_provider_name()}.generate() raised "
            f"{type(exc).__name__}: {exc} — returning fallback."
        )
        return FALLBACK_RESPONSE

    # 3b. Sanitizer — drop unusable (e.g. empty-evidence) diagnoses and
    # renormalise probabilities BEFORE the strict gate, so one malformed item
    # does not sink an otherwise-valid, grounded response.
    raw_text = sanitize_response(raw_text)
    if raw_text is None:
        return FALLBACK_RESPONSE

    # 4. Gatekeeper (parse + schema validate)
    response = gatekeeper_check(raw_text)
    if response is None:
        return FALLBACK_RESPONSE

    # 5. Auditor (grounding)
    if not audit_grounding(response, retrieved_chunks):
        return FALLBACK_RESPONSE

    # 6. Calibration (renormalise probabilities)
    response = _calibrate(response)

    # 7. Strategist (coherence)
    pipeline_confidence = strategist_check(response)
    if pipeline_confidence is None:
        return FALLBACK_RESPONSE

    return response.model_copy(update={"pipeline_confidence": pipeline_confidence})
