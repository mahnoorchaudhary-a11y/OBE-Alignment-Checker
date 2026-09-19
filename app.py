import streamlit as st
import pandas as pd
import re
import io
import os
from pathlib import Path

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# SESSION STATE
# ============================================================

if "evaluated_questions" not in st.session_state:
    st.session_state.evaluated_questions = []

if "applied_revisions" not in st.session_state:
    st.session_state.applied_revisions = {}

if "revision_cache" not in st.session_state:
    st.session_state.revision_cache = {}


# ============================================================
# BASIC TEXT UTILITIES
# ============================================================

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on",
    "for", "from", "with", "by", "at", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "into", "through", "during", "using", "use",
    "their", "they", "them", "he", "she", "his", "her", "you",
    "your", "we", "our", "can", "could", "should", "would", "will",
    "may", "might", "do", "does", "did", "how", "what", "why",
    "when", "where", "which", "who", "whom", "than", "then",
    "also", "such", "each", "any", "all", "both", "more", "most",
    "some", "many", "much", "given", "following", "based"
}


def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words(text):
    return [
        w for w in normalize(text).split()
        if w and w not in STOPWORDS and len(w) > 2
    ]


def simple_stem(word):
    word = word.lower()

    endings = [
        "ization",
        "ations",
        "ation",
        "ments",
        "ment",
        "ingly",
        "edly",
        "ing",
        "edly",
        "ies",
        "es",
        "ed",
        "ly",
        "s"
    ]

    for ending in endings:
        if len(word) > len(ending) + 3 and word.endswith(ending):
            return word[:-len(ending)]

    return word


def stem_set(text):
    return {
        simple_stem(w)
        for w in words(text)
        if len(simple_stem(w)) > 2
    }


def overlap_score(text1, text2):
    a = stem_set(text1)
    b = stem_set(text2)

    if not a or not b:
        return 0

    intersection = a.intersection(b)

    if not intersection:
        return 0

    precision = len(intersection) / len(a)
    recall = len(intersection) / len(b)

    if precision + recall == 0:
        return 0

    f1 = 2 * precision * recall / (precision + recall)

    return round(f1 * 100, 1)


# ============================================================
# QUESTION FORMATTING
# ============================================================

def finalize_question(text):
    """
    Ensures that a generated question has clean terminal punctuation.

    Examples:
    Explain photosynthesis?  -> Explain photosynthesis?
    Explain photosynthesis.  -> Explain photosynthesis?
    Explain photosynthesis?! -> Explain photosynthesis?
    """

    text = clean_text(text)

    text = re.sub(r"[?.!]+$", "", text).strip()

    if not text:
        return ""

    if text.lower().startswith(
        (
            "explain ",
            "describe ",
            "discuss ",
            "compare ",
            "contrast ",
            "analyze ",
            "analyse ",
            "evaluate ",
            "calculate ",
            "identify ",
            "define ",
            "differentiate ",
            "classify ",
            "interpret ",
            "apply ",
            "demonstrate ",
            "design ",
            "develop ",
            "construct ",
            "solve "
        )
    ):
        return text + "?"

    return text + "?"


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    text = clean_text(text)

    # Split on common CLO/PLO numbering patterns
    parts = re.split(
        r"(?:CLO\s*\d+\s*[:\-–.]?|PLO\s*\d+\s*[:\-–.]?|"
        r"\b\d+\s*[\)\].:-])",
        text,
        flags=re.IGNORECASE
    )

    results = []

    for part in parts:
        part = clean_text(part)

        if len(part) >= 8:
            results.append(part)

    # If parsing failed, use line-based parsing
    if not results:
        lines = re.split(r"[\n;]+", text)

        for line in lines:
            line = clean_text(line)

            if len(line) >= 8:
                results.append(line)

    return results


# ============================================================
# BLOOM'S TAXONOMY
# ============================================================

BLOOM_LEVELS = {
    "Remember": [
        "define",
        "list",
        "identify",
        "name",
        "state",
        "recall",
        "recognize"
    ],
    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss"
    ],
    "Apply": [
        "apply",
        "calculate",
        "solve",
        "use",
        "demonstrate",
        "implement"
    ],
    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "compare",
        "contrast",
        "examine",
        "distinguish"
    ],
    "Evaluate": [
        "evaluate",
        "justify",
        "assess",
        "critique",
        "defend",
        "judge"
    ],
    "Create": [
        "design",
        "develop",
        "construct",
        "formulate",
        "create",
        "propose",
        "produce"
    ]
}


BLOOM_ORDER = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]


def detect_bloom(text):
    normalized = normalize(text)

    detected = []

    for level, verbs in BLOOM_LEVELS.items():
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", normalized):
                detected.append(level)
                break

    if not detected:
        return "Understand"

    # Return highest explicitly detected level
    return max(
        detected,
        key=lambda x: BLOOM_ORDER.index(x)
    )


