"""
Auditor validation node.

The second of three validation nodes in the MediAssist validation pipeline.
The Auditor answers one question:

    Is every diagnosis's evidence actually traceable to the retrieved
    Standard Treatment Guidelines (STG) chunks?

It catches HALLUCINATED EVIDENCE — the failure mode where an LLM produces
a quote-shaped sentence that looks like it came from the STG but is in
fact invented. This is the highest-stakes failure in clinical AI: a
doctor reading a confident citation has no way to know it is fabricated
until they manually check the source. The Auditor is the defence.

This is a NOVEL implementation in the MediAssist project — it is not
present in standard LLM-pipeline frameworks. The Phase 7 evaluation
report should highlight it as a primary contribution of Role 3.

Algorithm (intentionally simple — transparent rather than clever):

    1. Concatenate all retrieved chunks into one lowercased corpus.
    2. For each DiagnosisItem, tokenise its `evidence` field into words.
    3. Filter to "distinctive" words — at least 6 characters long. This
       drops common short words ("the", "and", "with", "fever") that
       appear in any medical text and would inflate overlap scores.
    4. Count how many distinctive words appear somewhere in the corpus
       (substring match — credits the LLM for legitimate paraphrasing
       like "fever" → "feverish", "malaria" → "antimalarial").
    5. If fewer than MIN_OVERLAP distinctive words match, the evidence
       is flagged as weakly grounded.

The function returns True only if EVERY diagnosis is sufficiently grounded.
A False return tells the orchestrator that one or more diagnoses are
suspected hallucinations; the orchestrator decides whether to substitute
FALLBACK_RESPONSE, drop the offending diagnoses, or lower overall
confidence. That policy is set in main.py, not here — keeping the Auditor
focused on detection rather than remediation.

Position in the validation pipeline:

    Gatekeeper  ──→ JSON valid? Schema correct?
    Auditor     ──→ Every diagnosis grounded in STG?      ← THIS FILE
    Strategist  ──→ Probabilities sensible? Coherent?

Known limitations (acknowledged for honest evaluation in Phase 7):
    - False positives:  legitimate paraphrasing may share fewer than 3
                        distinctive words with the source.
    - False negatives:  evidence that is mostly fabricated but reuses 3
                        clinically common terms slips through.
    - English-only:     word-overlap matching does not handle mixed-
                        language evidence; Swahili was explicitly out
                        of scope per project requirements.
"""

from typing import List

from shared.schemas import DiagnosticResponse


# Minimum number of distinctive evidence-words that must appear in the
# corpus for grounding to be considered acceptable. Conservative: lower
# would accept fabricated evidence; higher would reject legitimate
# paraphrasing. Three is the threshold suggested by Stage 5.2 of the
# reference document.
MIN_OVERLAP = 3

# Minimum word length to count as "distinctive". Words shorter than this
# tend to be common across all medical text (function words, very common
# stems) and would inflate the overlap score with non-meaningful matches.
# Length ≥ 6 captures clinically specific terms: "malaria", "diagnosis",
# "headache", "presents", "guidelines", etc.
MIN_DISTINCTIVE_WORD_LENGTH = 6


def audit_grounding(
    response: DiagnosticResponse,
    retrieved_chunks: List[str],
) -> bool:
    """
    Verify every diagnosis's evidence is grounded in the retrieved STG.

    Args:
        response:         A validated DiagnosticResponse from the Gatekeeper.
        retrieved_chunks: The STG passages returned by Willard's RAG
                          pipeline. Each entry is a raw guideline-text
                          string. Order does not matter — we concatenate.

    Returns:
        True  — every diagnosis passed the grounding check.
        False — at least one diagnosis was weakly grounded; the names of
                the affected conditions are printed for live observation
                and Phase 7 metric collection.
    """
    # Build the searchable corpus once. Lowercasing here means we can do
    # case-insensitive substring matching without per-word .lower() calls
    # in the inner loop.
    corpus = " ".join(retrieved_chunks).lower()

    weakly_grounded: List[str] = []

    for diagnosis in response.diagnoses:
        # Tokenise the evidence string. .split() with no argument splits on
        # any whitespace and discards empty entries — exactly what we want.
        # Using a set deduplicates: a word that appears 5 times in evidence
        # only counts once toward the overlap.
        evidence_words = set(diagnosis.evidence.lower().split())

        # Keep only distinctive words. Short words ("the", "and", "fever")
        # appear in nearly every medical chunk; counting them would mean
        # any evidence that uses three common words trivially passes.
        distinctive_words = {
            word
            for word in evidence_words
            if len(word) >= MIN_DISTINCTIVE_WORD_LENGTH
        }

        # Substring match credits paraphrasing: "feverish" in evidence
        # matches "fever" in corpus. This is intentionally generous —
        # the cost of a false negative (missed hallucination) is higher
        # than a false positive (unfair rejection). We chose the generous
        # side knowing it lowers our hallucination-detection rate; that
        # is a documented trade-off for Phase 7.
        overlap_count = sum(1 for word in distinctive_words if word in corpus)

        if overlap_count < MIN_OVERLAP:
            weakly_grounded.append(diagnosis.condition)

    if weakly_grounded:
        # All offending conditions on one line — grep-friendly for the
        # benchmark script that counts hallucinations per provider.
        print(
            "[Auditor] WEAK GROUNDING: "
            + ", ".join(weakly_grounded)
        )
        return False

    print(
        f"[Auditor] PASSED — all {len(response.diagnoses)} diagnosis(es) grounded."
    )
    return True
