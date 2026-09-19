import io
import re
import os
from collections import Counter

import pandas as pd
import streamlit as st


# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz
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
# BLOOM LEVELS
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
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "label", "match", "select"
    ],
    "Understand": [
        "explain", "describe", "summarize", "discuss",
        "interpret", "classify", "illustrate", "compare",
        "paraphrase"
    ],
    "Apply": [
        "calculate", "solve", "apply", "use",
        "demonstrate", "implement", "execute",
        "compute", "determine"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine",
        "compare", "contrast", "categorize",
        "investigate", "distinguish"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "judge",
        "critique", "defend", "argue",
        "recommend", "appraise"
    ],
    "Create": [
        "design", "develop", "construct", "formulate",
        "create", "propose", "plan", "produce"
    ]
}


# ============================================================
# SUBJECT / DOMAIN LEXICONS
# ============================================================

DOMAIN_LEXICONS = {

    "Chemistry": [
        "atom", "molecule", "bond", "ionic", "covalent",
        "reaction", "acid", "base", "ph", "molarity",
        "mole", "stoichiometry", "equilibrium", "organic",
        "inorganic", "oxidation", "reduction", "electron",
        "periodic", "compound", "solution", "concentration",
        "thermodynamics", "kinetics", "catalyst",
        "chemical", "chemistry"
    ],

    "Physics": [
        "force", "motion", "velocity", "acceleration",
        "energy", "momentum", "mass", "work", "power",
        "electric", "magnetic", "field", "wave",
        "frequency", "voltage", "current", "resistance",
        "circuit", "optics", "quantum", "pressure",
        "physics"
    ],

    "Mathematics": [
        "equation", "function", "derivative", "integral",
        "matrix", "vector", "probability", "statistics",
        "limit", "algebra", "geometry", "calculus",
        "theorem", "variable", "coefficient", "logarithm",
        "sequence", "series", "mathematics"
    ],

    "Computer Science": [
        "algorithm", "program", "programming", "code",
        "database", "software", "hardware", "network",
        "class", "object", "function", "recursion",
        "array", "stack", "queue", "tree", "graph",
        "sorting", "searching", "operating system",
        "computer", "data structure", "machine learning",
        "security", "computer science"
    ],

    "English / Language": [
        "grammar", "writing", "reading", "paragraph",
        "essay", "thesis", "main idea", "tone", "purpose",
        "audience", "paraphrase", "summary", "argument",
        "rhetoric", "language", "sentence", "vocabulary",
        "comprehension", "organization", "english"
    ],

    "Literature": [
        "novel", "poem", "poetry", "character", "theme",
        "plot", "symbolism", "setting", "narrator",
        "metaphor", "imagery", "literary", "protagonist",
        "conflict", "author", "fiction", "literature"
    ],

    "Business / Management": [
        "management", "marketing", "leadership", "organization",
        "strategy", "business", "consumer", "market",
        "planning", "decision", "entrepreneur",
        "human resource", "motivation", "performance",
        "manager", "competitive", "business management"
    ],

    "Accounting / Finance": [
        "accounting", "ledger", "journal", "balance sheet",
        "income statement", "asset", "liability", "equity",
        "revenue", "expense", "profit", "cash flow",
        "audit", "finance", "investment", "ratio",
        "depreciation"
    ],

    "Economics": [
        "economics", "demand", "supply", "market",
        "inflation", "unemployment", "gdp", "price",
        "elasticity", "utility", "consumer", "producer",
        "fiscal", "monetary", "trade"
    ],

    "Engineering": [
        "engineering", "design", "system", "mechanical",
        "electrical", "civil", "structure", "material",
        "load", "stress", "circuit", "control",
        "machine", "process", "safety"
    ],

    "Psychology": [
        "psychology", "behavior", "cognition", "memory",
        "learning", "emotion", "personality", "motivation",
        "development", "perception", "attention",
        "mental", "social"
    ],

    "Sociology": [
        "society", "social", "culture", "class",
        "community", "institution", "inequality",
        "gender", "family", "socialization", "group",
        "deviance", "population"
    ],

    "Education": [
        "education", "teaching", "learning", "pedagogy",
        "curriculum", "assessment", "student", "teacher",
        "instruction", "classroom", "lesson",
        "learning theory", "evaluation"
    ],

    "History": [
        "history", "war", "empire", "revolution",
        "colonial", "independence", "civilization",
        "treaty", "political", "historical", "dynasty",
        "movement", "leader"
    ],

    "Law": [
        "law", "legal", "court", "contract", "tort",
        "constitution", "statute", "case", "judgment",
        "liability", "crime", "evidence", "rights",
        "legislation"
    ],

    "Pharmacy": [
        "drug", "medicine", "pharmacy", "dose", "dosage",
        "pharmacology", "tablet", "capsule", "patient",
        "therapeutic", "drug interaction", "prescription",
        "absorption", "metabolism"
    ],

    "Medical / Health Sciences": [
        "patient", "disease", "diagnosis", "treatment",
        "clinical", "medical", "health", "symptom",
        "anatomy", "physiology", "infection", "therapy",
        "hospital"
    ],

    "Environmental Science": [
        "environment", "pollution", "climate", "ecosystem",
        "biodiversity", "sustainability", "carbon", "waste",
        "water", "soil", "air", "conservation", "renewable"
    ]
}


# ============================================================
# GENERAL TEXT HELPERS
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

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def stem(word):

    word = word.lower()

    endings = [
        "ingly", "edly", "ing", "ies", "ied",
        "es", "s", "ment", "tion", "ions",
        "ness", "ity"
    ]

    for ending in endings:

        if (
            len(word)
            > len(ending) + 3
            and word.endswith(ending)
        ):
            return word[:-len(ending)]

    return word


def content_tokens(text):

    stopwords = {
        "the", "a", "an", "and", "or", "of", "to",
        "in", "on", "for", "with", "by", "from",
        "at", "is", "are", "was", "were", "be",
        "been", "being", "this", "that", "these",
        "those", "it", "its", "as", "into",
        "through", "using", "use", "used",
        "which", "what", "how", "why", "when",
        "where", "who", "will", "would", "can",
        "could", "should", "may", "might",
        "do", "does", "did", "than", "then"
    }

    words = normalize(text).split()

    return {
        stem(w)
        for w in words
        if len(w) > 2 and w not in stopwords
    }


# ============================================================
# CLEAN QUESTION PUNCTUATION
# ============================================================

