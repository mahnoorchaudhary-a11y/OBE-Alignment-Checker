import io
import re
import os
from collections import Counter

import pandas as pd
import streamlit as st

# Optional libraries
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from docx import Document
except Exception:
    Document = None


# ============================================================
# PAGE CONFIG
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

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state", "recall",
        "recognize", "label", "match", "select"
    ],
    "Understand": [
        "explain", "describe", "summarize", "discuss", "interpret",
        "classify", "illustrate", "compare", "paraphrase"
    ],
    "Apply": [
        "calculate", "solve", "apply", "use", "demonstrate",
        "implement", "execute", "compute", "determine"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine", "compare",
        "contrast", "categorize", "investigate", "distinguish"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "judge", "critique",
        "defend", "argue", "recommend", "appraise"
    ],
    "Create": [
        "design", "develop", "construct", "formulate", "create",
        "propose", "plan", "produce", "develop"
    ]
}


DOMAIN_LEXICONS = {
    "Chemistry": [
        "atom", "molecule", "bond", "ionic", "covalent", "reaction",
        "acid", "base", "ph", "molarity", "mole", "stoichiometry",
        "equilibrium", "organic", "inorganic", "oxidation",
        "reduction", "electron", "periodic", "compound", "solution",
        "concentration", "thermodynamics", "kinetics", "catalyst"
    ],
    "Physics": [
        "force", "motion", "velocity", "acceleration", "energy",
        "momentum", "mass", "work", "power", "electric", "magnetic",
        "field", "wave", "frequency", "voltage", "current",
        "resistance", "circuit", "optics", "quantum", "pressure"
    ],
    "Mathematics": [
        "equation", "function", "derivative", "integral", "matrix",
        "vector", "probability", "statistics", "limit", "algebra",
        "geometry", "calculus", "theorem", "variable", "coefficient",
        "logarithm", "sequence", "series"
    ],
    "Computer Science": [
        "algorithm", "program", "programming", "code", "database",
        "software", "hardware", "network", "class", "object",
        "function", "recursion", "array", "stack", "queue",
        "tree", "graph", "sorting", "searching", "operating system",
        "computer", "data structure", "machine learning", "security"
    ],
    "English / Language": [
        "grammar", "writing", "reading", "paragraph", "essay",
        "thesis", "main idea", "tone", "purpose", "audience",
        "paraphrase", "summary", "argument", "rhetoric", "language",
        "sentence", "vocabulary", "comprehension", "organization"
    ],
    "Literature": [
        "novel", "poem", "poetry", "character", "theme", "plot",
        "symbolism", "setting", "narrator", "metaphor", "imagery",
        "literary", "protagonist", "conflict", "author", "fiction"
    ],
    "Business / Management": [
        "management", "marketing", "leadership", "organization",
        "strategy", "business", "consumer", "market", "planning",
        "decision", "entrepreneur", "human resource", "motivation",
        "performance", "manager", "competitive"
    ],
    "Accounting / Finance": [
        "accounting", "ledger", "journal", "balance sheet",
        "income statement", "asset", "liability", "equity",
        "revenue", "expense", "profit", "cash flow", "audit",
        "finance", "investment", "ratio", "depreciation"
    ],
    "Economics": [
        "economics", "demand", "supply", "market", "inflation",
        "unemployment", "gdp", "price", "elasticity", "utility",
        "consumer", "producer", "fiscal", "monetary", "trade"
    ],
    "Engineering": [
        "engineering", "design", "system", "mechanical", "electrical",
        "civil", "structure", "material", "load", "stress",
        "circuit", "control", "machine", "process", "safety"
    ],
    "Psychology": [
        "psychology", "behavior", "cognition", "memory", "learning",
        "emotion", "personality", "motivation", "development",
        "perception", "attention", "mental", "social"
    ],
    "Sociology": [
        "society", "social", "culture", "class", "community",
        "institution", "inequality", "gender", "family",
        "socialization", "group", "deviance", "population"
    ],
    "Education": [
        "education", "teaching", "learning", "pedagogy", "curriculum",
        "assessment", "student", "teacher", "instruction",
        "classroom", "lesson", "learning theory", "evaluation"
    ],
    "History": [
        "history", "war", "empire", "revolution", "colonial",
        "independence", "civilization", "treaty", "political",
        "historical", "dynasty", "movement", "leader"
    ],
    "Law": [
        "law", "legal", "court", "contract", "tort", "constitution",
        "statute", "case", "judgment", "liability", "crime",
        "evidence", "rights", "legislation"
    ],
    "Pharmacy": [
        "drug", "medicine", "pharmacy", "dose", "dosage",
        "pharmacology", "tablet", "capsule", "patient",
        "therapeutic", "drug interaction", "prescription",
        "absorption", "metabolism"
    ],
    "Medical / Health Sciences": [
        "patient", "disease", "diagnosis", "treatment", "clinical",
        "medical", "health", "symptom", "anatomy", "physiology",
        "infection", "therapy", "hospital"
    ],
    "Environmental Science": [
        "environment", "pollution", "climate", "ecosystem",
        "biodiversity", "sustainability", "carbon", "waste",
        "water", "soil", "air", "conservation", "renewable"
    ]
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def stem(word):
    word = word.lower()

    endings = [
        "ingly", "edly", "ing", "ies", "ied",
        "es", "s", "ment", "tion", "ions",
        "ness", "ity"
    ]

    for ending in endings:
        if len(word) > len(ending) + 3 and word.endswith(ending):
            return word[:-len(ending)]

    return word


def content_tokens(text):
    stopwords = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on",
        "for", "with", "by", "from", "at", "is", "are", "was",
        "were", "be", "been", "being", "this", "that", "these",
        "those", "it", "its", "as", "into", "through", "using",
        "use", "used", "which", "what", "how", "why", "when",
        "where", "who", "will", "would", "can", "could", "should",
        "may", "might", "do", "does", "did", "than", "then"
    }

    words = normalize(text).split()

    return {
        stem(w)
        for w in words
        if len(w) > 2 and w not in stopwords
    }


