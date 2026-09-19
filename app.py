import streamlit as st
import pandas as pd
import re
import io
import os
from pathlib import Path

# ============================================================
# PAGE CONFIG
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
# TEXT UTILITIES
# ============================================================

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in",
    "on", "for", "from", "with", "by", "at", "as", "is",
    "are", "was", "were", "be", "been", "being", "this",
    "that", "these", "those", "it", "its", "into", "through",
    "during", "using", "use", "their", "they", "them", "he",
    "she", "his", "her", "you", "your", "we", "our", "can",
    "could", "should", "would", "will", "may", "might", "do",
    "does", "did", "how", "what", "why", "when", "where",
    "which", "who", "whom", "than", "then", "also", "such",
    "each", "any", "all", "both", "more", "most", "some",
    "many", "much", "given", "following", "based"
}


def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\xa0": " "
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def words(text):
    return [
        w
        for w in normalize(text).split()
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
        "ies",
        "es",
        "ed",
        "ly",
        "s"
    ]

    for ending in endings:
        if (
            len(word) >
            len(ending) + 3
            and word.endswith(ending)
        ):
            return word[:-len(ending)]

    return word


def stem_set(text):
    return {
        simple_stem(w)
        for w in words(text)
        if len(simple_stem(w)) > 2
    }


def finalize_question(text):
    """
    Ensures exactly one question mark at the end.
    Removes combinations such as .? or ?.
    """

    text = clean_text(text)

    text = re.sub(
        r"[.!?]+$",
        "",
        text
    ).strip()

    if not text:
        return ""

    return text + "?"


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):

    if not text:
        return []

    text = clean_text(text)

    # First try line-based extraction
    lines = re.split(
        r"[\n\r]+",
        text
    )

    outcomes = []

    for line in lines:

        line = clean_text(line)

        if not line:
            continue

        line = re.sub(
            r"^(?:CLO|PLO)?\s*\d+\s*[\.\):\-–]*\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        if len(words(line)) >= 4:
            outcomes.append(line)

    if outcomes:
        return outcomes

    # Semicolon-based fallback
    parts = re.split(
        r"[;]+",
        text
    )

    for part in parts:

        part = clean_text(part)

        if len(words(part)) >= 4:
            outcomes.append(part)

    return outcomes


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

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                normalized
            ):
                detected.append(level)
                break

    if not detected:
        return "Understand"

    return max(
        detected,
        key=lambda x: BLOOM_ORDER.index(x)
    )


def bloom_score(question, target):

    detected = detect_bloom(question)

    if not target:
        return 80

    target = target.title()

    if target not in BLOOM_ORDER:
        return 80

    if detected == target:
        return 100

    difference = abs(
        BLOOM_ORDER.index(detected)
        -
        BLOOM_ORDER.index(target)
    )

    if difference == 1:
        return 80

    if difference == 2:
        return 65

    if difference == 3:
        return 50

    return 40


# ============================================================
# CLO / PLO CONCEPTS
# ============================================================

GENERIC_WORDS = {
    "understand",
    "knowledge",
    "learn",
    "learning",
    "demonstrate",
    "ability",
    "abilities",
    "skills",
    "skill",
    "students",
    "student",
    "course",
    "concept",
    "concepts",
    "principle",
    "principles",
    "apply",
    "analyze",
    "analyse",
    "evaluate",
    "describe",
    "explain",
    "develop",
    "development"
}


def extract_clo_concepts(clo):

    result = []

    for word in words(clo):

        stem = simple_stem(word)

        if (
            stem not in GENERIC_WORDS
            and len(stem) > 3
        ):
            result.append(word)

    return result


def concept_phrase_from_clo(clo):

    result = []

    seen = set()

    for word in clean_text(clo).split():

        cleaned = re.sub(
            r"[^A-Za-z0-9\-]",
            "",
            word
        )

        if not cleaned:
            continue

        stem = simple_stem(
            cleaned.lower()
        )

        if (
            stem not in GENERIC_WORDS
            and len(stem) > 3
            and stem not in seen
        ):
            seen.add(stem)
            result.append(cleaned)

    return " ".join(result[:10])


PLO_ACTIONS = {
    "communication": [
        "communicate",
        "present",
        "write",
        "explain",
        "report",
        "communicate"
    ],
    "problem solving": [
        "solve",
        "analyze",
        "analyse",
        "identify",
        "evaluate",
        "problem"
    ],
    "teamwork": [
        "collaborate",
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
        "software",
        "tool",
        "digital",
        "technology"
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
        "justify",
        "critique"
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

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                normalized
            ):
                return category

    return "problem solving"


def extract_plo_concepts(plo):

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
        "learning"
    }

    return [
        simple_stem(w)
        for w in words(plo)
        if simple_stem(w) not in generic
    ]


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

