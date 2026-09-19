import io
import re

import pandas as pd
import streamlit as st

# ============================================================
# OPTIONAL IMPORTS
# ============================================================

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
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "label",
        "select"
    ],

    "Understand": [
        "explain",
        "summarize",
        "interpret",
        "classify",
        "compare",
        "contrast",
        "discuss",
        "illustrate",
        "describe",
        "paraphrase"
    ],

    "Apply": [
        "apply",
        "calculate",
        "solve",
        "use",
        "implement",
        "compute",
        "execute",
        "determine"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "examine",
        "compare",
        "contrast",
        "distinguish",
        "investigate",
        "categorize",
        "break down"
    ],

    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "judge",
        "defend",
        "argue",
        "validate",
        "appraise"
    ],

    "Create": [
        "design",
        "develop",
        "construct",
        "formulate",
        "create",
        "propose",
        "plan",
        "produce"
    ]
}


# ============================================================
# SUBJECT LEXICONS
# ============================================================

DOMAIN_LEXICONS = {

    "Chemistry": {
        "chemistry",
        "chemical",
        "atom",
        "atomic",
        "molecule",
        "molecular",
        "bond",
        "bonding",
        "ionic",
        "covalent",
        "reaction",
        "reactant",
        "product",
        "acid",
        "base",
        "ph",
        "molarity",
        "mole",
        "stoichiometry",
        "element",
        "compound",
        "periodic",
        "oxidation",
        "reduction",
        "redox",
        "equilibrium",
        "thermodynamics",
        "organic",
        "inorganic",
        "solution",
        "concentration",
        "catalyst",
        "electron",
        "proton",
        "neutron",
        "orbital",
        "isotope",
        "enthalpy",
        "entropy",
        "kinetics",
        "precipitate"
    },

    "Physics": {
        "physics",
        "force",
        "motion",
        "velocity",
        "acceleration",
        "momentum",
        "energy",
        "work",
        "power",
        "mass",
        "gravity",
        "friction",
        "pressure",
        "wave",
        "frequency",
        "wavelength",
        "electric",
        "electrical",
        "current",
        "voltage",
        "resistance",
        "circuit",
        "magnetic",
        "field",
        "charge",
        "optics",
        "lens",
        "mirror",
        "heat",
        "temperature",
        "thermodynamics",
        "quantum",
        "relativity",
        "mechanics"
    },

    "Mathematics": {
        "mathematics",
        "math",
        "algebra",
        "equation",
        "function",
        "derivative",
        "differentiation",
        "integral",
        "integration",
        "matrix",
        "vector",
        "probability",
        "statistics",
        "geometry",
        "trigonometry",
        "logarithm",
        "limit",
        "calculus",
        "sequence",
        "series",
        "set",
        "theorem",
        "proof",
        "variable",
        "polynomial",
        "quadratic",
        "linear",
        "differential",
        "optimization"
    },

    "Computer Science": {
        "computer",
        "computing",
        "programming",
        "algorithm",
        "software",
        "hardware",
        "database",
        "sql",
        "python",
        "java",
        "code",
        "coding",
        "data structure",
        "array",
        "linked list",
        "stack",
        "queue",
        "tree",
        "graph",
        "recursion",
        "complexity",
        "operating system",
        "network",
        "networking",
        "compiler",
        "machine learning",
        "artificial intelligence",
        "ai",
        "cybersecurity",
        "security",
        "object oriented",
        "class",
        "object",
        "inheritance",
        "polymorphism"
    },

    "English / Language": {
        "english",
        "language",
        "grammar",
        "writing",
        "reading",
        "paragraph",
        "essay",
        "sentence",
        "vocabulary",
        "syntax",
        "semantics",
        "pragmatics",
        "phonology",
        "morphology",
        "communication",
        "rhetoric",
        "tone",
        "purpose",
        "main idea",
        "paraphrase",
        "summarize",
        "argument",
        "thesis",
        "coherence",
        "cohesion",
        "listening",
        "speaking",
        "pronunciation"
    },

    "Literature": {
        "literature",
        "literary",
        "novel",
        "poem",
        "poetry",
        "drama",
        "play",
        "character",
        "plot",
        "setting",
        "theme",
        "symbolism",
        "metaphor",
        "narrator",
        "imagery",
        "irony",
        "fiction",
        "prose",
        "author",
        "narrative",
        "conflict",
        "point of view"
    },

    "Business / Management": {
        "business",
        "management",
        "manager",
        "organization",
        "leadership",
        "marketing",
        "strategy",
        "planning",
        "entrepreneurship",
        "human resource",
        "motivation",
        "decision",
        "consumer",
        "market",
        "finance",
        "operations",
        "supply chain",
        "stakeholder",
        "organizational",
        "performance",
        "competitive",
        "business model"
    },

    "Accounting / Finance": {
        "accounting",
        "finance",
        "financial",
        "balance sheet",
        "income statement",
        "cash flow",
        "ledger",
        "journal",
        "debit",
        "credit",
        "asset",
        "liability",
        "equity",
        "revenue",
        "expense",
        "profit",
        "loss",
        "budget",
        "ratio",
        "investment",
        "capital",
        "audit",
        "tax",
        "depreciation",
        "cost",
        "account"
    },

    "Economics": {
        "economics",
        "economic",
        "demand",
        "supply",
        "market",
        "price",
        "inflation",
        "unemployment",
        "gdp",
        "fiscal",
        "monetary",
        "elasticity",
        "consumer",
        "producer",
        "utility",
        "opportunity cost",
        "scarcity",
        "macroeconomics",
        "microeconomics",
        "trade",
        "tax"
    },

    "Engineering": {
        "engineering",
        "design",
        "mechanical",
        "electrical",
        "civil",
        "chemical engineering",
        "material",
        "stress",
        "strain",
        "circuit",
        "machine",
        "system",
        "manufacturing",
        "thermodynamics",
        "fluid",
        "structure",
        "load",
        "beam",
        "control",
        "process"
    },

    "Psychology": {
        "psychology",
        "psychological",
        "behavior",
        "behaviour",
        "cognition",
        "memory",
        "learning",
        "emotion",
        "personality",
        "motivation",
        "perception",
        "development",
        "social",
        "conditioning",
        "reinforcement",
        "theory"
    },

    "Sociology": {
        "sociology",
        "society",
        "social",
        "culture",
        "class",
        "institution",
        "family",
        "community",
        "inequality",
        "stratification",
        "socialization",
        "deviance",
        "population",
        "urbanization",
        "gender",
        "identity"
    },

    "Education": {
        "education",
        "teaching",
        "learning",
        "pedagogy",
        "curriculum",
        "assessment",
        "classroom",
        "teacher",
        "student",
        "instruction",
        "lesson",
        "evaluation",
        "educational",
        "learning theory",
        "methodology"
    },

    "History": {
        "history",
        "historical",
        "war",
        "empire",
        "revolution",
        "civilization",
        "colonial",
        "independence",
        "treaty",
        "dynasty",
        "political",
        "historical event",
        "ancient",
        "medieval",
        "modern",
        "primary source"
    },

    "Law": {
        "law",
        "legal",
        "court",
        "case",
        "contract",
        "tort",
        "statute",
        "constitution",
        "jurisdiction",
        "liability",
        "crime",
        "criminal",
        "civil",
        "evidence",
        "judge",
        "plaintiff",
        "defendant",
        "legislation"
    },

    "Pharmacy": {
        "pharmacy",
        "drug",
        "medicine",
        "pharmacology",
        "dose",
        "dosage",
        "drug interaction",
        "receptor",
        "pharmacokinetics",
        "pharmacodynamics",
        "tablet",
        "capsule",
        "patient",
        "therapeutic",
        "adverse",
        "prescription",
        "drug metabolism"
    },

    "Medical / Health Sciences": {
        "medicine",
        "medical",
        "health",
        "patient",
        "disease",
        "diagnosis",
        "symptom",
        "treatment",
        "clinical",
        "anatomy",
        "physiology",
        "pathology",
        "infection",
        "organ",
        "blood",
        "therapy",
        "nursing"
    },

    "Environmental Science": {
        "environment",
        "environmental",
        "ecosystem",
        "pollution",
        "climate",
        "biodiversity",
        "conservation",
        "carbon",
        "greenhouse",
        "sustainability",
        "waste",
        "water",
        "air",
        "soil",
        "renewable"
    }
}


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9%+\-./ ]+", " ", text)
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
        "ing",
        "ers",
        "ies",
        "ed",
        "es",
        "s"
    ]

    for ending in endings:

        if (
            word.endswith(ending)
            and len(word) - len(ending) >= 3
        ):
            return word[:-len(ending)]

    return word


