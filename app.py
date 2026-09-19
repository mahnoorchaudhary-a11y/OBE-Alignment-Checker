import io
import re
from collections import Counter

import pandas as pd
import streamlit as st

# ============================================================
# OPTIONAL FILE-READING LIBRARIES
# ============================================================

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# CONSTANTS
# ============================================================

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

BLOOM_ORDER = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "label", "select", "match"
    ],
    "Understand": [
        "explain", "describe", "summarize", "interpret",
        "classify", "discuss", "illustrate", "clarify"
    ],
    "Apply": [
        "apply", "calculate", "solve", "use", "demonstrate",
        "implement", "execute", "compute", "determine"
    ],
    "Analyze": [
        "analyze", "analyse", "compare", "contrast", "differentiate",
        "examine", "distinguish", "categorize", "deconstruct"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique", "judge",
        "defend", "validate", "appraise", "argue"
    ],
    "Create": [
        "design", "create", "develop", "construct", "formulate",
        "propose", "produce", "plan", "devise", "develop"
    ]
}

OUTCOME_GENERIC_WORDS = {
    "student",
    "students",
    "learner",
    "learners",
    "ability",
    "abilities",
    "knowledge",
    "understanding",
    "understand",
    "understands",
    "skill",
    "skills",
    "competence",
    "competencies",
    "demonstrate",
    "demonstrates",
    "demonstrating",
    "develop",
    "develops",
    "development",
    "appropriate",
    "effectively",
    "effectively",
    "discipline",
    "field",
    "area",
    "course",
    "courses",
    "program",
    "programs",
    "learning",
    "outcome",
    "outcomes",
    "ability",
    "abilities",
    "capable",
    "capability"
}

OBE_WORDS = {
    "clo",
    "clos",
    "plo",
    "plos",
    "ilo",
    "ilos",
    "bloom",
    "taxonomy",
    "learning",
    "outcome",
    "outcomes",
    "attainment",
    "alignment",
    "aligned",
    "assessment",
    "assessments"
}

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then",
    "of", "to", "in", "on", "for", "from", "with", "by",
    "as", "at", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its",
    "into", "about", "than", "through", "during", "after",
    "before", "between", "within", "using", "use", "used",
    "will", "would", "could", "should", "can", "may", "might",
    "your", "their", "our", "you", "they", "we", "he", "she",
    "which", "what", "when", "where", "why", "how"
}


# ============================================================
# GENERAL TEXT HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
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


def stem(word):
    word = word.lower().strip()

    if len(word) <= 4:
        return word

    endings = [
        "ingly",
        "edly",
        "ation",
        "ments",
        "ment",
        "ness",
        "ities",
        "ity",
        "ingly",
        "ing",
        "ers",
        "ies",
        "es",
        "ed",
        "s"
    ]

    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[:-len(ending)]

    return word


def content_tokens(text):
    words = normalize(text).split()

    result = set()

    for word in words:
        if word in STOP_WORDS:
            continue

        if word in OBE_WORDS:
            continue

        if len(word) < 3:
            continue

        result.add(stem(word))

    return result


def meaningful_outcome_tokens(text):
    words = normalize(text).split()

    result = set()

    bloom_words = set()

    for verbs in BLOOM_VERBS.values():
        bloom_words.update(verbs)

    for word in words:
        if word in STOP_WORDS:
            continue

        if word in OBE_WORDS:
            continue

        if word in OUTCOME_GENERIC_WORDS:
            continue

        if word in bloom_words:
            continue

        if len(word) < 3:
            continue

        result.add(stem(word))

    return result


# ============================================================
# QUESTION PUNCTUATION
# ============================================================

def finalize_question(text):
    """
    Ensures generated questions have exactly one terminal '?'.

    Examples:
    'Explain photosynthesis.?' -> 'Explain photosynthesis?'
    'Explain photosynthesis..' -> 'Explain photosynthesis?'
    'Explain photosynthesis!!!' -> 'Explain photosynthesis?'
    """
    text = clean_text(text)

    text = re.sub(r"[.!?]+$", "", text)
    text = text.strip()

    if not text:
        return ""

    return text + "?"


def normalize_question_punctuation(text):
    text = clean_text(text)

    # Fix '.?' / '..?' / '!!!?' etc.
    text = re.sub(r"[.!?]+$", "", text).strip()

    if not text:
        return ""

    return text + "?"


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    if not PDF_AVAILABLE:
        raise RuntimeError(
            "PyMuPDF is not installed. Install it with: pip install pymupdf"
        )

    data = uploaded_file.read()
    document = fitz.open(stream=data, filetype="pdf")

    pages = []

    for page in document:
        pages.append(page.get_text("text"))

    text = "\n".join(pages).strip()

    # OCR fallback
    if len(text) < 100 and OCR_AVAILABLE:
        ocr_parts = []

        document = fitz.open(stream=data, filetype="pdf")

        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            try:
                ocr_parts.append(pytesseract.image_to_string(image))
            except Exception:
                pass

        text = "\n".join(ocr_parts).strip()

    return text


def read_docx(uploaded_file):
    if not DOCX_AVAILABLE:
        raise RuntimeError(
            "python-docx is not installed. Install it with: pip install python-docx"
        )

    document = Document(uploaded_file)

    paragraphs = [
        p.text.strip()
        for p in document.paragraphs
        if p.text.strip()
    ]

    return "\n".join(paragraphs)


def read_excel(uploaded_file):
    data = uploaded_file.read()

    excel = pd.ExcelFile(io.BytesIO(data))

    parts = []

    for sheet in excel.sheet_names:
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet)

        parts.append(
            f"Sheet: {sheet}\n{df.fillna('').to_string(index=False)}"
        )

    return "\n\n".join(parts)


def read_csv(uploaded_file):
    data = uploaded_file.read()

    try:
        df = pd.read_csv(io.BytesIO(data))
    except Exception:
        df = pd.read_csv(
            io.BytesIO(data),
            encoding_errors="ignore"
        )

    return df.fillna("").to_string(index=False)