SUBJECT_ALIASES = {

    "chemistry": [
        "atom",
        "molecule",
        "reaction",
        "acid",
        "base",
        "chemical",
        "compound",
        "bond",
        "periodic",
        "solution",
        "ph",
        "organic",
        "inorganic"
    ],

    "physics": [
        "force",
        "energy",
        "motion",
        "velocity",
        "momentum",
        "electric",
        "magnetic",
        "wave",
        "light",
        "mass",
        "acceleration"
    ],

    "mathematics": [
        "equation",
        "function",
        "matrix",
        "derivative",
        "integral",
        "probability",
        "algebra",
        "geometry",
        "calculus",
        "vector"
    ],

    "biology": [
        "cell",
        "gene",
        "organism",
        "protein",
        "enzyme",
        "ecosystem",
        "dna",
        "rna",
        "evolution",
        "tissue"
    ],

    "english": [
        "writing",
        "reading",
        "grammar",
        "essay",
        "language",
        "rhetoric",
        "paragraph",
        "thesis",
        "tone",
        "purpose",
        "main idea"
    ],

    "programming": [
        "program",
        "programming",
        "code",
        "algorithm",
        "variable",
        "function",
        "loop",
        "array",
        "class",
        "object"
    ],

    "computer science": [
        "algorithm",
        "software",
        "computer",
        "code",
        "database",
        "network",
        "programming",
        "system"
    ],

    "business": [
        "market",
        "management",
        "business",
        "finance",
        "marketing",
        "organization",
        "strategy",
        "consumer"
    ],

    "economics": [
        "market",
        "demand",
        "supply",
        "inflation",
        "economy",
        "price",
        "consumer",
        "production"
    ],

    "statistics": [
        "mean",
        "median",
        "variance",
        "probability",
        "sample",
        "population",
        "distribution",
        "hypothesis",
        "regression"
    ]
}


def subject_score(question, subject):

    if not subject:
        return 85

    q = normalize(question)
    s = normalize(subject)

    q_stems = stem_set(question)
    s_stems = stem_set(subject)

    direct = q_stems.intersection(
        s_stems
    )

    if direct:
        return min(
            100,
            80 + len(direct) * 5
        )

    for key, aliases in SUBJECT_ALIASES.items():

        if key in s:

            matches = sum(
                1
                for alias in aliases
                if re.search(
                    r"\b" + re.escape(alias) + r"\b",
                    q
                )
            )

            if matches >= 3:
                return 100

            if matches == 2:
                return 95

            if matches == 1:
                return 88

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

    overlap = q_stems.intersection(
        c_stems
    )

    concepts = {
        simple_stem(x)
        for x in extract_clo_concepts(clo)
    }

    concept_overlap = q_stems.intersection(
        concepts
    )

    general_ratio = (
        len(overlap)
        /
        max(1, len(c_stems))
    )

    concept_ratio = (
        len(concept_overlap)
        /
        max(1, len(concepts))
    )

    score = (
        general_ratio * 35
        +
        concept_ratio * 65
    )

    if len(concept_overlap) >= 3:
        score += 30

    elif len(concept_overlap) == 2:
        score += 25

    elif len(concept_overlap) == 1:
        score += 15

    return round(
        min(100, score),
        1
    )


# ============================================================
# PLO ALIGNMENT
# ============================================================

def plo_score(question, plo):

    if not plo:
        return 0

    normalized_q = normalize(question)

    action = extract_plo_action(
        plo
    )

    action_words = PLO_ACTIONS.get(
        action,
        []
    )

    action_match = any(
        re.search(
            r"\b" + re.escape(word) + r"\b",
            normalized_q
        )
        for word in action_words
    )

    q_stems = stem_set(question)

    plo_concepts = set(
        extract_plo_concepts(plo)
    )

    concept_match = q_stems.intersection(
        plo_concepts
    )

    if action_match and concept_match:
        return 100

    if action_match:
        return 92

    if concept_match:
        return 86

    bloom = detect_bloom(question)

    if action in [
        "problem solving",
        "critical thinking",
        "research"
    ]:

        if bloom in [
            "Analyze",
            "Evaluate",
            "Create"
        ]:
            return 82

    if action == "communication":

        if any(
            x in normalized_q
            for x in [
                "explain",
                "describe",
                "present",
                "write",
                "discuss"
            ]
        ):
            return 82

    return 58


# ============================================================
# SPECIFICITY
# ============================================================