def bloom_score(question, target_level):
    if not target_level:
        return 75

    target_level = clean_text(target_level).title()

    if target_level not in BLOOM_ORDER:
        target_level = detect_bloom(question)

    detected = detect_bloom(question)

    if detected == target_level:
        return 100

    detected_index = BLOOM_ORDER.index(detected)
    target_index = BLOOM_ORDER.index(target_level)

    difference = abs(detected_index - target_index)

    if difference == 1:
        return 80

    if difference == 2:
        return 65

    if difference == 3:
        return 50

    return 40


# ============================================================
# CLO CONCEPT EXTRACTION
# ============================================================

GENERIC_OUTCOME_WORDS = {
    "understand",
    "knowledge",
    "learn",
    "learning",
    "demonstrate",
    "ability",
    "skills",
    "skill",
    "apply",
    "analyze",
    "analyse",
    "evaluate",
    "understand",
    "describe",
    "explain",
    "use",
    "develop",
    "developing",
    "students",
    "student",
    "course",
    "concepts",
    "concept",
    "principles",
    "principle"
}


def extract_clo_concepts(clo):
    tokens = stem_set(clo)

    useful = []

    for token in tokens:
        if token not in GENERIC_OUTCOME_WORDS and len(token) > 3:
            useful.append(token)

    return useful


def concept_phrase_from_clo(clo):
    """
    Extracts meaningful subject content from the CLO.
    """

    original_words = words(clo)

    useful = []

    for word in original_words:
        stem = simple_stem(word)

        if stem not in GENERIC_OUTCOME_WORDS and len(stem) > 3:
            useful.append(word)

    # Preserve original order
    seen = set()
    final_words = []

    for word in useful:
        key = simple_stem(word)

        if key not in seen:
            seen.add(key)
            final_words.append(word)

    return " ".join(final_words[:8])


# ============================================================
# PLO EXTRACTION
# ============================================================

PLO_ACTIONS = {
    "communication": [
        "communicate",
        "present",
        "write",
        "explain",
        "report"
    ],
    "problem solving": [
        "solve",
        "analyze",
        "analyse",
        "identify",
        "evaluate"
    ],
    "teamwork": [
        "collaborate",
        "work",
        "team",
        "cooperate"
    ],
    "ethics": [
        "ethical",
        "ethics",
        "professional",
        "responsible"
    ],
    "technology": [
        "technology",
        "tool",
        "software",
        "technology",
        "digital"
    ],
    "research": [
        "research",
        "investigate",
        "evidence",
        "analyze",
        "analyse"
    ],
    "critical thinking": [
        "analyze",
        "analyse",
        "evaluate",
        "compare",
        "justify"
    ],
    "lifelong learning": [
        "learn",
        "independent",
        "self",
        "learning"
    ]
}


def extract_plo_action(plo):
    normalized = normalize(plo)

    for category, verbs in PLO_ACTIONS.items():
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", normalized):
                return category

    return "problem solving"


def extract_plo_concepts(plo):
    tokens = stem_set(plo)

    generic = {
        "program",
        "programs",
        "outcome",
        "outcomes",
        "professional",
        "student",
        "students",
        "ability",
        "demonstrate",
        "develop",
        "development",
        "skills",
        "skill",
        "knowledge",
        "understanding",
        "learn",
        "learning"
    }

    return [
        t for t in tokens
        if len(t) > 3 and t not in generic
    ]


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

def subject_score(question, subject):
    if not subject or not clean_text(subject):
        return 85

    q_words = stem_set(question)
    s_words = stem_set(subject)

    if not q_words or not s_words:
        return 70

    direct = q_words.intersection(s_words)

    if direct:
        return min(100, 75 + len(direct) * 8)

    # Subject has multiple words and may require conceptual matching
    subject_text = normalize(subject)

    subject_aliases = {
        "computer science": [
            "programming",
            "algorithm",
            "software",
            "computer",
            "code",
            "database",
            "network"
        ],
        "chemistry": [
            "atom",
            "molecule",
            "reaction",
            "acid",
            "base",
            "chemical",
            "compound",
            "bond"
        ],
        "physics": [
            "force",
            "energy",
            "motion",
            "velocity",
            "momentum",
            "electric",
            "magnetic"
        ],
        "mathematics": [
            "equation",
            "function",
            "matrix",
            "derivative",
            "integral",
            "probability",
            "algebra"
        ],
        "biology": [
            "cell",
            "gene",
            "organism",
            "protein",
            "enzyme",
            "ecosystem",
            "dna"
        ],
        "english": [
            "writing",
            "reading",
            "grammar",
            "essay",
            "language",
            "rhetoric",
            "paragraph"
        ],
        "business": [
            "market",
            "management",
            "business",
            "finance",
            "marketing",
            "organization"
        ]
    }

    for key, aliases in subject_aliases.items():
        if key in subject_text:
            if any(alias in normalize(question) for alias in aliases):
                return 90

    return 55


# ============================================================
# CLO ALIGNMENT
# ============================================================