def content_tokens(text):
    text = normalize(text)

    words = re.findall(
        r"[a-zA-Z][a-zA-Z0-9\-]*",
        text
    )

    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "from",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "as",
        "at",
        "it",
        "its",
        "their",
        "they",
        "them",
        "he",
        "she",
        "we",
        "you",
        "your",
        "our",
        "will",
        "shall",
        "can",
        "could",
        "would",
        "should",
        "may",
        "might",
        "must",
        "into",
        "through",
        "using",
        "use",
        "given",
        "following"
    }

    return {
        stem(word)
        for word in words
        if word not in stopwords
        and len(word) > 2
    }


# ============================================================
# PDF / OCR
# ============================================================

def tesseract_available():
    if pytesseract is None:
        return False

    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def render_page(page, dpi=180):
    if fitz is None or Image is None:
        return None

    matrix = fitz.Matrix(
        dpi / 72,
        dpi / 72
    )

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    return Image.open(
        io.BytesIO(
            pix.tobytes("png")
        )
    )


def ocr_image(image):
    if image is None or pytesseract is None:
        return ""

    try:
        return clean_text(
            pytesseract.image_to_string(
                image,
                config="--psm 6"
            )
        )
    except Exception:
        return ""


def read_pdf(file_bytes):

    if fitz is None:
        return "", "PyMuPDF is not installed."

    try:
        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )
    except Exception as e:
        return "", f"Could not open PDF: {e}"

    pages = []
    ocr_count = 0

    for page_number, page in enumerate(
        document,
        start=1
    ):

        try:
            extracted = clean_text(
                page.get_text("text")
            )
        except Exception:
            extracted = ""

        if len(
            re.sub(
                r"\s+",
                "",
                extracted
            )
        ) < 80:

            if tesseract_available():

                image = render_page(page)

                ocr_text = ocr_image(
                    image
                )

                if ocr_text:
                    extracted = ocr_text
                    ocr_count += 1

        if extracted:

            pages.append(
                f"\n--- PAGE {page_number} ---\n"
                f"{extracted}"
            )

    document.close()

    info = (
        f"PDF pages read: {len(pages)}"
    )

    if ocr_count:
        info += (
            f" | OCR used on {ocr_count} page(s)"
        )

    return "\n".join(pages), info


# ============================================================
# DOCUMENT READERS
# ============================================================