def read_txt(uploaded_file):
    data = uploaded_file.read()

    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode("latin-1", errors="ignore")


def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if name.endswith(".docx"):
        return read_docx(uploaded_file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return read_excel(uploaded_file)

    if name.endswith(".csv"):
        return read_csv(uploaded_file)

    if name.endswith(".txt"):
        return read_txt(uploaded_file)

    raise ValueError(
        "Unsupported file format. Please upload PDF, DOCX, XLSX, XLS, CSV or TXT."
    )


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, prefix):
    """
    Extracts CLO/PLO lines from pasted or uploaded text.

    Examples:
    CLO1: Explain...
    CLO 1 - Explain...
    CLO-1: Explain...
    1. Explain...
    """

    if not text:
        return []

    lines = [
        clean_text(x)
        for x in str(text).splitlines()
        if clean_text(x)
    ]

    results = []

    pattern = re.compile(
        rf"^\s*(?:{prefix})?\s*[-:]?\s*\d+\s*[\)\.\-:\u2013]?\s*(.+)$",
        re.IGNORECASE
    )

    explicit_pattern = re.compile(
        rf"^\s*{prefix}\s*[-:]?\s*\d+\s*[\)\.\-:\u2013]?\s*(.+)$",
        re.IGNORECASE
    )

    for line in lines:
        match = explicit_pattern.match(line)

        if match:
            value = clean_text(match.group(1))

            if value:
                results.append(value)

    if results:
        return results

    # If no explicit prefix exists, allow numbered outcomes.
    for line in lines:
        match = pattern.match(line)

        if match:
            value = clean_text(match.group(1))

            if value:
                results.append(value)

    return results


def extract_outcome_core(outcome):
    """
    Removes generic outcome wording and keeps the meaningful
    disciplinary concepts.
    """

    words = normalize(outcome).split()

    bloom_words = set()

    for verbs in BLOOM_VERBS.values():
        bloom_words.update(verbs)

    kept = []

    for word in words:
        if word in STOP_WORDS:
            continue

        if word in OBE_WORDS:
            continue

        if word in OUTCOME_GENERIC_WORDS:
            continue

        if word in bloom_words:
            continue

        if len(word) < 3:
            continue

        kept.append(word)

    return " ".join(kept)


def outcome_concept_phrase(outcome, max_words=5):
    """
    Produces a short natural phrase from an outcome.

    It deliberately removes:
    CLO/PLO terminology,
    Bloom verbs,
    generic educational language.
    """

    core = extract_outcome_core(outcome)

    if not core:
        return ""

    words = core.split()

    # Remove duplicate words
    seen = set()
    selected = []

    for word in words:
        key = stem(word)

        if key in seen:
            continue

        seen.add(key)
        selected.append(word)

        if len(selected) >= max_words:
            break

    return " ".join(selected)


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):
    normalized = normalize(question)

    # Higher levels first so "compare" does not get
    # incorrectly interpreted as a lower level.
    priority = [
        "Create",
        "Evaluate",
        "Analyze",
        "Apply",
        "Understand",
        "Remember"
    ]

    for level in priority:
        verbs = BLOOM_VERBS[level]

        for verb in verbs:
            if re.search(rf"\b{re.escape(verb)}\w*\b", normalized):
                return level

    # Question stems
    if normalized.startswith(("why ", "how ")):
        return "Understand"

    if normalized.startswith(("what ", "who ", "when ", "where ")):
        return "Remember"

    return "Understand"


def bloom_score(question, target_level=None):
    actual = detect_bloom(question)

    if target_level is None:
        return 100

    actual_num = BLOOM_ORDER.get(actual, 2)
    target_num = BLOOM_ORDER.get(target_level, 2)

    if actual == target_level:
        return 100

    # Higher cognitive level can demonstrate a lower-level target.
    if actual_num > target_num:
        return 95

    if actual_num == target_num - 1:
        return 80

    return 55


# ============================================================
# COURSE / SUBJECT DETECTION
# ============================================================

DOMAIN_KEYWORDS = {
    "computer science": {
        "algorithm", "programming", "software", "database", "network",
        "computer", "code", "python", "java", "data", "system",
        "operating", "program", "algorithm", "function", "variable"
    },
    "chemistry": {
        "atom", "molecule", "chemical", "reaction", "bond", "acid",
        "base", "organic", "inorganic", "periodic", "electron",
        "compound", "solution", "molarity", "oxidation", "reduction"
    },
    "physics": {
        "force", "motion", "energy", "momentum", "velocity", "acceleration",
        "electric", "magnetic", "wave", "optics", "mass", "gravity",
        "current", "voltage", "resistance"
    },
    "mathematics": {
        "equation", "function", "matrix", "integral", "derivative",
        "probability", "statistics", "algebra", "geometry", "calculus",
        "vector", "limit", "theorem"
    },
    "biology": {
        "cell", "gene", "protein", "organism", "enzyme", "biology",
        "dna", "rna", "metabolism", "evolution", "tissue", "species"
    },
    "english": {
        "writing", "reading", "essay", "paragraph", "grammar", "tone",
        "purpose", "main", "idea", "organization", "rhetoric",
        "communication", "language", "author"
    },
    "business": {
        "marketing", "finance", "management", "business", "customer",
        "organization", "accounting", "strategy", "market", "investment",
        "leadership", "entrepreneurship"
    },
    "economics": {
        "economy", "economic", "demand", "supply", "market", "inflation",
        "gdp", "unemployment", "price", "consumer", "production"
    },
    "psychology": {
        "behavior", "cognitive", "memory", "emotion", "personality",
        "psychology", "learning", "motivation", "perception"
    }
}


def detect_domain(text):
    tokens = content_tokens(text)

    scores = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        keyword_stems = {stem(x) for x in keywords}

        overlap = tokens.intersection(keyword_stems)

        scores[domain] = len(overlap)

    if not scores:
        return None, 0

    domain = max(scores, key=scores.get)

    if scores[domain] == 0:
        return None, 0

    return domain, scores[domain]


