"""
expansion/synonyms.py
---------------------
Stage 4.2 — Medical Synonym & Abbreviation Resolution

A rule-based expander that maps Tanzanian clinical shorthand and lay
terms to full clinical vocabulary before embedding.

Why this matters:
    A doctor types: "patient has fits and high temp"
    The STG says:   "Febrile Seizures — convulsions with pyrexia"
    Without expansion, cosine similarity may be too low to retrieve it.

Adding to the dictionary:
    Look up terms at:
    - UMLS: https://uts.nlm.nih.gov/uts/umls/home
    - MedlinePlus: https://medlineplus.gov
    Then add entries to SYNONYM_MAP below.
"""

from __future__ import annotations
import re

# ── Core synonym/abbreviation map ─────────────────────────────────────────────
# Keys: common doctor shorthand, lay terms, or Swahili-influenced terms.
# Values: expanded clinical equivalents.
#
# FORMAT RULE: expand to the most specific clinical term first,
#              then include common synonyms separated by " or ".
SYNONYM_MAP: dict[str, str] = {
    # Symptoms — temperature
    "temp":         "fever or pyrexia",
    "high temp":    "fever or pyrexia or hyperthermia",
    "febrile":      "fever or pyrexia",
    "hot":          "fever or elevated temperature",

    # Symptoms — neurological
    "fits":         "convulsions or seizures or epileptic episode",
    "fit":          "convulsion or seizure",
    "shaking":      "tremors or convulsions or rigors",
    "confused":     "altered consciousness or disorientation or encephalopathy",
    "unconscious":  "loss of consciousness or unresponsive or comatose",
    "coma":         "comatose or unconscious or unresponsive",
    "stiff neck":   "neck stiffness or nuchal rigidity or meningismus",
    "headache":     "cephalgia or headache or head pain",
    "dizzy":        "dizziness or vertigo or light-headedness",

    # Symptoms — respiratory
    "SOB":          "shortness of breath or dyspnea or difficulty breathing",
    "short of breath": "dyspnea or shortness of breath",
    "cough":        "cough or tussis",
    "wet cough":    "productive cough or cough with sputum",
    "dry cough":    "non-productive cough or dry cough",
    "chest pain":   "chest pain or thoracic pain or pleuritis",
    "wheezing":     "wheezing or bronchospasm or stridor",

    # Symptoms — gastrointestinal
    "stomach pain": "abdominal pain or epigastric pain",
    "tummy ache":   "abdominal pain",
    "vomiting":     "vomiting or emesis or nausea with vomiting",
    "throwing up":  "vomiting or emesis",
    "diarrhoea":    "diarrhoea or loose stools or gastroenteritis",
    "diarrhea":     "diarrhoea or loose stools",
    "loose stool":  "diarrhoea or loose stools",
    "bloating":     "abdominal distension or bloating or flatulence",
    "jaundice":     "jaundice or icterus or yellow skin or hyperbilirubinaemia",

    # Symptoms — cardiovascular
    "fast heart":   "tachycardia or rapid heart rate",
    "racing heart": "palpitations or tachycardia",
    "chest tight":  "chest tightness or angina or dyspnea",
    "swollen legs": "oedema or pedal oedema or leg swelling",
    "swelling":     "oedema or swelling",

    # Symptoms — musculoskeletal
    "joint pain":   "arthralgia or joint pain",
    "back pain":    "back pain or lumbar pain or dorsalgia",
    "body aches":   "myalgia or body aches or generalised pain",
    "muscle pain":  "myalgia or muscle pain",
    "can't walk":   "inability to ambulate or mobility impairment or paralysis",
    "weakness":     "weakness or fatigue or asthenia",
    "tired":        "fatigue or lethargy or weakness",

    # Symptoms — skin & eyes
    "rash":         "skin rash or dermatitis or exanthem",
    "itchy":        "pruritus or itching",
    "yellow eyes":  "icterus or scleral jaundice or jaundice",
    "red eyes":     "conjunctivitis or eye redness",
    "pale":         "pallor or anaemia or paleness",

    # Symptoms — urinary
    "pain urinating": "dysuria or painful urination",
    "UTI":          "urinary tract infection or dysuria",
    "blood in urine": "haematuria or blood in urine",

    # Common abbreviations
    "BP":   "blood pressure",
    "HR":   "heart rate",
    "RR":   "respiratory rate",
    "Temp": "temperature",
    "Hb":   "haemoglobin",
    "Hgb":  "haemoglobin",
    "WBC":  "white blood cells or leucocytes",
    "RBC":  "red blood cells or erythrocytes",
    "IV":   "intravenous",
    "IM":   "intramuscular",
    "SC":   "subcutaneous",
    "PO":   "oral or by mouth",
    "PRN":  "as needed",
    "O2":   "oxygen saturation",
    "SpO2": "oxygen saturation",
    "Hx":   "history",
    "Dx":   "diagnosis",
    "Rx":   "prescription or treatment",

    # Tanzania-specific common presentations
    "malaria symptoms": "fever, chills, rigors, headache, myalgia, malaria",
    "typhoid":          "enteric fever or typhoid fever or Salmonella typhi",
    "TB":               "tuberculosis or pulmonary tuberculosis or Mycobacterium tuberculosis",
    "HIV":              "HIV or human immunodeficiency virus or immunodeficiency",
    "pneumonia":        "pneumonia or lower respiratory tract infection or lobar pneumonia",
}

# Sort keys by descending length so longer phrases match before sub-phrases
_SORTED_KEYS = sorted(SYNONYM_MAP.keys(), key=len, reverse=True)


def expand_with_synonyms(query: str) -> str:
    """
    Replace known abbreviations and lay terms with clinical equivalents.

    Strategy: whole-word replacement to avoid false matches.
    Example:
        "patient has fits and high temp" →
        "patient has convulsions or seizures or epileptic episode
         and fever or pyrexia or hyperthermia"

    Args:
        query: Preprocessed symptom description.

    Returns:
        Expanded query string (may be longer than the input).
    """
    result = query
    for key in _SORTED_KEYS:
        # Word-boundary match, case-insensitive
        pattern = r'\b' + re.escape(key) + r'\b'
        replacement = SYNONYM_MAP[key]
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def get_dictionary() -> dict[str, str]:
    """Return a copy of the full synonym map (for inspection/testing)."""
    return dict(SYNONYM_MAP)