def clean_question_punctuation(text):

    text = clean_text(text)

    if not text:
        return ""

    # Remove any combination of final punctuation.
    text = re.sub(
        r"[.!?]+$",
        "",
        text
    ).strip()

    # Remove spaces before punctuation.
    text = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        text
    )

    # Ensure exactly one question mark.
    return text + "?"


# ============================================================
# REMOVE OBE LANGUAGE
# ============================================================

def remove_obe_words(text):

    forbidden = [
        "course learning outcome",
        "program learning outcome",
        "learning outcome",
        "learning outcomes",
        "alignment",
        "aligned",
        "obe"
    ]

    result = text

    for phrase in forbidden:

        result = re.sub(
            rf"\b{re.escape(phrase)}\b",
            "",
            result,
            flags=re.IGNORECASE
        )

    result = re.sub(
        r"\bCLO\s*\d*\b",
        "",
        result,
        flags=re.IGNORECASE
    )

    result = re.sub(
        r"\bPLO\s*\d*\b",
        "",
        result,
        flags=re.IGNORECASE
    )

    result = re.sub(
        r"\s+",
        " ",
        result
    )

    return result.strip()


# ============================================================
# PDF / OCR
# ============================================================

def tesseract_available():

    return (
        pytesseract is not None
        and Image is not None
    )


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

        doc = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in doc:

            text = page.get_text("text") or ""

            if len(
                re.sub(
                    r"\s+",
                    "",
                    text
                )
            ) < 80:

                if tesseract_available():

                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(
                            2,
                            2
                        ),
                        alpha=False
                    )

                    image = Image.frombytes(
                        "RGB",
                        [
                            pix.width,
                            pix.height
                        ],
                        pix.samples
                    )

                    ocr_text = ocr_image(
                        image
                    )

                    if ocr_text.strip():
                        text += "\n" + ocr_text

            pages.append(text)

        doc.close()

        return (
            clean_text(
                "\n".join(pages)
            ),
            ""
        )

    except Exception as e:

        return (
            "",
            f"Could not read PDF: {e}"
        )


# ============================================================
# DOCX
# ============================================================

def read_docx(uploaded_file):

    if Document is None:

        return (
            "",
            "python-docx is not installed."
        )

    try:

        data = uploaded_file.read()

        doc = Document(
            io.BytesIO(data)
        )

        parts = []

        for paragraph in doc.paragraphs:

            if paragraph.text.strip():

                parts.append(
                    paragraph.text
                )

        for table in doc.tables:

            for row in table.rows:

                parts.append(
                    " | ".join(
                        cell.text
                        for cell in row.cells
                    )
                )

        return (
            clean_text(
                "\n".join(parts)
            ),
            ""
        )

    except Exception as e:

        return (
            "",
            f"Could not read DOCX: {e}"
        )


# ============================================================
# EXCEL
# ============================================================

def read_excel(uploaded_file):

    try:

        data = uploaded_file.read()

        sheets = pd.read_excel(
            io.BytesIO(data),
            sheet_name=None
        )

        parts = []

        for sheet_name, df in sheets.items():

            parts.append(
                f"Sheet: {sheet_name}"
            )

            if (
                df is not None
                and not df.empty
            ):

                parts.append(
                    df.fillna("")
                    .astype(str)
                    .to_csv(
                        index=False
                    )
                )

        return (
            clean_text(
                "\n".join(parts)
            ),
            ""
        )

    except Exception as e:

        return (
            "",
            f"Could not read Excel file: {e}"
        )


# ============================================================
# CSV
# ============================================================

def read_csv(uploaded_file):

    try:

        data = uploaded_file.read()

        df = pd.read_csv(
            io.BytesIO(data)
        )

        return (
            clean_text(
                df.fillna("")
                .astype(str)
                .to_csv(
                    index=False
                )
            ),
            ""
        )

    except Exception as e:

        return (
            "",
            f"Could not read CSV: {e}"
        )


# ============================================================
# TXT
# ============================================================

def read_txt(uploaded_file):

    try:

        data = uploaded_file.read()

        return (
            clean_text(
                data.decode(
                    "utf-8",
                    errors="ignore"
                )
            ),
            ""
        )

    except Exception as e:

        return (
            "",
            f"Could not read TXT: {e}"
        )


# ============================================================
# FILE ROUTER
# ============================================================

def read_uploaded_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if (
        filename.endswith(".xlsx")
        or filename.endswith(".xls")
    ):
        return read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    if filename.endswith(".txt"):
        return read_txt(uploaded_file)

    return (
        "",
        "Unsupported file format."
    )


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
            r"^\s*(?:CLO|PLO)?\s*"
            r"\d+\s*[-:.)]?\s*",
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

        line = clean_text(
            line
        )

        if len(line) >= 8:
            outcomes.append(line)

    return outcomes


# ============================================================
# OUTCOME CONCEPTS
# ============================================================

OUTCOME_ACTION_WORDS = {

    "identify", "define", "describe", "explain",
    "understand", "apply", "use", "demonstrate",
    "analyze", "analyse", "evaluate", "assess",
    "design", "develop", "create", "compare",
    "differentiate", "calculate", "interpret",
    "discuss", "classify", "implement", "solve",
    "construct", "formulate", "propose", "critique",
    "justify", "examine", "students", "student",
    "learners", "learner", "will", "able",
    "ability", "knowledge", "understanding"
}


def outcome_concept_tokens(text):

    words = normalize(text).split()

    result = []

    for word in words:

        if word in OUTCOME_ACTION_WORDS:
            continue

        if len(word) <= 2:
            continue

        result.append(
            stem(word)
        )

    return set(result)


# ============================================================
# OUTCOME CONCEPT SCORE
# ============================================================

def outcome_concept_score(
    question,
    outcome
):

    if not outcome:
        return 0

    q_tokens = content_tokens(
        question
    )

    o_tokens = outcome_concept_tokens(
        outcome
    )

    if not q_tokens or not o_tokens:
        return 0

    overlap = q_tokens & o_tokens

    if not overlap:
        return 0

    outcome_coverage = (
        len(overlap)
        / max(
            1,
            len(o_tokens)
        )
    ) * 100

    question_coverage = (
        len(overlap)
        / max(
            1,
            len(q_tokens)
        )
    ) * 100

    score = (
        outcome_coverage * 0.70
        + question_coverage * 0.30
    )

    if outcome_coverage >= 70:
        score = max(
            score,
            80
        )

    if outcome_coverage >= 85:
        score = max(
            score,
            90
        )

    if outcome_coverage >= 95:
        score = max(
            score,
            100
        )

    return int(
        min(
            100,
            round(score)
        )
    )