def specificity_score(question):

    token_count = len(
        words(question)
    )

    score = 45

    if token_count >= 8:
        score += 15

    if token_count >= 12:
        score += 10

    if token_count >= 16:
        score += 5

    terms = [
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
        "given",
        "scenario",
        "example",
        "evidence",
        "criteria",
        "steps"
    ]

    matches = sum(
        1
        for term in terms
        if re.search(
            r"\b" + re.escape(term) + r"\b",
            normalize(question)
        )
    )

    score += min(
        25,
        matches * 5
    )

    return round(
        min(100, score),
        1
    )


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question):

    q = clean_text(question)

    if not q:
        return 0

    score = 50

    if len(q) >= 30:
        score += 10

    if len(q) >= 60:
        score += 10

    if len(words(q)) >= 8:
        score += 10

    if q.endswith("?"):
        score += 10

    if re.search(
        r"[.!?]{2,}$",
        q
    ):
        score -= 25

    vague_phrases = [
        "say something about",
        "write something about",
        "tell me about",
        "what do you know about",
        "discuss anything"
    ]

    for phrase in vague_phrases:

        if phrase in normalize(q):
            score -= 20

    return round(
        max(
            0,
            min(100, score)
        ),
        1
    )


# ============================================================
# BEST CLO / PLO
# ============================================================

def find_best_clo(question, clos):

    if not clos:
        return None, 0

    best = None
    best_score = -1

    for clo in clos:

        score = clo_score(
            question,
            clo
        )

        if score > best_score:
            best_score = score
            best = clo

    return best, best_score


def find_best_plo(question, plos):

    if not plos:
        return None, 0

    best = None
    best_score = -1

    for plo in plos:

        score = plo_score(
            question,
            plo
        )

        if score > best_score:
            best_score = score
            best = plo

    return best, best_score


# ============================================================
# FULL QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    subject,
    clos,
    plos,
    target_bloom
):

    question = finalize_question(
        question
    )

    best_clo, c_score = find_best_clo(
        question,
        clos
    )

    best_plo, p_score = find_best_plo(
        question,
        plos
    )

    s_score = subject_score(
        question,
        subject
    )

    b_score = bloom_score(
        question,
        target_bloom
    )

    sp_score = specificity_score(
        question
    )

    q_score = quality_score(
        question
    )

    overall = (
        s_score * 0.20
        +
        c_score * 0.25
        +
        p_score * 0.25
        +
        b_score * 0.15
        +
        sp_score * 0.10
        +
        q_score * 0.05
    )

    overall = round(
        min(100, overall),
        1
    )

    attained = (
        overall >= 80
        and
        s_score >= 80
        and
        c_score >= 80
        and
        p_score >= 80
        and
        b_score >= 80
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
        "bloom": detect_bloom(question),
        "target_bloom": target_bloom,
        "best_clo": best_clo,
        "best_plo": best_plo,
        "attained": attained
    }


# ============================================================
# REVISION GENERATOR
# ============================================================

def build_revision_templates(
    concept,
    target_bloom,
    plo_action
):

    templates = []

    if target_bloom == "Remember":

        templates = [
            f"Define {concept} and identify its main characteristics",
            f"Identify the main elements of {concept} and state their functions",
            f"List the key features of {concept} and state their significance"
        ]

    elif target_bloom == "Understand":

        templates = [
            f"Explain {concept} and describe how its main elements are related",
            f"Describe {concept} and explain its main characteristics",
            f"Explain the main principles of {concept} and give a relevant example"
        ]

    elif target_bloom == "Apply":

        templates = [
            f"Apply {concept} to a relevant problem and explain the result",
            f"Given a relevant scenario involving {concept}, apply the appropriate method and show the result",
            f"Use {concept} to solve a relevant problem and explain the steps"
        ]

    elif target_bloom == "Analyze":

        templates = [
            f"Analyze {concept} by examining its main components and their relationships",
            f"Analyze {concept} in a relevant scenario and justify your conclusion",
            f"Differentiate the major components of {concept} and explain their relationships",
            f"Analyze a relevant problem involving {concept} and identify the factors affecting the outcome"
        ]

    elif target_bloom == "Evaluate":

        templates = [
            f"Evaluate {concept} using appropriate criteria and justify your conclusion",
            f"Assess {concept} in a relevant scenario and justify your decision",
            f"Evaluate the effectiveness of {concept} using relevant evidence and justify your conclusion",
            f"Compare the available approaches to {concept} and justify the most appropriate choice"
        ]

    else:

        templates = [
            f"Design a solution using {concept} and justify the major decisions",
            f"Develop an appropriate solution based on {concept} and explain the reasoning",
            f"Construct a solution involving {concept} and justify the proposed approach"
        ]

    # Add PLO-specific action without naming the PLO
    if plo_action == "communication":

        templates.extend([
            f"Explain {concept} clearly and support your explanation with a relevant example",
            f"Describe {concept} and communicate its practical significance using a relevant example"
        ])

    elif plo_action == "research":

        templates.extend([
            f"Analyze {concept} using relevant evidence and justify the conclusion",
            f"Evaluate {concept} using available evidence and justify your conclusion"
        ])

    elif plo_action == "critical thinking":

        templates.extend([
            f"Analyze {concept}, compare the relevant factors, and justify the conclusion",
            f"Evaluate the relevant factors in {concept} and justify the most appropriate conclusion"
        ])

    elif plo_action == "problem solving":

        templates.extend([
            f"Apply {concept} to a relevant problem and justify the solution",
            f"Analyze a problem involving {concept} and justify the appropriate solution"
        ])

    elif plo_action == "technology":

        templates.extend([
            f"Apply {concept} using an appropriate technological approach and explain the result",
            f"Develop a technological solution using {concept} and justify the approach"
        ])

    elif plo_action == "ethics":

        templates.extend([
            f"Evaluate {concept} in a professional situation and justify the appropriate course of action",
            f"Assess {concept} in an ethical situation and justify the most appropriate decision"
        ])

    return templates