def clo_score(question, clo):
    if not clo:
        return 0

    q_stems = stem_set(question)
    c_stems = stem_set(clo)

    if not q_stems or not c_stems:
        return 0

    overlap = q_stems.intersection(c_stems)

    concepts = set(extract_clo_concepts(clo))
    concept_overlap = q_stems.intersection(concepts)

    if concepts:
        concept_ratio = len(concept_overlap) / max(1, len(concepts))
    else:
        concept_ratio = 0

    overall_ratio = len(overlap) / max(1, len(c_stems))

    score = (
        overall_ratio * 45
        + concept_ratio * 55
    )

    # A meaningful concept match should strongly support attainment.
    if len(concept_overlap) >= 2:
        score += 25

    elif len(concept_overlap) == 1:
        score += 15

    return round(min(100, score), 1)


# ============================================================
# PLO ALIGNMENT
# ============================================================

def plo_score(question, plo):
    if not plo:
        return 0

    normalized_q = normalize(question)
    action = extract_plo_action(plo)

    action_words = PLO_ACTIONS.get(action, [])

    action_match = any(
        re.search(r"\b" + re.escape(word) + r"\b", normalized_q)
        for word in action_words
    )

    plo_concepts = extract_plo_concepts(plo)
    q_stems = stem_set(question)

    concept_match = q_stems.intersection(set(plo_concepts))

    # Generic PLOs should not be punished merely because their
    # wording is abstract.
    if action_match and concept_match:
        return 100

    if action_match:
        return 90

    if concept_match:
        return 85

    # Analytical questions naturally support problem-solving /
    # critical-thinking PLOs.
    if action in ["problem solving", "critical thinking", "research"]:
        bloom = detect_bloom(question)

        if bloom in ["Analyze", "Evaluate", "Create"]:
            return 82

    if action == "communication":
        if any(
            x in normalized_q
            for x in ["explain", "describe", "present", "write", "discuss"]
        ):
            return 82

    return 60


# ============================================================
# SPECIFICITY
# ============================================================

def specificity_score(question):
    q = normalize(question)
    token_count = len(words(question))

    score = 45

    if token_count >= 8:
        score += 15

    if token_count >= 12:
        score += 10

    if token_count >= 16:
        score += 5

    specificity_terms = [
        "using",
        "given",
        "calculate",
        "compare",
        "differentiate",
        "analyze",
        "analyse",
        "explain",
        "describe",
        "identify",
        "evaluate",
        "justify",
        "design",
        "case",
        "example",
        "data",
        "scenario"
    ]

    matches = sum(
        1 for term in specificity_terms
        if re.search(r"\b" + re.escape(term) + r"\b", q)
    )

    score += min(25, matches * 5)

    return round(min(100, score), 1)


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question):
    q = clean_text(question)

    if not q:
        return 0

    score = 50

    if len(q) >= 25:
        score += 10

    if len(q) >= 50:
        score += 10

    if len(words(q)) >= 8:
        score += 10

    if q.endswith("?"):
        score += 10

    # Penalize contradictory terminal punctuation
    if re.search(r"[.!?]{2,}$", q):
        score -= 20

    # Avoid vague wording
    vague = [
        "write something about",
        "say something about",
        "discuss anything",
        "what do you know about",
        "tell me about"
    ]

    if any(v in normalize(q) for v in vague):
        score -= 20

    return round(max(0, min(100, score)), 1)


# ============================================================
# BEST OUTCOME MATCHING
# ============================================================

def find_best_clo(question, clos):
    if not clos:
        return None, 0

    best_clo = None
    best_score = -1

    for clo in clos:
        score = clo_score(question, clo)

        if score > best_score:
            best_score = score
            best_clo = clo

    return best_clo, best_score


def find_best_plo(question, plos):
    if not plos:
        return None, 0

    best_plo = None
    best_score = -1

    for plo in plos:
        score = plo_score(question, plo)

        if score > best_score:
            best_score = score
            best_plo = plo

    return best_plo, best_score


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    subject,
    clos,
    plos,
    target_bloom=None
):
    question = finalize_question(question)

    best_clo, c_score = find_best_clo(question, clos)
    best_plo, p_score = find_best_plo(question, plos)

    s_score = subject_score(question, subject)

    detected_bloom = detect_bloom(question)

    b_score = bloom_score(
        question,
        target_bloom if target_bloom else detected_bloom
    )

    sp_score = specificity_score(question)
    q_score = quality_score(question)

    # Weighted alignment score
    overall = (
        s_score * 0.20
        + c_score * 0.25
        + p_score * 0.25
        + b_score * 0.15
        + sp_score * 0.10
        + q_score * 0.05
    )

    overall = round(min(100, overall), 1)

    attained = (
        overall >= 80
        and c_score >= 80
        and p_score >= 80
        and b_score >= 80
        and s_score >= 80
    )

    return {
        "question": question,
        "overall": overall,
        "subject_score": round(s_score, 1),
        "clo_score": round(c_score, 1),
        "plo_score": round(p_score, 1),
        "bloom_score": round(b_score, 1),
        "specificity_score": round(sp_score, 1),
        "quality_score": round(q_score, 1),
        "bloom": detected_bloom,
        "target_bloom": target_bloom or detected_bloom,
        "best_clo": best_clo,
        "best_plo": best_plo,
        "attained": attained
    }


# ============================================================
# REVISION GENERATION
# ============================================================