def subject_relevance_score(question, course_name, course_content):
    reference = f"{course_name} {course_content}"

    q_tokens = content_tokens(question)
    ref_tokens = content_tokens(reference)

    if not q_tokens or not ref_tokens:
        return 50

    overlap = q_tokens.intersection(ref_tokens)

    # Strong direct evidence.
    if len(overlap) >= 5:
        return 100

    if len(overlap) == 4:
        return 95

    if len(overlap) == 3:
        return 90

    if len(overlap) == 2:
        return 80

    if len(overlap) == 1:
        return 65

    # Domain fallback
    q_domain, q_domain_score = detect_domain(question)
    c_domain, c_domain_score = detect_domain(reference)

    if q_domain and c_domain and q_domain == c_domain:
        return 85

    return 40


# ============================================================
# OUTCOME ALIGNMENT
# ============================================================

def token_overlap_score(question_tokens, reference_tokens):
    if not question_tokens or not reference_tokens:
        return 0

    overlap = question_tokens.intersection(reference_tokens)

    if not overlap:
        return 0

    # Coverage of the reference concepts.
    reference_coverage = (
        len(overlap) / max(1, len(reference_tokens))
    ) * 100

    # Coverage in the question.
    question_coverage = (
        len(overlap) / max(1, min(len(question_tokens), 8))
    ) * 100

    score = (
        reference_coverage * 0.70
        + question_coverage * 0.30
    )

    return min(100, round(score))


def outcome_action_level(outcome):
    normalized = normalize(outcome)

    found = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(rf"\b{re.escape(verb)}\w*\b", normalized):
                found.append(BLOOM_ORDER[level])

    if not found:
        return None

    # Use the highest explicitly stated cognitive demand.
    return max(found)


def action_alignment_score(question, outcome):
    question_level = detect_bloom(question)
    question_num = BLOOM_ORDER.get(question_level, 2)

    outcome_num = outcome_action_level(outcome)

    if outcome_num is None:
        return 100

    if question_num == outcome_num:
        return 100

    # A higher Bloom level can demonstrate a lower-level outcome.
    if question_num > outcome_num:
        return 95

    if question_num == outcome_num - 1:
        return 80

    if question_num == outcome_num - 2:
        return 65

    return 45


def outcome_alignment_score(
    question,
    outcome,
    course_name="",
    course_content="",
    role="CLO"
):
    q_tokens = content_tokens(question)

    outcome_tokens = meaningful_outcome_tokens(outcome)

    reference = f"{course_name} {course_content}"
    course_tokens = content_tokens(reference)

    concept_score = token_overlap_score(
        q_tokens,
        outcome_tokens
    )

    action_score = action_alignment_score(
        question,
        outcome
    )

    course_score = token_overlap_score(
        q_tokens,
        course_tokens
    )

    # Generic PLOs such as:
    # "Apply knowledge of the discipline"
    # do not have useful literal concepts.
    #
    # For these, action + disciplinary evidence is used.
    if len(outcome_tokens) <= 1:
        score = (
            action_score * 0.65
            + course_score * 0.35
        )
    else:
        if role == "CLO":
            score = (
                concept_score * 0.70
                + action_score * 0.20
                + course_score * 0.10
            )
        else:
            score = (
                concept_score * 0.55
                + action_score * 0.30
                + course_score * 0.15
            )

    return min(100, max(0, round(score)))


def best_outcome(
    question,
    outcomes,
    course_name="",
    course_content="",
    role="CLO"
):
    if not outcomes:
        return "", 0

    scored = []

    for outcome in outcomes:
        score = outcome_alignment_score(
            question,
            outcome,
            course_name,
            course_content,
            role
        )

        scored.append((outcome, score))

    scored.sort(
        key=lambda item: item[1],
        reverse=True
    )

    return scored[0]


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question):
    q = clean_text(question)

    if not q:
        return 0

    score = 70

    word_count = len(q.split())

    if 5 <= word_count <= 35:
        score += 15

    elif 36 <= word_count <= 50:
        score += 5

    elif word_count < 4:
        score -= 20

    else:
        score -= 10

    # Direct question indicators
    if re.search(
        r"\b(define|identify|list|explain|describe|apply|solve|"
        r"analyze|analyse|compare|evaluate|justify|design|create|"
        r"develop|calculate|determine|assess)\b",
        normalize(q)
    ):
        score += 10

    # Avoid OBE jargon inside student-facing questions.
    forbidden = [
        "clo",
        "plo",
        "learning outcome",
        "attainment",
        "alignment",
        "bloom taxonomy"
    ]

    if any(term in normalize(q) for term in forbidden):
        score -= 30

    # Penalize duplicated punctuation.
    if re.search(r"[.!?]{2,}$", q):
        score -= 25

    # Penalize vague wording.
    vague = [
        "discuss everything",
        "write something about",
        "tell me about",
        "explain the learning outcome",
        "according to the clo",
        "according to the plo"
    ]

    for phrase in vague:
        if phrase in normalize(q):
            score -= 25

    return max(0, min(100, round(score)))


# ============================================================
# MAIN EVALUATOR
# ============================================================