def generate_revisions(
    original_question,
    subject,
    clos,
    plos,
    target_bloom
):

    # --------------------------------------------------------
    # Match the original question to its most relevant CLO/PLO
    # --------------------------------------------------------

    best_clo, _ = find_best_clo(
        original_question,
        clos
    )

    if not best_clo and clos:
        best_clo = clos[0]

    best_plo, _ = find_best_plo(
        original_question,
        plos
    )

    if not best_plo and plos:
        best_plo = plos[0]

    if best_clo:
        concept = concept_phrase_from_clo(
            best_clo
        )
    else:
        concept = clean_text(
            subject
        )

    if not concept:
        concept = "the relevant course concept"

    plo_action = (
        extract_plo_action(best_plo)
        if best_plo
        else "problem solving"
    )

    templates = build_revision_templates(
        concept,
        target_bloom,
        plo_action
    )

    evaluated = []

    seen = set()

    # --------------------------------------------------------
    # Evaluate every candidate
    # --------------------------------------------------------

    for template in templates:

        candidate = finalize_question(
            template
        )

        key = normalize(candidate)

        if key in seen:
            continue

        seen.add(key)

        result = evaluate_question(
            candidate,
            subject,
            clos,
            plos,
            target_bloom
        )

        evaluated.append(result)

    # --------------------------------------------------------
    # Additional targeted candidates
    # --------------------------------------------------------

    if best_clo:

        concept_words = extract_clo_concepts(
            best_clo
        )

        if concept_words:

            compact_concept = " ".join(
                concept_words[:6]
            )

            extra_templates = [
                f"Analyze {compact_concept} in a relevant situation and justify your conclusion",
                f"Apply {compact_concept} to a relevant problem and explain the result",
                f"Evaluate {compact_concept} using appropriate criteria and justify your conclusion",
                f"Explain {compact_concept} and describe its practical significance"
            ]

            for template in extra_templates:

                candidate = finalize_question(
                    template
                )

                key = normalize(candidate)

                if key in seen:
                    continue

                seen.add(key)

                result = evaluate_question(
                    candidate,
                    subject,
                    clos,
                    plos,
                    target_bloom
                )

                evaluated.append(result)

    # --------------------------------------------------------
    # Prioritize genuinely attained revisions
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

    # --------------------------------------------------------
    # Return up to 3 different revisions
    # --------------------------------------------------------

    final = []

    for result in evaluated:

        if result["question"] not in [
            x["question"]
            for x in final
        ]:

            final.append(result)

        if len(final) >= 3:
            break

    return final


# ============================================================
# PDF READER
# ============================================================

def read_pdf(uploaded_file):

    data = uploaded_file.getvalue()

    # --------------------------------------------------------
    # Method 1: pypdf
    # --------------------------------------------------------

    try:

        import pypdf

        reader = pypdf.PdfReader(
            io.BytesIO(data)
        )

        pages = []

        for page in reader.pages:

            text = page.extract_text()

            if text:
                pages.append(text)

        result = "\n".join(
            pages
        ).strip()

        if result:
            return result

    except Exception:
        pass

    # --------------------------------------------------------
    # Method 2: PyMuPDF
    # --------------------------------------------------------

    try:

        import fitz

        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in document:

            text = page.get_text(
                "text"
            )

            if text:
                pages.append(text)

        result = "\n".join(
            pages
        ).strip()

        if result:
            return result

    except Exception:
        pass

    # --------------------------------------------------------
    # Method 3: pdfplumber
    # --------------------------------------------------------

    try:

        import pdfplumber

        pages = []

        with pdfplumber.open(
            io.BytesIO(data)
        ) as pdf:

            for page in pdf.pages:

                text = page.extract_text()

                if text:
                    pages.append(text)

        result = "\n".join(
            pages
        ).strip()

        if result:
            return result

    except Exception:
        pass

    return ""