def remove_obe_words(text):
    forbidden = [
        "clo",
        "plo",
        "course learning outcome",
        "program learning outcome",
        "learning outcome",
        "learning outcomes",
        "obe",
        "outcome",
        "alignment",
        "aligned"
    ]

    result = text

    for phrase in forbidden:
        result = re.sub(
            rf"\b{re.escape(phrase)}\b",
            "",
            result,
            flags=re.IGNORECASE
        )

    result = re.sub(r"\s+", " ", result)
    return result.strip()


# ============================================================
# FILE READING
# ============================================================

def tesseract_available():
    return pytesseract is not None and Image is not None


def ocr_image(image):
    if not tesseract_available():
        return ""

    try:
        return pytesseract.image_to_string(image)
    except Exception:
        return ""


def read_pdf(uploaded_file):
    if fitz is None:
        return (
            "",
            "PyMuPDF is not installed. Add PyMuPDF to requirements.txt."
        )

    try:
        data = uploaded_file.read()
        doc = fitz.open(stream=data, filetype="pdf")

        pages = []

        for page in doc:
            text = page.get_text("text") or ""

            if len(re.sub(r"\s+", "", text)) < 80:
                if tesseract_available():
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2, 2),
                        alpha=False
                    )

                    img = Image.frombytes(
                        "RGB",
                        [pix.width, pix.height],
                        pix.samples
                    )

                    ocr_text = ocr_image(img)

                    if ocr_text.strip():
                        text = text + "\n" + ocr_text

            pages.append(text)

        doc.close()

        return clean_text("\n".join(pages)), ""

    except Exception as e:
        return "", f"Could not read PDF: {e}"


def read_docx(uploaded_file):
    if Document is None:
        return "", "python-docx is not installed."

    try:
        data = uploaded_file.read()
        doc = Document(io.BytesIO(data))

        parts = []

        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text)

        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))

        return clean_text("\n".join(parts)), ""

    except Exception as e:
        return "", f"Could not read DOCX: {e}"


def read_excel(uploaded_file):
    try:
        data = uploaded_file.read()

        sheets = pd.read_excel(
            io.BytesIO(data),
            sheet_name=None
        )

        parts = []

        for sheet_name, df in sheets.items():
            parts.append(f"Sheet: {sheet_name}")

            if df is not None and not df.empty:
                parts.append(
                    df.fillna("").astype(str).to_csv(
                        index=False
                    )
                )

        return clean_text("\n".join(parts)), ""

    except Exception as e:
        return "", f"Could not read Excel file: {e}"


def read_csv(uploaded_file):
    try:
        data = uploaded_file.read()

        df = pd.read_csv(io.BytesIO(data))

        return clean_text(
            df.fillna("").astype(str).to_csv(index=False)
        ), ""

    except Exception as e:
        return "", f"Could not read CSV: {e}"