def evaluate_question(
    question,
    course_name,
    course_content,
    clos,
    plos,
    target_bloom=None
):
    question = clean_text(question)

    subject = subject_relevance_score(
        question,
        course_name,
        course_content
    )

    matched_clo, clo_score = best_outcome(
        question,
        clos,
        course_name,
        course_content,
        "CLO"
    )

    matched_plo, plo_score = best_outcome(
        question,
        plos,
        course_name,
        course_content,
        "PLO"
    )

    actual_bloom = detect_bloom(question)

    bloom = bloom_score(
        question,
        target_bloom
    )

    quality = quality_score(question)

    # Overall score deliberately gives CLO/PLO substantial weight.
    overall = round(
        subject * 0.20
        + clo_score * 0.30
        + plo_score * 0.25
        + bloom * 0.15
        + quality * 0.10
    )

    # ========================================================
    # ALIGNMENT ATTAINMENT
    #
    # CLO and PLO MUST both be >=80.
    # ========================================================

    attained = (
        overall >= 80
        and subject >= 80
        and clo_score >= 80
        and plo_score >= 80
        and bloom >= 80
        and quality >= 70
    )

    if attained:
        status = "Alignment Attained"
    elif overall >= 60:
        status = "Needs Revision"
    else:
        status = "Not Aligned"

    return {
        "question": question,
        "overall": overall,
        "subject": subject,
        "clo": clo_score,
        "plo": plo_score,
        "bloom": bloom,
        "quality": quality,
        "actual_bloom": actual_bloom,
        "matched_clo": matched_clo,
        "matched_plo": matched_plo,
        "status": status
    }


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def clean_question_candidate(text):
    text = clean_text(text)

    # Remove common question numbering.
    text = re.sub(
        r"^\s*(?:Q(?:uestion)?\s*)?\d+\s*[\)\.\-:]\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Remove bullets.
    text = re.sub(r"^\s*[-*•]\s*", "", text)

    return clean_text(text)


def looks_like_question(text):
    text = clean_text(text)

    if len(text.split()) < 4:
        return False

    # Exclude obvious headings.
    heading_terms = [
        "course objectives",
        "course description",
        "learning outcomes",
        "clo",
        "plo",
        "rubric",
        "answer key",
        "marks distribution",
        "instructions"
    ]

    normalized = normalize(text)

    if any(normalized == x for x in heading_terms):
        return False

    return True


def extract_questions_from_text(text):
    if not text:
        return []

    text = text.replace("\r\n", "\n")

    questions = []

    # First try line-based extraction.
    lines = text.splitlines()

    current = ""

    for line in lines:
        line = clean_question_candidate(line)

        if not line:
            continue

        # Numbered question
        numbered = re.match(
            r"^\s*(?:Q(?:uestion)?\s*)?\d+\s*[\)\.\-:]\s*(.+)",
            line,
            flags=re.IGNORECASE
        )

        if numbered:
            if current and looks_like_question(current):
                questions.append(current)

            current = numbered.group(1).strip()
            continue

        # If line ends with ? treat it as a question.
        if "?" in line:
            if current:
                current += " " + line
            else:
                current = line

            if looks_like_question(current):
                questions.append(current)

            current = ""
            continue

        # Continuation line
        if current:
            current += " " + line
        else:
            current = line

    if current and looks_like_question(current):
        questions.append(current)

    # Second fallback: sentence extraction.
    if not questions:
        sentence_parts = re.split(
            r"(?<=[?])\s+",
            clean_text(text)
        )

        for part in sentence_parts:
            part = clean_question_candidate(part)

            if looks_like_question(part):
                questions.append(part)

    # Remove duplicates
    final = []
    seen = set()

    for question in questions:
        key = normalize(question)

        if key in seen:
            continue

        seen.add(key)
        final.append(question)

    return final


# ============================================================
# REVISION TOPIC EXTRACTION
# ============================================================

def extract_topic_phrases(course_content):
    if not course_content:
        return []

    lines = [
        clean_text(line)
        for line in str(course_content).splitlines()
        if clean_text(line)
    ]

    topics = []

    for line in lines:
        line = re.sub(
            r"^\s*(?:\d+[\)\.\-:]|[-*•])\s*",
            "",
            line
        )

        if len(line.split()) >= 2:
            topics.append(line)

    # If there are no useful lines, use sentence fragments.
    if not topics:
        pieces = re.split(r"[.;]\s+", clean_text(course_content))

        for piece in pieces:
            if len(piece.split()) >= 2:
                topics.append(piece)

    return topics[:100]


def choose_revision_topic(
    course_name,
    course_content,
    matched_clo,
    matched_plo
):
    topics = extract_topic_phrases(course_content)

    if not topics:
        if course_name:
            return clean_text(course_name)

        return outcome_concept_phrase(
            matched_clo,
            5
        ) or outcome_concept_phrase(
            matched_plo,
            5
        ) or "the given topic"

    clo_tokens = meaningful_outcome_tokens(matched_clo)
    plo_tokens = meaningful_outcome_tokens(matched_plo)

    best_topic = topics[0]
    best_score = -1

    for topic in topics:
        topic_tokens = content_tokens(topic)

        clo_overlap = len(
            topic_tokens.intersection(clo_tokens)
        )

        plo_overlap = len(
            topic_tokens.intersection(plo_tokens)
        )

        topic_score = (
            clo_overlap * 5
            + plo_overlap * 4
            + min(len(topic_tokens), 8)
        )

        if topic_score > best_score:
            best_score = topic_score
            best_topic = topic

    # Keep questions direct rather than embedding an entire paragraph.
    words = best_topic.split()

    if len(words) > 10:
        best_topic = " ".join(words[:10])

    return best_topic


# ============================================================
# REVISION ANCHORS
# ============================================================

def get_alignment_anchors(
    course_name,
    course_content,
    matched_clo,
    matched_plo
):
    topic = choose_revision_topic(
        course_name,
        course_content,
        matched_clo,
        matched_plo
    )

    clo_phrase = outcome_concept_phrase(
        matched_clo,
        max_words=4
    )

    plo_phrase = outcome_concept_phrase(
        matched_plo,
        max_words=4
    )

    # Generic PLO fallback:
    #
    # Example:
    # "Apply knowledge of the discipline"
    #
    # There may be no useful PLO noun.
    # In that situation the actual course topic becomes
    # the disciplinary evidence.
    if not plo_phrase:
        plo_phrase = topic

    if not clo_phrase:
        clo_phrase = topic

    return {
        "topic": topic,
        "clo": clo_phrase,
        "plo": plo_phrase
    }


# ============================================================
# REVISION CANDIDATE GENERATION
# ============================================================

def generate_revision_candidates(
    original_question,
    course_name,
    course_content,
    matched_clo,
    matched_plo,
    target_bloom
):
    anchors = get_alignment_anchors(
        course_name,
        course_content,
        matched_clo,
        matched_plo
    )

    topic = anchors["topic"]
    clo = anchors["clo"]
    plo = anchors["plo"]

    candidates = []

    if target_bloom == "Remember":
        candidates = [
            f"Define {topic} and identify its key features",
            f"Define {clo} in the context of {topic} and list its main features",
            f"Identify the main features of {topic} and state the role of {clo}",
            f"List the key characteristics of {topic} related to {clo}",
            f"Define {topic} and identify the main elements involved in {clo}",
            f"Identify {clo} and state its main characteristics in {topic}"
        ]

    elif target_bloom == "Understand":
        candidates = [
            f"Explain {topic} and describe how {clo} relates to it",
            f"Explain {topic} and describe the role of {clo}",
            f"Describe {topic} and explain the relationship between {clo} and {plo}",
            f"Explain the main features of {topic} and how they involve {clo}",
            f"Describe {topic} and explain how {clo} contributes to its operation",
            f"Explain {clo} within the context of {topic} and describe its main features"
        ]

    elif target_bloom == "Apply":
        candidates = [
            f"Given a practical situation involving {topic}, apply {clo} to determine the correct result",
            f"Apply {clo} to solve a practical problem involving {topic}",
            f"Given a problem involving {topic}, use {clo} to determine an appropriate solution",
            f"Use {clo} to solve the following practical problem involving {topic}",
            f"Given a practical case involving {topic}, apply the principles of {clo} to obtain the result",
            f"Apply {clo} to a practical situation involving {topic} and determine the outcome"
        ]

    elif target_bloom == "Analyze":
        candidates = [
            f"Analyze {topic} and explain how {clo} affects {plo}",
            f"Analyze {topic} by examining the relationship between {clo} and {plo}",
            f"Analyze {topic} and distinguish the major components related to {clo}",
            f"Analyze the main components of {topic} and explain their relationship to {clo}",
            f"Examine {topic} and analyze how {clo} influences the resulting outcome",
            f"Compare the relevant components of {topic} and analyze their connection with {clo}"
        ]

    elif target_bloom == "Evaluate":
        candidates = [
            f"Evaluate {topic} using {clo} as a criterion and justify your conclusion",
            f"Assess {topic} using relevant criteria related to {clo} and justify your judgment",
            f"Evaluate the effectiveness of {topic} with reference to {clo} and justify your conclusion",
            f"Critique {topic} using {clo} as evidence and justify your conclusion",
            f"Assess {topic} and justify your conclusion using evidence related to {clo}",
            f"Evaluate the solution to a problem involving {topic} and justify the decision using {clo}"
        ]

    else:
        candidates = [
            f"Design a practical solution for a problem involving {topic} using {clo} and {plo}",
            f"Develop a solution to a practical problem involving {topic} using the principles of {clo}",
            f"Design an approach to address a problem involving {topic} using {clo}",
            f"Create a practical solution involving {topic} that applies {clo}",
            f"Develop a practical model for {topic} using {clo} and explain its main components",
            f"Design a solution involving {topic} that integrates {clo} with {plo}"
        ]

    # Always finalize punctuation here.
    finalized = []

    for candidate in candidates:
        candidate = finalize_question(candidate)

        if candidate:
            finalized.append(candidate)

    # Remove duplicates.
    unique = []
    seen = set()

    for candidate in finalized:
        key = normalize(candidate)

        if key in seen:
            continue

        seen.add(key)
        unique.append(candidate)

    return unique


# ============================================================
# STRONGER REVISION CANDIDATES
# ============================================================

def generate_stronger_candidates(
    course_name,
    course_content,
    matched_clo,
    matched_plo,
    target_bloom
):
    anchors = get_alignment_anchors(
        course_name,
        course_content,
        matched_clo,
        matched_plo
    )

    topic = anchors["topic"]
    clo = anchors["clo"]
    plo = anchors["plo"]

    candidates = []

    if target_bloom == "Remember":
        candidates = [
            f"Define {topic} and list the key elements of {clo}",
            f"Identify the key elements of {topic} and state their characteristics",
            f"Define {clo} and identify its key elements in {topic}",
            f"List the major features of {topic} associated with {clo}"
        ]

    elif target_bloom == "Understand":
        candidates = [
            f"Explain {topic} and describe how {clo} operates within it",
            f"Explain the relationship between {topic} and {clo}",
            f"Describe {topic} and explain how {clo} contributes to it",
            f"Explain {clo} using {topic} as the context"
        ]

    elif target_bloom == "Apply":
        candidates = [
            f"Given a practical problem involving {topic}, apply {clo} to solve it",
            f"Apply {clo} to determine the correct solution to a problem involving {topic}",
            f"Use {clo} to solve a practical problem based on {topic}",
            f"Given a case involving {topic}, apply {clo} and determine the result"
        ]

    elif target_bloom == "Analyze":
        candidates = [
            f"Analyze {topic} by examining how {clo} affects its major components",
            f"Analyze the relationship between {topic}, {clo}, and {plo}",
            f"Examine {topic} and analyze the effect of {clo} on the outcome",
            f"Analyze the major components of {topic} and their relationship to {clo}"
        ]

    elif target_bloom == "Evaluate":
        candidates = [
            f"Evaluate {topic} using {clo} as a criterion and justify your conclusion with evidence",
            f"Assess {topic} against relevant criteria related to {clo} and justify your judgment",
            f"Evaluate a solution involving {topic} and justify the decision using {clo}",
            f"Critique {topic} using evidence related to {clo} and justify your conclusion"
        ]

    else:
        candidates = [
            f"Design a practical solution for {topic} using {clo} and {plo}",
            f"Develop a solution to a problem involving {topic} by applying {clo}",
            f"Create a practical approach to {topic} using {clo} and {plo}",
            f"Design a model involving {topic} that integrates {clo}"
        ]

    return [
        finalize_question(candidate)
        for candidate in candidates
    ]


# ============================================================
# REVISION VALIDATION
# ============================================================

def revision_passes(result):
    """
    STRICT SUCCESS CONDITION.

    A revision is successful ONLY when:
      Overall >= 80
      Subject >= 80
      CLO >= 80
      PLO >= 80
      Bloom >= 80
      Quality >= 70
    """

    return (
        result["overall"] >= 80
        and result["subject"] >= 80
        and result["clo"] >= 80
        and result["plo"] >= 80
        and result["bloom"] >= 80
        and result["quality"] >= 70
    )


def revision_strength(result):
    """
    Ranks candidates by their weakest important metric first.

    This prevents a candidate with Overall 88 but CLO 65
    from beating a candidate with Overall 83 and CLO 82.
    """

    minimum = min(
        result["subject"],
        result["clo"],
        result["plo"],
        result["bloom"]
    )

    total = (
        result["overall"]
        + result["subject"]
        + result["clo"]
        + result["plo"]
        + result["bloom"]
        + result["quality"]
    )

    return (
        minimum,
        total,
        result["overall"]
    )


def create_validated_revision(
    original_question,
    course_name,
    course_content,
    clos,
    plos,
    target_bloom
):
    """
    Generate multiple revisions and ONLY accept one that passes
    the strict 80% thresholds.
    """

    if not clos or not plos:
        return {
            "question": "",
            "result": None,
            "attained": False,
            "message": "Both CLO and PLO information are required."
        }

    # Find the outcomes that the ORIGINAL question is closest to.
    matched_clo, _ = best_outcome(
        original_question,
        clos,
        course_name,
        course_content,
        "CLO"
    )

    matched_plo, _ = best_outcome(
        original_question,
        plos,
        course_name,
        course_content,
        "PLO"
    )

    candidates = generate_revision_candidates(
        original_question,
        course_name,
        course_content,
        matched_clo,
        matched_plo,
        target_bloom
    )

    stronger = generate_stronger_candidates(
        course_name,
        course_content,
        matched_clo,
        matched_plo,
        target_bloom
    )

    candidates.extend(stronger)

    tested = []

    seen = set()

    for candidate in candidates:
        candidate = finalize_question(candidate)

        key = normalize(candidate)

        if key in seen:
            continue

        seen.add(key)

        result = evaluate_question(
            candidate,
            course_name,
            course_content,
            clos,
            plos,
            target_bloom
        )

        tested.append(
            (candidate, result)
        )

        # ====================================================
        # CRITICAL:
        # DO NOT ACCEPT A REVISION BELOW 80.
        # ====================================================

        if revision_passes(result):
            return {
                "question": candidate,
                "result": result,
                "attained": True,
                "matched_clo": matched_clo,
                "matched_plo": matched_plo,
                "message": "Alignment achieved after validated revision."
            }

    # No candidate passed.
    if tested:
        best_question, best_result = max(
            tested,
            key=lambda item: revision_strength(item[1])
        )

        return {
            "question": best_question,
            "result": best_result,
            "attained": False,
            "matched_clo": matched_clo,
            "matched_plo": matched_plo,
            "message": (
                "No generated revision reached all 80% thresholds. "
                "The displayed question is the strongest tested revision."
            )
        }

    return {
        "question": "",
        "result": None,
        "attained": False,
        "message": "No revision could be generated."
    }


# ============================================================
# DISPLAY HELPERS
# ============================================================

def score_color(score):
    if score >= 80:
        return "🟢"

    if score >= 60:
        return "🟡"

    return "🔴"


def display_score_card(label, score):
    st.metric(
        label,
        f"{score}/100",
        delta="Attained" if score >= 80 else "Below 80"
    )


def show_evaluation(result):
    if not result:
        return

    st.markdown("### Evaluation Scores")

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        display_score_card(
            "Overall",
            result["overall"]
        )

    with c2:
        display_score_card(
            "Subject",
            result["subject"]
        )

    with c3:
        display_score_card(
            "CLO",
            result["clo"]
        )

    with c4:
        display_score_card(
            "PLO",
            result["plo"]
        )

    with c5:
        display_score_card(
            "Bloom",
            result["bloom"]
        )

    with c6:
        display_score_card(
            "Quality",
            result["quality"]
        )

    if result["status"] == "Alignment Attained":
        st.success(
            "✅ ALIGNMENT ATTAINED — Overall, CLO and PLO requirements are all at or above 80%."
        )
    elif result["overall"] >= 60:
        st.warning(
            "⚠️ Revision Required — one or more alignment requirements are below 80%."
        )
    else:
        st.error(
            "❌ NOT ALIGNED — substantial revision is required."
        )

    st.markdown("### Alignment Evidence")

    e1, e2 = st.columns(2)

    with e1:
        st.write(
            f"**Matched CLO:** "
            f"{result.get('matched_clo', 'Not detected')}"
        )

        st.write(
            f"**CLO Score:** "
            f"{score_color(result['clo'])} {result['clo']}/100"
        )

    with e2:
        st.write(
            f"**Matched PLO:** "
            f"{result.get('matched_plo', 'Not detected')}"
        )

        st.write(
            f"**PLO Score:** "
            f"{score_color(result['plo'])} {result['plo']}/100"
        )

    st.write(
        f"**Detected Bloom Level:** {result['actual_bloom']}"
    )


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = []

if "revision_results" not in st.session_state:
    st.session_state.revision_results = {}

if "stronger_revision_counter" not in st.session_state:
    st.session_state.stronger_revision_counter = {}


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Assessment Alignment Checker")

st.caption(
    "Evaluate assessment questions against course content, CLOs, PLOs and Bloom's Taxonomy."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Assessment Setup")

    course_name = st.text_input(
        "Course / Subject Name",
        placeholder="e.g., Chemistry, English I, Programming Fundamentals"
    )

    target_bloom = st.selectbox(
        "Target Bloom's Level",
        BLOOM_LEVELS,
        index=2
    )

    st.markdown("---")

    st.info(
        "A successful revised question must achieve at least "
        "**80/100 Overall, Subject, CLO, PLO and Bloom scores**."
    )


# ============================================================
# MAIN INPUTS
# ============================================================

left, right = st.columns(2)

with left:
    st.subheader("Course Content")

    course_content = st.text_area(
        "Enter syllabus/course content",
        height=220,
        placeholder=(
            "Paste topics, syllabus content, chapters, concepts, "
            "or course material here."
        )
    )

with right:
    st.subheader("CLOs")

    clo_text = st.text_area(
        "Enter CLOs",
        height=220,
        placeholder=(
            "CLO 1: Explain fundamental principles of chemical bonding\n"
            "CLO 2: Apply chemical bonding principles to solve problems"
        )
    )


st.subheader("PLOs")

plo_text = st.text_area(
    "Enter PLOs",
    height=160,
    placeholder=(
        "PLO 1: Apply knowledge of the discipline\n"
        "PLO 2: Analyze problems and develop appropriate solutions"
    )
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.markdown("---")

st.subheader("📄 Upload Assessment File")

uploaded_file = st.file_uploader(
    "Upload an assessment",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt"
    ]
)

uploaded_text = ""

if uploaded_file is not None:
    try:
        uploaded_text = read_uploaded_file(uploaded_file)

        if uploaded_text:
            st.success(
                f"Successfully read: {uploaded_file.name}"
            )

            with st.expander("Preview extracted content"):
                st.text(
                    uploaded_text[:10000]
                )
        else:
            st.warning(
                "The file was read but no usable text was extracted."
            )

    except Exception as exc:
        st.error(
            f"Could not read the uploaded file: {exc}"
        )


# ============================================================
# MANUAL QUESTION
# ============================================================

st.markdown("---")

st.subheader("✍️ Assessment Question")

manual_question = st.text_area(
    "Enter one question manually",
    height=130,
    placeholder="Enter the assessment question here..."
)


# ============================================================
# QUESTION SOURCE SELECTION
# ============================================================

questions_from_file = []

if uploaded_text:
    questions_from_file = extract_questions_from_text(
        uploaded_text
    )

all_questions = []

if questions_from_file:
    all_questions.extend(questions_from_file)

if manual_question.strip():
    all_questions.append(
        clean_text(manual_question)
    )

# Deduplicate
unique_questions = []
seen_questions = set()

for question in all_questions:
    key = normalize(question)

    if key in seen_questions:
        continue

    seen_questions.add(key)
    unique_questions.append(question)

all_questions = unique_questions


if questions_from_file:
    st.info(
        f"{len(questions_from_file)} assessment question(s) detected from the file."
    )


# ============================================================
# PARSE CLO / PLO
# ============================================================

clos = parse_outcomes(
    clo_text,
    "CLO"
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)

if clos:
    with st.expander(
        f"Detected CLOs ({len(clos)})"
    ):
        for i, clo in enumerate(clos, 1):
            st.write(f"**CLO {i}:** {clo}")

if plos:
    with st.expander(
        f"Detected PLOs ({len(plos)})"
    ):
        for i, plo in enumerate(plos, 1):
            st.write(f"**PLO {i}:** {plo}")


# ============================================================
# VALIDATION
# ============================================================

st.markdown("---")

missing_items = []

if not course_name.strip():
    missing_items.append("Course / Subject Name")

if not course_content.strip():
    missing_items.append("Course Content")

if not clos:
    missing_items.append("at least one CLO")

if not plos:
    missing_items.append("at least one PLO")

if not all_questions:
    missing_items.append("at least one assessment question")


if missing_items:
    st.warning(
        "Please provide: " + ", ".join(missing_items) + "."
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

analyze_button = st.button(
    "🔍 Evaluate Assessment",
    type="primary",
    use_container_width=True
)


if analyze_button:

    if missing_items:
        st.error(
            "The assessment cannot be evaluated until all required information is provided."
        )
        st.stop()

    results = []

    progress = st.progress(0)

    for index, question in enumerate(all_questions):

        question = clean_text(question)

        result = evaluate_question(
            question,
            course_name,
            course_content,
            clos,
            plos,
            target_bloom
        )

        results.append(result)

        progress.progress(
            (index + 1) / len(all_questions)
        )

    progress.empty()

    st.session_state.analysis_results = results
    st.session_state.revision_results = {}

    st.success(
        f"Evaluation completed for {len(results)} question(s)."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis_results:

    st.markdown("---")
    st.header("📊 Assessment Results")

    results = st.session_state.analysis_results

    summary_data = []

    for i, result in enumerate(results, 1):
        summary_data.append({
            "Question": f"Q{i}",
            "Overall": result["overall"],
            "Subject": result["subject"],
            "CLO": result["clo"],
            "PLO": result["plo"],
            "Bloom": result["bloom"],
            "Quality": result["quality"],
            "Status": result["status"]
        })

    summary_df = pd.DataFrame(summary_data)

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # QUESTION-BY-QUESTION RESULTS
    # ========================================================

    for index, result in enumerate(results):

        question_number = index + 1

        with st.expander(
            f"Question {question_number} — "
            f"{result['status']} — "
            f"{result['overall']}/100"
        ):

            st.markdown("### Original Question")

            st.write(
                result["question"]
            )

            show_evaluation(result)

            # =================================================
            # REVISION
            # =================================================

            st.markdown("---")

            st.markdown("### 🔧 Validated Revision")

            revision_key = f"revision_{index}"

            generate_revision_button = st.button(
                "Generate Revision",
                key=f"generate_{index}"
            )

            if generate_revision_button:

                with st.spinner(
                    "Generating and validating revision..."
                ):

                    revision = create_validated_revision(
                        result["question"],
                        course_name,
                        course_content,
                        clos,
                        plos,
                        target_bloom
                    )

                st.session_state.revision_results[
                    revision_key
                ] = revision

            # =================================================
            # DISPLAY REVISION
            # =================================================

            if revision_key in st.session_state.revision_results:

                revision = st.session_state.revision_results[
                    revision_key
                ]

                if revision["question"]:

                    if revision["attained"]:
                        st.success(
                            "✅ VALIDATED REVISION — ALIGNMENT ATTAINED"
                        )
                    else:
                        st.warning(
                            "⚠️ The generated revision did not pass all "
                            "80% requirements. It is shown only as the "
                            "strongest tested revision."
                        )

                    st.markdown("#### Revised Question")

                    # Extra punctuation protection
                    displayed_revision = finalize_question(
                        revision["question"]
                    )

                    st.text_area(
                        "Revision",
                        value=displayed_revision,
                        height=120,
                        key=f"display_revision_{index}"
                    )

                    if revision["result"]:

                        revised_result = revision["result"]

                        st.markdown(
                            "#### Revised Question Scores"
                        )

                        r1, r2, r3, r4, r5, r6 = st.columns(6)

                        with r1:
                            st.metric(
                                "Overall",
                                f"{revised_result['overall']}/100"
                            )

                        with r2:
                            st.metric(
                                "Subject",
                                f"{revised_result['subject']}/100"
                            )

                        with r3:
                            st.metric(
                                "CLO",
                                f"{revised_result['clo']}/100"
                            )

                        with r4:
                            st.metric(
                                "PLO",
                                f"{revised_result['plo']}/100"
                            )

                        with r5:
                            st.metric(
                                "Bloom",
                                f"{revised_result['bloom']}/100"
                            )

                        with r6:
                            st.metric(
                                "Quality",
                                f"{revised_result['quality']}/100"
                            )

                        # =====================================
                        # VERY IMPORTANT SUCCESS CHECK
                        # =====================================

                        if revision["attained"]:

                            st.success(
                                "🎯 ALIGNMENT ACHIEVED AFTER REVISION"
                            )

                            st.markdown(
                                f"""
**Overall:** {revised_result['overall']}/100  
**Subject:** {revised_result['subject']}/100  
**CLO:** {revised_result['clo']}/100  
**PLO:** {revised_result['plo']}/100  
**Bloom:** {revised_result['bloom']}/100  
**Quality:** {revised_result['quality']}/100
"""
                            )

                            st.info(
                                "The revised question passed the strict "
                                "80% alignment requirements."
                            )

                        else:

                            failed_metrics = []

                            if revised_result["overall"] < 80:
                                failed_metrics.append(
                                    f"Overall {revised_result['overall']}"
                                )

                            if revised_result["subject"] < 80:
                                failed_metrics.append(
                                    f"Subject {revised_result['subject']}"
                                )

                            if revised_result["clo"] < 80:
                                failed_metrics.append(
                                    f"CLO {revised_result['clo']}"
                                )

                            if revised_result["plo"] < 80:
                                failed_metrics.append(
                                    f"PLO {revised_result['plo']}"
                                )

                            if revised_result["bloom"] < 80:
                                failed_metrics.append(
                                    f"Bloom {revised_result['bloom']}"
                                )

                            st.error(
                                "Revision still below required threshold: "
                                + ", ".join(failed_metrics)
                            )

                        # =====================================
                        # MATCHED OUTCOMES
                        # =====================================

                        with st.expander(
                            "View alignment evidence"
                        ):

                            st.write(
                                "**Matched CLO:**",
                                revised_result.get(
                                    "matched_clo",
                                    "Not detected"
                                )
                            )

                            st.write(
                                "**Matched PLO:**",
                                revised_result.get(
                                    "matched_plo",
                                    "Not detected"
                                )
                            )

                            st.write(
                                "**Detected Bloom Level:**",
                                revised_result.get(
                                    "actual_bloom",
                                    "Not detected"
                                )
                            )

                            st.write(
                                "**Target Bloom Level:**",
                                target_bloom
                            )

                    # =========================================
                    # STRONGER REVISION
                    # =========================================

                    if not revision["attained"]:

                        stronger_button = st.button(
                            "🔄 Generate Stronger Revision",
                            key=f"stronger_{index}"
                        )

                        if stronger_button:

                            with st.spinner(
                                "Generating a stronger alignment-focused revision..."
                            ):

                                stronger = create_validated_revision(
                                    result["question"],
                                    course_name,
                                    course_content,
                                    clos,
                                    plos,
                                    target_bloom
                                )

                            st.session_state.revision_results[
                                revision_key
                            ] = stronger

                            st.rerun()

                else:
                    st.error(
                        revision.get(
                            "message",
                            "Unable to generate revision."
                        )
                    )


# ============================================================
# EXPORT RESULTS
# ============================================================

if st.session_state.analysis_results:

    st.markdown("---")
    st.header("📥 Export Results")

    export_rows = []

    for index, original in enumerate(
        st.session_state.analysis_results
    ):

        revision_key = f"revision_{index}"

        revision = st.session_state.revision_results.get(
            revision_key
        )

        row = {
            "Question": f"Q{index + 1}",
            "Original Question": original["question"],
            "Original Overall": original["overall"],
            "Original Subject": original["subject"],
            "Original CLO": original["clo"],
            "Original PLO": original["plo"],
            "Original Bloom": original["bloom"],
            "Original Quality": original["quality"],
            "Original Status": original["status"],
            "Revised Question": "",
            "Revised Overall": "",
            "Revised Subject": "",
            "Revised CLO": "",
            "Revised PLO": "",
            "Revised Bloom": "",
            "Revised Quality": "",
            "Revision Alignment Attained": ""
        }

        if revision and revision.get("result"):

            rr = revision["result"]

            row["Revised Question"] = finalize_question(
                revision.get("question", "")
            )

            row["Revised Overall"] = rr["overall"]
            row["Revised Subject"] = rr["subject"]
            row["Revised CLO"] = rr["clo"]
            row["Revised PLO"] = rr["plo"]
            row["Revised Bloom"] = rr["bloom"]
            row["Revised Quality"] = rr["quality"]

            row["Revision Alignment Attained"] = (
                "YES"
                if revision.get("attained")
                else "NO"
            )

        export_rows.append(row)

    export_df = pd.DataFrame(export_rows)

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Evaluation Report",
        data=csv_data,
        file_name="OBE_Assessment_Alignment_Report.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "OBE Assessment Alignment Checker | "
    "Validated CLO/PLO revision scoring"
)