# ============================================================
# DOCX READER
# ============================================================

def read_docx(uploaded_file):

    try:

        from docx import Document

        document = Document(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        sections = []

        # Paragraphs
        for paragraph in document.paragraphs:

            text = clean_text(
                paragraph.text
            )

            if text:
                sections.append(text)

        # Tables
        for table in document.tables:

            for row in table.rows:

                cells = []

                for cell in row.cells:

                    value = clean_text(
                        cell.text
                    )

                    if value:
                        cells.append(value)

                if cells:
                    sections.append(
                        " ".join(cells)
                    )

        return "\n".join(
            sections
        )

    except Exception:
        return ""


# ============================================================
# EXCEL READER
# ============================================================

def read_excel_file(uploaded_file):

    try:

        excel_bytes = io.BytesIO(
            uploaded_file.getvalue()
        )

        workbook = pd.ExcelFile(
            excel_bytes
        )

        sections = []

        for sheet in workbook.sheet_names:

            df = pd.read_excel(
                io.BytesIO(
                    uploaded_file.getvalue()
                ),
                sheet_name=sheet,
                header=None
            )

            sections.append(
                f"--- {sheet} ---"
            )

            for row in df.fillna("").values:

                row_values = [
                    clean_text(x)
                    for x in row
                    if clean_text(x)
                ]

                if row_values:
                    sections.append(
                        " ".join(row_values)
                    )

        return "\n".join(
            sections
        )

    except Exception:
        return ""


# ============================================================
# CSV READER
# ============================================================

def read_csv_file(uploaded_file):

    data = uploaded_file.getvalue()

    try:

        df = pd.read_csv(
            io.BytesIO(data),
            header=None
        )

        rows = []

        for row in df.fillna("").values:

            values = [
                clean_text(x)
                for x in row
                if clean_text(x)
            ]

            if values:
                rows.append(
                    " ".join(values)
                )

        return "\n".join(
            rows
        )

    except Exception:

        return data.decode(
            "utf-8",
            errors="ignore"
        )


# ============================================================
# TXT READER
# ============================================================

def read_txt_file(uploaded_file):

    return uploaded_file.getvalue().decode(
        "utf-8",
        errors="ignore"
    )


# ============================================================
# UNIVERSAL FILE READER
# ============================================================

def read_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(
            uploaded_file
        )

    if filename.endswith(".docx"):
        return read_docx(
            uploaded_file
        )

    if filename.endswith(".xlsx"):
        return read_excel_file(
            uploaded_file
        )

    if filename.endswith(".csv"):
        return read_csv_file(
            uploaded_file
        )

    if filename.endswith(".txt"):
        return read_txt_file(
            uploaded_file
        )

    if filename.endswith(".doc"):
        return ""

    if filename.endswith(".xls"):
        return ""

    return ""


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def remove_mcq_options(text):

    text = clean_text(text)

    # Find first option such as:
    # A. / A) / (A)
    option_pattern = re.compile(
        r"\s+(?:\([A-H]\)|[A-H][\.\):])\s+",
        re.IGNORECASE
    )

    match = option_pattern.search(
        text
    )

    if match:

        text = text[
            :match.start()
        ]

    return clean_text(text)


def looks_like_question(text):

    text = clean_text(text)

    if len(words(text)) < 4:
        return False

    lower = normalize(text)

    # Obvious non-question lines
    non_question_starts = [
        "student name",
        "roll number",
        "registration number",
        "date",
        "time",
        "marks",
        "total marks",
        "instructions",
        "answer key",
        "section",
        "course code",
        "course title",
        "semester",
        "teacher",
        "instructor"
    ]

    for phrase in non_question_starts:

        if lower.startswith(phrase):
            return False

    # Very likely question verbs
    question_verbs = [
        "define",
        "identify",
        "explain",
        "describe",
        "discuss",
        "compare",
        "contrast",
        "differentiate",
        "analyze",
        "analyse",
        "evaluate",
        "assess",
        "justify",
        "calculate",
        "solve",
        "apply",
        "determine",
        "state",
        "list",
        "design",
        "develop",
        "construct",
        "formulate",
        "interpret",
        "classify",
        "what",
        "why",
        "how",
        "which",
        "when",
        "where"
    ]

    if any(
        re.search(
            r"\b" + re.escape(v) + r"\b",
            lower
        )
        for v in question_verbs
    ):
        return True

    if "?" in text:
        return True

    # Numbered assessment content can be a question
    if len(words(text)) >= 7:
        return True

    return False


def extract_numbered_blocks(text):

    """
    Handles:

    1. Question
    2. Question

    Q1. Question
    Q2. Question

    1) Question
    2) Question

    Question numbers may be on separate lines.
    """

    text = text.replace(
        "\r\n",
        "\n"
    )

    pattern = re.compile(
        r"(?:^|\n)"
        r"\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*"
        r"[\.\):\-]"
        r"\s*"
        r"(.*?)"
        r"(?="
        r"\n\s*(?:Q(?:uestion)?\s*)?"
        r"\d{1,3}"
        r"\s*[\.\):\-]"
        r"|$)",
        re.IGNORECASE |
        re.DOTALL
    )

    matches = pattern.findall(
        text
    )

    questions = []

    for _, content in matches:

        content = clean_text(
            content
        )

        if not content:
            continue

        content = remove_mcq_options(
            content
        )

        # Remove common marks at end
        content = re.sub(
            r"\s+\d+\s*marks?$",
            "",
            content,
            flags=re.IGNORECASE
        )

        if looks_like_question(
            content
        ):
            questions.append(
                content
            )

    return questions


def extract_question_sentences(text):

    questions = []

    # First split on question marks
    chunks = re.split(
        r"(?<=\?)",
        text
    )

    for chunk in chunks:

        chunk = clean_text(
            chunk
        )

        if not chunk:
            continue

        if looks_like_question(
            chunk
        ):
            questions.append(
                remove_mcq_options(
                    chunk
                )
            )

    return questions


def extract_paragraph_questions(text):

    questions = []

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    for paragraph in paragraphs:

        paragraph = clean_text(
            paragraph
        )

        if not paragraph:
            continue

        if looks_like_question(
            paragraph
        ):

            # Remove leading numbering
            paragraph = re.sub(
                r"^(?:Q(?:uestion)?\s*)?"
                r"\d{1,3}"
                r"\s*[\.\):\-]\s*",
                "",
                paragraph,
                flags=re.IGNORECASE
            )

            paragraph = remove_mcq_options(
                paragraph
            )

            questions.append(
                paragraph
            )

    return questions


def extract_questions(text):

    text = text.replace(
        "\x00",
        " "
    )

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    # --------------------------------------------------------
    # Normalize excessive spaces while keeping newlines
    # --------------------------------------------------------

    lines = []

    for line in text.split("\n"):

        line = clean_text(
            line
        )

        if line:
            lines.append(line)

    normalized_text = "\n".join(
        lines
    )

    questions = []

    # --------------------------------------------------------
    # Method 1: numbered blocks
    # --------------------------------------------------------

    questions.extend(
        extract_numbered_blocks(
            normalized_text
        )
    )

    # --------------------------------------------------------
    # Method 2: explicit question sentences
    # --------------------------------------------------------

    questions.extend(
        extract_question_sentences(
            normalized_text
        )
    )

    # --------------------------------------------------------
    # Method 3: paragraph-based
    # --------------------------------------------------------

    questions.extend(
        extract_paragraph_questions(
            normalized_text
        )
    )

    # --------------------------------------------------------
    # Method 4: line-by-line question detection
    # --------------------------------------------------------

    for line in lines:

        candidate = line

        candidate = re.sub(
            r"^(?:Q(?:uestion)?\s*)?"
            r"\d{1,3}"
            r"\s*[\.\):\-]\s*",
            "",
            candidate,
            flags=re.IGNORECASE
        )

        candidate = remove_mcq_options(
            candidate
        )

        if looks_like_question(
            candidate
        ):
            questions.append(
                candidate
            )

    # --------------------------------------------------------
    # Method 5: handle questions where number and text
    # are separated across lines
    # --------------------------------------------------------

    i = 0

    while i < len(lines):

        line = lines[i]

        if re.match(
            r"^(?:Q(?:uestion)?\s*)?\d{1,3}\s*[\.\):\-]?$",
            line,
            re.IGNORECASE
        ):

            combined = line

            if i + 1 < len(lines):
                combined += " " + lines[i + 1]

            combined = re.sub(
                r"^(?:Q(?:uestion)?\s*)?\d{1,3}"
                r"\s*[\.\):\-]?\s*",
                "",
                combined,
                flags=re.IGNORECASE
            )

            if looks_like_question(
                combined
            ):
                questions.append(
                    combined
                )

            i += 2
            continue

        i += 1

    # --------------------------------------------------------
    # Remove answer choices that may have remained
    # --------------------------------------------------------

    cleaned = []

    for question in questions:

        question = clean_text(
            question
        )

        question = remove_mcq_options(
            question
        )

        # Remove leading question numbering
        question = re.sub(
            r"^(?:Q(?:uestion)?\s*)?"
            r"\d{1,3}"
            r"\s*[\.\):\-]\s*",
            "",
            question,
            flags=re.IGNORECASE
        )

        # Remove marks
        question = re.sub(
            r"\s+\(?\d+\s*marks?\)?$",
            "",
            question,
            flags=re.IGNORECASE
        )

        if looks_like_question(
            question
        ):
            cleaned.append(
                question
            )

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    final = []

    seen = set()

    for question in cleaned:

        key = normalize(
            question
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)

        final.append(
            question
        )

    return final


# ============================================================
# FILE DIAGNOSTICS
# ============================================================

def show_file_diagnostics(
    filename,
    raw_text
):

    with st.expander(
        "🔎 File Reading Diagnostics"
    ):

        st.write(
            f"**File:** {filename}"
        )

        st.write(
            f"**Extracted characters:** {len(raw_text):,}"
        )

        if raw_text:

            preview = raw_text[:3000]

            st.text_area(
                "Extracted text preview",
                preview,
                height=220
            )

        else:

            st.error(
                "No readable text was extracted from this file."
            )

            st.info(
                "If this is a scanned/image PDF, OCR is required. "
                "Please upload a text-based PDF or DOCX, or provide an OCR-readable file."
            )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎓 OBE Assessment Alignment Checker"
)