def read_docx(file_bytes):

    if Document is None:
        return "", "python-docx is not installed."

    try:
        document = Document(
            io.BytesIO(file_bytes)
        )

        parts = []

        for paragraph in document.paragraphs:

            text = clean_text(
                paragraph.text
            )

            if text:
                parts.append(text)

        for table in document.tables:

            for row in table.rows:

                row_text = " | ".join(
                    clean_text(cell.text)
                    for cell in row.cells
                )

                if row_text:
                    parts.append(row_text)

        return (
            "\n".join(parts),
            "DOCX read successfully."
        )

    except Exception as e:
        return "", f"Could not read DOCX: {e}"


def read_excel(file_bytes):

    try:

        workbook = pd.ExcelFile(
            io.BytesIO(file_bytes)
        )

        sheets = []

        for sheet in workbook.sheet_names:

            df = pd.read_excel(
                io.BytesIO(file_bytes),
                sheet_name=sheet,
                header=None
            )

            sheets.append(
                f"\n--- SHEET: {sheet} ---\n"
                +
                df.fillna("")
                .astype(str)
                .to_csv(
                    index=False,
                    header=False
                )
            )

        return (
            "\n".join(sheets),
            "Excel file read successfully."
        )

    except Exception as e:
        return "", f"Could not read Excel: {e}"


def read_csv(file_bytes):

    try:

        df = pd.read_csv(
            io.BytesIO(file_bytes),
            header=None
        )

        return (
            df.fillna("")
            .astype(str)
            .to_csv(
                index=False,
                header=False
            ),
            "CSV file read successfully."
        )

    except Exception as e:
        return "", f"Could not read CSV: {e}"


def read_text_file(file_bytes):

    for encoding in [
        "utf-8",
        "utf-16",
        "latin-1"
    ]:

        try:
            return (
                file_bytes.decode(encoding),
                "Text file read successfully."
            )
        except UnicodeDecodeError:
            continue

    return "", "Could not decode text file."


def read_uploaded_file(uploaded_file):

    extension = (
        uploaded_file.name
        .lower()
        .split(".")[-1]
    )

    data = uploaded_file.getvalue()

    if extension == "pdf":
        return read_pdf(data)

    if extension == "docx":
        return read_docx(data)

    if extension in [
        "xlsx",
        "xls"
    ]:
        return read_excel(data)

    if extension == "csv":
        return read_csv(data)

    if extension in [
        "txt",
        "text"
    ]:
        return read_text_file(data)

    return (
        "",
        f"Unsupported file type: .{extension}"
    )


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):

    if not text:
        return []

    outcomes = []

    for line in text.splitlines():

        line = clean_text(line)

        if not line:
            continue

        line = re.sub(
            r"^(?:CLO|PLO)"
            r"\s*[-_:]?\s*\d+"
            r"\s*[:.)-]?\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r"^\d+\s*[:.)-]\s*",
            "",
            line
        )

        if len(line) >= 5:
            outcomes.append(
                line.strip()
            )

    return outcomes


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


QUESTION_METADATA_PATTERNS = [
    r"questionwell",
    r"question\s*set",
    r"generated\s*by",
    r"generated\s*on",
    r"date\s*generated",
    r"time\s*generated",
    r"\bpage\s+\d+\b",
    r"student\s*name",
    r"student\s*id",
    r"roll\s*(?:no|number)",
    r"registration\s*(?:no|number)",
    r"course\s*(?:title|code|name)",
    r"instructor",
    r"teacher\s*name",
    r"exam\s*date",
    r"assessment\s*date",
    r"submission\s*date"
]


def is_metadata_line(text):

    normalized = normalize(text)

    if not normalized:
        return True

    for pattern in QUESTION_METADATA_PATTERNS:

        if re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE
        ):
            return True

    if re.fullmatch(
        r"\d{1,2}:\d{2}\s*(?:am|pm)?",
        normalized,
        flags=re.IGNORECASE
    ):
        return True

    if re.fullmatch(
        r"\d{1,4}[/-]\d{1,2}[/-]\d{1,4}",
        normalized
    ):
        return True

    if re.fullmatch(
        r"(?:page\s*)?\d+\s*(?:of\s*\d+)?",
        normalized
    ):
        return True

    if re.fullmatch(
        r"[/\d\s\-]+",
        normalized
    ) and "/" in normalized:
        return True

    return False


def is_option_line(text):

    text = clean_text(text)

    return bool(
        re.match(
            r"^\s*(?:[A-Da-d]|[1-4])"
            r"[\)\.\-:]\s+",
            text
        )
    )


def is_question_candidate(text):

    text = clean_text(text)

    if not text:
        return False

    if is_metadata_line(text):
        return False

    if is_option_line(text):
        return False

    normalized = normalize(text)

    if len(normalized) < 8:
        return False

    if re.fullmatch(
        r"[\d\s:/\-.,]+",
        normalized
    ):
        return False

    if "?" in text:
        return True

    command_pattern = (
        r"^(define|identify|explain|describe|discuss|"
        r"compare|contrast|analyze|analyse|evaluate|"
        r"assess|calculate|solve|apply|determine|"
        r"derive|find|state|list|justify|design|"
        r"develop|construct|interpret|distinguish|"
        r"differentiate|classify|illustrate|examine|"
        r"using|given|consider|suppose|assume)\b"
    )

    if re.search(
        command_pattern,
        normalized
    ):
        return True

    if re.match(
        r"^(what|why|how|which|when|where|who|whose)\b",
        normalized
    ):
        return True

    return False