def read_txt(uploaded_file):
    try:
        data = uploaded_file.read()

        return clean_text(
            data.decode("utf-8", errors="ignore")
        ), ""

    except Exception as e:
        return "", f"Could not read TXT file: {e}"


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

    return "", "Unsupported file format."


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    lines = [
        clean_text(x)
        for x in str(text).splitlines()
        if clean_text(x)
    ]

    outcomes = []

    for line in lines:

        line = re.sub(
            r"^\s*(?:CLO|PLO)?\s*[-#:.)]?\s*\d+\s*[-:.)]?\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r"^\s*(?:CLO|PLO)\s*[-:]\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        line = clean_text(line)

        if len(line) >= 8:
            outcomes.append(line)

    return outcomes


def extract_outcome_core(outcome):
    if not outcome:
        return ""

    text = remove_obe_words(outcome)

    # Remove common outcome verbs from the beginning.
    text = re.sub(
        r"^\s*(?:"
        r"identify|define|describe|explain|understand|apply|use|"
        r"demonstrate|analyze|analyse|evaluate|assess|design|"
        r"develop|create|compare|differentiate|calculate|"
        r"interpret|discuss|classify|implement|solve|"
        r"construct|formulate|propose"
        r")\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"^\s*(?:students?|learners?)\s+(?:will\s+)?", "", text, flags=re.I)
    text = re.sub(r"^\s*be able to\s+", "", text, flags=re.I)

    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# QUESTION EXTRACTION
# ============================================================

NUMBERED_QUESTION_RE = re.compile(
    r"^\s*"
    r"(?:Q(?:uestion)?\s*)?"
    r"(\d{1,3})"
    r"\s*[\.\):\-]\s*"
    r"(.+?)"
    r"\s*$",
    re.IGNORECASE
)


def looks_like_metadata(text):
    n = normalize(text)

    if not n:
        return True

    metadata_patterns = [
        "questionwell",
        "question set",
        "generated by",
        "student name",
        "student id",
        "roll number",
        "course code",
        "course instructor",
        "date",
        "time",
        "marks",
        "total marks",
        "page",
        "semester",
        "department",
        "university"
    ]

    if any(pattern in n for pattern in metadata_patterns):
        return True

    # Times
    if re.fullmatch(r"\d{1,2}:\d{2}\s*(?:am|pm)?", n):
        return True

    # Page-like numbers
    if re.fullmatch(r"\d{1,3}\s*/\s*\d{1,3}", n):
        return True

    if re.fullmatch(r"\d{1,3}\s*of\s*\d{1,3}", n):
        return True

    # Date-like lines
    if re.fullmatch(
        r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}",
        n
    ):
        return True

    # Headers that are not questions
    if len(n.split()) <= 8:
        if any(
            x in n
            for x in [
                "general chemistry",
                "question set",
                "question bank"
            ]
        ):
            return True

    return False


def remove_mcq_options(text):
    lines = text.splitlines()

    kept = []

    for line in lines:
        stripped = line.strip()

        if re.match(
            r"^[A-Da-d][\.\)]\s+",
            stripped
        ):
            continue

        if re.match(
            r"^\(?[A-Da-d]\)?\s*[-:]\s+",
            stripped
        ):
            continue

        kept.append(stripped)

    return " ".join(x for x in kept if x)


def is_question_candidate(text):
    text = clean_text(text)

    if not text:
        return False

    if looks_like_metadata(text):
        return False

    if len(text) < 10:
        return False

    if len(text) > 1000:
        return False

    n = normalize(text)

    if "questionwell" in n:
        return False

    question_words = [
        "what",
        "why",
        "how",
        "which",
        "who",
        "where",
        "when",
        "explain",
        "describe",
        "define",
        "identify",
        "calculate",
        "solve",
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "evaluate",
        "assess",
        "design",
        "develop",
        "discuss",
        "determine",
        "interpret",
        "apply",
        "using",
        "given",
        "consider",
        "suppose",
        "assume"
    ]

    if "?" in text:
        return True

    if any(
        re.search(rf"\b{re.escape(word)}\b", n)
        for word in question_words
    ):
        return True

    return False


def extract_questions(text):
    text = clean_text(text)

    lines = text.splitlines()

    questions = []
    current = ""

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        match = NUMBERED_QUESTION_RE.match(line)

        if match:
            if current:
                candidate = remove_mcq_options(current)

                if is_question_candidate(candidate):
                    questions.append(candidate)

            current = match.group(2)
        else:
            if current:
                current += " " + line
            elif is_question_candidate(line):
                current = line

    if current:
        candidate = remove_mcq_options(current)

        if is_question_candidate(candidate):
            questions.append(candidate)

    # Remove duplicates
    final = []
    seen = set()

    for q in questions:
        q = clean_text(q)
        q = re.sub(r"\s+", " ", q)

        key = normalize(q)

        if key and key not in seen:
            seen.add(key)
            final.append(q)

    return final


# ============================================================
# DOMAIN / SUBJECT
# ============================================================

def detect_domain(text):
    tokens = content_tokens(text)

    scores = {}

    for domain, words in DOMAIN_LEXICONS.items():
        domain_tokens = {
            stem(w)
            for w in words
        }

        overlap = tokens & domain_tokens

        scores[domain] = len(overlap)

    if not scores:
        return None, 0

    domain = max(scores, key=scores.get)

    return domain, scores[domain]


def check_subject(question, course_name, course_content):
    combined_course = f"{course_name} {course_content}".strip()

    if not combined_course:
        return 100, True, "Not specified"

    q_tokens = content_tokens(question)
    course_tokens = content_tokens(combined_course)

    if not q_tokens or not course_tokens:
        return 50, False, "Unknown"

    overlap = q_tokens & course_tokens

    direct_score = min(
        100,
        int((len(overlap) / max(1, min(len(q_tokens), 8))) * 100)
    )

    course_domain, course_domain_hits = detect_domain(combined_course)
    question_domain, question_domain_hits = detect_domain(question)

    if course_domain and question_domain:
        if course_domain == question_domain:
            direct_score = max(direct_score, 85)
        else:
            # Strong domain conflict = subject mismatch
            if question_domain_hits >= 2 and course_domain_hits >= 2:
                return 15, False, question_domain

    # Course name keywords are particularly important.
    course_name_tokens = content_tokens(course_name)

    if course_name_tokens:
        name_overlap = q_tokens & course_name_tokens

        if name_overlap:
            direct_score = max(
                direct_score,
                min(
                    100,
                    65 + len(name_overlap) * 10
                )
            )

    detected = question_domain or course_domain or "Unknown"

    return direct_score, direct_score >= 60, detected


# ============================================================
# OUTCOME ALIGNMENT
# ============================================================

def best_outcome(question, outcomes):
    if not outcomes:
        return "", 0

    q_tokens = content_tokens(question)

    best = ""
    best_score = 0

    for outcome in outcomes:
        o_tokens = content_tokens(outcome)

        if not o_tokens:
            continue

        overlap = q_tokens & o_tokens

        # Fuzzy-ish score based on outcome coverage.
        score_1 = (
            len(overlap) / max(1, len(o_tokens))
        ) * 100

        score_2 = (
            len(overlap) / max(1, len(q_tokens))
        ) * 100

        score = int(
            round(
                (score_1 * 0.65) +
                (score_2 * 0.35)
            )
        )

        # Strong phrase matching.
        q_normal = normalize(question)
        o_normal = normalize(outcome)

        if o_normal and len(o_normal) > 12:
            if o_normal in q_normal:
                score = 100

        if score > best_score:
            best_score = score
            best = outcome

    return best, min(100, best_score)


# ============================================================
# BLOOM
# ============================================================

def detect_bloom(question):
    n = normalize(question)

    for level in reversed(BLOOM_LEVELS):
        verbs = BLOOM_VERBS[level]

        for verb in verbs:
            if re.search(
                rf"\b{re.escape(verb)}\b",
                n
            ):
                return level

    return "Understand"


def bloom_score(question, intended_bloom):
    actual = detect_bloom(question)

    if actual == intended_bloom:
        return 100, actual

    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    actual_num = order.get(actual, 2)
    intended_num = order.get(intended_bloom, 2)

    difference = abs(actual_num - intended_num)

    if difference == 1:
        return 70, actual

    if difference == 2:
        return 45, actual

    return 20, actual


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question):
    q = clean_text(question)
    n = normalize(q)

    score = 50

    if "?" in q:
        score += 10

    if len(q.split()) >= 7:
        score += 10

    if len(q.split()) <= 60:
        score += 5

    command_words = set(
        word
        for level in BLOOM_VERBS.values()
        for word in level
    )

    if any(
        re.search(rf"\b{re.escape(v)}\b", n)
        for v in command_words
    ):
        score += 10

    vague_phrases = [
        "discuss something",
        "write something",
        "explain everything",
        "do the following",
        "solve a problem",
        "give details",
        "write about"
    ]

    if any(x in n for x in vague_phrases):
        score -= 20

    if re.search(
        r"\b(clo|plo|learning outcome|obe|alignment)\b",
        n
    ):
        score -= 40

    return max(0, min(100, score))


# ============================================================
# OVERALL EVALUATOR
# ============================================================

def evaluate_question(
    question,
    course_name,
    course_content,
    clo_text,
    plo_text,
    intended_bloom
):
    clos = parse_outcomes(clo_text)
    plos = parse_outcomes(plo_text)

    subject_score, subject_ok, detected_subject = check_subject(
        question,
        course_name,
        course_content
    )

    matched_clo, clo_score = best_outcome(
        question,
        clos
    )

    matched_plo, plo_score = best_outcome(
        question,
        plos
    )

    bloom_alignment, actual_bloom = bloom_score(
        question,
        intended_bloom
    )

    quality = quality_score(question)

    # --------------------------------------------------------
    # HARD SUBJECT GATE
    # --------------------------------------------------------

    if not subject_ok:
        status = "Rejected"

        effective_clo = 0
        effective_plo = 0
        effective_bloom = 0

    else:
        effective_clo = clo_score
        effective_plo = plo_score
        effective_bloom = bloom_alignment

        if clo_score < 60:
            status = "Rejected"

        elif bloom_alignment < 80:
            status = "Rejected"

        elif plo_score < 45:
            status = "Needs Review"

        elif quality < 60:
            status = "Needs Review"

        else:
            status = "Approved"

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    overall_score = (
        subject_score * 0.30
        + effective_clo * 0.30
        + effective_plo * 0.20
        + effective_bloom * 0.15
        + quality * 0.05
    )

    overall_score = int(
        round(
            max(
                0,
                min(
                    100,
                    overall_score
                )
            )
        )
    )

    attained = (
        status == "Approved"
        and subject_score >= 60
        and clo_score >= 60
        and plo_score >= 45
        and bloom_alignment >= 80
        and quality >= 60
    )

    return {
        "Question": question,
        "Overall Score": overall_score,
        "Subject Relevance": int(subject_score),
        "CLO Alignment": int(effective_clo),
        "PLO Alignment": int(effective_plo),
        "Bloom Alignment": int(effective_bloom),
        "Quality": int(quality),
        "Matched CLO": matched_clo,
        "Matched PLO": matched_plo,
        "Detected Bloom": actual_bloom,
        "Detected Subject": detected_subject or "Not detected",
        "Status": status,
        "Alignment Attained": attained
    }


# ============================================================
# REVISION HELPERS
# ============================================================

def extract_key_terms(text, maximum=8):
    tokens = content_tokens(text)

    if not tokens:
        return []

    # Keep meaningful terms.
    result = []

    for token in tokens:
        if len(token) >= 4:
            result.append(token)

    return result[:maximum]


def choose_core_topic(
    original_question,
    matched_clo,
    matched_plo,
    course_name,
    course_content
):
    sources = [
        matched_clo,
        matched_plo,
        course_content,
        course_name,
        original_question
    ]

    for source in sources:
        core = extract_outcome_core(source)

        if core and len(core.split()) >= 2:
            return core

    return clean_text(original_question)


def domain_terms_for_revision(
    question,
    matched_clo,
    matched_plo,
    course_content,
    course_name
):
    text = " ".join([
        question,
        matched_clo,
        matched_plo,
        course_content,
        course_name
    ])

    detected_domain, _ = detect_domain(text)

    terms = []

    if detected_domain in DOMAIN_LEXICONS:
        for word in DOMAIN_LEXICONS[detected_domain]:
            if len(word.split()) <= 3:
                terms.append(word)

    # Add terms actually appearing in source material.
    source_tokens = content_tokens(text)

    for token in source_tokens:
        if token not in terms:
            terms.append(token)

    return terms[:15]


def build_candidate_revisions(
    original_question,
    matched_clo,
    matched_plo,
    intended_bloom,
    course_name,
    course_content
):
    """
    Generate multiple DIRECT assessment questions.

    These questions intentionally do not mention:
    CLO, PLO, OBE, learning outcome, or alignment.
    """

    core = choose_core_topic(
        original_question,
        matched_clo,
        matched_plo,
        course_name,
        course_content
    )

    core = remove_obe_words(core)

    if len(core) > 180:
        core = core[:180].rsplit(" ", 1)[0]

    terms = domain_terms_for_revision(
        original_question,
        matched_clo,
        matched_plo,
        course_content,
        course_name
    )

    term_a = terms[0] if len(terms) > 0 else "the concept"
    term_b = terms[1] if len(terms) > 1 else "its application"

    bloom = intended_bloom.lower()

    candidates = []

    # --------------------------------------------------------
    # REMEMBER
    # --------------------------------------------------------

    if bloom == "remember":

        candidates.extend([
            f"What is {core}? State its main characteristics.",
            f"Define {core} and list two important characteristics.",
            f"Identify the main characteristics of {core} and state their significance.",
            f"Name the key components of {core} and state the function of each."
        ])

    # --------------------------------------------------------
    # UNDERSTAND
    # --------------------------------------------------------

    elif bloom == "understand":

        candidates.extend([
            f"Explain {core} and describe how its main components are related.",
            f"Describe {core} and explain the role of its major components.",
            f"Explain the main principles of {core} and illustrate them with a relevant example.",
            f"Compare the main features of {core} and explain how they differ."
        ])

    # --------------------------------------------------------
    # APPLY
    # --------------------------------------------------------

    elif bloom == "apply":

        candidates.extend([
            f"Given a relevant example involving {core}, apply the appropriate principles to determine the correct result and show your steps.",
            f"Use the principles of {core} to solve a relevant problem. Show the method and justify the result.",
            f"Given a practical situation involving {term_a} and {term_b}, apply {core} to determine the appropriate solution.",
            f"Apply {core} to the following situation: a problem requires the use of {term_a} and {term_b}. Determine the appropriate solution and show the steps."
        ])

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    elif bloom == "analyze":

        candidates.extend([
            f"Analyze {core} by identifying its major components and explaining the relationship between them.",
            f"Analyze the relationship between {term_a} and {term_b} within {core}. Support your analysis with relevant evidence.",
            f"Compare the major components of {core} and explain how their differences affect the overall result.",
            f"Examine {core} and distinguish between its major components, explaining the role of each."
        ])

    # --------------------------------------------------------
    # EVALUATE
    # --------------------------------------------------------

    elif bloom == "evaluate":

        candidates.extend([
            f"Evaluate {core} using appropriate criteria and justify your conclusion with relevant evidence.",
            f"Assess the effectiveness of {core} in a relevant context and justify your judgment with specific evidence.",
            f"Compare two approaches related to {core}, evaluate their effectiveness using clear criteria, and justify which approach is more suitable for the stated context.",
            f"Evaluate the strengths and limitations of {core} and justify your conclusion using relevant evidence."
        ])

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    elif bloom == "create":

        candidates.extend([
            f"Design a practical solution based on {core} for a clearly defined situation and explain the major design decisions.",
            f"Develop a solution that applies {core} to address a relevant problem. Describe the main components of your solution.",
            f"Design a suitable approach for a problem involving {term_a} and {term_b}. Explain how your proposed solution addresses the problem.",
            f"Construct a practical solution using the principles of {core} and explain the reasoning behind the major components."
        ])

    else:
        candidates.extend([
            f"Explain {core} and illustrate its application with a relevant example.",
            f"Describe {core} and explain its main components."
        ])

    # --------------------------------------------------------
    # CLEAN ALL CANDIDATES
    # --------------------------------------------------------

    cleaned = []

    for candidate in candidates:

        candidate = remove_obe_words(candidate)

        candidate = re.sub(
            r"\s+",
            " ",
            candidate
        ).strip()

        candidate = re.sub(
            r"\s+([?.!,])",
            r"\1",
            candidate
        )

        if not candidate.endswith("?"):
            candidate += "?"

        # Never allow OBE terminology in final question.
        if re.search(
            r"\b(clo|plo|obe|learning outcome|learning outcomes|alignment|aligned)\b",
            candidate,
            flags=re.IGNORECASE
        ):
            continue

        if candidate not in cleaned:
            cleaned.append(candidate)

    return cleaned


# ============================================================
# VALIDATED REVISION GENERATOR
# ============================================================