st.write(
    "Evaluate assessment questions against CLOs, PLOs, "
    "Bloom's Taxonomy, subject relevance, specificity, "
    "and question quality."
)

st.info(
    "The tool supports MCQs, short-answer questions, "
    "descriptive questions, numerical questions, "
    "scenario-based questions, and other assessment formats."
)


# ============================================================
# INPUT
# ============================================================

st.subheader(
    "1. Assessment Information"
)

col1, col2 = st.columns(2)

with col1:

    subject = st.text_input(
        "Subject / Course",
        placeholder=(
            "Example: Chemistry, English I, "
            "Programming Fundamentals"
        )
    )

with col2:

    target_bloom = st.selectbox(
        "Target Bloom's Level",
        BLOOM_ORDER,
        index=2
    )


st.subheader(
    "2. Learning Outcomes"
)

clo_text = st.text_area(
    "CLOs",
    placeholder=(
        "CLO 1: Explain the principles of chemical bonding\n"
        "CLO 2: Apply chemical concepts to solve problems"
    ),
    height=150
)

plo_text = st.text_area(
    "PLOs",
    placeholder=(
        "PLO 1: Apply knowledge to solve problems\n"
        "PLO 2: Communicate effectively"
    ),
    height=150
)


st.subheader(
    "3. Upload Assessment"
)