def extract_questions(text):

    if not text:
        return []

    questions = []
    current = ""

    for raw_line in text.splitlines():

        line = clean_text(raw_line)

        if not line:
            continue

        if is_metadata_line(line):
            continue

        match = NUMBERED_QUESTION_RE.match(
            line
        )

        if match:

            if (
                current
                and is_question_candidate(current)
            ):
                questions.append(
                    current.strip()
                )

            current = match.group(2).strip()

        else:

            if is_option_line(line):
                continue

            if current:
                current += " " + line

            elif is_question_candidate(line):
                current = line

    if (
        current
        and is_question_candidate(current)
    ):
        questions.append(
            current.strip()
        )

    unique_questions = []
    seen = set()

    for question in questions:

        question = clean_text(
            question
        )

        question = re.sub(
            r"^\s*(?:Q(?:uestion)?\s*)?"
            r"\d{1,3}\s*[\.\):\-]\s*",
            "",
            question,
            flags=re.IGNORECASE
        )

        key = normalize(question)

        if len(key) < 8:
            continue

        if key in seen:
            continue

        seen.add(key)
        unique_questions.append(
            question
        )

    return unique_questions


# ============================================================
# DOMAIN DETECTION
# ============================================================

def detect_domain(text):

    normalized = normalize(text)

    best_domain = None
    best_score = 0

    for domain, terms in DOMAIN_LEXICONS.items():

        score = 0

        for term in terms:

            term_norm = normalize(term)

            if " " in term_norm:

                if term_norm in normalized:
                    score += 2

            else:

                if re.search(
                    rf"\b{re.escape(term_norm)}\b",
                    normalized
                ):
                    score += 1

        if score > best_score:

            best_score = score
            best_domain = domain

    return best_domain, best_score


def domain_terms(domain):

    if not domain:
        return set()

    return {
        stem(term)
        for term in DOMAIN_LEXICONS.get(
            domain,
            set()
        )
        if len(term) > 2
    }


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

def check_subject(
    question,
    course_name,
    course_content
):

    q_tokens = content_tokens(
        question
    )

    course_text = (
        f"{course_name} "
        f"{course_content}"
    )

    expected_domain, _ = detect_domain(
        course_text
    )

    question_domain, question_score = (
        detect_domain(question)
    )

    if expected_domain:

        terms = domain_terms(
            expected_domain
        )

        matches = 0

        for term in terms:

            if term in q_tokens:
                matches += 1

        course_tokens = content_tokens(
            course_name
        )

        course_matches = len(
            course_tokens.intersection(
                q_tokens
            )
        )

        content_overlap = len(
            content_tokens(
                course_content
            ).intersection(q_tokens)
        )

        if matches >= 2:

            score = min(
                100,
                55
                + matches * 8
                + content_overlap * 2
            )

            return (
                score,
                True,
                expected_domain
            )

        if (
            course_matches >= 1
            and content_overlap >= 2
        ):

            score = min(
                100,
                65
                + course_matches * 10
                + content_overlap * 3
            )

            return (
                score,
                True,
                expected_domain
            )

        if (
            question_domain
            and question_domain != expected_domain
        ):
            return (
                0,
                False,
                expected_domain
            )

        if question_score == 0:

            return (
                0,
                False,
                expected_domain
            )

        return (
            35,
            False,
            expected_domain
        )

    course_tokens = content_tokens(
        course_text
    )

    question_tokens = content_tokens(
        question
    )

    if not course_tokens:
        return (
            75,
            True,
            None
        )

    overlap = len(
        course_tokens.intersection(
            question_tokens
        )
    )

    if overlap >= 5:
        return (
            90,
            True,
            None
        )

    if overlap >= 3:
        return (
            75,
            True,
            None
        )

    if overlap >= 1:
        return (
            55,
            False,
            None
        )

    return (
        0,
        False,
        None
    )


# ============================================================
# OUTCOME SCORING
# ============================================================

def outcome_score(
    question,
    outcome
):

    if not outcome:
        return 0

    q_tokens = content_tokens(
        question
    )

    o_tokens = content_tokens(
        outcome
    )

    if not o_tokens:
        return 0

    intersection = (
        q_tokens.intersection(
            o_tokens
        )
    )

    overlap_ratio = (
        len(intersection)
        / len(o_tokens)
    )

    score = overlap_ratio * 100

    q_norm = normalize(question)
    o_norm = normalize(outcome)

    phrases = re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9\- ]{3,}\b",
        o_norm
    )

    for phrase in phrases:

        phrase = phrase.strip()

        if (
            len(phrase.split()) >= 2
            and phrase in q_norm
        ):
            score += 20
            break

    return int(
        min(
            100,
            round(score)
        )
    )


def best_outcome(
    question,
    outcomes
):

    if not outcomes:
        return "", 0

    scored = [
        (
            outcome,
            outcome_score(
                question,
                outcome
            )
        )
        for outcome in outcomes
    ]

    scored.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scored[0]


# ============================================================
# BLOOM
# ============================================================

def detect_bloom(question):

    normalized = normalize(
        question
    )

    scores = {}

    for level, verbs in BLOOM_VERBS.items():

        score = 0

        for verb in verbs:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                normalized
            ):
                score += 1

        scores[level] = score

    if max(scores.values()) == 0:
        return (
            "Understand",
            0
        )

    level = max(
        scores,
        key=scores.get
    )

    confidence = min(
        100,
        scores[level] * 35
    )

    return (
        level,
        confidence
    )


def bloom_score(
    question,
    intended_bloom
):

    actual, _ = detect_bloom(
        question
    )

    if (
        actual.lower()
        == intended_bloom.lower()
    ):
        return (
            100,
            actual
        )

    normalized = normalize(
        question
    )

    for verb in BLOOM_VERBS.get(
        intended_bloom,
        []
    ):

        if re.search(
            rf"\b{re.escape(verb)}\b",
            normalized
        ):
            return (
                100,
                actual
            )

    order = {
        "remember": 0,
        "understand": 1,
        "apply": 2,
        "analyze": 3,
        "evaluate": 4,
        "create": 5
    }

    actual_number = order.get(
        actual.lower(),
        1
    )

    intended_number = order.get(
        intended_bloom.lower(),
        1
    )

    distance = abs(
        actual_number
        - intended_number
    )

    if distance == 1:
        return (
            65,
            actual
        )

    if distance == 2:
        return (
            45,
            actual
        )

    return (
        25,
        actual
    )


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question):

    question = clean_text(
        question
    )

    if not question:
        return 0

    score = 50

    words = question.split()

    if len(words) >= 7:
        score += 10

    if len(words) >= 12:
        score += 10

    if "?" in question:
        score += 10

    _, bloom_confidence = detect_bloom(
        question
    )

    if bloom_confidence >= 35:
        score += 10

    if re.search(
        r"\b(what|why|how|which|define|"
        r"explain|calculate|analyze|"
        r"analyse|evaluate|design|apply|"
        r"compare|determine|solve|justify)\b",
        normalize(question)
    ):
        score += 10

    if is_metadata_line(question):
        score -= 50

    return int(
        max(
            0,
            min(
                100,
                score
            )
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

    clos = parse_outcomes(
        clo_text
    )

    plos = parse_outcomes(
        plo_text
    )

    subject_score, subject_ok, detected_subject = (
        check_subject(
            question,
            course_name,
            course_content
        )
    )

    matched_clo, clo_score = (
        best_outcome(
            question,
            clos
        )
    )

    matched_plo, plo_score = (
        best_outcome(
            question,
            plos
        )
    )

    bloom_alignment, actual_bloom = (
        bloom_score(
            question,
            intended_bloom
        )
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
    # OVERALL SCORE / 100
    #
    # Subject = 30
    # CLO     = 30
    # PLO     = 20
    # Bloom   = 15
    # Quality = 5
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
# REVISION GENERATOR
# ============================================================

OBE_TERMS = [
    "CLO",
    "PLO",
    "CLOs",
    "PLOs",
    "OBE",
    "learning outcome",
    "learning outcomes",
    "outcome",
    "outcomes",
    "alignment"
]


def remove_obe_words(text):

    if not text:
        return ""

    cleaned = text

    for term in OBE_TERMS:

        cleaned = re.sub(
            rf"\b{re.escape(term)}\b",
            "",
            cleaned,
            flags=re.IGNORECASE
        )

    cleaned = re.sub(
        r"\bstudents?\s+(?:will|should|can|must)\b",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\bbe able to\b",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\bdemonstrate (?:the )?ability to\b",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    )

    return cleaned.strip()


def extract_outcome_core(outcome):

    if not outcome:
        return ""

    text = remove_obe_words(
        outcome
    )

    action_patterns = [
        r"^\s*identify\s+",
        r"^\s*define\s+",
        r"^\s*describe\s+",
        r"^\s*explain\s+",
        r"^\s*discuss\s+",
        r"^\s*understand\s+",
        r"^\s*apply\s+",
        r"^\s*calculate\s+",
        r"^\s*solve\s+",
        r"^\s*analyze\s+",
        r"^\s*analyse\s+",
        r"^\s*evaluate\s+",
        r"^\s*assess\s+",
        r"^\s*compare\s+",
        r"^\s*contrast\s+",
        r"^\s*demonstrate\s+",
        r"^\s*develop\s+",
        r"^\s*design\s+",
        r"^\s*construct\s+",
        r"^\s*formulate\s+",
        r"^\s*interpret\s+",
        r"^\s*examine\s+",
        r"^\s*distinguish\s+",
        r"^\s*differentiate\s+",
        r"^\s*use\s+"
    ]

    for pattern in action_patterns:

        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE
        )

    text = re.sub(
        r"^\s*students?\s+"
        r"(?:should|can|will|must)\s+",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\bthe ability to\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip(
        " .,:;-"
    )


def construct_revision_question(
    original_question,
    matched_clo,
    matched_plo,
    intended_bloom,
    course_name,
    course_content
):

    # --------------------------------------------------------
    # PRIMARY TARGET = CLO
    # --------------------------------------------------------

    core = extract_outcome_core(
        matched_clo
    )

    # Fallback to PLO if no CLO is available
    if not core:

        core = extract_outcome_core(
            matched_plo
        )

    # Final fallback to original question
    if not core:

        core = remove_obe_words(
            original_question
        )

    core = re.sub(
        r"\s+",
        " ",
        core
    ).strip()

    if len(core) > 200:

        core = (
            core[:200]
            .rsplit(" ", 1)[0]
        )

    bloom = intended_bloom.lower()

    # --------------------------------------------------------
    # DIRECT ASSESSMENT QUESTIONS
    # --------------------------------------------------------

    if bloom == "remember":

        question = (
            f"Define {core} and list "
            f"its main characteristics."
        )

    elif bloom == "understand":

        question = (
            f"Explain {core} and describe "
            f"the relationship between its "
            f"main concepts."
        )

    elif bloom == "apply":

        question = (
            f"Apply the principles of {core} "
            f"to solve the following problem. "
            f"Show the steps used to reach "
            f"your answer."
        )

    elif bloom == "analyze":

        question = (
            f"Analyze {core} by identifying "
            f"its key components and explaining "
            f"the relationships among them."
        )

    elif bloom == "evaluate":

        question = (
            f"Evaluate {core} using appropriate "
            f"criteria and justify your conclusion "
            f"with relevant evidence."
        )

    elif bloom == "create":

        question = (
            f"Design a solution based on "
            f"{core} and explain the reasoning "
            f"behind your design."
        )

    else:

        question = (
            f"Explain {core} and provide "
            f"a relevant example."
        )

    # --------------------------------------------------------
    # FINAL CLEANUP
    # --------------------------------------------------------

    question = remove_obe_words(
        question
    )

    question = re.sub(
        r"\s+",
        " ",
        question
    ).strip()

    question = re.sub(
        r"\s+([?.!,])",
        r"\1",
        question
    )

    if not question.endswith("?"):
        question += "?"

    return question


def build_suggested_revision(
    original_question,
    clo_text,
    plo_text,
    intended_bloom,
    course_name,
    course_content
):

    clos = parse_outcomes(
        clo_text
    )

    plos = parse_outcomes(
        plo_text
    )

    matched_clo, original_clo_score = (
        best_outcome(
            original_question,
            clos
        )
    )

    # If the failed question has weak CLO alignment,
    # choose the CLO that should actually be assessed.
    if (
        not matched_clo
        and clos
    ):

        matched_clo = clos[0]

    if (
        original_clo_score < 30
        and clos
    ):

        ranked = sorted(
            clos,
            key=lambda x: outcome_score(
                original_question,
                x
            ),
            reverse=True
        )

        if ranked:
            matched_clo = ranked[0]

    matched_plo, _ = best_outcome(
        original_question,
        plos
    )

    if (
        not matched_plo
        and plos
    ):
        matched_plo = plos[0]

    return construct_revision_question(
        original_question=original_question,
        matched_clo=matched_clo,
        matched_plo=matched_plo,
        intended_bloom=intended_bloom,
        course_name=course_name,
        course_content=course_content
    )


# ============================================================
# RESULTS DATAFRAME
# ============================================================

def results_to_dataframe(
    results
):

    rows = []

    for index, result in enumerate(
        results,
        start=1
    ):

        rows.append({
            "Question No.": index,
            "Question": result["Question"],
            "Score / 100": result["Overall Score"],
            "Subject (%)": result["Subject Relevance"],
            "CLO (%)": result["CLO Alignment"],
            "PLO (%)": result["PLO Alignment"],
            "Bloom (%)": result["Bloom Alignment"],
            "Quality (%)": result["Quality"],
            "Status": result["Status"]
        })

    return pd.DataFrame(rows)


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = []

if "assessment_text" not in st.session_state:
    st.session_state.assessment_text = ""

if "file_info" not in st.session_state:
    st.session_state.file_info = ""

if "revision_suggestions" not in st.session_state:
    st.session_state.revision_suggestions = {}

if "revision_texts" not in st.session_state:
    st.session_state.revision_texts = {}

if "revised_results" not in st.session_state:
    st.session_state.revised_results = {}


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


# ============================================================
# COURSE INFORMATION
# ============================================================

st.subheader(
    "1. Course Information"
)

course_name = st.text_input(
    "Course Name",
    placeholder="e.g., General Chemistry"
)

course_content = st.text_area(
    "Course Content / Syllabus",
    height=140,
    placeholder=(
        "Paste the relevant course topics, syllabus, "
        "or course description here."
    )
)


# ============================================================
# OUTCOMES
# ============================================================

st.subheader(
    "2. Learning Outcomes"
)

col1, col2 = st.columns(2)

with col1:

    clo_text = st.text_area(
        "CLOs",
        height=180,
        placeholder=(
            "CLO 1: Explain the principles of chemical bonding.\n"
            "CLO 2: Apply stoichiometric calculations "
            "to chemical reactions."
        )
    )

with col2:

    plo_text = st.text_area(
        "PLOs",
        height=180,
        placeholder=(
            "PLO 1: Apply knowledge to solve disciplinary problems.\n"
            "PLO 2: Analyze problems using appropriate methods."
        )
    )


# ============================================================
# BLOOM
# ============================================================

st.subheader(
    "3. Intended Cognitive Level"
)

intended_bloom = st.selectbox(
    "Select the intended Bloom's level",
    BLOOM_LEVELS,
    index=1
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader(
    "4. Upload Assessment"
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
# EVALUATE
# ============================================================

if st.button(
    "🔍 Evaluate Assessment",
    type="primary",
    use_container_width=True
):

    if not course_name.strip():

        st.error(
            "Please enter the course name."
        )

    elif not clo_text.strip():

        st.error(
            "Please enter at least one CLO."
        )

    elif not uploaded_file:

        st.error(
            "Please upload an assessment file."
        )

    else:

        with st.spinner(
            "Reading and evaluating the assessment..."
        ):

            assessment_text, info = (
                read_uploaded_file(
                    uploaded_file
                )
            )

            st.session_state.assessment_text = (
                assessment_text
            )

            st.session_state.file_info = (
                info
            )

            questions = extract_questions(
                assessment_text
            )

            if not questions:

                st.session_state.results = []

                st.error(
                    "No valid assessment questions "
                    "were detected. Please check "
                    "the uploaded file."
                )

            else:

                results = []

                for question in questions:

                    result = evaluate_question(
                        question=question,
                        course_name=course_name,
                        course_content=course_content,
                        clo_text=clo_text,
                        plo_text=plo_text,
                        intended_bloom=intended_bloom
                    )

                    results.append(
                        result
                    )

                st.session_state.results = (
                    results
                )

                st.session_state.revision_suggestions = {}
                st.session_state.revision_texts = {}
                st.session_state.revised_results = {}

                st.success(
                    f"{len(results)} question(s) "
                    f"evaluated successfully."
                )


# ============================================================
# FILE INFO
# ============================================================

if st.session_state.file_info:

    st.caption(
        f"📄 {st.session_state.file_info}"
    )


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.results

if results:

    st.divider()

    st.header(
        "Assessment Results"
    )

    total = len(results)

    approved = sum(
        1
        for result in results
        if result["Status"] == "Approved"
    )

    needs_review = sum(
        1
        for result in results
        if result["Status"] == "Needs Review"
    )

    rejected = sum(
        1
        for result in results
        if result["Status"] == "Rejected"
    )

    average_score = sum(
        result["Overall Score"]
        for result in results
    ) / total

    attainment_rate = (
        approved / total * 100
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric(
            "Questions",
            total
        )

    with c2:
        st.metric(
            "Approved",
            approved
        )

    with c3:
        st.metric(
            "Needs Review",
            needs_review
        )

    with c4:
        st.metric(
            "Rejected",
            rejected
        )

    with c5:
        st.metric(
            "Average Score",
            f"{average_score:.1f}/100"
        )

    st.progress(
        int(attainment_rate)
    )

    st.caption(
        f"Alignment attained: "
        f"{attainment_rate:.1f}% of questions"
    )

    # --------------------------------------------------------
    # TABLE
    # --------------------------------------------------------

    st.subheader(
        "Question Scores"
    )

    results_df = results_to_dataframe(
        results
    )

    st.dataframe(
        results_df,
        use_container_width=True,
        hide_index=True
    )

    csv_data = (
        results_df
        .to_csv(index=False)
        .encode("utf-8")
    )

    st.download_button(
        "⬇️ Download Results CSV",
        data=csv_data,
        file_name=(
            "OBE_Assessment_Alignment_Results.csv"
        ),
        mime="text/csv"
    )

    # ========================================================
    # DETAILS
    # ========================================================

    st.divider()

    st.header(
        "Question Details"
    )

    for index, result in enumerate(
        results
    ):

        question_number = index + 1

        if result["Status"] == "Approved":
            icon = "✅"
        elif result["Status"] == "Needs Review":
            icon = "⚠️"
        else:
            icon = "❌"

        with st.expander(
            f"{icon} Question {question_number} "
            f"— Score {result['Overall Score']}/100"
        ):

            # ------------------------------------------------
            # ORIGINAL QUESTION
            # ------------------------------------------------

            st.markdown(
                "### Original Question"
            )

            st.write(
                result["Question"]
            )

            # ------------------------------------------------
            # ORIGINAL SCORE
            # ------------------------------------------------

            st.markdown(
                "### Original Score"
            )

            m1, m2, m3, m4, m5, m6 = (
                st.columns(6)
            )

            with m1:
                st.metric(
                    "Overall",
                    f"{result['Overall Score']}/100"
                )

            with m2:
                st.metric(
                    "Subject",
                    f"{result['Subject Relevance']}%"
                )

            with m3:
                st.metric(
                    "CLO",
                    f"{result['CLO Alignment']}%"
                )

            with m4:
                st.metric(
                    "PLO",
                    f"{result['PLO Alignment']}%"
                )

            with m5:
                st.metric(
                    "Bloom",
                    f"{result['Bloom Alignment']}%"
                )

            with m6:
                st.metric(
                    "Quality",
                    f"{result['Quality']}%"
                )

            st.write(
                f"**Status:** {result['Status']}"
            )

            st.write(
                f"**Detected Subject:** "
                f"{result['Detected Subject']}"
            )

            st.write(
                f"**Detected Bloom:** "
                f"{result['Detected Bloom']}"
            )

            if result["Matched CLO"]:

                st.write(
                    f"**Matched CLO:** "
                    f"{result['Matched CLO']}"
                )

            if result["Matched PLO"]:

                st.write(
                    f"**Matched PLO:** "
                    f"{result['Matched PLO']}"
                )

            # =================================================
            # REVISION
            # =================================================

            if result["Status"] != "Approved":

                st.divider()

                st.subheader(
                    "💡 Suggested Revision"
                )

                # ------------------------------------------------
                # GENERATE SUGGESTION
                # ------------------------------------------------

                if (
                    question_number
                    not in st.session_state.revision_suggestions
                ):

                    suggestion = (
                        build_suggested_revision(
                            original_question=(
                                result["Question"]
                            ),
                            clo_text=clo_text,
                            plo_text=plo_text,
                            intended_bloom=(
                                intended_bloom
                            ),
                            course_name=(
                                course_name
                            ),
                            course_content=(
                                course_content
                            )
                        )
                    )

                    st.session_state.revision_suggestions[
                        question_number
                    ] = suggestion

                suggestion = (
                    st.session_state.revision_suggestions[
                        question_number
                    ]
                )

                # ------------------------------------------------
                # SHOW SUGGESTION
                # ------------------------------------------------

                st.info(
                    suggestion
                )

                # ------------------------------------------------
                # USE SUGGESTION
                # ------------------------------------------------

                if st.button(
                    "Use Suggested Revision",
                    key=(
                        f"use_suggestion_"
                        f"{question_number}"
                    ),
                    use_container_width=True
                ):

                    st.session_state.revision_texts[
                        question_number
                    ] = suggestion

                    # Remove old test result because
                    # the revision has changed.
                    st.session_state.revised_results.pop(
                        question_number,
                        None
                    )

                    st.rerun()

                # ------------------------------------------------
                # REVISION BOX
                # ------------------------------------------------

                revision_value = (
                    st.session_state.revision_texts.get(
                        question_number,
                        ""
                    )
                )

                revised_question = st.text_area(
                    "Revised Question",
                    value=revision_value,
                    key=(
                        f"revision_box_"
                        f"{question_number}"
                    ),
                    height=120
                )

                st.session_state.revision_texts[
                    question_number
                ] = revised_question

                # ------------------------------------------------
                # TEST
                # ------------------------------------------------

                if st.button(
                    "Test Revised Question",
                    key=(
                        f"test_revision_"
                        f"{question_number}"
                    ),
                    type="primary",
                    use_container_width=True
                ):

                    if not revised_question.strip():

                        st.warning(
                            "Please select the suggested "
                            "revision or enter a revised "
                            "question first."
                        )

                    else:

                        revised_result = (
                            evaluate_question(
                                question=(
                                    revised_question
                                ),
                                course_name=(
                                    course_name
                                ),
                                course_content=(
                                    course_content
                                ),
                                clo_text=clo_text,
                                plo_text=plo_text,
                                intended_bloom=(
                                    intended_bloom
                                )
                            )
                        )

                        st.session_state.revised_results[
                            question_number
                        ] = revised_result

                        st.rerun()

                # =================================================
                # REVISED RESULT
                # =================================================

                if (
                    question_number
                    in st.session_state.revised_results
                ):

                    revised_result = (
                        st.session_state.revised_results[
                            question_number
                        ]
                    )

                    st.divider()

                    st.markdown(
                        "### Revised Question Result"
                    )

                    st.write(
                        revised_result["Question"]
                    )

                    r1, r2, r3, r4, r5, r6 = (
                        st.columns(6)
                    )

                    with r1:
                        st.metric(
                            "Revised Score",
                            (
                                f"{revised_result['Overall Score']}"
                                f"/100"
                            )
                        )

                    with r2:
                        st.metric(
                            "Subject",
                            (
                                f"{revised_result['Subject Relevance']}"
                                "%"
                            )
                        )

                    with r3:
                        st.metric(
                            "CLO",
                            (
                                f"{revised_result['CLO Alignment']}"
                                "%"
                            )
                        )

                    with r4:
                        st.metric(
                            "PLO",
                            (
                                f"{revised_result['PLO Alignment']}"
                                "%"
                            )
                        )

                    with r5:
                        st.metric(
                            "Bloom",
                            (
                                f"{revised_result['Bloom Alignment']}"
                                "%"
                            )
                        )

                    with r6:
                        st.metric(
                            "Quality",
                            (
                                f"{revised_result['Quality']}"
                                "%"
                            )
                        )

                    # ------------------------------------------------
                    # BEFORE / AFTER
                    # ------------------------------------------------

                    original_score = (
                        result["Overall Score"]
                    )

                    revised_score = (
                        revised_result["Overall Score"]
                    )

                    score_change = (
                        revised_score
                        - original_score
                    )

                    st.markdown(
                        "### Before vs. After Revision"
                    )

                    b1, b2, b3 = (
                        st.columns(3)
                    )

                    with b1:

                        st.metric(
                            "Before",
                            f"{original_score}/100"
                        )

                    with b2:

                        st.metric(
                            "After",
                            f"{revised_score}/100",
                            delta=(
                                f"{score_change:+d}"
                            )
                        )

                    with b3:

                        if (
                            revised_result[
                                "Alignment Attained"
                            ]
                        ):

                            st.success(
                                "✓ Alignment Attained"
                            )

                        else:

                            st.warning(
                                "Needs Further Improvement"
                            )

                    # ------------------------------------------------
                    # RESULT DETAILS
                    # ------------------------------------------------

                    st.write(
                        f"**Status:** "
                        f"{revised_result['Status']}"
                    )

                    st.write(
                        f"**Detected Subject:** "
                        f"{revised_result['Detected Subject']}"
                    )

                    st.write(
                        f"**Detected Bloom:** "
                        f"{revised_result['Detected Bloom']}"
                    )

                    # ------------------------------------------------
                    # ATTAINMENT MESSAGE
                    # ------------------------------------------------

                    if (
                        revised_result[
                            "Alignment Attained"
                        ]
                    ):

                        st.success(
                            "✓ The revised question "
                            "meets the required "
                            "alignment criteria."
                        )

                    else:

                        reasons = []

                        if (
                            revised_result[
                                "Subject Relevance"
                            ] < 60
                        ):

                            reasons.append(
                                "Subject relevance is below 60%."
                            )

                        if (
                            revised_result[
                                "CLO Alignment"
                            ] < 60
                        ):

                            reasons.append(
                                "CLO alignment is below 60%."
                            )

                        if (
                            revised_result[
                                "PLO Alignment"
                            ] < 45
                        ):

                            reasons.append(
                                "PLO alignment is below 45%."
                            )

                        if (
                            revised_result[
                                "Bloom Alignment"
                            ] < 80
                        ):

                            reasons.append(
                                "Bloom alignment is below 80%."
                            )

                        if (
                            revised_result[
                                "Quality"
                            ] < 60
                        ):

                            reasons.append(
                                "Question quality is below 60%."
                            )

                        if reasons:

                            st.warning(
                                "The revised question "
                                "still needs improvement."
                            )

                            for reason in reasons:

                                st.write(
                                    f"• {reason}"
                                )


# ============================================================
# SYSTEM INFORMATION
# ============================================================

with st.expander(
    "System Information"
):

    st.write(
        "Supported assessment formats: "
        "PDF, DOCX, XLSX, XLS, CSV, TXT"
    )

    st.write(
        f"PyMuPDF available: "
        f"{'Yes' if fitz else 'No'}"
    )

    st.write(
        f"Tesseract available: "
        f"{'Yes' if tesseract_available() else 'No'}"
    )