# ============================================================
# BEST OUTCOME
# ============================================================

def best_outcome(
    question,
    outcomes
):

    if not outcomes:
        return "", 0

    best = ""
    best_score = 0

    for outcome in outcomes:

        score = outcome_concept_score(
            question,
            outcome
        )

        q_tokens = content_tokens(
            question
        )

        o_tokens = content_tokens(
            outcome
        )

        overlap = q_tokens & o_tokens

        if o_tokens:

            basic_score = int(
                round(
                    len(overlap)
                    / max(
                        1,
                        len(o_tokens)
                    )
                    * 100
                )
            )

        else:

            basic_score = 0

        score = max(
            score,
            basic_score
        )

        if score > best_score:

            best_score = score
            best = outcome

    return (
        best,
        min(
            100,
            best_score
        )
    )


# ============================================================
# OUTCOME CORE
# ============================================================

def extract_outcome_core(
    outcome
):

    if not outcome:
        return ""

    text = remove_obe_words(
        outcome
    )

    text = re.sub(
        r"^\s*(?:"
        r"identify|define|describe|explain|understand|"
        r"apply|use|demonstrate|analyze|analyse|evaluate|"
        r"assess|design|develop|create|compare|differentiate|"
        r"calculate|interpret|discuss|classify|implement|"
        r"solve|construct|formulate|propose|justify|examine|"
        r"critique"
        r")\b\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^\s*(?:students?|learners?)"
        r"(?:\s+will)?"
        r"(?:\s+be\s+able\s+to)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

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

    n = normalize(
        text
    )

    if not n:
        return True

    metadata = [
        "questionwell",
        "question set",
        "generated by",
        "student name",
        "student id",
        "roll number",
        "course code",
        "course instructor",
        "total marks",
        "page number",
        "semester",
        "department",
        "university"
    ]

    if any(
        x in n
        for x in metadata
    ):
        return True

    if re.fullmatch(
        r"\d{1,2}:\d{2}\s*(?:am|pm)?",
        n
    ):
        return True

    if re.fullmatch(
        r"\d{1,3}\s*/\s*\d{1,3}",
        n
    ):
        return True

    if re.fullmatch(
        r"\d{1,3}\s+of\s+\d{1,3}",
        n
    ):
        return True

    if re.fullmatch(
        r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}",
        n
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

        kept.append(
            stripped
        )

    return " ".join(
        x
        for x in kept
        if x
    )


def is_question_candidate(text):

    text = clean_text(
        text
    )

    if not text:
        return False

    if looks_like_metadata(
        text
    ):
        return False

    if len(text) < 10:
        return False

    if len(text) > 1000:
        return False

    n = normalize(
        text
    )

    if "questionwell" in n:
        return False

    if "?" in text:
        return True

    question_words = [
        "what", "why", "how", "which",
        "who", "where", "when",
        "explain", "describe", "define",
        "identify", "calculate", "solve",
        "analyze", "analyse", "compare",
        "contrast", "evaluate", "assess",
        "design", "develop", "discuss",
        "determine", "interpret", "apply",
        "using", "given", "consider",
        "suppose", "assume"
    ]

    return any(
        re.search(
            rf"\b{re.escape(word)}\b",
            n
        )
        for word in question_words
    )


def extract_questions(text):

    text = clean_text(
        text
    )

    lines = text.splitlines()

    questions = []

    current = ""

    for line in lines:

        line = clean_text(
            line
        )

        if not line:
            continue

        match = NUMBERED_QUESTION_RE.match(
            line
        )

        if match:

            if current:

                candidate = remove_mcq_options(
                    current
                )

                if is_question_candidate(
                    candidate
                ):
                    questions.append(
                        candidate
                    )

            current = match.group(2)

        else:

            if current:

                current += " " + line

            elif is_question_candidate(
                line
            ):

                current = line

    if current:

        candidate = remove_mcq_options(
            current
        )

        if is_question_candidate(
            candidate
        ):
            questions.append(
                candidate
            )

    final = []

    seen = set()

    for question in questions:

        question = clean_text(
            question
        )

        key = normalize(
            question
        )

        if (
            key
            and key not in seen
        ):

            seen.add(
                key
            )

            final.append(
                question
            )

    return final


# ============================================================
# SUBJECT DETECTION
# ============================================================

def detect_domain(text):

    tokens = content_tokens(
        text
    )

    scores = {}

    for domain, words in DOMAIN_LEXICONS.items():

        domain_tokens = {
            stem(w)
            for w in words
        }

        scores[domain] = len(
            tokens & domain_tokens
        )

    if not scores:
        return None, 0

    domain = max(
        scores,
        key=scores.get
    )

    return (
        domain,
        scores[domain]
    )


def check_subject(
    question,
    course_name,
    course_content
):

    combined = (
        f"{course_name} "
        f"{course_content}"
    ).strip()

    if not combined:

        return (
            100,
            True,
            "Not specified"
        )

    q_tokens = content_tokens(
        question
    )

    course_tokens = content_tokens(
        combined
    )

    if not q_tokens or not course_tokens:

        return (
            50,
            False,
            "Unknown"
        )

    overlap = (
        q_tokens & course_tokens
    )

    direct_score = min(
        100,
        int(
            (
                len(overlap)
                / max(
                    1,
                    min(
                        len(q_tokens),
                        8
                    )
                )
            )
            * 100
        )
    )

    course_domain, course_hits = detect_domain(
        combined
    )

    question_domain, question_hits = detect_domain(
        question
    )

    if (
        course_domain
        and question_domain
    ):

        if course_domain == question_domain:

            direct_score = max(
                direct_score,
                90
            )

        elif (
            question_hits >= 2
            and course_hits >= 2
        ):

            return (
                10,
                False,
                question_domain
            )

    course_name_tokens = content_tokens(
        course_name
    )

    if course_name_tokens:

        name_overlap = (
            q_tokens
            & course_name_tokens
        )

        if name_overlap:

            direct_score = max(
                direct_score,
                min(
                    100,
                    70
                    + len(name_overlap) * 10
                )
            )

    detected = (
        question_domain
        or course_domain
        or "Unknown"
    )

    return (
        direct_score,
        direct_score >= 60,
        detected
    )


# ============================================================
# BLOOM
# ============================================================

def detect_bloom(question):

    n = normalize(
        question
    )

    for level in reversed(
        BLOOM_LEVELS
    ):

        for verb in BLOOM_VERBS[level]:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                n
            ):
                return level

    return "Understand"