uploaded_file = st.file_uploader(
    "Upload your assessment",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "csv",
        "txt"
    ]
)


# ============================================================
# EVALUATE BUTTON
# ============================================================

if uploaded_file is not None:

    if st.button(
        "🔍 Evaluate Assessment",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Reading and evaluating your assessment..."
        ):

            raw_text = read_file(
                uploaded_file
            )

            show_file_diagnostics(
                uploaded_file.name,
                raw_text
            )

            if not raw_text.strip():

                st.error(
                    "The file could not be read. "
                    "Please upload a text-based PDF, DOCX, XLSX, CSV, or TXT file."
                )

            else:

                questions = extract_questions(
                    raw_text
                )

                if not questions:

                    st.error(
                        "No assessment questions could be extracted."
                    )

                    st.warning(
                        "The file was read successfully, but its structure "
                        "does not match the current question patterns."
                    )

                    st.info(
                        "Use the File Reading Diagnostics above to inspect "
                        "the extracted text."
                    )

                else:

                    clos = parse_outcomes(
                        clo_text
                    )

                    plos = parse_outcomes(
                        plo_text
                    )

                    results = []

                    for number, question in enumerate(
                        questions,
                        start=1
                    ):

                        result = evaluate_question(
                            question,
                            subject,
                            clos,
                            plos,
                            target_bloom
                        )

                        result["number"] = number

                        results.append(
                            result
                        )

                    st.session_state.evaluated_questions = results

                    st.session_state.applied_revisions = {}

                    st.session_state.revision_cache = {}

                    st.success(
                        f"{len(results)} assessment question(s) "
                        f"were extracted and evaluated successfully."
                    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.evaluated_questions:

    results = (
        st.session_state.evaluated_questions
    )

    st.divider()

    st.header(
        "📊 Assessment Results"
    )

    initial_average = sum(
        x["overall"]
        for x in results
    ) / len(results)

    initially_attained = sum(
        1
        for x in results
        if x["attained"]
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Questions Evaluated",
            len(results)
        )

    with c2:

        st.metric(
            "Average Alignment Score",
            f"{initial_average:.1f}/100"
        )

    with c3:

        st.metric(
            "Initially Attained",
            f"{initially_attained}/{len(results)}"
        )

    st.divider()

    # ========================================================
    # EACH QUESTION
    # ========================================================

    for item in results:

        number = item["number"]

        st.subheader(
            f"Question {number}"
        )

        st.write(
            f"**Original Question:** "
            f"{item['question']}"
        )

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "Original Alignment Score",
                f"{item['overall']:.1f}/100"
            )

        with c2:

            if item["attained"]:

                st.success(
                    "✓ Alignment is Attained"
                )

            else:

                st.warning(
                    "Alignment Needs Revision"
                )

        score_df = pd.DataFrame(
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
            score_df,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            f"Detected Bloom's Level: "
            f"{item['bloom']} | "
            f"Target: {item['target_bloom']}"
        )

        if item["best_clo"]:

            st.caption(
                f"Best CLO match: "
                f"{item['best_clo']}"
            )

        if item["best_plo"]:

            st.caption(
                f"Best PLO match: "
                f"{item['best_plo']}"
            )

        # ====================================================
        # REVISION
        # ====================================================

        if not item["attained"]:

            st.markdown(
                "### 🔧 Suggested Revisions"
            )

            cache_key = str(
                number
            )

            if cache_key not in st.session_state.revision_cache:

                revisions = generate_revisions(
                    item["question"],
                    subject,
                    parse_outcomes(
                        clo_text
                    ),
                    parse_outcomes(
                        plo_text
                    ),
                    target_bloom
                )

                st.session_state.revision_cache[
                    cache_key
                ] = revisions

            revisions = (
                st.session_state.revision_cache[
                    cache_key
                ]
            )

            if not revisions:

                st.error(
                    "No suitable revision could be generated."
                )

            else:

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

                    r1, r2, r3 = st.columns(3)

                    with r1:

                        st.metric(
                            "Revised Score",
                            f"{revision['overall']:.1f}/100"
                        )

                    with r2:

                        st.metric(
                            "CLO",
                            f"{revision['clo_score']:.1f}%"
                        )

                    with r3:

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
                            "This revision is below 80/100."
                        )

                    comparison = pd.DataFrame(
                        {
                            "Metric": [
                                "Overall",
                                "Subject",
                                "CLO",
                                "PLO",
                                "Bloom's",
                                "Specificity",
                                "Quality"
                            ],
                            "Before": [
                                item["overall"],
                                item["subject_score"],
                                item["clo_score"],
                                item["plo_score"],
                                item["bloom_score"],
                                item["specificity_score"],
                                item["quality_score"]
                            ],
                            "After": [
                                revision["overall"],
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
                        comparison,
                        use_container_width=True,
                        hide_index=True
                    )

                    if st.button(
                        "✓ Select This Revision",
                        key=(
                            f"select_{number}_"
                            f"{revision_index}"
                        ),
                        use_container_width=True
                    ):

                        st.session_state.applied_revisions[
                            number
                        ] = revision

                        st.rerun()

                    st.divider()

        # ====================================================
        # SELECTED REVISION
        # ====================================================

        if number in (
            st.session_state.applied_revisions
        ):

            selected = (
                st.session_state.applied_revisions[
                    number
                ]
            )

            st.markdown(
                "### ✅ Revised Question"
            )

            st.write(
                f"**{selected['question']}**"
            )

            # IMPORTANT:
            # This green message appears only when the
            # calculated revised score is actually 80+.

            if selected["overall"] >= 80:

                st.success(
                    "✓ Alignment is Attained After Revision"
                )

                st.metric(
                    "Final Alignment Score",
                    f"{selected['overall']:.1f}/100"
                )

            else:

                st.error(
                    "The selected revision did not reach "
                    "the required 80/100 alignment score."
                )

                st.metric(
                    "Final Alignment Score",
                    f"{selected['overall']:.1f}/100"
                )

            after_df = pd.DataFrame(
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
                after_df,
                use_container_width=True,
                hide_index=True
            )

        st.divider()


# ============================================================
# FINAL SUMMARY
# ============================================================

if st.session_state.evaluated_questions:

    st.header(
        "📋 Final Summary"
    )

    summary = []

    for item in (
        st.session_state.evaluated_questions
    ):

        number = item["number"]

        if number in (
            st.session_state.applied_revisions
        ):

            selected = (
                st.session_state.applied_revisions[
                    number
                ]
            )

            summary.append(
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
                    "Status":
                        "Alignment is Attained After Revision"
                        if selected["overall"] >= 80
                        else "Needs Further Revision",
                    "Final Question":
                        selected["question"]
                }
            )

        else:

            summary.append(
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
                    "Status":
                        "Alignment is Attained"
                        if item["attained"]
                        else "Needs Revision",
                    "Final Question":
                        item["question"]
                }
            )

    summary_df = pd.DataFrame(
        summary
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

    csv_data = summary_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Final Evaluation",
        data=csv_data,
        file_name=(
            "OBE_Alignment_Evaluation.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )
