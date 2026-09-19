import io
import re
from collections import Counter

import pandas as pd
import streamlit as st

# Optional libraries
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image, ImageOps, ImageEnhance
except ImportError:
    Image = None
    ImageOps = None
    ImageEnhance = None

try:
    from docx import Document
except ImportError:
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
# BLOOM TAXONOMY
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
    "Remember": {
        "define", "list", "name", "identify", "state", "recall",
        "recognize", "label", "match", "select", "describe"
    },
    "Understand": {
        "explain", "summarize", "interpret", "classify", "discuss",
        "compare", "contrast", "illustrate", "paraphrase", "describe"
    },
    "Apply": {
        "apply", "calculate", "solve", "demonstrate", "use",
        "implement", "execute", "compute", "perform", "construct"
    },
    "Analyze": {
        "analyze", "analyse", "differentiate", "examine", "investigate",
        "categorize", "deconstruct", "infer", "distinguish", "break down"
    },
    "Evaluate": {
        "evaluate", "justify", "assess", "critique", "judge",
        "defend", "argue", "appraise", "validate", "recommend"
    },
    "Create": {
        "create", "design", "develop", "formulate", "produce",
        "construct", "generate", "plan", "propose", "compose"
    }
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than",
    "of", "to", "in", "on", "for", "from", "with", "by", "as",
    "at", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "their",
    "they", "them", "he", "she", "his", "her", "you", "your",
    "we", "our", "I", "me", "my", "which", "who", "what",
    "when", "where", "why", "how", "do", "does", "did",
    "can", "could", "may", "might", "should", "would", "will",
    "shall", "must", "have", "has", "had", "also", "very",
    "into", "about", "over", "under", "between", "through",
    "following", "given", "using", "based", "question",
    "questions", "answer", "answers", "following"
}


# ============================================================
# SUBJECT / DOMAIN LEXICONS
# ============================================================