def build_validated_revision(
    original_question,
    course_name,
    course_content,
    clo_text,
    plo_text,
    intended_bloom
):
    """
    Generate multiple candidate questions and actually run each
    through the evaluator.

    The strongest candidate that reaches:
        Subject >= 60
        CLO >= 60
        Bloom >= 80
        PLO >= 45
        Quality >= 60
        Overall >= 80

    is selected.

    No score is manually inflated.
    """

    initial = evaluate_question(
        original_question,
        course_name,
        course_content,
        clo_text,
        plo_text,
        intended_bloom
    )

    candidates = build_candidate_revisions(
        original_question,
        initial["Matched CLO"],
        initial["Matched PLO"],
        intended_bloom,
        course_name,
        course_content
    )

    evaluated = []

    for candidate in candidates:

        result = evaluate_question(
            candidate,
            course_name,
            course_content,
            clo_text,
            plo_text,
            intended_bloom
        )

        evaluated.append(result)

    if not evaluated:
        return original_question, initial, False

    # --------------------------------------------------------
    # First preference:
    # actual attainment
    # --------------------------------------------------------

    attained = [
        x for x in evaluated
        if (
            x["Alignment Attained"]
            and x["Overall Score"] >= 80
        )
    ]

    if attained:

        attained.sort(
            key=lambda x: (
                x["Overall Score"],
                x["CLO Alignment"],
                x["PLO Alignment"],
                x["Bloom Alignment"],
                x["Subject Relevance"]
            ),
            reverse=True
        )

        best = attained[0]

        return (
            best["Question"],
            best,
            True
        )

    # --------------------------------------------------------
    # Second preference:
    # CLO + Bloom + Subject strong
    # --------------------------------------------------------

    strong = [
        x for x in evaluated
        if (
            x["Subject Relevance"] >= 60
            and x["CLO Alignment"] >= 60
            and x["Bloom Alignment"] >= 80
        )
    ]

    if strong:

        strong.sort(
            key=lambda x: (
                x["Overall Score"],
                x["CLO Alignment"],
                x["PLO Alignment"],
                x["Quality"]
            ),
            reverse=True
        )

        best = strong[0]

        return (
            best["Question"],
            best,
            best["Overall Score"] >= 80
        )

    # --------------------------------------------------------
    # Final fallback:
    # highest actual evaluated score
    # --------------------------------------------------------

    evaluated.sort(
        key=lambda x: (
            x["Overall Score"],
            x["CLO Alignment"],
            x["Bloom Alignment"],
            x["Subject Relevance"],
            x["PLO Alignment"]
        ),
        reverse=True
    )

    best = evaluated[0]

    return (
        best["Question"],
        best,
        False
    )


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = []

if "revision_data" not in st.session_state:
    st.session_state.revision_data = {}

if "revision_values" not in st.session_state:
    st.session_state.revision_values = {}

if "tested_revisions" not in st.session_state:
    st.session_state.tested_revisions = {}


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Assessment Alignment Checker")

st.write(
    "Evaluate assessment questions for subject relevance, CLO alignment, "
    "PLO alignment, Bloom's level, question quality, and overall alignment."
)

st.info(
    "The revision engine tests suggested questions using the same evaluator "
    "used for the original question. It does not simply increase the score."
)


# ============================================================
# COURSE INFORMATION
# ============================================================

st.subheader("1. Course Information")

col1, col2 = st.columns(2)

with col1:
    course_name = st.text_input(
        "Course / Subject Name",
        placeholder="e.g., General Chemistry"
    )

with col2:
    intended_bloom = st.selectbox(
        "Intended Bloom's Level",
        BLOOM_LEVELS
    )

course_content = st.text_area(
    "Course Content / Topics",
    placeholder=(
        "Enter the major topics taught in the course.\n"
        "Example:\n"
        "Atomic structure\n"
        "Chemical bonding\n"
        "Stoichiometry\n"
        "Acids and bases"
    ),
    height=130
)


# ============================================================
# OUTCOMES
# ============================================================

st.subheader("2. CLOs and PLOs")

col1, col2 = st.columns(2)

with col1:
    clo_text = st.text_area(
        "Course Learning Outcomes (CLOs)",
        placeholder=(
            "CLO 1: Explain the fundamental principles of chemistry.\n"
            "CLO 2: Apply chemical concepts to solve numerical problems."
        ),
        height=170
    )

with col2:
    plo_text = st.text_area(
        "Program Learning Outcomes (PLOs)",
        placeholder=(
            "PLO 1: Apply knowledge of the relevant discipline.\n"
            "PLO 2: Analyze and solve problems using appropriate methods."
        ),
        height=170
    )


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("3. Upload Assessment File")

uploaded_file = st.file_uploader(
    "Upload PDF, DOCX, XLSX, XLS, CSV, or TXT",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt"
    ]
)


# ============================================================
# ANALYZE
# ============================================================

if st.button(
    "🔍 Analyze Assessment",
    type="primary",
    use_container_width=True
):

    if not course_name.strip():
        st.error("Please enter the course / subject name.")
        st.stop()

    if not clo_text.strip():
        st.error("Please enter at least one CLO.")
        st.stop()

    if not plo_text.strip():
        st.warning(
            "No PLO was entered. PLO alignment may therefore be low."
        )

    if not uploaded_file:
        st.error("Please upload an assessment file.")
        st.stop()

    with st.spinner("Reading and analyzing the assessment..."):

        text, error = read_uploaded_file(
            uploaded_file
        )

        if error:
            st.error(error)
            st.stop()

        if not text.strip():
            st.error(
                "No readable text was found in the uploaded file."
            )
            st.stop()

        questions = extract_questions(text)

        if not questions:
            st.error(
                "No assessment questions were detected. "
                "Please check the file format or question formatting."
            )
            st.stop()

        results = []

        for question in questions:

            result = evaluate_question(
                question,
                course_name,
                course_content,
                clo_text,
                plo_text,
                intended_bloom
            )

            results.append(result)

        st.session_state.analysis_results = results

        # Clear previous revision data.
        st.session_state.revision_data = {}
        st.session_state.revision_values = {}
        st.session_state.tested_revisions = {}


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.analysis_results

if results:

    st.divider()

    st.subheader("4. Assessment Results")

    total = len(results)

    approved = sum(
        1 for r in results
        if r["Status"] == "Approved"
    )

    rejected = sum(
        1 for r in results
        if r["Status"] == "Rejected"
    )

    review = sum(
        1 for r in results
        if r["Status"] == "Needs Review"
    )

    avg_score = int(
        round(
            sum(r["Overall Score"] for r in results)
            / max(1, total)
        )
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total Questions",
        total
    )

    c2.metric(
        "Approved",
        approved
    )

    c3.metric(
        "Needs Review / Rejected",
        rejected + review
    )

    c4.metric(
        "Average Score",
        f"{avg_score}/100"
    )

    # --------------------------------------------------------
    # SUMMARY TABLE
    # --------------------------------------------------------

    table_rows = []

    for i, r in enumerate(results, start=1):

        table_rows.append({
            "Question No.": i,
            "Question": r["Question"],
            "Score / 100": r["Overall Score"],
            "Subject (%)": r["Subject Relevance"],
            "CLO (%)": r["CLO Alignment"],
            "PLO (%)": r["PLO Alignment"],
            "Bloom (%)": r["Bloom Alignment"],
            "Quality (%)": r["Quality"],
            "Status": r["Status"]
        })

    df = pd.DataFrame(table_rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # QUESTION DETAILS
    # ========================================================

    st.divider()

    st.subheader("5. Question Review and Revision")

    for i, result in enumerate(results):

        question_key = f"question_{i}"

        status = result["Status"]

        if status == "Approved":
            status_icon = "🟢"
        elif status == "Needs Review":
            status_icon = "🟠"
        else:
            status_icon = "🔴"

        with st.expander(
            f"{status_icon} Question {i + 1} — "
            f"Score: {result['Overall Score']}/100 — "
            f"{status}",
            expanded=False
        ):

            st.markdown(
                f"**Original Question:**  \n"
                f"{result['Question']}"
            )

            # ------------------------------------------------
            # ORIGINAL SCORE
            # ------------------------------------------------

            st.markdown("### Original Evaluation")

            score_cols = st.columns(6)

            score_cols[0].metric(
                "Overall",
                f"{result['Overall Score']}/100"
            )

            score_cols[1].metric(
                "Subject",
                f"{result['Subject Relevance']}%"
            )

            score_cols[2].metric(
                "CLO",
                f"{result['CLO Alignment']}%"
            )

            score_cols[3].metric(
                "PLO",
                f"{result['PLO Alignment']}%"
            )

            score_cols[4].metric(
                "Bloom",
                f"{result['Bloom Alignment']}%"
            )

            score_cols[5].metric(
                "Quality",
                f"{result['Quality']}%"
            )

            if result["Matched CLO"]:
                st.write(
                    f"**Matched CLO:** {result['Matched CLO']}"
                )

            if result["Matched PLO"]:
                st.write(
                    f"**Matched PLO:** {result['Matched PLO']}"
                )

            st.write(
                f"**Detected Subject:** "
                f"{result['Detected Subject']}"
            )

            st.write(
                f"**Detected Bloom Level:** "
                f"{result['Detected Bloom']}"
            )

            # ------------------------------------------------
            # ALREADY ATTAINED
            # ------------------------------------------------

            if result["Alignment Attained"]:

                st.success(
                    f"✓ Alignment Attained — "
                    f"Original Score: {result['Overall Score']}/100"
                )

            # ------------------------------------------------
            # REVISION
            # ------------------------------------------------

            if not result["Alignment Attained"]:

                st.markdown("### Suggested Revision")

                # --------------------------------------------
                # Generate validated revision only once.
                # --------------------------------------------

                if question_key not in st.session_state.revision_data:

                    with st.spinner(
                        "Generating and testing a stronger revision..."
                    ):

                        (
                            suggested_question,
                            suggested_result,
                            suggested_attained
                        ) = build_validated_revision(
                            result["Question"],
                            course_name,
                            course_content,
                            clo_text,
                            plo_text,
                            intended_bloom
                        )

                        st.session_state.revision_data[
                            question_key
                        ] = {
                            "suggestion": suggested_question,
                            "result": suggested_result,
                            "attained": suggested_attained
                        }

                        st.session_state.revision_values[
                            question_key
                        ] = suggested_question

                revision_info = st.session_state.revision_data[
                    question_key
                ]

                suggested_question = revision_info[
                    "suggestion"
                ]

                suggested_result = revision_info[
                    "result"
                ]

                suggested_attained = revision_info[
                    "attained"
                ]

                # --------------------------------------------
                # Show the validated suggestion
                # --------------------------------------------

                st.info(
                    suggested_question
                )

                preview_cols = st.columns(5)

                preview_cols[0].metric(
                    "Suggested Score",
                    f"{suggested_result['Overall Score']}/100"
                )

                preview_cols[1].metric(
                    "CLO",
                    f"{suggested_result['CLO Alignment']}%"
                )

                preview_cols[2].metric(
                    "PLO",
                    f"{suggested_result['PLO Alignment']}%"
                )

                preview_cols[3].metric(
                    "Bloom",
                    f"{suggested_result['Bloom Alignment']}%"
                )

                preview_cols[4].metric(
                    "Subject",
                    f"{suggested_result['Subject Relevance']}%"
                )

                if suggested_attained:
                    st.success(
                        "✓ Suggested Revision Already Attains Alignment "
                        f"with a score of "
                        f"{suggested_result['Overall Score']}/100."
                    )
                else:
                    st.warning(
                        "The strongest automatically generated revision "
                        f"currently scores "
                        f"{suggested_result['Overall Score']}/100. "
                        "Use the revision box below to test further edits."
                    )

                # --------------------------------------------
                # USE SUGGESTED REVISION
                # --------------------------------------------

                if st.button(
                    "Use Suggested Revision",
                    key=f"use_revision_{i}",
                    use_container_width=True
                ):

                    st.session_state.revision_values[
                        question_key
                    ] = suggested_question

                    st.session_state.tested_revisions[
                        question_key
                    ] = suggested_result

                    st.rerun()

                # --------------------------------------------
                # REVISION TEXT AREA
                # --------------------------------------------

                revision_value = st.session_state.revision_values.get(
                    question_key,
                    suggested_question
                )

                st.markdown("### Revised Question")

                revised_question = st.text_area(
                    "Edit or test the revised question:",
                    value=revision_value,
                    key=f"revision_text_{i}",
                    height=120
                )

                # Keep latest text.
                st.session_state.revision_values[
                    question_key
                ] = revised_question

                # --------------------------------------------
                # TEST REVISED QUESTION
                # --------------------------------------------

                if st.button(
                    "🧪 Test Revised Question",
                    key=f"test_revision_{i}",
                    type="primary",
                    use_container_width=True
                ):

                    if not revised_question.strip():

                        st.error(
                            "Please enter a revised question first."
                        )

                    else:

                        tested = evaluate_question(
                            revised_question,
                            course_name,
                            course_content,
                            clo_text,
                            plo_text,
                            intended_bloom
                        )

                        st.session_state.tested_revisions[
                            question_key
                        ] = tested

                        st.rerun()

                # --------------------------------------------
                # TESTED RESULT
                # --------------------------------------------

                if question_key in st.session_state.tested_revisions:

                    tested = st.session_state.tested_revisions[
                        question_key
                    ]

                    st.markdown("### Revised Evaluation")

                    revised_cols = st.columns(6)

                    revised_cols[0].metric(
                        "Revised Score",
                        f"{tested['Overall Score']}/100"
                    )

                    revised_cols[1].metric(
                        "Subject",
                        f"{tested['Subject Relevance']}%"
                    )

                    revised_cols[2].metric(
                        "CLO",
                        f"{tested['CLO Alignment']}%"
                    )

                    revised_cols[3].metric(
                        "PLO",
                        f"{tested['PLO Alignment']}%"
                    )

                    revised_cols[4].metric(
                        "Bloom",
                        f"{tested['Bloom Alignment']}%"
                    )

                    revised_cols[5].metric(
                        "Quality",
                        f"{tested['Quality']}%"
                    )

                    # ----------------------------------------
                    # BEFORE / AFTER
                    # ----------------------------------------

                    difference = (
                        tested["Overall Score"]
                        - result["Overall Score"]
                    )

                    st.markdown(
                        f"**Before:** "
                        f"{result['Overall Score']}/100  "
                        f"→ **After:** "
                        f"{tested['Overall Score']}/100  "
                        f"(**{difference:+d} points**)"
                    )

                    # ----------------------------------------
                    # FINAL ATTAINMENT
                    # ----------------------------------------

                    if tested["Alignment Attained"]:

                        st.success(
                            "✓ ALIGNMENT ATTAINED AFTER REVISION"
                        )

                        st.success(
                            f"The revised question scores "
                            f"**{tested['Overall Score']}/100** "
                            f"and satisfies the required evaluation "
                            f"criteria."
                        )

                    elif tested["Overall Score"] >= 80:

                        st.warning(
                            "The revised question has reached "
                            f"**{tested['Overall Score']}/100**, "
                            "but one or more mandatory alignment "
                            "criteria are still not attained."
                        )

                    else:

                        st.error(
                            f"Alignment is not yet attained. "
                            f"Revised score: "
                            f"{tested['Overall Score']}/100."
                        )

                    # ----------------------------------------
                    # SPECIFIC FEEDBACK
                    # ----------------------------------------

                    problems = []

                    if tested["Subject Relevance"] < 60:
                        problems.append(
                            "The question is not sufficiently related "
                            "to the selected subject/course content."
                        )

                    if tested["CLO Alignment"] < 60:
                        problems.append(
                            "The question does not sufficiently address "
                            "the selected CLO."
                        )

                    if tested["PLO Alignment"] < 45:
                        problems.append(
                            "The question has weak connection with "
                            "the selected PLO."
                        )

                    if tested["Bloom Alignment"] < 80:
                        problems.append(
                            f"The question does not clearly demonstrate "
                            f"the intended Bloom level "
                            f"({intended_bloom})."
                        )

                    if tested["Quality"] < 60:
                        problems.append(
                            "The question needs clearer or more specific "
                            "assessment wording."
                        )

                    if problems:

                        st.markdown(
                            "**What still needs improvement:**"
                        )

                        for problem in problems:
                            st.write(
                                f"• {problem}"
                            )

                    # ----------------------------------------
                    # PREVENT OBE TERMS
                    # ----------------------------------------

                    if re.search(
                        r"\b(clo|plo|obe|learning outcome|alignment)\b",
                        revised_question,
                        flags=re.IGNORECASE
                    ):
                        st.warning(
                            "The revised question contains OBE terminology. "
                            "Assessment questions should directly ask the "
                            "student to demonstrate the required knowledge "
                            "or skill instead."
                        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Assessment Alignment Checker • "
    "Subject relevance is treated as a mandatory gate. "
    "Suggested revisions are evaluated using the same scoring logic "
    "as the original questions."
)