def bloom_score(
    question,
    intended_bloom
):

    actual = detect_bloom(
        question
    )

    if actual == intended_bloom:

        return (
            100,
            actual
        )

    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    difference = abs(
        order.get(
            actual,
            2
        )
        -
        order.get(
            intended_bloom,
            2
        )
    )

    if difference == 1:

        return (
            70,
            actual
        )

    if difference == 2:

        return (
            45,
            actual
        )

    return (
        20,
        actual
    )


# ============================================================
# QUALITY
# ============================================================

def quality_score(question):

    q = clean_text(
        question
    )

    n = normalize(
        q
    )

    score = 50

    if "?" in q:
        score += 10

    words = q.split()

    if len(words) >= 7:
        score += 10

    if len(words) <= 60:
        score += 5

    all_verbs = set()

    for verbs in BLOOM_VERBS.values():

        all_verbs.update(
            verbs
        )

    if any(
        re.search(
            rf"\b{re.escape(v)}\b",
            n
        )
        for v in all_verbs
    ):
        score += 10

    vague = [
        "discuss something",
        "write something",
        "explain everything",
        "do the following",
        "solve a problem",
        "give details",
        "write about"
    ]

    if any(
        x in n
        for x in vague
    ):
        score -= 20

    if re.search(
        r"\b(?:clo|plo|learning outcome|obe|alignment)\b",
        n
    ):
        score -= 40

    return max(
        0,
        min(
            100,
            score
        )
    )


# ============================================================
# PLO ALIGNMENT
# ============================================================

def calculate_plo_alignment(
    question,
    matched_clo,
    matched_plo
):

    if not matched_plo:
        return 0

    direct_plo = outcome_concept_score(
        question,
        matched_plo
    )

    clo_alignment = 0

    if matched_clo:

        clo_alignment = outcome_concept_score(
            question,
            matched_clo
        )

    clo_tokens = outcome_concept_tokens(
        matched_clo
    )

    plo_tokens = outcome_concept_tokens(
        matched_plo
    )

    if (
        clo_tokens
        and plo_tokens
    ):

        shared = (
            clo_tokens
            & plo_tokens
        )

        clo_plo_relationship = (
            len(shared)
            / max(
                1,
                len(plo_tokens)
            )
        ) * 100

    else:

        clo_plo_relationship = 0

    score = (
        direct_plo * 0.55
        + clo_alignment * 0.20
        + clo_plo_relationship * 0.25
    )

    if (
        clo_alignment >= 80
        and clo_plo_relationship >= 50
    ):

        score = max(
            score,
            80
        )

    if (
        clo_alignment >= 90
        and clo_plo_relationship >= 65
    ):

        score = max(
            score,
            90
        )

    if (
        clo_alignment >= 95
        and clo_plo_relationship >= 80
    ):

        score = max(
            score,
            100
        )

    return int(
        min(
            100,
            round(score)
        )
    )


# ============================================================
# MAIN EVALUATOR
# ============================================================

def evaluate_question(
    question,
    course_name,
    course_content,
    clo_text,
    plo_text,
    intended_bloom
):

    question = clean_text(
        question
    )

    clos = parse_outcomes(
        clo_text
    )

    plos = parse_outcomes(
        plo_text
    )

    subject_score, subject_ok, detected_subject = check_subject(
        question,
        course_name,
        course_content
    )

    matched_clo, clo_score = best_outcome(
        question,
        clos
    )

    matched_plo, direct_plo_score = best_outcome(
        question,
        plos
    )

    plo_score = calculate_plo_alignment(
        question,
        matched_clo,
        matched_plo
    )

    bloom_alignment, actual_bloom = bloom_score(
        question,
        intended_bloom
    )

    quality = quality_score(
        question
    )

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

        if clo_score < 80:

            status = "Rejected"

        elif plo_score < 80:

            status = "Rejected"

        elif bloom_alignment < 80:

            status = "Rejected"

        elif quality < 80:

            status = "Needs Review"

        else:

            status = "Approved"

    # --------------------------------------------------------
    # OVERALL
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

    # --------------------------------------------------------
    # STRICT ALIGNMENT
    # ALL REQUIRED DIMENSIONS MUST BE >= 80
    # --------------------------------------------------------

    attained = (
        overall_score >= 80
        and subject_score >= 80
        and clo_score >= 80
        and plo_score >= 80
        and bloom_alignment >= 80
        and quality >= 80
    )

    if attained:
        status = "Approved"

    return {

        "Question": question,

        "Overall Score": overall_score,

        "Subject Relevance": int(
            subject_score
        ),

        "CLO Alignment": int(
            effective_clo
        ),

        "PLO Alignment": int(
            effective_plo
        ),

        "Bloom Alignment": int(
            effective_bloom
        ),

        "Quality": int(
            quality
        ),

        "Matched CLO": matched_clo,

        "Matched PLO": matched_plo,

        "Detected Bloom": actual_bloom,

        "Detected Subject": (
            detected_subject
            or "Not detected"
        ),

        "Status": status,

        "Alignment Attained": attained
    }


# ============================================================
# COURSE TOPICS
# ============================================================

def extract_course_topics(
    course_content,
    course_name
):

    topics = []

    for line in str(
        course_content
    ).splitlines():

        line = clean_text(
            line
        )

        if not line:
            continue

        line = re.sub(
            r"^\s*(?:[-•*]|\d+[\.\)])\s*",
            "",
            line
        )

        if len(line) >= 3:

            topics.append(
                line
            )

    if not topics:

        topics = [
            x.strip()
            for x in re.split(
                r"[,;|]",
                course_content
            )
            if x.strip()
        ]

    if course_name.strip():

        topics.insert(
            0,
            course_name.strip()
        )

    final = []

    seen = set()

    for topic in topics:

        key = normalize(
            topic
        )

        if (
            key
            and key not in seen
        ):

            seen.add(
                key
            )

            final.append(
                topic
            )

    return final[:50]


# ============================================================
# STRONG TOPIC SELECTION
# ============================================================