DOMAIN_LEXICONS = {

    "Chemistry": {
        "atom", "atoms", "molecule", "molecules", "element",
        "elements", "compound", "compounds", "chemical",
        "reaction", "reactions", "bond", "bonds", "ionic",
        "covalent", "organic", "inorganic", "acid", "acids",
        "base", "bases", "ph", "mole", "moles", "stoichiometry",
        "oxidation", "reduction", "redox", "equilibrium",
        "catalyst", "catalysis", "solution", "solubility",
        "concentration", "periodic", "electron", "electrons",
        "proton", "neutron", "valence", "orbital", "thermochemistry",
        "enthalpy", "entropy", "kinetics", "isomer", "polymer"
    },

    "Physics": {
        "force", "forces", "motion", "velocity", "acceleration",
        "momentum", "energy", "work", "power", "mass", "weight",
        "gravity", "gravitational", "friction", "pressure",
        "density", "wave", "waves", "frequency", "wavelength",
        "amplitude", "electric", "electricity", "current",
        "voltage", "resistance", "circuit", "magnetic", "magnetism",
        "charge", "field", "light", "optics", "lens", "mirror",
        "quantum", "relativity", "thermodynamics", "temperature"
    },

    "Mathematics": {
        "equation", "equations", "algebra", "algebraic", "variable",
        "variables", "function", "functions", "derivative",
        "derivatives", "integral", "integrals", "calculus",
        "matrix", "matrices", "vector", "vectors", "probability",
        "statistics", "mean", "median", "mode", "variance",
        "geometry", "triangle", "angle", "polynomial", "factor",
        "factorization", "logarithm", "logarithmic", "sequence",
        "series", "limit", "limits", "set", "sets", "number",
        "theorem", "proof", "graph", "linear", "quadratic"
    },

    "Computer Science": {
        "algorithm", "algorithms", "program", "programming",
        "code", "coding", "software", "hardware", "computer",
        "database", "databases", "sql", "python", "java", "c++",
        "javascript", "class", "object", "objects", "inheritance",
        "polymorphism", "encapsulation", "recursion", "array",
        "arrays", "stack", "queue", "linked", "list", "tree",
        "graph", "network", "networks", "operating", "system",
        "systems", "compiler", "binary", "data", "structure",
        "structures", "machine", "learning", "artificial",
        "intelligence", "security", "cybersecurity"
    },

    "English / Language": {
        "grammar", "sentence", "sentences", "paragraph", "paragraphs",
        "essay", "essays", "writing", "writer", "reading",
        "main", "idea", "ideas", "purpose", "tone", "author",
        "audience", "organization", "organizing", "paraphrase",
        "summarize", "summary", "thesis", "argument", "rhetorical",
        "language", "vocabulary", "pronunciation", "listening",
        "speaking", "communication", "style", "coherence",
        "cohesion", "transition", "transitions", "clause", "clauses"
    },

    "Literature": {
        "poem", "poetry", "novel", "novels", "story", "stories",
        "character", "characters", "plot", "theme", "themes",
        "symbolism", "metaphor", "simile", "narrator", "narrative",
        "author", "literary", "literature", "protagonist",
        "antagonist", "setting", "imagery", "irony", "drama",
        "fiction", "genre", "stanza", "verse", "sonnet"
    },

    "Business / Management": {
        "business", "management", "manager", "organization",
        "organizational", "leadership", "marketing", "market",
        "strategy", "strategic", "customer", "customers",
        "entrepreneur", "entrepreneurship", "planning", "operations",
        "human", "resources", "hr", "motivation", "decision",
        "decisions", "performance", "consumer", "product",
        "brand", "finance", "supply", "stakeholder", "stakeholders"
    },

    "Accounting / Finance": {
        "accounting", "account", "accounts", "ledger", "journal",
        "debit", "credit", "assets", "liabilities", "equity",
        "revenue", "expense", "expenses", "profit", "loss",
        "balance", "sheet", "income", "cash", "flow", "audit",
        "auditing", "financial", "finance", "budget", "capital",
        "investment", "ratio", "ratios", "depreciation", "tax"
    },

    "Economics": {
        "economics", "economic", "demand", "supply", "market",
        "price", "prices", "inflation", "unemployment", "gdp",
        "gross", "domestic", "product", "fiscal", "monetary",
        "policy", "utility", "consumer", "producer", "cost",
        "revenue", "elasticity", "equilibrium", "competition",
        "monopoly", "microeconomics", "macroeconomics"
    },

    "Engineering": {
        "engineering", "design", "mechanical", "electrical",
        "civil", "structural", "material", "materials", "machine",
        "machines", "manufacturing", "circuit", "circuits",
        "stress", "strain", "load", "loads", "beam", "bridge",
        "fluid", "fluids", "thermodynamics", "mechanics",
        "control", "system", "systems", "process", "technical"
    },

    "Psychology": {
        "psychology", "psychological", "behavior", "behaviour",
        "cognitive", "memory", "learning", "emotion", "emotions",
        "personality", "development", "motivation", "perception",
        "attention", "intelligence", "therapy", "mental",
        "conditioning", "reinforcement", "neuroscience"
    },

    "Sociology": {
        "society", "social", "sociology", "culture", "cultural",
        "class", "gender", "socialization", "institution",
        "institutions", "family", "community", "inequality",
        "stratification", "deviance", "population", "urban",
        "rural", "group", "groups", "norms", "values"
    },

    "Education": {
        "education", "teaching", "learning", "teacher", "student",
        "students", "pedagogy", "curriculum", "assessment",
        "instruction", "classroom", "lesson", "learning",
        "outcome", "outcomes", "educational", "school", "university",
        "evaluation", "rubric", "learning", "methodology"
    },

    "History": {
        "history", "historical", "war", "wars", "empire", "king",
        "kingdom", "colonial", "colonialism", "revolution",
        "independence", "treaty", "dynasty", "civilization",
        "ancient", "medieval", "modern", "political", "event",
        "events", "period", "era"
    },

    "Law": {
        "law", "legal", "court", "courts", "judge", "judgment",
        "judgement", "case", "cases", "contract", "contracts",
        "constitution", "constitutional", "statute", "statutes",
        "tort", "criminal", "civil", "liability", "evidence",
        "rights", "rights", "plaintiff", "defendant", "legislation"
    },

    "Pharmacy": {
        "drug", "drugs", "medicine", "medication", "pharmacy",
        "pharmacology", "dose", "dosage", "tablet", "capsule",
        "drug", "receptor", "adverse", "therapeutic", "antibiotic",
        "antibiotics", "pharmacokinetics", "pharmacodynamics",
        "prescription", "formulation"
    },

    "Medical / Health Sciences": {
        "patient", "patients", "disease", "diseases", "clinical",
        "diagnosis", "diagnostic", "treatment", "symptom", "symptoms",
        "health", "medical", "medicine", "anatomy", "physiology",
        "pathology", "infection", "hospital", "nursing", "therapy",
        "blood", "cell", "cells", "organ", "organs"
    },

    "Environmental Science": {
        "environment", "environmental", "ecosystem", "ecosystems",
        "pollution", "climate", "climate", "biodiversity",
        "conservation", "sustainability", "waste", "water",
        "air", "soil", "forest", "forests", "carbon", "emission",
        "emissions", "global", "warming", "renewable", "energy"
    }
}


DOMAIN_ALIASES = {
    "chemistry": "Chemistry",
    "physics": "Physics",
    "mathematics": "Mathematics",
    "math": "Mathematics",
    "computer science": "Computer Science",
    "computer": "Computer Science",
    "programming": "Computer Science",
    "english": "English / Language",
    "english language": "English / Language",
    "language": "English / Language",
    "literature": "Literature",
    "business": "Business / Management",
    "management": "Business / Management",
    "accounting": "Accounting / Finance",
    "finance": "Accounting / Finance",
    "economics": "Economics",
    "engineering": "Engineering",
    "psychology": "Psychology",
    "sociology": "Sociology",
    "education": "Education",
    "history": "History",
    "law": "Law",
    "pharmacy": "Pharmacy",
    "medicine": "Medical / Health Sciences",
    "medical": "Medical / Health Sciences",
    "health sciences": "Medical / Health Sciences",
    "environmental science": "Environmental Science"
}


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("’", "'")

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

    suffixes = [
        "ingly",
        "edly",
        "ing",
        "tion",
        "sion",
        "ment",
        "ness",
        "ies",
        "es",
        "s"
    ]

    for suffix in suffixes:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            if suffix == "ies":
                return word[:-3] + "y"
            return word[:-len(suffix)]

    return word


def content_tokens(text):
    words = normalize(text).split()

    result = []

    for word in words:
        if word in STOP_WORDS:
            continue

        if len(word) < 3:
            continue

        result.append(stem(word))

    return set(result)


# ============================================================
# OCR / FILE READING
# ============================================================

def tesseract_available():
    if pytesseract is None:
        return False

    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def render_page(page):
    if fitz is None or Image is None:
        return None

    try:
        matrix = fitz.Matrix(2.5, 2.5)
        pix = page.get_pixmap(
            matrix=matrix,
            colorspace=fitz.csRGB,
            alpha=False
        )

        image = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

        image = ImageOps.grayscale(image)
        image = ImageOps.autocontrast(image)

        return image

    except Exception:
        return None


def ocr_image(image):
    if pytesseract is None or image is None:
        return ""

    try:
        text = pytesseract.image_to_string(
            image,
            config="--psm 6"
        )
        return clean_text(text)
    except Exception:
        return ""


def read_pdf(uploaded_file):
    if fitz is None:
        return "", "PyMuPDF is not installed."

    try:
        data = uploaded_file.read()

        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []
        ocr_pages = 0

        for page in document:
            text = clean_text(page.get_text("text"))

            # OCR scanned/poor-text page
            if len(re.sub(r"\s+", "", text)) < 80:
                if tesseract_available():
                    image = render_page(page)

                    if image is not None:
                        ocr_text = ocr_image(image)

                        if len(ocr_text) > len(text):
                            text = ocr_text
                            ocr_pages += 1

            if text:
                pages.append(text)

        document.close()

        full_text = "\n\n".join(pages)

        info = f"PDF read successfully. OCR used on {ocr_pages} page(s)."

        return full_text, info

    except Exception as e:
        return "", f"Could not read PDF: {e}"


def read_docx(uploaded_file):
    if Document is None:
        return "", "python-docx is not installed."

    try:
        document = Document(
            io.BytesIO(uploaded_file.read())
        )

        parts = []

        for paragraph in document.paragraphs:
            text = clean_text(paragraph.text)

            if text:
                parts.append(text)

        for table in document.tables:
            for row in table.rows:
                cells = []

                for cell in row.cells:
                    value = clean_text(cell.text)

                    if value:
                        cells.append(value)

                if cells:
                    parts.append(" | ".join(cells))

        return "\n".join(parts), "DOCX read successfully."

    except Exception as e:
        return "", f"Could not read DOCX: {e}"


def read_excel(uploaded_file):
    try:
        data = uploaded_file.read()

        sheets = pd.read_excel(
            io.BytesIO(data),
            sheet_name=None,
            header=None
        )

        parts = []

        for sheet_name, dataframe in sheets.items():

            parts.append(f"Sheet: {sheet_name}")

            for row in dataframe.fillna("").astype(str).values:
                row_text = " ".join(
                    str(x).strip()
                    for x in row
                    if str(x).strip()
                )

                if row_text:
                    parts.append(row_text)

        return "\n".join(parts), "Excel file read successfully."

    except Exception as e:
        return "", f"Could not read Excel file: {e}"


def read_csv(uploaded_file):
    try:
        dataframe = pd.read_csv(
            uploaded_file
        )

        dataframe = dataframe.fillna("").astype(str)

        parts = []

        for row in dataframe.values:
            row_text = " ".join(
                str(x).strip()
                for x in row
                if str(x).strip()
            )

            if row_text:
                parts.append(row_text)

        return "\n".join(parts), "CSV file read successfully."

    except Exception as e:
        return "", f"Could not read CSV file: {e}"


def read_file(uploaded_file):
    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    try:
        content = uploaded_file.read()

        if isinstance(content, bytes):
            content = content.decode(
                "utf-8",
                errors="ignore"
            )

        return clean_text(content), "Text file read successfully."

    except Exception as e:
        return "", f"Could not read file: {e}"


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, prefix):
    text = clean_text(text)

    if not text:
        return []

    lines = text.splitlines()

    outcomes = []

    current_code = None
    current_text = []

    pattern = re.compile(
        rf"\b({re.escape(prefix)}\s*[-_]?\s*\d+)\b",
        re.IGNORECASE
    )

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        match = pattern.search(line)

        if match:
            if current_code and current_text:
                outcomes.append({
                    "code": current_code.upper(),
                    "text": " ".join(current_text).strip()
                })

            current_code = match.group(1)
            remaining = line[match.end():].strip()

            remaining = re.sub(
                r"^[\s:\-–—.)]+",
                "",
                remaining
            )

            current_text = [remaining] if remaining else []

        elif current_code:
            current_text.append(line)

    if current_code and current_text:
        outcomes.append({
            "code": current_code.upper(),
            "text": " ".join(current_text).strip()
        })

    return outcomes


# ============================================================
# QUESTION EXTRACTION
# ============================================================

PAGE_MARKER_RE = re.compile(
    r"^\s*(?:page\s*)?\d+\s*(?:of\s*\d+)?\s*$",
    re.IGNORECASE
)

TIME_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\s*$",
    re.IGNORECASE
)

DATE_RE = re.compile(
    r"^\s*(?:"
    r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}"
    r"|"
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}"
    r"|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}"
    r")\s*$",
    re.IGNORECASE
)

NUMBERED_QUESTION_RE = re.compile(
    r"^\s*"
    r"(?:Q(?:uestion)?\s*)?"
    r"(\d{1,3})"
    r"\s*[\.\):\-]\s*"
    r"(.+?)"
    r"\s*$",
    re.IGNORECASE
)

OPTION_RE = re.compile(
    r"^\s*(?:\([A-H]\)|[A-H][\.\):]|[A-H]\s+-)\s+",
    re.IGNORECASE
)


QUESTION_START_VERBS = {
    "define",
    "explain",
    "describe",
    "discuss",
    "identify",
    "list",
    "state",
    "compare",
    "contrast",
    "analyze",
    "analyse",
    "evaluate",
    "assess",
    "justify",
    "calculate",
    "solve",
    "find",
    "determine",
    "derive",
    "apply",
    "use",
    "demonstrate",
    "interpret",
    "classify",
    "differentiate",
    "examine",
    "investigate",
    "design",
    "develop",
    "create",
    "construct",
    "formulate",
    "propose",
    "write",
    "summarize",
    "summarise",
    "critique",
    "discuss",
    "illustrate",
    "show",
    "prove",
    "compute",
    "predict",
    "identify",
    "mention",
    "outline"
}


def is_metadata(line):
    text = clean_text(line)

    if not text:
        return True

    lower = text.lower()

    if PAGE_MARKER_RE.match(text):
        return True

    if TIME_RE.match(text):
        return True

    if DATE_RE.match(text):
        return True

    # Examples such as /19/26, 19/26, 2026/19
    if re.fullmatch(r"[\d\s/\\_.-]+", text):
        if "/" in text or "\\" in text:
            return True

    # Common document metadata
    metadata_phrases = [
        "questionwell",
        "question set",
        "generated by",
        "generated on",
        "date:",
        "time:",
        "page:",
        "student name",
        "student id",
        "roll number",
        "registration number",
        "course instructor",
        "instructor:",
        "teacher:",
        "semester:",
        "section:",
        "university:",
        "department:",
        "assessment:",
        "assessment title",
        "total marks",
        "maximum marks",
        "marks:",
        "duration:",
        "instructions:"
    ]

    for phrase in metadata_phrases:
        if phrase in lower:
            return True

    # Headers that are clearly not questions
    header_phrases = [
        "multiple choice questions",
        "short questions",
        "long questions",
        "subjective questions",
        "objective questions",
        "assessment questions",
        "question paper",
        "quiz",
        "midterm examination",
        "final examination",
        "examination paper"
    ]

    if lower in header_phrases:
        return True

    return False


def is_heading(line):
    text = clean_text(line)

    if not text:
        return True

    if text.endswith(":"):
        return True

    words = text.split()

    if len(words) <= 7 and not text.endswith("?"):
        if text.isupper():
            return True

    return False


def is_question_candidate(text):
    text = clean_text(text)

    if not text:
        return False

    if is_metadata(text):
        return False

    if len(text) < 10:
        return False

    # Direct question
    if "?" in text:
        return True

    normalized = normalize(text)
    words = normalized.split()

    if not words:
        return False

    # Command / task question
    if words[0] in QUESTION_START_VERBS:
        return True

    # Common question structures
    if words[0] in {
        "what",
        "why",
        "how",
        "when",
        "where",
        "which",
        "who"
    }:
        return True

    # Useful academic instructions
    if words[0] in {
        "using",
        "given",
        "consider",
        "calculate",
        "suppose",
        "assume"
    }:
        return True

    return False


def remove_mcq_options(text):
    lines = text.splitlines()

    cleaned = []

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        if OPTION_RE.match(line):
            continue

        cleaned.append(line)

    return " ".join(cleaned).strip()


def extract_questions(text):
    text = clean_text(text)

    if not text:
        return []

    lines = [
        clean_text(line)
        for line in text.splitlines()
    ]

    questions = []

    current = None
    current_number = None

    def save_current():
        nonlocal current, current_number

        if not current:
            return

        candidate = clean_text(" ".join(current))
        candidate = remove_mcq_options(candidate)

        if is_question_candidate(candidate):
            questions.append({
                "number": current_number,
                "text": candidate
            })

        current = None
        current_number = None

    for line in lines:

        if not line:
            continue

        if is_metadata(line):
            continue

        match = NUMBERED_QUESTION_RE.match(line)

        if match:
            save_current()

            number = match.group(1)
            body = clean_text(match.group(2))

            if body:
                current = [body]
                current_number = number

            continue

        # Ignore obvious answer choices
        if OPTION_RE.match(line):
            continue

        # If no numbered question has started
        if current is None:

            if is_question_candidate(line):
                current = [line]
                current_number = None

            continue

        # Avoid adding obvious headings into an existing question
        if is_heading(line) and not line.endswith("?"):
            continue

        # Continuation of current question
        current.append(line)

        # If line itself completes a question, save it
        if line.endswith("?"):
            save_current()

    save_current()

    # Remove duplicates
    unique = []
    seen = set()

    for q in questions:
        normalized = normalize(q["text"])

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        unique.append(q)

    # Re-number if necessary
    for index, q in enumerate(unique, start=1):
        if not q["number"]:
            q["number"] = str(index)

    return unique


# ============================================================
# DOMAIN DETECTION
# ============================================================

def detect_domain(course_name, course_content, questions):
    combined = " ".join([
        course_name or "",
        course_content or "",
        " ".join(q["text"] for q in questions[:30])
    ])

    normalized = normalize(combined)

    # Explicit course name aliases get priority
    for alias, domain in DOMAIN_ALIASES.items():
        if alias in normalized:
            return domain, 0.95

    tokens = set(normalized.split())

    scores = {}

    for domain, vocabulary in DOMAIN_LEXICONS.items():
        hits = len(tokens.intersection(vocabulary))
        scores[domain] = hits

    if not scores:
        return "Unknown", 0.0

    ordered = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    best_domain, best_score = ordered[0]

    if best_score == 0:
        return "Unknown", 0.0

    total = sum(scores.values())

    confidence = best_score / max(total, 1)

    return best_domain, confidence


def check_subject(question, selected_domain, course_content):
    if selected_domain == "Unknown":
        return True, 50, "Subject could not be determined."

    vocabulary = DOMAIN_LEXICONS.get(
        selected_domain,
        set()
    )

    question_tokens = set(
        normalize(question).split()
    )

    course_tokens = set(
        normalize(course_content).split()
    )

    direct_hits = question_tokens.intersection(vocabulary)

    course_hits = question_tokens.intersection(
        course_tokens
    )

    # Strong domain evidence
    domain_score = min(
        100,
        len(direct_hits) * 25
    )

    # Course-content evidence
    course_score = min(
        100,
        len(course_hits) * 15
    )

    combined = max(
        domain_score,
        course_score
    )

    # Explicitly reject clear mismatch
    if len(direct_hits) >= 2:
        return True, min(100, max(70, combined)), \
            f"Relevant {selected_domain} terminology detected."

    if len(direct_hits) == 1 and len(course_hits) >= 1:
        return True, 65, \
            f"Question has {selected_domain} and course-content evidence."

    if len(course_hits) >= 2:
        return True, 60, \
            "Question shares important terms with the course content."

    return False, combined, \
        f"Insufficient evidence that the question belongs to {selected_domain}."


# ============================================================
# CLO / PLO ALIGNMENT
# ============================================================

def outcome_score(question, outcome_text):
    q_tokens = content_tokens(question)
    o_tokens = content_tokens(outcome_text)

    if not q_tokens or not o_tokens:
        return 0

    overlap = q_tokens.intersection(o_tokens)

    if not overlap:
        return 0

    # Weighted overlap
    score_1 = len(overlap) / max(len(q_tokens), 1)
    score_2 = len(overlap) / max(len(o_tokens), 1)

    score = (
        score_1 * 60
        +
        score_2 * 40
    )

    return round(min(100, score), 1)


def best_outcome(question, outcomes):
    if not outcomes:
        return None, 0

    scored = []

    for outcome in outcomes:
        score = outcome_score(
            question,
            outcome["text"]
        )

        scored.append(
            (score, outcome)
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    best_score, best = scored[0]

    return best, best_score


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):
    normalized = normalize(question)
    words = normalized.split()

    matches = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:
            if verb in words:
                matches.append(
                    (level, verb)
                )

    if not matches:
        return None, None

    priority = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    matches.sort(
        key=lambda x: priority[x[0]],
        reverse=True
    )

    return matches[0][0], matches[0][1]


def bloom_score(detected, selected):
    if not detected or not selected:
        return 50

    if detected == selected:
        return 100

    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    distance = abs(
        order[detected] -
        order[selected]
    )

    if distance == 1:
        return 70

    if distance == 2:
        return 45

    return 25


# ============================================================
# QUESTION QUALITY
# ============================================================

def quality_score(question):
    score = 100
    text = clean_text(question)

    if len(text) < 20:
        score -= 25

    if len(text) > 500:
        score -= 10

    words = text.split()

    if len(words) > 100:
        score -= 10

    if text.count("?") > 2:
        score -= 10

    repeated = Counter(
        normalize(text).split()
    )

    if repeated:
        most_common = repeated.most_common(1)[0]

        if most_common[1] > 5:
            score -= 10

    return max(0, min(100, score))


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    selected_domain,
    course_content,
    clos,
    plos,
    selected_bloom
):
    subject_ok, subject_score, subject_reason = check_subject(
        question,
        selected_domain,
        course_content
    )

    detected_bloom, bloom_verb = detect_bloom(
        question
    )

    quality = quality_score(
        question
    )

    # --------------------------------------------------------
    # HARD SUBJECT GATE
    # --------------------------------------------------------

    if not subject_ok:
        return {
            "Status": "Rejected",
            "Alignment Attained": False,
            "Subject Relevance": subject_score,
            "CLO Alignment": 0,
            "PLO Alignment": 0,
            "Bloom Alignment": 0,
            "Quality": quality,
            "Detected Bloom": detected_bloom or "Not detected",
            "Bloom Verb": bloom_verb or "",
            "Matched CLO": "None",
            "Matched PLO": "None",
            "Reason": "Subject relevance failed. CLO/PLO/Bloom scores are not used for approval.",
            "Subject Reason": subject_reason
        }

    # --------------------------------------------------------
    # CLO
    # --------------------------------------------------------

    matched_clo, clo_score = best_outcome(
        question,
        clos
    )

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------

    matched_plo, plo_score = best_outcome(
        question,
        plos
    )

    # --------------------------------------------------------
    # BLOOM
    # --------------------------------------------------------

    bloom_alignment = bloom_score(
        detected_bloom,
        selected_bloom
    )

    # --------------------------------------------------------
    # DECISION
    # --------------------------------------------------------

    status = "Approved"
    attained = True

    reasons = []

    if clo_score < 60:
        status = "Rejected"
        attained = False
        reasons.append(
            "CLO alignment is below the required threshold."
        )

    if selected_bloom and bloom_alignment < 80:
        status = "Rejected"
        attained = False
        reasons.append(
            f"The question's Bloom level does not sufficiently match the selected {selected_bloom} level."
        )

    if plo_score < 45:
        if status == "Approved":
            status = "Needs Review"

        reasons.append(
            "PLO alignment is weak."
        )

    if quality < 60:
        if status == "Approved":
            status = "Needs Review"

        reasons.append(
            "Question wording needs improvement."
        )

    if not reasons:
        reasons.append(
            "Subject, CLO, PLO and Bloom requirements are sufficiently aligned."
        )

    return {
        "Status": status,
        "Alignment Attained": attained,
        "Subject Relevance": round(subject_score, 1),
        "CLO Alignment": round(clo_score, 1),
        "PLO Alignment": round(plo_score, 1),
        "Bloom Alignment": round(bloom_alignment, 1),
        "Quality": round(quality, 1),
        "Detected Bloom": detected_bloom or "Not detected",
        "Bloom Verb": bloom_verb or "",
        "Matched CLO": (
            matched_clo["code"]
            if matched_clo
            else "None"
        ),
        "Matched PLO": (
            matched_plo["code"]
            if matched_plo
            else "None"
        ),
        "Reason": " ".join(reasons),
        "Subject Reason": subject_reason
    }


# ============================================================
# DIRECT REVISION
# ============================================================

def remove_bloom_verbs(text):
    words = clean_text(text).split()

    all_verbs = set()

    for verbs in BLOOM_VERBS.values():
        all_verbs.update(verbs)

    result = []

    for word in words:
        normalized = normalize(word)

        if normalized in all_verbs:
            continue

        result.append(word)

    return " ".join(result)


def clo_topic(clo_text):
    text = clean_text(clo_text)

    # Remove common CLO action verbs
    text = remove_bloom_verbs(text)

    # Remove common OBE wording
    text = re.sub(
        r"\b(students?|learners?)\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\bwill be able to\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\bunderstand\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip(" .,:;-")

    return text


def extract_core_topic(clo_text):
    topic = clo_topic(clo_text)

    if not topic:
        return "the main concepts covered in this course"

    return topic


def make_revision(
    original_question,
    clo,
    selected_bloom,
    course_content
):
    if not clo:
        return original_question

    topic = extract_core_topic(
        clo["text"]
    )

    original = clean_text(
        original_question
    )

    # --------------------------------------------------------
    # Use direct, specific wording.
    # Do NOT mention CLO/PLO.
    # --------------------------------------------------------

    if selected_bloom == "Remember":
        return (
            f"Define {topic} and state its key characteristics."
        )

    if selected_bloom == "Understand":
        return (
            f"Explain {topic} and describe how its main components are related."
        )

    if selected_bloom == "Apply":
        return (
            f"Apply the principles of {topic} to solve a relevant problem."
        )

    if selected_bloom == "Analyze":
        return (
            f"Analyze {topic} by identifying its main components and explaining their relationships."
        )

    if selected_bloom == "Evaluate":
        return (
            f"Evaluate {topic} using appropriate criteria and justify your conclusion."
        )

    if selected_bloom == "Create":
        return (
            f"Design a solution based on the principles of {topic} and explain your design choices."
        )

    # Fallback
    return (
        f"Explain {topic} using an appropriate example."
    )


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = None

if "revised_results" not in st.session_state:
    st.session_state.revised_results = None


# ============================================================
# TITLE
# ============================================================

st.title("🎓 OBE Assessment Alignment Checker")

st.write(
    "Evaluate assessment questions for subject relevance, "
    "CLO alignment, PLO alignment and Bloom's Taxonomy."
)


# ============================================================
# COURSE INFORMATION
# ============================================================

st.subheader("1. Course Information")

course_name = st.text_input(
    "Course / Subject Name",
    placeholder="e.g., General Chemistry"
)

course_content = st.text_area(
    "Course Content / Syllabus",
    height=150,
    placeholder=(
        "Paste important course topics, syllabus content, "
        "or learning material here. This improves subject detection."
    )
)


# ============================================================
# CLO / PLO
# ============================================================

st.subheader("2. Learning Outcomes")

col1, col2 = st.columns(2)

with col1:
    clo_text = st.text_area(
        "Course Learning Outcomes (CLOs)",
        height=220,
        placeholder=(
            "CLO1: Explain the structure and properties of atoms.\n"
            "CLO2: Apply chemical principles to solve numerical problems."
        )
    )

with col2:
    plo_text = st.text_area(
        "Program Learning Outcomes (PLOs)",
        height=220,
        placeholder=(
            "PLO1: Apply knowledge of mathematics and science.\n"
            "PLO2: Analyze problems using appropriate methods."
        )
    )


# ============================================================
# BLOOM
# ============================================================

st.subheader("3. Assessment Level")

selected_bloom = st.selectbox(
    "Intended Bloom's Taxonomy Level",
    BLOOM_LEVELS,
    index=1
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("4. Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload the assessment file",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt"
    ],
    help=(
        "The assessment may contain MCQs, short questions, "
        "long questions, numerical questions, analytical questions, "
        "or mixed question types."
    )
)


# ============================================================
# EVALUATE BUTTON
# ============================================================

if st.button(
    "🔍 Evaluate Assessment",
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
        st.warning(
            "No PLOs were entered. PLO alignment will be limited."
        )

    if uploaded_file is None:
        st.error(
            "Please upload an assessment file."
        )
        st.stop()

    # Read file
    with st.spinner("Reading assessment..."):
        extracted_text, file_message = read_file(
            uploaded_file
        )

    if not extracted_text.strip():
        st.error(
            f"{file_message}\n\n"
            "No readable assessment text was found."
        )
        st.stop()

    # Parse outcomes
    clos = parse_outcomes(
        clo_text,
        "CLO"
    )

    plos = parse_outcomes(
        plo_text,
        "PLO"
    )

    if not clos:
        st.error(
            "No CLOs were detected. Please use formats such as CLO1, CLO2, etc."
        )
        st.stop()

    # Extract questions
    questions = extract_questions(
        extracted_text
    )

    if not questions:
        st.error(
            "No assessment questions could be detected."
        )

        with st.expander(
            "Show extracted text for troubleshooting"
        ):
            st.text(extracted_text[:12000])

        st.stop()

    # Detect subject
    detected_domain, confidence = detect_domain(
        course_name,
        course_content,
        questions
    )

    # User course name should take priority
    requested_domain = None

    normalized_course = normalize(
        course_name
    )

    for alias, domain in DOMAIN_ALIASES.items():
        if alias in normalized_course:
            requested_domain = domain
            break

    if requested_domain:
        detected_domain = requested_domain
        confidence = 0.95

    # Evaluate
    results = []

    for question in questions:

        evaluation = evaluate_question(
            question=question["text"],
            selected_domain=detected_domain,
            course_content=course_content,
            clos=clos,
            plos=plos,
            selected_bloom=selected_bloom
        )

        row = {
            "Question": question["text"],
            **evaluation
        }

        results.append(row)

    st.session_state.results = {
        "results": results,
        "questions": questions,
        "clos": clos,
        "plos": plos,
        "detected_domain": detected_domain,
        "confidence": confidence,
        "file_message": file_message,
        "extracted_text": extracted_text,
        "selected_bloom": selected_bloom,
        "course_name": course_name,
        "course_content": course_content
    }

    st.session_state.revised_results = None


# ============================================================
# RESULTS
# ============================================================

if st.session_state.results:

    data = st.session_state.results

    results = data["results"]
    questions = data["questions"]

    st.divider()

    st.header("📊 Results")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    approved = sum(
        1
        for r in results
        if r["Status"] == "Approved"
    )

    review = sum(
        1
        for r in results
        if r["Status"] == "Needs Review"
    )

    rejected = sum(
        1
        for r in results
        if r["Status"] == "Rejected"
    )

    total = len(results)

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            "Questions",
            total
        )

    with m2:
        st.metric(
            "Approved",
            approved
        )

    with m3:
        st.metric(
            "Needs Review",
            review
        )

    with m4:
        st.metric(
            "Rejected",
            rejected
        )

    # --------------------------------------------------------
    # Subject information
    # --------------------------------------------------------

    st.info(
        f"Detected Subject: **{data['detected_domain']}**  \n"
        f"Detection Confidence: **{data['confidence'] * 100:.1f}%**"
    )

    # --------------------------------------------------------
    # Main results table
    # --------------------------------------------------------

    display_rows = []

    for index, row in enumerate(results, start=1):

        display_rows.append({
            "Q#": index,
            "Question": row["Question"],
            "Status": row["Status"],
            "Subject": row["Subject Relevance"],
            "CLO": row["CLO Alignment"],
            "PLO": row["PLO Alignment"],
            "Bloom": row["Bloom Alignment"],
            "Detected Bloom": row["Detected Bloom"],
            "Matched CLO": row["Matched CLO"],
            "Matched PLO": row["Matched PLO"]
        })

    result_df = pd.DataFrame(
        display_rows
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # DETAILED EVALUATION
    # ========================================================

    st.subheader("Detailed Evaluation")

    for index, row in enumerate(results, start=1):

        status = row["Status"]

        if status == "Approved":
            icon = "✅"
        elif status == "Needs Review":
            icon = "⚠️"
        else:
            icon = "❌"

        with st.expander(
            f"{icon} Question {index}: {row['Question'][:100]}"
        ):

            st.write(
                f"**Question:** {row['Question']}"
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    "Subject",
                    f"{row['Subject Relevance']:.0f}%"
                )

            with c2:
                st.metric(
                    "CLO",
                    f"{row['CLO Alignment']:.0f}%"
                )

            with c3:
                st.metric(
                    "PLO",
                    f"{row['PLO Alignment']:.0f}%"
                )

            with c4:
                st.metric(
                    "Bloom",
                    f"{row['Bloom Alignment']:.0f}%"
                )

            st.write(
                f"**Detected Bloom:** {row['Detected Bloom']}"
            )

            if row["Bloom Verb"]:
                st.write(
                    f"**Bloom Verb:** {row['Bloom Verb']}"
                )

            st.write(
                f"**Matched CLO:** {row['Matched CLO']}"
            )

            st.write(
                f"**Matched PLO:** {row['Matched PLO']}"
            )

            st.write(
                f"**Subject Check:** {row['Subject Reason']}"
            )

            st.write(
                f"**Decision:** {row['Reason']}"
            )


    # ========================================================
    # REVISION
    # ========================================================

    st.divider()

    st.header("🔧 Revise Failed Questions")

    st.write(
        "Questions that fail alignment can be revised into direct, "
        "subject-specific assessment questions."
    )

    failed_indices = [
        i
        for i, row in enumerate(results)
        if row["Status"] != "Approved"
    ]

    if not failed_indices:

        st.success(
            "🎉 All questions currently meet the required alignment criteria."
        )

    else:

        selected_index = st.selectbox(
            "Select a question to revise",
            failed_indices,
            format_func=lambda i:
                f"Question {i + 1}: {results[i]['Question'][:90]}"
        )

        selected_row = results[selected_index]

        matched_clo = None

        for clo in data["clos"]:

            if clo["code"].upper() == str(
                selected_row["Matched CLO"]
            ).upper():

                matched_clo = clo
                break

        # If the question has no acceptable CLO match,
        # choose the strongest CLO directly.
        if matched_clo is None:

            matched_clo, _ = best_outcome(
                selected_row["Question"],
                data["clos"]
            )

        revised_question = make_revision(
            original_question=selected_row["Question"],
            clo=matched_clo,
            selected_bloom=data["selected_bloom"],
            course_content=data["course_content"]
        )

        st.text_area(
            "Revised Question",
            value=revised_question,
            height=130,
            key="revised_question_box"
        )

        if st.button(
            "🔍 Test Revised Question",
            type="primary"
        ):

            revised_text = st.session_state.get(
                "revised_question_box",
                revised_question
            )

            revised_evaluation = evaluate_question(
                question=revised_text,
                selected_domain=data["detected_domain"],
                course_content=data["course_content"],
                clos=data["clos"],
                plos=data["plos"],
                selected_bloom=data["selected_bloom"]
            )

            st.session_state.revised_results = {
                "question": revised_text,
                "evaluation": revised_evaluation
            }


    # ========================================================
    # REVISED RESULT
    # ========================================================

    if st.session_state.revised_results:

        revised = st.session_state.revised_results

        st.divider()

        st.subheader(
            "Revised Question Result"
        )

        st.write(
            f"**Revised Question:** {revised['question']}"
        )

        evaluation = revised["evaluation"]

        r1, r2, r3, r4 = st.columns(4)

        with r1:
            st.metric(
                "Subject",
                f"{evaluation['Subject Relevance']:.0f}%"
            )

        with r2:
            st.metric(
                "CLO",
                f"{evaluation['CLO Alignment']:.0f}%"
            )

        with r3:
            st.metric(
                "PLO",
                f"{evaluation['PLO Alignment']:.0f}%"
            )

        with r4:
            st.metric(
                "Bloom",
                f"{evaluation['Bloom Alignment']:.0f}%"
            )

        if evaluation["Alignment Attained"]:

            st.success(
                "✅ ALIGNMENT ATTAINED"
            )

            st.write(
                "The revised question satisfies the required "
                "subject relevance, CLO alignment and Bloom criteria."
            )

        else:

            st.warning(
                "⚠️ Alignment is not yet attained."
            )

            st.write(
                evaluation["Reason"]
            )

        st.write(
            f"**Detected Bloom:** {evaluation['Detected Bloom']}"
        )

        st.write(
            f"**Matched CLO:** {evaluation['Matched CLO']}"
        )

        st.write(
            f"**Matched PLO:** {evaluation['Matched PLO']}"
        )


    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    export_rows = []

    for index, row in enumerate(results, start=1):

        export_rows.append({
            "Question Number": index,
            "Question": row["Question"],
            "Status": row["Status"],
            "Alignment Attained": row["Alignment Attained"],
            "Subject Relevance": row["Subject Relevance"],
            "CLO Alignment": row["CLO Alignment"],
            "PLO Alignment": row["PLO Alignment"],
            "Bloom Alignment": row["Bloom Alignment"],
            "Quality": row["Quality"],
            "Detected Bloom": row["Detected Bloom"],
            "Bloom Verb": row["Bloom Verb"],
            "Matched CLO": row["Matched CLO"],
            "Matched PLO": row["Matched PLO"],
            "Reason": row["Reason"]
        })

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Results CSV",
        data=csv_data,
        file_name="obe_alignment_results.csv",
        mime="text/csv",
        use_container_width=True
    )


    # ========================================================
    # OCR / FILE INFO
    # ========================================================

    with st.expander(
        "📄 File Reading Information"
    ):

        st.write(
            data["file_message"]
        )

        st.write(
            f"Detected {len(questions)} assessment question(s)."
        )

        if pytesseract is None:
            st.warning(
                "Tesseract OCR is not installed. "
                "Scanned PDFs may not be readable."
            )

        elif not tesseract_available():
            st.warning(
                "Tesseract OCR is unavailable in the current environment."
            )

        else:
            st.success(
                "Tesseract OCR is available."
            )

        st.write(
            "The evaluator supports MCQs, short questions, "
            "long questions, numerical questions, analytical questions "
            "and mixed assessment formats."
        )