def bloom_instruction(level):
    instructions = {
        "Remember": "Identify or state the relevant concept",
        "Understand": "Explain the relevant concept clearly",
        "Apply": "Apply the relevant concept to a specific situation or problem",
        "Analyze": "Analyze the relevant concept by examining its parts, relationships, or differences",
        "Evaluate": "Evaluate the relevant concept using evidence or explicit criteria",
        "Create": "Design or formulate a solution using the relevant concept"
    }

    return instructions.get(
        level,
        "Explain the relevant concept clearly"
    )


def make_revision_candidates(
    original_question,
    subject,
    clo,
    plo,
    target_bloom
):
    """
    Creates several subject-specific revisions.

    The question is built from the actual CLO concepts and
    PLO-related action instead of inserting the words CLO/PLO.
    """

    candidates = []

    concept = concept_phrase_from_clo(clo)

    if not concept:
        concept = clean_text(clo)

    action = extract_plo_action(plo)

    bloom_text = bloom_instruction(target_bloom)

    # --------------------------------------------------------
    # Candidate 1: direct conceptual question
    # --------------------------------------------------------

    if target_bloom == "Remember":
        q1 = f"Identify the key elements of {concept} and state their functions"

    elif target_bloom == "Understand":
        q1 = f"Explain {concept} and describe how its main elements are related"

    elif target_bloom == "Apply":
        q1 = f"Apply {concept} to the given situation and show how it would be used"

    elif target_bloom == "Analyze":
        q1 = f"Analyze {concept} by examining its main components and their relationships"

    elif target_bloom == "Evaluate":
        q1 = f"Evaluate {concept} using relevant evidence and justify your conclusion"

    else:
        q1 = f"Design a solution using {concept} and explain how the solution addresses the problem"

    candidates.append(finalize_question(q1))

    # --------------------------------------------------------
    # Candidate 2: comparison / relationship
    # --------------------------------------------------------

    if target_bloom in ["Analyze", "Evaluate"]:
        q2 = (
            f"Analyze {concept} in a relevant scenario, "
            f"identify the important factors, and justify your conclusion"
        )
    elif target_bloom == "Apply":
        q2 = (
            f"Apply {concept} to a relevant scenario, "
            f"show the steps involved, and state the resulting outcome"
        )
    elif target_bloom == "Create":
        q2 = (
            f"Develop a solution based on {concept}, "
            f"identify the main steps, and justify the proposed approach"
        )
    else:
        q2 = (
            f"Explain {concept}, identify its main characteristics, "
            f"and give a relevant example"
        )

    candidates.append(finalize_question(q2))

    # --------------------------------------------------------
    # Candidate 3: PLO-oriented action without mentioning PLO
    # --------------------------------------------------------

    if action == "communication":
        q3 = (
            f"Explain {concept} clearly and support your explanation "
            f"with a relevant example"
        )

    elif action == "research":
        q3 = (
            f"Analyze {concept} using relevant evidence and "
            f"justify the conclusion drawn from the evidence"
        )

    elif action == "teamwork":
        q3 = (
            f"Analyze {concept} in a practical situation and "
            f"propose an approach for addressing the situation"
        )

    elif action == "ethics":
        q3 = (
            f"Evaluate {concept} in a professional situation and "
            f"justify the most appropriate course of action"
        )

    elif action == "technology":
        q3 = (
            f"Apply {concept} using an appropriate technological approach "
            f"and explain the result"
        )

    elif action == "critical thinking":
        q3 = (
            f"Analyze {concept}, compare the relevant factors, "
            f"and justify the conclusion"
        )

    else:
        q3 = (
            f"Analyze {concept} in a relevant situation, "
            f"identify the key factors, and justify the conclusion"
        )

    candidates.append(finalize_question(q3))

    # --------------------------------------------------------
    # Candidate 4: stronger scenario-based version
    # --------------------------------------------------------

    if target_bloom == "Apply":
        q4 = (
            f"Given a relevant scenario involving {concept}, "
            f"apply the appropriate method and explain the result"
        )
    elif target_bloom == "Analyze":
        q4 = (
            f"Given a relevant scenario involving {concept}, "
            f"analyze the factors involved and explain their relationships"
        )
    elif target_bloom == "Evaluate":
        q4 = (
            f"Given a relevant scenario involving {concept}, "
            f"evaluate the available options and justify your decision"
        )
    elif target_bloom == "Create":
        q4 = (
            f"Given a relevant problem involving {concept}, "
            f"design an appropriate solution and justify the major decisions"
        )
    else:
        q4 = (
            f"Given a relevant example of {concept}, "
            f"explain the concept and identify its main features"
        )

    candidates.append(finalize_question(q4))

    # --------------------------------------------------------
    # Candidate 5: very direct version
    # --------------------------------------------------------

    if target_bloom == "Remember":
        q5 = f"Define {concept} and list its main characteristics"

    elif target_bloom == "Understand":
        q5 = f"Describe {concept} and explain its significance"

    elif target_bloom == "Apply":
        q5 = f"Calculate or determine the required result using {concept}"

    elif target_bloom == "Analyze":
        q5 = f"Differentiate the major components of {concept} and explain their relationships"

    elif target_bloom == "Evaluate":
        q5 = f"Assess {concept} against appropriate criteria and justify the assessment"

    else:
        q5 = f"Construct a solution based on {concept} and explain the reasoning behind it"

    candidates.append(finalize_question(q5))

    return candidates


def generate_revisions(
    original_question,
    subject,
    clos,
    plos,
    target_bloom
):
    """
    Generates revisions and selects the highest-scoring
    genuinely evaluated revision.

    The function prioritizes candidates that achieve
    80+ in the actual evaluation.
    """

    if not clos:
        clos = [subject] if subject else ["the relevant course concept"]

    if not plos:
        plos = ["Apply knowledge to solve relevant problems"]

    # --------------------------------------------------------
    # First generation round
    # --------------------------------------------------------

    candidates = make_revision_candidates(
        original_question,
        subject,
        clos,
        plos,
        target_bloom
    )

    evaluated = []

    for candidate in candidates:
        result = evaluate_question(
            candidate,
            subject,
            clos,
            plos,
            target_bloom
        )

        evaluated.append(result)

    # --------------------------------------------------------
    # If no candidate reaches 80, build a stronger question
    # from the actual CLO concepts.
    # --------------------------------------------------------

    attained = [
        item for item in evaluated
        if item["attained"]
    ]

    if attained:
        attained.sort(
            key=lambda x: x["overall"],
            reverse=True
        )

        return attained[:3]

    # --------------------------------------------------------
    # Strong fallback construction
    # --------------------------------------------------------

    best_clo, _ = find_best_clo(original_question, clos)

    if not best_clo:
        best_clo = clos[0]

    best_plo, _ = find_best_plo(original_question, plos)

    if not best_plo:
        best_plo = plos[0]

    concept = concept_phrase_from_clo(best_clo)

    if not concept:
        concept = clean_text(best_clo)

    action = extract_plo_action(best_plo)

    if target_bloom == "Analyze":
        fallback_questions = [
            (
                f"Analyze {concept} in a relevant scenario, "
                f"identify the key factors, compare their relationships, "
                f"and justify your conclusion"
            ),
            (
                f"Analyze the main components of {concept}, "
                f"explain how they interact, and justify the resulting conclusion"
            ),
            (
                f"Given a problem involving {concept}, "
                f"analyze the relevant factors and justify the most appropriate conclusion"
            )
        ]

    elif target_bloom == "Evaluate":
        fallback_questions = [
            (
                f"Evaluate {concept} using relevant criteria, "
                f"consider the available evidence, and justify your conclusion"
            ),
            (
                f"Assess {concept} in a relevant scenario, "
                f"compare the available alternatives, and justify your decision"
            ),
            (
                f"Evaluate the effectiveness of {concept} in a relevant situation "
                f"and justify your conclusion with appropriate evidence"
            )
        ]

    elif target_bloom == "Apply":
        fallback_questions = [
            (
                f"Apply {concept} to a relevant problem, "
                f"show the appropriate steps, and explain the result"
            ),
            (
                f"Given a relevant problem involving {concept}, "
                f"apply the appropriate method and justify the resulting answer"
            ),
            (
                f"Use {concept} to solve a relevant problem, "
                f"show the main steps, and explain the result"
            )
        ]

    elif target_bloom == "Create":
        fallback_questions = [
            (
                f"Design a solution for a relevant problem using {concept} "
                f"and justify the major decisions"
            ),
            (
                f"Develop an appropriate solution using {concept} "
                f"and explain why the proposed approach is suitable"
            ),
            (
                f"Construct a solution based on {concept}, "
                f"explain the main steps, and justify the approach"
            )
        ]

    elif target_bloom == "Understand":
        fallback_questions = [
            (
                f"Explain {concept}, describe its main components, "
                f"and explain how they are related"
            ),
            (
                f"Describe {concept} clearly, explain its major characteristics, "
                f"and provide a relevant example"
            ),
            (
                f"Explain the main principles of {concept} "
                f"and describe their practical significance"
            )
        ]

    else:
        fallback_questions = [
            f"Identify the main elements of {concept} and state their functions",
            f"Define {concept} and list its main characteristics",
            f"Identify the key features of {concept} and explain their functions"
        ]

    for q in fallback_questions:
        result = evaluate_question(
            finalize_question(q),
            subject,
            clos,
            plos,
            target_bloom
        )

        evaluated.append(result)

    # --------------------------------------------------------
    # Final selection
    # --------------------------------------------------------

    evaluated.sort(
        key=lambda x: (
            x["attained"],
            x["overall"],
            x["clo_score"],
            x["plo_score"],
            x["bloom_score"]
        ),
        reverse=True
    )

    # Return top distinct revisions
    final = []
    seen = set()

    for item in evaluated:
        key = normalize(item["question"])

        if key not in seen:
            seen.add(key)
            final.append(item)

        if len(final) == 3:
            break

    return final


# ============================================================
# FILE READING
# ============================================================

def read_pdf(uploaded_file):
    try:
        import pypdf

        reader = pypdf.PdfReader(uploaded_file)

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                pages.append(text)

        return "\n".join(pages)

    except Exception as e:
        return f"PDF_READ_ERROR: {e}"


def read_docx(uploaded_file):
    try:
        from docx import Document

        document = Document(uploaded_file)

        paragraphs = [
            p.text
            for p in document.paragraphs
            if p.text.strip()
        ]

        return "\n".join(paragraphs)

    except Exception as e:
        return f"DOCX_READ_ERROR: {e}"


def read_xlsx(uploaded_file):
    try:
        excel = pd.ExcelFile(uploaded_file)

        sections = []

        for sheet in excel.sheet_names:
            df = pd.read_excel(
                uploaded_file,
                sheet_name=sheet,
                header=None
            )

            sections.append(
                f"\n--- Sheet: {sheet} ---\n"
                + df.fillna("").astype(str).to_csv(
                    index=False,
                    header=False
                )
            )

        return "\n".join(sections)

    except Exception as e:
        return f"XLSX_READ_ERROR: {e}"


def read_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)

        return df.fillna("").astype(str).to_csv(
            index=False
        )

    except Exception:
        try:
            uploaded_file.seek(0)

            return uploaded_file.read().decode(
                "utf-8",
                errors="ignore"
            )

        except Exception as e:
            return f"CSV_READ_ERROR: {e}"


def read_txt(uploaded_file):
    try:
        return uploaded_file.read().decode(
            "utf-8",
            errors="ignore"
        )
    except Exception as e:
        return f"TXT_READ_ERROR: {e}"


def read_file(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".xlsx"):
        return read_xlsx(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    if filename.endswith(".txt"):
        return read_txt(uploaded_file)

    if filename.endswith(".doc"):
        return (
            "DOC_ERROR: Legacy .doc files are not directly supported. "
            "Please save the document as .docx and upload it again."
        )

    if filename.endswith(".xls"):
        return (
            "XLS_ERROR: Legacy .xls files are not directly supported. "
            "Please save the spreadsheet as .xlsx and upload it again."
        )

    return (
        "UNSUPPORTED_FILE: Please upload PDF, DOCX, XLSX, CSV, or TXT."
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):
    """
    Extracts questions from a variety of assessment formats.

    It is not restricted to MCQs.
    """

    text = clean_text(text)

    if not text:
        return []

    # Restore basic line separation for extraction
    raw_lines = re.split(r"[\n\r]+", text)

    lines = []

    for line in raw_lines:
        line = clean_text(line)

        if line:
            lines.append(line)

    questions = []

    # --------------------------------------------------------
    # Numbered questions
    # --------------------------------------------------------

    numbered_pattern = re.compile(
        r"^(?:Q(?:uestion)?\s*)?\d+\s*[\.\):\-]\s*(.+)$",
        re.IGNORECASE
    )

    for line in lines:
        match = numbered_pattern.match(line)

        if match:
            q = clean_text(match.group(1))

            # Do not treat short option-like lines as questions
            if len(words(q)) >= 4:
                questions.append(q)

    if questions:
        return questions

    # --------------------------------------------------------
    # Lines ending in question marks
    # --------------------------------------------------------

    for line in lines:
        if "?" in line and len(words(line)) >= 4:
            q = re.sub(r"\s+", " ", line)
            questions.append(q)

    if questions:
        return questions

    # --------------------------------------------------------
    # MCQ-style blocks
    # --------------------------------------------------------

    block_pattern = re.compile(
        r"(?:^|\s)(?:Q(?:uestion)?\s*)?(\d+)\s*[\.\):\-]\s*(.*?)(?="
        r"(?:\s+Q(?:uestion)?\s*\d+\s*[\.\):\-])|$)",
        re.IGNORECASE | re.DOTALL
    )

    matches = block_pattern.findall(text)

    for _, content in matches:
        content = clean_text(content)

        # Remove answer choices from the end
        content = re.split(
            r"\s+[A-Da-d]\s*[\.\):]\s+",
            content
        )[0]

        if len(words(content)) >= 4:
            questions.append(content)

    if questions:
        return questions

    # --------------------------------------------------------
    # Sentence fallback
    # --------------------------------------------------------

    sentences = re.split(
        r"(?<=[?.])\s+",
        text
    )

    for sentence in sentences:
        sentence = clean_text(sentence)

        if len(words(sentence)) >= 5:
            questions.append(sentence)

    # Remove duplicates
    final = []
    seen = set()

    for q in questions:
        key = normalize(q)

        if key not in seen:
            seen.add(key)
            final.append(q)

    return final


# ============================================================
# SCORE LABEL
# ============================================================

def score_label(score):
    if score >= 80:
        return "Aligned"
    if score >= 70:
        return "Partially Aligned"
    if score >= 50:
        return "Needs Revision"

    return "Poor Alignment"


# ============================================================
# STREAMLIT HEADER
# ============================================================

st.title("🎓 OBE Assessment Alignment Checker")

st.write(
    "Evaluate assessment questions against subject relevance, CLOs, "
    "PLOs, Bloom's level, specificity, and question quality."
)

st.info(
    "The tool supports different assessment types, not only MCQs. "
    "Upload your assessment file and review question-level alignment."
)


# ============================================================
# INPUT SECTION
# ============================================================

st.subheader("1. Assessment Information")

col1, col2 = st.columns(2)

with col1:
    subject = st.text_input(
        "Subject / Course",
        placeholder="e.g., Chemistry, English I, Programming Fundamentals"
    )

with col2:
    bloom_target = st.selectbox(
        "Target Bloom's Level",
        BLOOM_ORDER,
        index=2
    )

st.subheader("2. Learning Outcomes")

clo_text = st.text_area(
    "Enter CLOs",
    placeholder=(
        "CLO 1: Explain the principles of chemical bonding\n"
        "CLO 2: Apply chemical concepts to solve problems"
    ),
    height=140
)

plo_text = st.text_area(
    "Enter PLOs",
    placeholder=(
        "PLO 1: Apply knowledge to solve problems\n"
        "PLO 2: Communicate effectively"
    ),
    height=140
)

st.subheader("3. Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload Assessment File",
    type=["pdf", "docx", "xlsx", "csv", "txt"]
)


# ============================================================
# EVALUATION
# ============================================================

if uploaded_file is not None:

    if st.button(
        "🔍 Evaluate Assessment",
        type="primary",
        use_container_width=True
    ):

        with st.spinner("Reading and evaluating the assessment..."):

            file_text = read_file(uploaded_file)

            if file_text.startswith(
                (
                    "PDF_READ_ERROR",
                    "DOCX_READ_ERROR",
                    "XLSX_READ_ERROR",
                    "CSV_READ_ERROR",
                    "TXT_READ_ERROR",
                    "DOC_ERROR",
                    "XLS_ERROR",
                    "UNSUPPORTED_FILE"
                )
            ):
                st.error(file_text)

            else:
                questions = extract_questions(file_text)

                if not questions:
                    st.error(
                        "No assessment questions could be extracted. "
                        "Please check the file format and content."
                    )

                else:
                    clos = parse_outcomes(clo_text)
                    plos = parse_outcomes(plo_text)

                    results = []

                    for i, question in enumerate(
                        questions,
                        start=1
                    ):

                        result = evaluate_question(
                            question,
                            subject,
                            clos,
                            plos,
                            bloom_target
                        )

                        result["number"] = i

                        results.append(result)

                    st.session_state.evaluated_questions = results
                    st.session_state.applied_revisions = {}
                    st.session_state.revision_cache = {}

                    st.success(
                        f"{len(results)} question(s) evaluated successfully."
                    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.evaluated_questions:

    results = st.session_state.evaluated_questions

    st.divider()

    st.header("Assessment Evaluation")

    total_questions = len(results)

    attained_count = sum(
        1 for item in results
        if item["attained"]
    )

    average_score = (
        sum(item["overall"] for item in results)
        / max(1, total_questions)
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Questions",
            total_questions
        )

    with col2:
        st.metric(
            "Average Alignment",
            f"{average_score:.1f}/100"
        )

    with col3:
        st.metric(
            "Initially Attained",
            f"{attained_count}/{total_questions}"
        )

    st.divider()

    # ========================================================
    # QUESTION-BY-QUESTION RESULTS
    # ========================================================

    for item in results:

        number = item["number"]

        st.subheader(
            f"Question {number}"
        )

        st.write(
            f"**Original Question:** {item['question']}"
        )

        # ----------------------------------------------------
        # ORIGINAL SCORE
        # ----------------------------------------------------

        original_col1, original_col2 = st.columns(
            [1, 2]
        )

        with original_col1:
            st.metric(
                "Original Score",
                f"{item['overall']:.1f}/100"
            )

        with original_col2:

            if item["attained"]:
                st.success(
                    "✓ Alignment is Attained"
                )
            else:
                st.warning(
                    "Alignment Needs Revision"
                )

        # ----------------------------------------------------
        # SCORE BREAKDOWN
        # ----------------------------------------------------

        breakdown = pd.DataFrame(
            {
                "Metric": [
                    "Subject Relevance",
                    "CLO Alignment",
                    "PLO Alignment",
                    "Bloom's Alignment",
                    "Specificity",
                    "Question Quality"
                ],
                "Score": [
                    item["subject_score"],
                    item["clo_score"],
                    item["plo_score"],
                    item["bloom_score"],
                    item["specificity_score"],
                    item["quality_score"]
                ]
            }
        )

        st.dataframe(
            breakdown,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            f"Detected Bloom's Level: {item['bloom']} | "
            f"Target Bloom's Level: {item['target_bloom']}"
        )

        if item["best_clo"]:
            st.caption(
                f"Best matching CLO: {item['best_clo']}"
            )

        if item["best_plo"]:
            st.caption(
                f"Best matching PLO: {item['best_plo']}"
            )

        # ----------------------------------------------------
        # REVISION SECTION
        # ----------------------------------------------------

        if not item["attained"]:

            st.markdown(
                "### 🔧 Suggested Revisions"
            )

            cache_key = str(number)

            if cache_key not in st.session_state.revision_cache:

                revisions = generate_revisions(
                    item["question"],
                    subject,
                    clos,
                    plos,
                    bloom_target
                )

                st.session_state.revision_cache[
                    cache_key
                ] = revisions

            revisions = st.session_state.revision_cache[
                cache_key
            ]

            for revision_index, revision in enumerate(
                revisions,
                start=1
            ):

                st.markdown(
                    f"#### Revision {revision_index}"
                )

                st.write(
                    revision["question"]
                )

                rev_col1, rev_col2, rev_col3 = st.columns(3)

                with rev_col1:
                    st.metric(
                        "Revised Score",
                        f"{revision['overall']:.1f}/100"
                    )

                with rev_col2:
                    st.metric(
                        "CLO",
                        f"{revision['clo_score']:.1f}%"
                    )

                with rev_col3:
                    st.metric(
                        "PLO",
                        f"{revision['plo_score']:.1f}%"
                    )

                if revision["attained"]:
                    st.success(
                        "✓ Alignment is Attained After Revision"
                    )
                else:
                    st.warning(
                        "This revision is below 80. "
                        "Select another revision."
                    )

                rev_breakdown = pd.DataFrame(
                    {
                        "Metric": [
                            "Subject Relevance",
                            "CLO Alignment",
                            "PLO Alignment",
                            "Bloom's Alignment",
                            "Specificity",
                            "Question Quality"
                        ],
                        "Before": [
                            item["subject_score"],
                            item["clo_score"],
                            item["plo_score"],
                            item["bloom_score"],
                            item["specificity_score"],
                            item["quality_score"]
                        ],
                        "After": [
                            revision["subject_score"],
                            revision["clo_score"],
                            revision["plo_score"],
                            revision["bloom_score"],
                            revision["specificity_score"],
                            revision["quality_score"]
                        ]
                    }
                )

                st.dataframe(
                    rev_breakdown,
                    use_container_width=True,
                    hide_index=True
                )

                button_key = (
                    f"select_revision_{number}_"
                    f"{revision_index}"
                )

                if st.button(
                    "✓ Select This Revision",
                    key=button_key,
                    use_container_width=True
                ):

                    st.session_state.applied_revisions[
                        number
                    ] = revision

                    st.rerun()

                st.divider()

        # ----------------------------------------------------
        # SELECTED REVISION
        # ----------------------------------------------------

        if number in st.session_state.applied_revisions:

            selected = st.session_state.applied_revisions[
                number
            ]

            st.markdown(
                "### ✅ Revised Question"
            )

            st.write(
                f"**{selected['question']}**"
            )

            st.success(
                f"✓ Alignment is Attained After Revision — "
                f"Revised Alignment Score: "
                f"{selected['overall']:.1f}/100"
            )

            st.caption(
                "The revised score shown above is calculated from "
                "the revised question's subject, CLO, PLO, Bloom's, "
                "specificity, and quality metrics."
            )

            before_after = pd.DataFrame(
                {
                    "Metric": [
                        "Overall Alignment",
                        "Subject Relevance",
                        "CLO Alignment",
                        "PLO Alignment",
                        "Bloom's Alignment",
                        "Specificity",
                        "Question Quality"
                    ],
                    "Before Revision": [
                        item["overall"],
                        item["subject_score"],
                        item["clo_score"],
                        item["plo_score"],
                        item["bloom_score"],
                        item["specificity_score"],
                        item["quality_score"]
                    ],
                    "After Revision": [
                        selected["overall"],
                        selected["subject_score"],
                        selected["clo_score"],
                        selected["plo_score"],
                        selected["bloom_score"],
                        selected["specificity_score"],
                        selected["quality_score"]
                    ]
                }
            )

            st.dataframe(
                before_after,
                use_container_width=True,
                hide_index=True
            )

        st.divider()


# ============================================================
# FINAL SUMMARY
# ============================================================

if st.session_state.evaluated_questions:

    results = st.session_state.evaluated_questions

    st.header("📊 Final Assessment Summary")

    summary_rows = []

    for item in results:

        number = item["number"]

        if number in st.session_state.applied_revisions:

            selected = st.session_state.applied_revisions[
                number
            ]

            summary_rows.append(
                {
                    "Question": number,
                    "Original Score": round(
                        item["overall"],
                        1
                    ),
                    "Final Score": round(
                        selected["overall"],
                        1
                    ),
                    "Final Status":
                        "Alignment is Attained After Revision",
                    "Final Question":
                        selected["question"]
                }
            )

        else:

            summary_rows.append(
                {
                    "Question": number,
                    "Original Score": round(
                        item["overall"],
                        1
                    ),
                    "Final Score": round(
                        item["overall"],
                        1
                    ),
                    "Final Status":
                        "Alignment is Attained"
                        if item["attained"]
                        else "Needs Revision",
                    "Final Question":
                        item["question"]
                }
            )

    summary_df = pd.DataFrame(summary_rows)

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # EXPORT
    # ========================================================

    csv_data = summary_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Final Evaluation",
        data=csv_data,
        file_name="OBE_Alignment_Evaluation.csv",
        mime="text/csv",
        use_container_width=True
    )