def select_revision_topic(
    matched_clo,
    matched_plo,
    course_content,
    course_name
):

    clo_tokens = outcome_concept_tokens(
        matched_clo
    )

    plo_tokens = outcome_concept_tokens(
        matched_plo
    )

    topics = extract_course_topics(
        course_content,
        course_name
    )

    best_topic = ""
    best_score = -1

    for topic in topics:

        topic_tokens = content_tokens(
            topic
        )

        if not topic_tokens:
            continue

        clo_overlap = (
            topic_tokens
            & clo_tokens
        )

        plo_overlap = (
            topic_tokens
            & plo_tokens
        )

        course_domain, course_hits = detect_domain(
            course_name
            + " "
            + course_content
        )

        topic_domain, topic_hits = detect_domain(
            topic
        )

        domain_bonus = 0

        if (
            course_domain
            and topic_domain
            and course_domain == topic_domain
        ):
            domain_bonus = 30

        score = (
            len(clo_overlap) * 25
            + len(plo_overlap) * 20
            + len(topic_tokens) * 2
            + domain_bonus
        )

        if score > best_score:

            best_score = score
            best_topic = topic

    if best_topic:
        return best_topic

    core = extract_outcome_core(
        matched_clo
    )

    if core:
        return core

    core = extract_outcome_core(
        matched_plo
    )

    if core:
        return core

    return course_name


# ============================================================
# GENERATE REVISION CANDIDATES
# ============================================================

def generate_revision_candidates(
    original_question,
    matched_clo,
    matched_plo,
    intended_bloom,
    course_name,
    course_content
):

    topic = select_revision_topic(
        matched_clo,
        matched_plo,
        course_content,
        course_name
    )

    topic = extract_outcome_core(
        topic
    )

    clo_core = extract_outcome_core(
        matched_clo
    )

    plo_core = extract_outcome_core(
        matched_plo
    )

    topic = remove_obe_words(
        topic
    )

    clo_core = remove_obe_words(
        clo_core
    )

    plo_core = remove_obe_words(
        plo_core
    )

    if not topic:
        topic = clo_core

    if not topic:
        topic = plo_core

    if not topic:
        topic = course_name

    # Keep phrases manageable.
    if len(topic) > 160:

        topic = (
            topic[:160]
            .rsplit(
                " ",
                1
            )[0]
        )

    if len(clo_core) > 160:

        clo_core = (
            clo_core[:160]
            .rsplit(
                " ",
                1
            )[0]
        )

    if len(plo_core) > 160:

        plo_core = (
            plo_core[:160]
            .rsplit(
                " ",
                1
            )[0]
        )

    candidates = []

    # ========================================================
    # REMEMBER
    # ========================================================

    if intended_bloom == "Remember":

        candidates.extend([

            f"Define {topic} and list its main characteristics",

            f"Identify the key characteristics of {topic} and state the function of each",

            f"What is {topic}? State its main components",

            f"List the major components of {topic} and state the function of each",

            f"Identify the fundamental elements of {topic} and state their roles"
        ])

    # ========================================================
    # UNDERSTAND
    # ========================================================

    elif intended_bloom == "Understand":

        candidates.extend([

            f"Explain {topic} and describe the relationship among its main components",

            f"Describe {topic} and explain the role of its major components",

            f"Explain the main principles of {topic} and illustrate them with a relevant example",

            f"Compare the main features of {topic} and explain how they are related",

            f"Explain {topic} and describe how its major components work together"
        ])

    # ========================================================
    # APPLY
    # ========================================================

    elif intended_bloom == "Apply":

        candidates.extend([

            f"Apply the principles of {topic} to solve a relevant problem and show all necessary steps",

            f"Given a practical situation involving {topic}, apply the appropriate principles to determine the correct result",

            f"Use {topic} to solve a problem and show the method used to obtain the solution",

            f"Apply the appropriate method to a practical problem involving {topic} and obtain the solution",

            f"Given a problem involving {topic}, apply the relevant concepts to determine the correct solution"
        ])

    # ========================================================
    # ANALYZE
    # ========================================================

    elif intended_bloom == "Analyze":

        candidates.extend([

            f"Analyze {topic} by identifying its major components and explaining the relationships among them",

            f"Examine {topic} and distinguish its major components. Explain how each component contributes to the result",

            f"Analyze the relationship among the major components of {topic} and explain how they influence one another",

            f"Compare the major components of {topic} and analyze how their differences affect the overall result",

            f"Analyze {topic} by examining its major elements and explaining their relationships"
        ])

    # ========================================================
    # EVALUATE
    # ========================================================

    elif intended_bloom == "Evaluate":

        candidates.extend([

            f"Evaluate {topic} using appropriate criteria and justify your conclusion with relevant evidence",

            f"Assess the effectiveness of {topic} in a relevant context and justify your judgment with specific evidence",

            f"Compare two approaches related to {topic}, evaluate their effectiveness using clear criteria, and justify your conclusion",

            f"Evaluate the strengths and limitations of {topic} and justify your conclusion using relevant evidence",

            f"Assess {topic} using clear criteria and justify your evaluation with relevant evidence"
        ])

    # ========================================================
    # CREATE
    # ========================================================

    elif intended_bloom == "Create":

        candidates.extend([

            f"Design a practical solution based on {topic} for a clearly defined problem and explain the major design decisions",

            f"Develop a solution that applies {topic} to address a relevant problem. Describe the main components of your solution",

            f"Design an appropriate approach for a problem involving {topic} and explain how your proposed solution addresses the problem",

            f"Construct a practical solution using the principles of {topic} and explain the reasoning behind its major components",

            f"Develop a practical solution involving {topic} and explain how the proposed solution addresses the problem"
        ])

    # ========================================================
    # CLO-SPECIFIC
    # ========================================================

    if clo_core:

        if intended_bloom == "Remember":

            candidates.append(
                f"Define {clo_core} and state its key characteristics"
            )

        elif intended_bloom == "Understand":

            candidates.append(
                f"Explain {clo_core} using {topic} as a relevant example"
            )

        elif intended_bloom == "Apply":

            candidates.append(
                f"Apply {clo_core} to a practical problem involving {topic} and show the steps used"
            )

        elif intended_bloom == "Analyze":

            candidates.append(
                f"Analyze {clo_core} in the context of {topic} and explain the relationships among its major components"
            )

        elif intended_bloom == "Evaluate":

            candidates.append(
                f"Evaluate {clo_core} in the context of {topic} using clear criteria and justify your conclusion"
            )

        elif intended_bloom == "Create":

            candidates.append(
                f"Design a practical solution involving {topic} using {clo_core} and explain the major design decisions"
            )

    # ========================================================
    # PLO-SPECIFIC
    # ========================================================

    if plo_core:

        if intended_bloom == "Remember":

            candidates.append(
                f"Identify the key elements of {plo_core} using {topic} and state their main characteristics"
            )

        elif intended_bloom == "Understand":

            candidates.append(
                f"Explain {topic} and describe how it demonstrates {plo_core}"
            )

        elif intended_bloom == "Apply":

            candidates.append(
                f"Apply {topic} to a practical problem and demonstrate {plo_core}"
            )

        elif intended_bloom == "Analyze":

            candidates.append(
                f"Analyze {topic} and explain how its major components demonstrate {plo_core}"
            )

        elif intended_bloom == "Evaluate":

            candidates.append(
                f"Evaluate a solution involving {topic} using criteria related to {plo_core} and justify your conclusion"
            )

        elif intended_bloom == "Create":

            candidates.append(
                f"Design a solution involving {topic} that demonstrates {plo_core} and explain the major design decisions"
            )

    # ========================================================
    # COMBINED CLO + PLO
    # ========================================================

    if clo_core and plo_core:

        if intended_bloom == "Remember":

            candidates.append(
                f"Identify the key elements of {topic} related to {clo_core} and state their main characteristics"
            )

        elif intended_bloom == "Understand":

            candidates.append(
                f"Explain {clo_core} using {topic} and describe how it demonstrates {plo_core}"
            )

        elif intended_bloom == "Apply":

            candidates.append(
                f"Apply {clo_core} to a practical problem involving {topic} and demonstrate {plo_core}"
            )

        elif intended_bloom == "Analyze":

            candidates.append(
                f"Analyze {clo_core} in the context of {topic} and explain how its components demonstrate {plo_core}"
            )

        elif intended_bloom == "Evaluate":

            candidates.append(
                f"Evaluate a solution involving {topic} using {clo_core} and justify the result using criteria related to {plo_core}"
            )

        elif intended_bloom == "Create":

            candidates.append(
                f"Design a solution involving {topic} using {clo_core} that demonstrates {plo_core}"
            )

    # ========================================================
    # CLEAN AND DEDUPLICATE
    # ========================================================

    cleaned = []

    seen = set()

    for candidate in candidates:

        candidate = remove_obe_words(
            candidate
        )

        candidate = re.sub(
            r"\s+",
            " ",
            candidate
        ).strip()

        candidate = clean_question_punctuation(
            candidate
        )

        if re.search(
            r"\b(?:CLO|PLO|OBE|learning outcome|alignment)\b",
            candidate,
            flags=re.IGNORECASE
        ):
            continue

        key = normalize(
            candidate
        )

        if (
            key
            and key not in seen
        ):

            seen.add(
                key
            )

            cleaned.append(
                candidate
            )

    return cleaned


# ============================================================
# STRICT REVISION PASS
# ============================================================

def revision_passes(result):

    return (
        result["Overall Score"] >= 80
        and result["Subject Relevance"] >= 80
        and result["CLO Alignment"] >= 80
        and result["PLO Alignment"] >= 80
        and result["Bloom Alignment"] >= 80
        and result["Quality"] >= 80
        and result["Alignment Attained"] is True
    )


# ============================================================
# BUILD VALIDATED REVISION
# ============================================================

def create_validated_revision(
    original_question,
    course_name,
    course_content,
    clo_text,
    plo_text,
    intended_bloom
):

    original_result = evaluate_question(
        original_question,
        course_name,
        course_content,
        clo_text,
        plo_text,
        intended_bloom
    )

    clos = parse_outcomes(
        clo_text
    )

    plos = parse_outcomes(
        plo_text
    )

    # --------------------------------------------------------
    # FIND BEST ORIGINAL CLO/PLO
    # --------------------------------------------------------

    matched_clo, _ = best_outcome(
        original_question,
        clos
    )

    matched_plo, _ = best_outcome(
        original_question,
        plos
    )

    # --------------------------------------------------------
    # IF ORIGINAL QUESTION HAS NO GOOD MATCH,
    # USE THE FIRST AVAILABLE OUTCOMES AS THE REVISION TARGET.
    # --------------------------------------------------------

    if not matched_clo and clos:

        matched_clo = clos[0]

    if not matched_plo and plos:

        matched_plo = plos[0]

    # --------------------------------------------------------
    # GENERATE MANY CANDIDATES
    # --------------------------------------------------------

    candidates = generate_revision_candidates(
        original_question,
        matched_clo,
        matched_plo,
        intended_bloom,
        course_name,
        course_content
    )

    evaluated = []

    # --------------------------------------------------------
    # EVALUATE EVERY CANDIDATE
    # --------------------------------------------------------

    for candidate in candidates:

        candidate = clean_question_punctuation(
            candidate
        )

        result = evaluate_question(
            candidate,
            course_name,
            course_content,
            clo_text,
            plo_text,
            intended_bloom
        )

        evaluated.append(
            result
        )

    # --------------------------------------------------------
    # FIND TRUE PASSING REVISIONS
    # --------------------------------------------------------

    passing = [
        r
        for r in evaluated
        if revision_passes(r)
    ]

    if passing:

        passing.sort(
            key=lambda r: (
                r["Overall Score"],
                r["CLO Alignment"],
                r["PLO Alignment"],
                r["Bloom Alignment"],
                r["Subject Relevance"],
                r["Quality"]
            ),
            reverse=True
        )

        best = passing[0]

        return {
            "question": clean_question_punctuation(
                best["Question"]
            ),
            "result": best,
            "attained": True
        }

    # --------------------------------------------------------
    # NO TRUE PASSING REVISION
    # RETURN BEST REAL RESULT
    # --------------------------------------------------------

    if evaluated:

        evaluated.sort(
            key=lambda r: (
                r["Overall Score"],
                r["CLO Alignment"],
                r["PLO Alignment"],
                r["Bloom Alignment"],
                r["Subject Relevance"],
                r["Quality"]
            ),
            reverse=True
        )

        best = evaluated[0]

        return {
            "question": clean_question_punctuation(
                best["Question"]
            ),
            "result": best,
            "attained": False
        }

    return {
        "question": clean_question_punctuation(
            original_question
        ),
        "result": original_result,
        "attained": False
    }


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

st.title(
    "🎓 OBE Assessment Alignment Checker"
)

st.write(
    "Evaluate assessment questions for subject relevance, "
    "CLO alignment, PLO alignment, Bloom's level, "
    "question quality, and overall alignment."
)

st.info(
    "Automatic revisions are tested against the same "
    "alignment criteria before they are accepted."
)


# ============================================================
# COURSE INFORMATION
# ============================================================

st.subheader(
    "1. Course Information"
)

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
    height=140
)


# ============================================================
# CLO / PLO
# ============================================================

st.subheader(
    "2. CLOs and PLOs"
)

col1, col2 = st.columns(2)

with col1:

    clo_text = st.text_area(
        "Course Learning Outcomes (CLOs)",
        placeholder=(
            "CLO 1: Explain fundamental principles.\n"
            "CLO 2: Apply concepts to solve problems."
        ),
        height=180
    )

with col2:

    plo_text = st.text_area(
        "Program Learning Outcomes (PLOs)",
        placeholder=(
            "PLO 1: Apply knowledge of the discipline.\n"
            "PLO 2: Analyze and solve problems."
        ),
        height=180
    )


# ============================================================
# FILE
# ============================================================

st.subheader(
    "3. Upload Assessment"
)

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

        st.error(
            "Please enter the course / subject name."
        )

        st.stop()

    if not clo_text.strip():

        st.error(
            "Please enter at least one CLO."
        )

        st.stop()

    if not plo_text.strip():

        st.error(
            "Please enter at least one PLO."
        )

        st.stop()

    if not uploaded_file:

        st.error(
            "Please upload an assessment file."
        )

        st.stop()

    with st.spinner(
        "Reading and analyzing the assessment..."
    ):

        text, error = read_uploaded_file(
            uploaded_file
        )

        if error:

            st.error(
                error
            )

            st.stop()

        if not text.strip():

            st.error(
                "No readable text was found."
            )

            st.stop()

        questions = extract_questions(
            text
        )

        if not questions:

            st.error(
                "No assessment questions were detected."
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

            results.append(
                result
            )

        st.session_state.analysis_results = results

        st.session_state.revision_data = {}

        st.session_state.revision_values = {}

        st.session_state.tested_revisions = {}


# ============================================================
# DISPLAY RESULTS
# ============================================================

results = st.session_state.analysis_results


if results:

    st.divider()

    st.subheader(
        "4. Assessment Results"
    )

    total = len(
        results
    )

    approved = sum(
        1
        for r in results
        if r["Alignment Attained"]
    )

    rejected = sum(
        1
        for r in results
        if r["Status"] == "Rejected"
    )

    review = sum(
        1
        for r in results
        if r["Status"] == "Needs Review"
    )

    average = int(
        round(
            sum(
                r["Overall Score"]
                for r in results
            )
            /
            max(
                1,
                total
            )
        )
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total Questions",
        total
    )

    c2.metric(
        "Aligned",
        approved
    )

    c3.metric(
        "Needs Review / Rejected",
        rejected + review
    )

    c4.metric(
        "Average Score",
        f"{average}/100"
    )

    # ========================================================
    # TABLE
    # ========================================================

    table_rows = []

    for number, result in enumerate(
        results,
        start=1
    ):

        table_rows.append({

            "Question No.": number,

            "Question": result[
                "Question"
            ],

            "Score / 100": result[
                "Overall Score"
            ],

            "Subject (%)": result[
                "Subject Relevance"
            ],

            "CLO (%)": result[
                "CLO Alignment"
            ],

            "PLO (%)": result[
                "PLO Alignment"
            ],

            "Bloom (%)": result[
                "Bloom Alignment"
            ],

            "Quality (%)": result[
                "Quality"
            ],

            "Status": (
                "Approved"
                if result[
                    "Alignment Attained"
                ]
                else result[
                    "Status"
                ]
            )
        })

    result_df = pd.DataFrame(
        table_rows
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # DETAILS
    # ========================================================

    st.divider()

    st.subheader(
        "5. Question Review and Revision"
    )

    for i, result in enumerate(
        results
    ):

        revision_key = (
            f"revision_{i}"
        )

        if result[
            "Alignment Attained"
        ]:

            icon = "🟢"

        elif result[
            "Status"
        ] == "Needs Review":

            icon = "🟠"

        else:

            icon = "🔴"

        with st.expander(
            f"{icon} Question {i + 1} — "
            f"{result['Overall Score']}/100",
            expanded=False
        ):

            st.markdown(
                "**Original Question:**"
            )

            st.write(
                result[
                    "Question"
                ]
            )

            # ------------------------------------------------
            # ORIGINAL SCORE
            # ------------------------------------------------

            st.markdown(
                "### Original Evaluation"
            )

            cols = st.columns(6)

            cols[0].metric(
                "Overall",
                f"{result['Overall Score']}/100"
            )

            cols[1].metric(
                "Subject",
                f"{result['Subject Relevance']}%"
            )

            cols[2].metric(
                "CLO",
                f"{result['CLO Alignment']}%"
            )

            cols[3].metric(
                "PLO",
                f"{result['PLO Alignment']}%"
            )

            cols[4].metric(
                "Bloom",
                f"{result['Bloom Alignment']}%"
            )

            cols[5].metric(
                "Quality",
                f"{result['Quality']}%"
            )

            if result[
                "Matched CLO"
            ]:

                st.write(
                    "**Matched CLO:** "
                    + result[
                        "Matched CLO"
                    ]
                )

            if result[
                "Matched PLO"
            ]:

                st.write(
                    "**Matched PLO:** "
                    + result[
                        "Matched PLO"
                    ]
                )

            st.write(
                "**Detected Subject:** "
                + str(
                    result[
                        "Detected Subject"
                    ]
                )
            )

            st.write(
                "**Detected Bloom:** "
                + str(
                    result[
                        "Detected Bloom"
                    ]
                )
            )

            # ------------------------------------------------
            # ALREADY ALIGNED
            # ------------------------------------------------

            if result[
                "Alignment Attained"
            ]:

                st.success(
                    f"✓ ALIGNMENT ATTAINED — "
                    f"{result['Overall Score']}/100"
                )

                continue

            # ------------------------------------------------
            # GENERATE REVISION
            # ------------------------------------------------

            st.markdown(
                "### Suggested Revision"
            )

            if (
                revision_key
                not in st.session_state.revision_data
            ):

                with st.spinner(
                    "Generating and testing multiple revisions..."
                ):

                    revision = create_validated_revision(
                        result[
                            "Question"
                        ],
                        course_name,
                        course_content,
                        clo_text,
                        plo_text,
                        intended_bloom
                    )

                    st.session_state.revision_data[
                        revision_key
                    ] = revision

                    st.session_state.revision_values[
                        revision_key
                    ] = revision[
                        "question"
                    ]

            revision = (
                st.session_state.revision_data[
                    revision_key
                ]
            )

            suggested_question = revision[
                "question"
            ]

            suggested_result = revision[
                "result"
            ]

            suggested_attained = revision[
                "attained"
            ]

            # ------------------------------------------------
            # SHOW REVISION
            # ------------------------------------------------

            st.markdown(
                "**Suggested Revised Question:**"
            )

            st.info(
                clean_question_punctuation(
                    suggested_question
                )
            )

            s1, s2, s3, s4, s5, s6 = st.columns(6)

            s1.metric(
                "Score",
                f"{suggested_result['Overall Score']}/100"
            )

            s2.metric(
                "Subject",
                f"{suggested_result['Subject Relevance']}%"
            )

            s3.metric(
                "CLO",
                f"{suggested_result['CLO Alignment']}%"
            )

            s4.metric(
                "PLO",
                f"{suggested_result['PLO Alignment']}%"
            )

            s5.metric(
                "Bloom",
                f"{suggested_result['Bloom Alignment']}%"
            )

            s6.metric(
                "Quality",
                f"{suggested_result['Quality']}%"
            )

            if suggested_attained:

                st.success(
                    f"✓ ALIGNMENT ATTAINED — "
                    f"{suggested_result['Overall Score']}/100"
                )

            else:

                st.warning(
                    "This is the strongest automatically "
                    "generated revision found from the supplied "
                    "course, CLO, and PLO information. It has "
                    "not been labelled aligned because one or "
                    "more required criteria remain below 80%."
                )

            # ------------------------------------------------
            # USE SUGGESTED
            # ------------------------------------------------

            if st.button(
                "✓ Use Suggested Revision",
                key=f"use_{i}",
                type="primary",
                use_container_width=True
            ):

                st.session_state.revision_values[
                    revision_key
                ] = clean_question_punctuation(
                    suggested_question
                )

                st.session_state.tested_revisions[
                    revision_key
                ] = suggested_result

                st.rerun()

            # ------------------------------------------------
            # EDITABLE REVISION
            # ------------------------------------------------

            current_revision = (
                st.session_state.revision_values.get(
                    revision_key,
                    suggested_question
                )
            )

            revised_question = st.text_area(
                "Revised Question",
                value=current_revision,
                key=f"revision_box_{i}",
                height=130
            )

            st.session_state.revision_values[
                revision_key
            ] = revised_question

            # ------------------------------------------------
            # TEST
            # ------------------------------------------------

            if st.button(
                "🧪 Test Revised Question",
                key=f"test_{i}",
                use_container_width=True
            ):

                if not revised_question.strip():

                    st.error(
                        "Please enter a revised question."
                    )

                else:

                    revised_question = clean_question_punctuation(
                        revised_question
                    )

                    st.session_state.revision_values[
                        revision_key
                    ] = revised_question

                    tested_result = evaluate_question(
                        revised_question,
                        course_name,
                        course_content,
                        clo_text,
                        plo_text,
                        intended_bloom
                    )

                    st.session_state.tested_revisions[
                        revision_key
                    ] = tested_result

                    st.rerun()

            # ------------------------------------------------
            # TESTED RESULT
            # ------------------------------------------------

            if (
                revision_key
                in st.session_state.tested_revisions
            ):

                tested = (
                    st.session_state.tested_revisions[
                        revision_key
                    ]
                )

                st.markdown(
                    "### Revised Evaluation"
                )

                r1, r2, r3, r4, r5, r6 = st.columns(6)

                r1.metric(
                    "Revised Score",
                    f"{tested['Overall Score']}/100"
                )

                r2.metric(
                    "Subject",
                    f"{tested['Subject Relevance']}%"
                )

                r3.metric(
                    "CLO",
                    f"{tested['CLO Alignment']}%"
                )

                r4.metric(
                    "PLO",
                    f"{tested['PLO Alignment']}%"
                )

                r5.metric(
                    "Bloom",
                    f"{tested['Bloom Alignment']}%"
                )

                r6.metric(
                    "Quality",
                    f"{tested['Quality']}%"
                )

                change = (
                    tested[
                        "Overall Score"
                    ]
                    -
                    result[
                        "Overall Score"
                    ]
                )

                st.write(
                    f"**Before:** "
                    f"{result['Overall Score']}/100 "
                    f"→ **After:** "
                    f"{tested['Overall Score']}/100 "
                    f"(**{change:+d} points**)"
                )

                # ------------------------------------------------
                # FINAL DECISION
                # ------------------------------------------------

                if tested[
                    "Alignment Attained"
                ]:

                    st.success(
                        f"✓ ALIGNMENT ACHIEVED AFTER REVISION — "
                        f"{tested['Overall Score']}/100"
                    )

                else:

                    st.error(
                        f"Alignment is not yet attained. "
                        f"Revised score: "
                        f"{tested['Overall Score']}/100."
                    )

                    problems = []

                    if tested[
                        "Overall Score"
                    ] < 80:

                        problems.append(
                            "Overall score is below 80%."
                        )

                    if tested[
                        "Subject Relevance"
                    ] < 80:

                        problems.append(
                            "Subject relevance is below 80%."
                        )

                    if tested[
                        "CLO Alignment"
                    ] < 80:

                        problems.append(
                            "CLO alignment is below 80%."
                        )

                    if tested[
                        "PLO Alignment"
                    ] < 80:

                        problems.append(
                            "PLO alignment is below 80%."
                        )

                    if tested[
                        "Bloom Alignment"
                    ] < 80:

                        problems.append(
                            f"Bloom alignment is below 80% "
                            f"for {intended_bloom}."
                        )

                    if tested[
                        "Quality"
                    ] < 80:

                        problems.append(
                            "Question quality is below 80%."
                        )

                    if problems:

                        st.markdown(
                            "**Remaining issues:**"
                        )

                        for problem in problems:

                            st.write(
                                "• " + problem
                            )

                    # ------------------------------------------------
                    # STRONGER REVISION
                    # ------------------------------------------------

                    if st.button(
                        "🔄 Generate Stronger Revision",
                        key=f"stronger_{i}",
                        use_container_width=True
                    ):

                        st.session_state.revision_data.pop(
                            revision_key,
                            None
                        )

                        st.session_state.revision_values.pop(
                            revision_key,
                            None
                        )

                        st.session_state.tested_revisions.pop(
                            revision_key,
                            None
                        )

                        st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Assessment Alignment Checker | "
    "Full alignment requires Overall, Subject, CLO, PLO, "
    "Bloom, and Quality scores of at least 80%."
)
