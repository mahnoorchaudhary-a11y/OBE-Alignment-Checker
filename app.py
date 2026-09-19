import io
import re
from collections import Counter

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide",
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
    "Create",
]

BLOOM_RANK = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6,
}

BLOOM_VERBS = {
    "Remember": {
        "define", "identify", "name", "list", "state",
        "recall", "recognize", "recognise", "label",
        "select", "match", "mention"
    },
    "Understand": {
        "explain", "summarize", "summarise", "interpret",
        "classify", "compare", "contrast", "discuss",
        "illustrate", "paraphrase", "describe",
        "differentiate", "distinguish"
    },
    "Apply": {
        "calculate", "compute", "solve", "use", "apply",
        "demonstrate", "implement", "execute", "determine",
        "find", "perform", "derive"
    },
    "Analyze": {
        "analyze", "analyse", "examine", "organize",
        "organise", "investigate", "categorize",
        "categorise", "infer", "differentiate",
        "distinguish", "compare", "contrast"
    },
    "Evaluate": {
        "evaluate", "judge", "justify", "critique",
        "assess", "defend", "appraise", "argue",
        "validate", "recommend"
    },
    "Create": {
        "design", "create", "develop", "formulate",
        "construct", "produce", "propose", "plan",
        "generate", "devise"
    },
}


# ============================================================
# SUBJECT LEXICONS
# ============================================================

DOMAIN_LEXICONS = {
    "Chemistry": {
        "atom", "molecule", "element", "compound", "reaction",
        "equilibrium", "acid", "base", "ph", "molarity",
        "mole", "stoichiometry", "bond", "ionic", "covalent",
        "organic", "inorganic", "oxidation", "reduction",
        "redox", "catalyst", "kinetics", "thermodynamics",
        "enthalpy", "entropy", "solution", "concentration",
        "periodic", "electron", "proton", "neutron", "isotope",
        "spectroscopy", "titration", "precipitate",
        "solubility", "buffer", "electrochemistry"
    },

    "Physics": {
        "force", "motion", "velocity", "acceleration", "mass",
        "energy", "momentum", "gravity", "friction", "work",
        "power", "wave", "frequency", "wavelength", "electric",
        "magnetic", "voltage", "current", "resistance",
        "circuit", "charge", "field", "optics", "lens",
        "mirror", "pressure", "density", "kinematic",
        "newton", "quantum", "relativity"
    },

    "Mathematics": {
        "equation", "algebra", "matrix", "vector", "calculus",
        "derivative", "integral", "function", "limit",
        "probability", "statistics", "mean", "median",
        "variance", "geometry", "trigonometry", "logarithm",
        "polynomial", "theorem", "proof", "set", "sequence",
        "series", "differential", "linear", "quadratic", "graph"
    },

    "Computer Science": {
        "algorithm", "program", "programming", "code", "software",
        "hardware", "database", "sql", "network", "computer",
        "operating", "system", "memory", "processor", "cpu",
        "data", "structure", "array", "stack", "queue", "tree",
        "graph", "recursion", "class", "object", "inheritance",
        "python", "java", "javascript", "machine", "learning",
        "artificial", "intelligence", "compiler", "security"
    },

    "Biology": {
        "cell", "organism", "gene", "dna", "rna", "protein",
        "enzyme", "mitosis", "meiosis", "evolution", "species",
        "ecosystem", "photosynthesis", "respiration", "membrane",
        "chromosome", "genetics", "bacteria", "virus", "tissue",
        "organ", "metabolism", "homeostasis", "population",
        "ecology", "mutation", "transcription", "translation"
    },

    "English / Language": {
        "grammar", "sentence", "paragraph", "essay", "writing",
        "reading", "author", "tone", "purpose", "main",
        "idea", "paraphrase", "thesis", "argument", "rhetoric",
        "language", "communication", "vocabulary", "syntax",
        "morphology", "phonology", "semantics", "pragmatics",
        "listening", "speaking", "audience", "organization",
        "organisation"
    },

    "Literature": {
        "novel", "poem", "poetry", "character", "plot", "theme",
        "symbolism", "metaphor", "narrator", "narrative",
        "author", "literary", "fiction", "drama", "tragedy",
        "irony", "imagery", "setting", "protagonist", "genre",
        "sonnet", "stanza", "verse", "interpretation"
    },

    "Business / Management": {
        "management", "manager", "organization", "organisation",
        "leadership", "strategy", "marketing", "customer",
        "market", "business", "planning", "decision",
        "entrepreneur", "entrepreneurship", "human",
        "resource", "operations", "competitive", "stakeholder",
        "performance", "motivation"
    },

    "Accounting / Finance": {
        "accounting", "account", "ledger", "journal", "balance",
        "asset", "liability", "equity", "revenue", "expense",
        "profit", "loss", "financial", "statement", "audit",
        "debit", "credit", "cash", "budget", "investment",
        "capital", "ratio", "income", "tax", "cost"
    },

    "Economics": {
        "economics", "economic", "demand", "supply", "market",
        "price", "inflation", "unemployment", "gdp", "fiscal",
        "monetary", "policy", "elasticity", "utility", "consumer",
        "producer", "equilibrium", "scarcity", "opportunity",
        "trade", "exchange", "interest", "macroeconomic",
        "microeconomic"
    },

    "Engineering": {
        "engineering", "design", "machine", "mechanical",
        "electrical", "civil", "structure", "material",
        "circuit", "system", "load", "stress", "strain",
        "fluid", "thermodynamic", "control", "manufacturing",
        "prototype", "safety", "process", "technical"
    },

    "Psychology": {
        "psychology", "behavior", "behaviour", "cognition",
        "memory", "learning", "emotion", "personality",
        "development", "motivation", "perception", "therapy",
        "mental", "social", "cognitive", "conditioning",
        "reinforcement", "intelligence"
    },

    "Sociology": {
        "society", "social", "culture", "class", "status",
        "institution", "family", "community", "inequality",
        "stratification", "norm", "value", "deviance",
        "socialization", "socialisation", "urbanization",
        "globalization", "group", "identity"
    },

    "Education": {
        "education", "teaching", "learning", "student",
        "curriculum", "pedagogy", "assessment", "classroom",
        "instruction", "teacher", "lesson", "outcome",
        "rubric", "evaluation", "educational", "methodology",
        "school", "instructional"
    },

    "History": {
        "history", "historical", "war", "empire", "king",
        "queen", "revolution", "colonial", "independence",
        "treaty", "civilization", "civilisation", "dynasty",
        "political", "ancient", "medieval", "modern",
        "movement", "colonialism"
    },

    "Law": {
        "law", "legal", "court", "contract", "tort", "crime",
        "criminal", "civil", "statute", "constitution",
        "judge", "judgment", "jurisdiction", "liability",
        "negligence", "evidence", "case", "plaintiff",
        "defendant", "rights"
    },

    "Pharmacy": {
        "drug", "medicine", "pharmacy", "pharmacology",
        "dose", "dosage", "tablet", "capsule", "prescription",
        "pharmacokinetics", "pharmacodynamics", "adverse",
        "patient", "therapeutic", "antibiotic", "formulation",
        "medication", "receptor"
    },

    "Medical / Health Sciences": {
        "patient", "disease", "diagnosis", "symptom", "treatment",
        "clinical", "medical", "health", "anatomy", "physiology",
        "pathology", "infection", "hospital", "therapy",
        "syndrome", "blood", "heart", "lung", "organ",
        "nursing"
    },

    "Environmental Science": {
        "environment", "ecosystem", "pollution", "climate",
        "carbon", "waste", "water", "air", "soil", "biodiversity",
        "conservation", "sustainability", "greenhouse",
        "global", "warming", "renewable", "resource",
        "environmental"
    },
}


RELATED_DOMAINS = {
    "Chemistry": {
        "Pharmacy",
        "Environmental Science",
        "Engineering",
        "Biology"
    },
    "Physics": {
        "Engineering",
        "Mathematics",
        "Computer Science"
    },
    "Mathematics": {
        "Physics",
        "Engineering",
        "Economics",
        "Computer Science"
    },
    "Biology": {
        "Chemistry",
        "Pharmacy",
        "Medical / Health Sciences",
        "Environmental Science"
    },
    "Computer Science": {
        "Mathematics",
        "Engineering"
    },
    "Business / Management": {
        "Economics",
        "Accounting / Finance"
    },
    "Accounting / Finance": {
        "Business / Management",
        "Economics"
    },
    "Economics": {
        "Business / Management",
        "Accounting / Finance",
        "Mathematics"
    },
    "Pharmacy": {
        "Chemistry",
        "Biology",
        "Medical / Health Sciences"
    },
    "Medical / Health Sciences": {
        "Biology",
        "Pharmacy",
        "Chemistry"
    },
    "Environmental Science": {
        "Biology",
        "Chemistry",
        "Engineering"
    },
}


COURSE_ALIASES = {
    "chemistry": "Chemistry",
    "general chemistry": "Chemistry",
    "organic chemistry": "Chemistry",
    "inorganic chemistry": "Chemistry",
    "physical chemistry": "Chemistry",
    "analytical chemistry": "Chemistry",

    "physics": "Physics",
    "general physics": "Physics",

    "mathematics": "Mathematics",
    "math": "Mathematics",
    "calculus": "Mathematics",
    "statistics": "Mathematics",

    "computer science": "Computer Science",
    "programming": "Computer Science",
    "programming fundamentals": "Computer Science",
    "data structures": "Computer Science",
    "database": "Computer Science",
    "database systems": "Computer Science",
    "artificial intelligence": "Computer Science",

    "english": "English / Language",
    "english i": "English / Language",
    "english ii": "English / Language",
    "academic writing": "English / Language",
    "communication skills": "English / Language",

    "literature": "Literature",
    "english literature": "Literature",

    "business": "Business / Management",
    "management": "Business / Management",
    "principles of management": "Business / Management",
    "marketing": "Business / Management",

    "accounting": "Accounting / Finance",
    "financial accounting": "Accounting / Finance",
    "finance": "Accounting / Finance",

    "economics": "Economics",
    "microeconomics": "Economics",
    "macroeconomics": "Economics",

    "engineering": "Engineering",
    "mechanical engineering": "Engineering",
    "electrical engineering": "Engineering",
    "civil engineering": "Engineering",

    "biology": "Biology",
    "general biology": "Biology",

    "psychology": "Psychology",
    "sociology": "Sociology",
    "education": "Education",
    "history": "History",
    "law": "Law",
    "pharmacy": "Pharmacy",
    "medicine": "Medical / Health Sciences",
    "medical": "Medical / Health Sciences",
    "health sciences": "Medical / Health Sciences",
    "environmental science": "Environmental Science",
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in",
    "on", "for", "with", "from", "by", "is", "are", "was",
    "were", "be", "been", "being", "as", "at", "that", "this",
    "these", "those", "it", "its", "their", "they", "them",
    "he", "she", "his", "her", "you", "your", "we", "our",
    "which", "what", "when", "where", "why", "how", "who",
    "does", "do", "did", "can", "could", "would", "should",
    "will", "may", "might", "must", "than", "then", "also",
    "into", "through", "using", "given", "following",
    "according", "each", "any", "all", "some", "such",
    "question", "questions", "answer", "answers"
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_inline(text):
    if text is None:
        return ""

    text = str(text)

    replacements = {
        "\u00a0": " ",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def normalize_document(text):
    if not text:
        return ""

    lines = []

    for line in str(text).splitlines():
        line = normalize_inline(line)

        if line:
            lines.append(line)

    return "\n".join(lines)


def tokenize(text):
    words = re.findall(
        r"[A-Za-z][A-Za-z0-9'-]*",
        str(text).lower()
    )

    result = []

    for word in words:
        word = re.sub(
            r"[^a-z0-9]+",
            "",
            word.lower()
        )

        if len(word) <= 2:
            continue

        if word in STOP_WORDS:
            continue

        result.append(word)

    return result


def simple_stem(word):
    word = word.lower()

    suffixes = [
        "ization",
        "isation",
        "ational",
        "fulness",
        "ousness",
        "iveness",
        "ment",
        "ness",
        "tion",
        "sion",
        "ing",
        "ed",
        "ies",
        "es",
        "s",
    ]

    for suffix in suffixes:
        if (
            word.endswith(suffix)
            and len(word) > len(suffix) + 3
        ):
            return word[:-len(suffix)]

    return word


def stem_set(text):
    result = set()

    for word in tokenize(text):
        stem = simple_stem(word)

        if len(stem) > 2:
            result.add(stem)

    return result


def overlap_score(text_a, text_b):
    a = stem_set(text_a)
    b = stem_set(text_b)

    if not a or not b:
        return 0.0

    common = a & b

    precision = len(common) / len(a)
    recall = len(common) / len(b)

    if precision + recall == 0:
        return 0.0

    f1 = (
        2 * precision * recall
        / (precision + recall)
    )

    return round(f1 * 100, 1)


# ============================================================
# METADATA DETECTION
# ============================================================

def looks_like_date_or_time(text):
    value = normalize_inline(text).lower()

    patterns = [
        r"^\d{1,2}/\d{1,2}/\d{2,4}$",
        r"^\d{1,2}-\d{1,2}-\d{2,4}$",
        r"^\d{1,2}:\d{2}\s*(am|pm)?$",
        r"^\d{1,2}/\d{1,2}$",
        r"^\d{1,2}:\d{2}\s*(am|pm)?\s+.*$",
        r"^\d{1,2}\s*(am|pm)$",
    ]

    return any(
        re.fullmatch(pattern, value)
        for pattern in patterns
    )


def looks_like_page_marker(text):
    value = normalize_inline(text).lower()

    patterns = [
        r"^\d+\s*/\s*\d+$",
        r"^page\s+\d+$",
        r"^page\s+\d+\s+of\s+\d+$",
        r"^\d+\s+of\s+\d+$",
        r"^p\.\s*\d+$",
    ]

    return any(
        re.fullmatch(pattern, value)
        for pattern in patterns
    )


def looks_like_metadata(text):
    value = normalize_inline(text)

    if not value:
        return True

    lower = value.lower()

    if looks_like_date_or_time(value):
        return True

    if looks_like_page_marker(value):
        return True

    patterns = [
        r"questionwell",
        r"question\s*set",
        r"generated\s+by",
        r"created\s+with",
        r"created\s+on",
        r"exported\s+on",
        r"downloaded\s+on",
        r"general\s+chemistry\s*\+",
        r"copyright",
        r"www\.",
        r"https?://",
        r"page\s+\d+",
        r"student\s+name",
        r"roll\s+number",
        r"registration\s+number",
        r"date\s*:",
        r"time\s*:",
        r"instructor\s*:",
        r"teacher\s*:",
        r"course\s*:",
        r"section\s*:",
    ]

    for pattern in patterns:
        if re.search(pattern, lower):
            return True

    if re.fullmatch(r"[\d\s./_-]+", value):
        return True

    return False


def looks_like_heading(text):
    value = normalize_inline(text)

    if not value:
        return True

    lower = value.lower()

    headings = {
        "general chemistry",
        "question set",
        "multiple choice questions",
        "multiple choice",
        "short questions",
        "short answer questions",
        "long questions",
        "essay questions",
        "true false",
        "true/false",
        "section a",
        "section b",
        "section c",
        "instructions",
        "learning outcomes",
        "course learning outcomes",
        "assessment",
        "quiz",
        "midterm",
        "final examination",
        "examination",
        "answer key",
        "references",
    }

    if lower in headings:
        return True

    if (
        lower.startswith("section ")
        and len(value.split()) <= 8
    ):
        return True

    if (
        lower.startswith("chapter ")
        and len(value.split()) <= 8
    ):
        return True

    if (
        lower.startswith("unit ")
        and len(value.split()) <= 8
    ):
        return True

    if (
        value.endswith(":")
        and len(value.split()) <= 12
    ):
        return True

    return False


# ============================================================
# QUESTION EXTRACTION
# ============================================================

QUESTION_NUMBER_PATTERN = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?"
    r"(\d{1,3})\s*[\.\):\-]\s*(.+)$",
    re.IGNORECASE
)

Q_PATTERN = re.compile(
    r"^\s*Q(?:uestion)?\s*(\d{1,3})"
    r"\s*[:\.\)\-]\s*(.+)$",
    re.IGNORECASE
)

OPTION_PATTERN = re.compile(
    r"^\s*[\(\[]?([A-Ha-h])[\)\].:\-]\s+(.+)$"
)


def remove_question_prefix(text):
    value = normalize_inline(text)

    patterns = [
        r"^\s*Q(?:uestion)?\s*\d{1,3}\s*[:\.\)\-]\s*",
        r"^\s*\(?\d{1,3}\)?\s*[\.\):\-]\s*",
    ]

    for pattern in patterns:
        value = re.sub(
            pattern,
            "",
            value,
            flags=re.IGNORECASE
        )

    return value.strip()


def has_bloom_verb(text):
    lower = text.lower()

    for verbs in BLOOM_VERBS.values():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                lower
            ):
                return True

    return False


def has_question_structure(text):
    lower = text.lower()

    if "?" in text:
        return True

    patterns = [
        r"\bwhat\b",
        r"\bwhy\b",
        r"\bhow\b",
        r"\bwhich\b",
        r"\bwho\b",
        r"\bwhere\b",
        r"\bwhen\b",
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bsolve\b",
        r"\bdetermine\b",
        r"\bexplain\b",
        r"\bdefine\b",
        r"\bidentify\b",
        r"\bdescribe\b",
        r"\bcompare\b",
        r"\banalyze\b",
        r"\banalyse\b",
        r"\bevaluate\b",
        r"\bjustify\b",
        r"\bdesign\b",
        r"\bderive\b",
        r"\bdiscuss\b",
        r"\bconstruct\b",
    ]

    return any(
        re.search(pattern, lower)
        for pattern in patterns
    )


def is_genuine_question(text):
    value = remove_question_prefix(text)

    if not value:
        return False

    if looks_like_metadata(value):
        return False

    if looks_like_heading(value):
        return False

    if len(value.split()) < 5:
        return False

    return (
        has_question_structure(value)
        or has_bloom_verb(value)
    )


def remove_repeated_lines(lines):
    counts = Counter()

    normalized_lines = []

    for line in lines:
        clean = normalize_inline(line)

        if not clean:
            continue

        normalized = re.sub(
            r"\d+",
            "#",
            clean.lower()
        )

        counts[normalized] += 1
        normalized_lines.append(
            (clean, normalized)
        )

    output = []

    for clean, normalized in normalized_lines:

        if counts[normalized] >= 3:
            continue

        output.append(clean)

    return output


def extract_questions(text):
    document = normalize_document(text)

    if not document:
        return []

    lines = document.splitlines()

    lines = remove_repeated_lines(lines)

    questions = []

    current = None

    def save_current():
        nonlocal current

        if current is None:
            return

        question_text = normalize_inline(
            current["text"]
        )

        if not is_genuine_question(
            question_text
        ):
            current = None
            return

        question_text = remove_question_prefix(
            question_text
        )

        options = current.get(
            "options",
            []
        )

        if len(options) >= 2:
            question_text += "\n" + "\n".join(
                options
            )

        if len(question_text.split()) >= 5:
            questions.append(
                {
                    "number": current.get(
                        "number",
                        ""
                    ),
                    "text": question_text,
                    "options": options,
                }
            )

        current = None

    for line in lines:

        line = normalize_inline(line)

        if not line:
            continue

        # ----------------------------------------------------
        # Metadata and headings are ignored.
        # ----------------------------------------------------

        if looks_like_metadata(line):
            continue

        if looks_like_heading(line):
            continue

        # ----------------------------------------------------
        # Numbered question.
        # ----------------------------------------------------

        match = QUESTION_NUMBER_PATTERN.match(
            line
        )

        if match:

            candidate = match.group(2).strip()

            if is_genuine_question(
                candidate
            ):

                save_current()

                current = {
                    "number": match.group(1),
                    "text": candidate,
                    "options": [],
                }

                continue

        # ----------------------------------------------------
        # Q1, Q2, etc.
        # ----------------------------------------------------

        qmatch = Q_PATTERN.match(
            line
        )

        if qmatch:

            candidate = qmatch.group(2).strip()

            if is_genuine_question(
                candidate
            ):

                save_current()

                current = {
                    "number": qmatch.group(1),
                    "text": candidate,
                    "options": [],
                }

                continue

        # ----------------------------------------------------
        # Options.
        # ----------------------------------------------------

        option_match = OPTION_PATTERN.match(
            line
        )

        if option_match and current:

            option = (
                option_match.group(1).upper()
                + ". "
                + option_match.group(2).strip()
            )

            current["options"].append(
                option
            )

            continue

        # ----------------------------------------------------
        # Standalone question.
        # ----------------------------------------------------

        if (
            line.endswith("?")
            and is_genuine_question(line)
        ):

            save_current()

            current = {
                "number": "",
                "text": line,
                "options": [],
            }

            continue

        # ----------------------------------------------------
        # Continuation.
        # ----------------------------------------------------

        if current:

            if not looks_like_metadata(line):

                current["text"] += " " + line

                if line.endswith("?"):
                    save_current()

    save_current()

    # --------------------------------------------------------
    # Remove duplicates.
    # --------------------------------------------------------

    unique = []
    seen = set()

    for item in questions:

        key = re.sub(
            r"\s+",
            " ",
            item["text"].lower()
        ).strip()

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# ============================================================
# PDF OCR
# ============================================================

def pdf_has_embedded_text(file_bytes):
    try:
        import fitz

        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        total_pages = len(document)

        pages_with_text = 0

        for page in document:

            text = page.get_text(
                "text"
            ).strip()

            if len(text) >= 30:
                pages_with_text += 1

        document.close()

        if total_pages == 0:
            return False

        return (
            pages_with_text / total_pages
        ) >= 0.30

    except Exception:
        return False


def ocr_pdf(file_bytes):
    try:
        import fitz
    except ImportError:
        st.error(
            "PyMuPDF is not installed."
        )
        return ""

    try:
        import pytesseract
    except ImportError:
        st.error(
            "pytesseract is not installed."
        )
        return ""

    try:
        from PIL import Image
    except ImportError:
        st.error(
            "Pillow is not installed."
        )
        return ""

    try:
        # Check whether Tesseract itself is available.
        try:
            version = pytesseract.get_tesseract_version()
        except Exception:
            st.error(
                "Tesseract OCR engine is not available. "
                "Add tesseract-ocr and tesseract-ocr-eng "
                "to packages.txt and redeploy the app."
            )
            return ""

        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        total_pages = len(document)

        if total_pages == 0:
            document.close()
            return ""

        progress = st.progress(
            0,
            text="Starting OCR..."
        )

        ocr_pages = []

        for page_number, page in enumerate(
            document
        ):

            progress_value = int(
                (
                    page_number
                    / total_pages
                ) * 100
            )

            progress.progress(
                progress_value,
                text=(
                    f"OCR: processing page "
                    f"{page_number + 1} of "
                    f"{total_pages}"
                ),
            )

            # 300 DPI equivalent rendering.
            zoom = 2.5

            matrix = fitz.Matrix(
                zoom,
                zoom
            )

            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False
            )

            image_bytes = pixmap.tobytes(
                "png"
            )

            image = Image.open(
                io.BytesIO(image_bytes)
            )

            # OCR with normal English model.
            page_text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6"
            )

            if page_text.strip():
                ocr_pages.append(
                    page_text
                )

        document.close()

        progress.progress(
            100,
            text="OCR completed."
        )

        return "\n".join(
            ocr_pages
        )

    except Exception as error:
        st.error(
            "OCR failed: " + str(error)
        )
        return ""


def read_pdf(file_bytes):
    # ========================================================
    # 1. Try pypdf
    # ========================================================

    text_parts = []

    try:
        from pypdf import PdfReader

        reader = PdfReader(
            io.BytesIO(file_bytes)
        )

        for page in reader.pages:

            try:
                text = (
                    page.extract_text()
                    or ""
                )

                if text.strip():
                    text_parts.append(
                        text
                    )

            except Exception:
                continue

        extracted = "\n".join(
            text_parts
        ).strip()

        if len(extracted) >= 100:
            return extracted, "Embedded PDF text"

    except Exception:
        pass


    # ========================================================
    # 2. Try PyMuPDF
    # ========================================================

    text_parts = []

    try:
        import fitz

        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        for page in document:

            try:
                text = (
                    page.get_text(
                        "text"
                    )
                    or ""
                )

                if text.strip():
                    text_parts.append(
                        text
                    )

            except Exception:
                continue

        document.close()

        extracted = "\n".join(
            text_parts
        ).strip()

        if len(extracted) >= 100:
            return extracted, "PyMuPDF text"

    except Exception:
        pass


    # ========================================================
    # 3. OCR
    # ========================================================

    st.info(
        "This PDF appears to be scanned or contains insufficient "
        "embedded text. OCR is being used automatically."
    )

    ocr_text = ocr_pdf(
        file_bytes
    )

    if ocr_text.strip():
        return ocr_text, "OCR"

    return "", "Failed"


# ============================================================
# DOCX / EXCEL / CSV
# ============================================================

def read_docx(file_bytes):
    try:
        from docx import Document

        document = Document(
            io.BytesIO(file_bytes)
        )

        parts = []

        for paragraph in document.paragraphs:

            text = normalize_inline(
                paragraph.text
            )

            if text:
                parts.append(text)

        for table in document.tables:

            for row in table.rows:

                cells = []

                for cell in row.cells:

                    value = normalize_inline(
                        cell.text
                    )

                    if value:
                        cells.append(
                            value
                        )

                if cells:
                    parts.append(
                        " | ".join(cells)
                    )

        return "\n".join(parts)

    except Exception as error:
        st.error(
            "DOCX could not be read: "
            + str(error)
        )

        return ""


def read_excel(file_bytes):
    try:
        workbook = pd.ExcelFile(
            io.BytesIO(file_bytes)
        )

        parts = []

        for sheet in workbook.sheet_names:

            parts.append(
                f"Sheet: {sheet}"
            )

            dataframe = pd.read_excel(
                io.BytesIO(file_bytes),
                sheet_name=sheet,
                header=None
            )

            for row in dataframe.fillna("").values:

                values = []

                for value in row:

                    value = normalize_inline(
                        value
                    )

                    if value:
                        values.append(
                            value
                        )

                if values:
                    parts.append(
                        " ".join(values)
                    )

        return "\n".join(parts)

    except Exception as error:

        st.error(
            "Excel file could not be read: "
            + str(error)
        )

        return ""


def read_uploaded_file(uploaded_file):
    filename = uploaded_file.name.lower()

    file_bytes = uploaded_file.getvalue()

    if filename.endswith(".pdf"):
        return read_pdf(
            file_bytes
        )

    if filename.endswith(".docx"):
        return (
            read_docx(file_bytes),
            "DOCX"
        )

    if filename.endswith(
        (".xlsx", ".xls")
    ):
        return (
            read_excel(file_bytes),
            "Excel"
        )

    if filename.endswith(".csv"):

        try:

            dataframe = pd.read_csv(
                io.BytesIO(file_bytes),
                header=None
            )

            rows = []

            for row in dataframe.fillna("").values:

                values = []

                for value in row:

                    value = normalize_inline(
                        value
                    )

                    if value:
                        values.append(
                            value
                        )

                if values:
                    rows.append(
                        " ".join(values)
                    )

            return (
                "\n".join(rows),
                "CSV"
            )

        except Exception:
            return "", "Failed"

    try:
        return (
            file_bytes.decode(
                "utf-8",
                errors="ignore"
            ),
            "Text"
        )

    except Exception:
        return "", "Failed"


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, prefix):
    outcomes = []

    if not text:
        return outcomes

    pattern = re.compile(
        rf"^\s*{prefix}\s*[-_ ]?"
        rf"(\d+)\s*[:\-\)]\s*(.+)$",
        re.IGNORECASE
    )

    for line in text.splitlines():

        match = pattern.match(
            line.strip()
        )

        if match:

            description = normalize_inline(
                match.group(2)
            )

            if description:

                outcomes.append(
                    {
                        "id": (
                            f"{prefix.upper()}"
                            f"{match.group(1)}"
                        ),
                        "text": description
                    }
                )

    return outcomes


# ============================================================
# SUBJECT DETECTION
# ============================================================

def determine_course_domain(
    course_name,
    clos_text,
    plos_text,
    assessment_text
):
    context = " ".join(
        [
            course_name or "",
            clos_text or "",
            plos_text or ""
        ]
    ).lower()

    # Explicit course name gets priority.
    for alias, domain in sorted(
        COURSE_ALIASES.items(),
        key=lambda x: len(x[0]),
        reverse=True
    ):

        if alias in context:
            return domain, 100

    scores = {}

    for domain, lexicon in DOMAIN_LEXICONS.items():

        hits = 0

        for term in lexicon:

            if re.search(
                r"\b"
                + re.escape(term)
                + r"\b",
                context
            ):
                hits += 1

        scores[domain] = hits

    if scores:

        best_domain = max(
            scores,
            key=scores.get
        )

        best_score = scores[
            best_domain
        ]

        if best_score >= 3:

            return (
                best_domain,
                min(
                    95,
                    50 + best_score * 10
                )
            )

    # Assessment fallback.
    scores = {}

    for domain, lexicon in DOMAIN_LEXICONS.items():

        hits = 0

        for term in lexicon:

            if re.search(
                r"\b"
                + re.escape(term)
                + r"\b",
                assessment_text.lower()
            ):
                hits += 1

        scores[domain] = hits

    if scores:

        best_domain = max(
            scores,
            key=scores.get
        )

        best_score = scores[
            best_domain
        ]

        if best_score >= 4:

            return (
                best_domain,
                min(
                    80,
                    40 + best_score * 8
                )
            )

    return "Unknown", 0


def domain_hits(text, domain):
    hits = []

    if domain not in DOMAIN_LEXICONS:
        return hits

    lower = text.lower()

    for term in DOMAIN_LEXICONS[domain]:

        if re.search(
            r"\b"
            + re.escape(term)
            + r"\b",
            lower
        ):
            hits.append(term)

    return sorted(
        set(hits)
    )


def question_subject_check(
    question,
    expected_domain
):
    if expected_domain == "Unknown":

        return {
            "status": "REVIEW",
            "score": 40,
            "detected_domain": "Unknown",
            "evidence": [],
            "reason": (
                "The selected course does not provide "
                "enough information to establish the subject."
            )
        }

    scores = {}

    for domain in DOMAIN_LEXICONS:

        scores[domain] = len(
            domain_hits(
                question,
                domain
            )
        )

    expected_score = scores.get(
        expected_domain,
        0
    )

    sorted_domains = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    strongest_domain = (
        sorted_domains[0][0]
        if sorted_domains
        else "Unknown"
    )

    strongest_score = (
        sorted_domains[0][1]
        if sorted_domains
        else 0
    )

    related = RELATED_DOMAINS.get(
        expected_domain,
        set()
    )

    related_scores = [
        scores.get(
            domain,
            0
        )
        for domain in related
    ]

    related_score = max(
        related_scores
        or [0]
    )

    evidence = domain_hits(
        question,
        expected_domain
    )

    # Strong contradiction.
    if (
        strongest_domain != expected_domain
        and strongest_domain not in related
        and strongest_score >= 3
        and strongest_score >= expected_score + 2
    ):

        return {
            "status": "FAIL",
            "score": 0,
            "detected_domain": strongest_domain,
            "evidence": domain_hits(
                question,
                strongest_domain
            ),
            "reason": (
                f"The question contains stronger evidence "
                f"for {strongest_domain} than for "
                f"{expected_domain}."
            )
        }

    if expected_score >= 3:

        return {
            "status": "PASS",
            "score": 100,
            "detected_domain": expected_domain,
            "evidence": evidence,
            "reason": (
                f"Strong {expected_domain} content evidence "
                f"was found."
            )
        }

    if expected_score >= 1:

        return {
            "status": "PASS",
            "score": 80,
            "detected_domain": expected_domain,
            "evidence": evidence,
            "reason": (
                f"The question contains identifiable "
                f"{expected_domain} content."
            )
        }

    if related_score >= 2:

        related_domain = max(
            related,
            key=lambda d: scores.get(
                d,
                0
            )
        )

        return {
            "status": "REVIEW",
            "score": 60,
            "detected_domain": related_domain,
            "evidence": domain_hits(
                question,
                related_domain
            ),
            "reason": (
                f"The question appears related to "
                f"{related_domain}, but the evidence "
                f"is insufficient to automatically confirm "
                f"{expected_domain}."
            )
        }

    return {
        "status": "REVIEW",
        "score": 30,
        "detected_domain": (
            strongest_domain
            if strongest_score
            else "Unknown"
        ),
        "evidence": (
            domain_hits(
                question,
                strongest_domain
            )
            if strongest_score
            else []
        ),
        "reason": (
            f"Insufficient subject-specific evidence "
            f"to automatically confirm that this question "
            f"belongs to {expected_domain}."
        )
    }


# ============================================================
# BLOOM ANALYSIS
# ============================================================

def detect_bloom(question):
    lower = question.lower()

    matches = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b"
                + re.escape(verb)
                + r"\b",
                lower
            ):

                matches.append(
                    {
                        "level": level,
                        "verb": verb
                    }
                )

    if re.search(
        r"\b"
        r"(calculate|compute|solve|determine|derive)"
        r"\b",
        lower
    ):

        matches.append(
            {
                "level": "Apply",
                "verb": "problem solving"
            }
        )

    if re.search(
        r"\b"
        r"(justify|defend|critique|evaluate|assess)"
        r"\b",
        lower
    ):

        matches.append(
            {
                "level": "Evaluate",
                "verb": "judgment"
            }
        )

    if re.search(
        r"\b"
        r"(design|develop|create|formulate|propose)"
        r"\b",
        lower
    ):

        matches.append(
            {
                "level": "Create",
                "verb": "creation/design"
            }
        )

    if not matches:

        return {
            "level": "Unknown",
            "confidence": 0,
            "evidence": []
        }

    # Highest cognitive operation.
    highest_rank = max(
        BLOOM_RANK[
            item["level"]
        ]
        for item in matches
    )

    strongest = [
        item
        for item in matches
        if BLOOM_RANK[
            item["level"]
        ] == highest_rank
    ]

    return {
        "level": strongest[0]["level"],
        "confidence": min(
            100,
            60 + len(strongest) * 10
        ),
        "evidence": strongest
    }


def bloom_alignment(
    question,
    intended_bloom
):
    detected = detect_bloom(
        question
    )

    if detected["level"] == "Unknown":

        return {
            "status": "REVIEW",
            "score": 40,
            "detected": "Unknown",
            "evidence": [],
            "reason": (
                "The cognitive operation could not be "
                "determined reliably from the question."
            )
        }

    intended_rank = BLOOM_RANK[
        intended_bloom
    ]

    actual_rank = BLOOM_RANK[
        detected["level"]
    ]

    difference = (
        actual_rank
        - intended_rank
    )

    if difference == 0:

        return {
            "status": "PASS",
            "score": 100,
            "detected": detected["level"],
            "evidence": detected["evidence"],
            "reason": (
                f"The detected cognitive operation "
                f"matches the entered Bloom level."
            )
        }

    if abs(difference) == 1:

        return {
            "status": "REVIEW",
            "score": 55,
            "detected": detected["level"],
            "evidence": detected["evidence"],
            "reason": (
                f"The question appears to operate at "
                f"{detected['level']} while "
                f"{intended_bloom} was entered."
            )
        }

    return {
        "status": "FAIL",
        "score": 0,
        "detected": detected["level"],
        "evidence": detected["evidence"],
        "reason": (
            f"The question operates at "
            f"{detected['level']} rather than the "
            f"entered Bloom level {intended_bloom}."
        )
    }


# ============================================================
# CLO ALIGNMENT
# ============================================================

def outcome_action(text):
    lower = text.lower()

    matches = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b"
                + re.escape(verb)
                + r"\b",
                lower
            ):

                matches.append(
                    {
                        "level": level,
                        "verb": verb
                    }
                )

    if not matches:

        return {
            "level": "Unknown",
            "verbs": []
        }

    highest_rank = max(
        BLOOM_RANK[
            x["level"]
        ]
        for x in matches
    )

    strongest = [
        x
        for x in matches
        if BLOOM_RANK[
            x["level"]
        ] == highest_rank
    ]

    return {
        "level": strongest[0]["level"],
        "verbs": [
            x["verb"]
            for x in strongest
        ]
    }


def calculate_clo_alignment(
    question,
    clos
):
    if not clos:

        return {
            "status": "REVIEW",
            "score": 0,
            "matched": None,
            "reason": "No CLO was provided.",
            "content_score": 0,
            "action_score": 0,
            "shared_content": []
        }

    question_tokens = stem_set(
        question
    )

    question_action = outcome_action(
        question
    )

    best = None

    for clo in clos:

        clo_tokens = stem_set(
            clo["text"]
        )

        clo_action = outcome_action(
            clo["text"]
        )

        shared = (
            question_tokens
            & clo_tokens
        )

        if question_tokens and clo_tokens:

            precision = (
                len(shared)
                / len(question_tokens)
            )

            recall = (
                len(shared)
                / len(clo_tokens)
            )

            if precision + recall:

                content_f1 = (
                    2
                    * precision
                    * recall
                    / (
                        precision
                        + recall
                    )
                )

            else:
                content_f1 = 0

        else:
            content_f1 = 0

        content_score = (
            content_f1 * 100
        )

        if (
            question_action["level"]
            != "Unknown"
            and clo_action["level"]
            != "Unknown"
        ):

            difference = abs(
                BLOOM_RANK[
                    question_action["level"]
                ]
                - BLOOM_RANK[
                    clo_action["level"]
                ]
            )

            if difference == 0:
                action_score = 100
            elif difference == 1:
                action_score = 60
            else:
                action_score = 20

        else:
            action_score = 50

        # Content is more important than action.
        combined = (
            content_score * 0.70
            + action_score * 0.30
        )

        candidate = {
            "clo": clo,
            "score": combined,
            "content_score": content_score,
            "action_score": action_score,
            "shared_content": sorted(
                shared
            ),
            "question_action": (
                question_action["level"]
            ),
            "clo_action": (
                clo_action["level"]
            )
        }

        if (
            best is None
            or candidate["score"]
            > best["score"]
        ):
            best = candidate

    if best["score"] >= 70:

        status = "PASS"

        reason = (
            f"The question sufficiently assesses "
            f"the content and action represented by "
            f"{best['clo']['id']}."
        )

    elif best["score"] >= 50:

        status = "REVIEW"

        reason = (
            f"The question shows partial alignment "
            f"with {best['clo']['id']}."
        )

    else:

        status = "FAIL"

        reason = (
            f"The question does not sufficiently "
            f"assess {best['clo']['id']}."
        )

    return {
        "status": status,
        "score": round(
            best["score"],
            1
        ),
        "matched": best["clo"],
        "reason": reason,
        "content_score": round(
            best["content_score"],
            1
        ),
        "action_score": round(
            best["action_score"],
            1
        ),
        "shared_content": best[
            "shared_content"
        ],
        "question_action": best[
            "question_action"
        ],
        "clo_action": best[
            "clo_action"
        ]
    }


# ============================================================
# PLO ALIGNMENT
# ============================================================

PLO_CAPABILITIES = {
    "knowledge": {
        "knowledge", "concept", "principle",
        "theory", "fundamental", "understand"
    },

    "problem_solving": {
        "solve", "problem", "solution",
        "calculate", "apply", "determine"
    },

    "analysis": {
        "analyze", "analyse", "analysis",
        "examine", "investigate", "interpret",
        "data", "evidence"
    },

    "communication": {
        "communicate", "communication",
        "write", "writing", "present",
        "presentation", "explain", "report"
    },

    "teamwork": {
        "team", "group", "collaborate",
        "collaboration", "cooperate",
        "teamwork"
    },

    "ethics": {
        "ethical", "ethics", "professional",
        "responsibility", "responsible",
        "integrity", "society"
    },

    "design": {
        "design", "develop", "create",
        "formulate", "prototype", "plan"
    },

    "technology": {
        "technology", "software", "tool",
        "computer", "digital", "technical"
    },

    "lifelong_learning": {
        "learning", "learn", "research",
        "independent", "development",
        "lifelong"
    }
}


def infer_plo_capabilities(text):
    tokens = stem_set(text)

    found = []

    for capability, terms in PLO_CAPABILITIES.items():

        normalized_terms = {
            simple_stem(term)
            for term in terms
        }

        hits = (
            tokens
            & normalized_terms
        )

        if hits:

            found.append(
                {
                    "capability": capability,
                    "hits": sorted(hits)
                }
            )

    return found


def question_capabilities(question):
    lower = question.lower()

    capabilities = set()

    if re.search(
        r"\b"
        r"(calculate|compute|solve|determine|apply|derive)"
        r"\b",
        lower
    ):
        capabilities.add(
            "problem_solving"
        )

    if re.search(
        r"\b"
        r"(analyze|analyse|examine|interpret|"
        r"investigate|compare|contrast)"
        r"\b",
        lower
    ):
        capabilities.add(
            "analysis"
        )

    if re.search(
        r"\b"
        r"(explain|describe|summarize|discuss)"
        r"\b",
        lower
    ):
        capabilities.add(
            "communication"
        )

    if re.search(
        r"\b"
        r"(design|develop|create|formulate|"
        r"construct|propose)"
        r"\b",
        lower
    ):
        capabilities.add(
            "design"
        )

    if re.search(
        r"\b"
        r"(justify|evaluate|critique|assess|defend)"
        r"\b",
        lower
    ):
        capabilities.add(
            "analysis"
        )

    if re.search(
        r"\b"
        r"(ethical|professional|responsible|ethics)"
        r"\b",
        lower
    ):
        capabilities.add(
            "ethics"
        )

    if not capabilities:
        capabilities.add(
            "knowledge"
        )

    return capabilities


def calculate_plo_alignment(
    question,
    plos
):
    if not plos:

        return {
            "status": "NOT ASSESSED",
            "score": 100,
            "matched": None,
            "reason": "No PLO was provided.",
            "shared": []
        }

    q_capabilities = question_capabilities(
        question
    )

    best = None

    for plo in plos:

        plo_capabilities = {
            item["capability"]
            for item in infer_plo_capabilities(
                plo["text"]
            )
        }

        shared = (
            q_capabilities
            & plo_capabilities
        )

        text_score = overlap_score(
            question,
            plo["text"]
        )

        capability_score = (
            100
            if shared
            else 0
        )

        combined = (
            capability_score * 0.70
            + text_score * 0.30
        )

        candidate = {
            "plo": plo,
            "score": combined,
            "shared": sorted(
                shared
            )
        }

        if (
            best is None
            or candidate["score"]
            > best["score"]
        ):
            best = candidate

    if best["score"] >= 65:

        status = "PASS"

        reason = (
            f"The question demonstrates capability "
            f"associated with {best['plo']['id']}."
        )

    elif best["score"] >= 40:

        status = "REVIEW"

        reason = (
            f"Some evidence of alignment with "
            f"{best['plo']['id']} was found, but "
            f"the capability evidence is limited."
        )

    else:

        status = "FAIL"

        reason = (
            f"The question does not sufficiently "
            f"demonstrate the capability represented "
            f"by {best['plo']['id']}."
        )

    return {
        "status": status,
        "score": round(
            best["score"],
            1
        ),
        "matched": best["plo"],
        "reason": reason,
        "shared": best["shared"]
    }


# ============================================================
# QUESTION EFFECTIVENESS
# ============================================================

def question_quality(
    question,
    options
):
    text = remove_question_prefix(
        question
    )

    lower = text.lower()

    clarity = 100
    specificity = 100
    measurability = 100

    word_count = len(
        text.split()
    )

    if word_count < 6:
        clarity -= 30

    if word_count > 120:
        clarity -= 15

    vague_phrases = [
        "discuss everything",
        "write something",
        "say something",
        "tell me about",
        "what do you know about",
        "explain everything",
        "various things"
    ]

    for phrase in vague_phrases:

        if phrase in lower:
            specificity -= 30

    if re.search(
        r"\b"
        r"(something|anything|everything|various things)"
        r"\b",
        lower
    ):
        specificity -= 15

    if not has_question_structure(
        text
    ):
        measurability -= 20

    if options:

        if len(options) < 3:
            specificity -= 15

        option_texts = []

        for option in options:

            cleaned = re.sub(
                r"^\s*[A-Ha-h][\)\].:\-]\s*",
                "",
                option
            )

            option_texts.append(
                normalize_inline(
                    cleaned
                )
            )

        if len(
            set(option_texts)
        ) != len(option_texts):

            specificity -= 25

    clarity = max(
        0,
        clarity
    )

    specificity = max(
        0,
        specificity
    )

    measurability = max(
        0,
        measurability
    )

    score = (
        clarity * 0.35
        + specificity * 0.35
        + measurability * 0.30
    )

    if score >= 75:
        status = "PASS"
    elif score >= 55:
        status = "REVIEW"
    else:
        status = "FAIL"

    return {
        "status": status,
        "score": round(
            score,
            1
        ),
        "clarity": clarity,
        "specificity": specificity,
        "measurability": measurability
    }


# ============================================================
# DIRECT REVISION
# ============================================================

def revision_for_question(
    question,
    clo,
    intended_bloom
):
    original = remove_question_prefix(
        question
    )

    if clo:
        clo_text = clo["text"]
    else:
        clo_text = ""

    # Preserve important content from the original
    # rather than inserting CLO wording.
    original_tokens = [
        word
        for word in re.findall(
            r"\b[A-Za-z][A-Za-z0-9-]+\b",
            original
        )
        if word.lower()
        not in STOP_WORDS
    ]

    content = " ".join(
        original_tokens[:12]
    )

    if not content:
        content = clo_text

    if intended_bloom == "Remember":
        return (
            f"Identify {content}."
        )

    if intended_bloom == "Understand":
        return (
            f"Explain how {content} works and "
            f"why it produces the stated result."
        )

    if intended_bloom == "Apply":
        return (
            f"Calculate or determine the required "
            f"result using {content}."
        )

    if intended_bloom == "Analyze":
        return (
            f"Analyze {content} and identify the "
            f"factors responsible for the result."
        )

    if intended_bloom == "Evaluate":
        return (
            f"Evaluate {content} and justify your "
            f"conclusion using relevant evidence."
        )

    if intended_bloom == "Create":
        return (
            f"Design a suitable solution involving "
            f"{content} and explain how it works."
        )

    return original


# ============================================================
# FINAL EVALUATION
# ============================================================

def evaluate_question(
    item,
    expected_domain,
    clos,
    plos,
    intended_bloom
):
    question = item["text"]

    subject = question_subject_check(
        question,
        expected_domain
    )

    quality = question_quality(
        question,
        item["options"]
    )

    # --------------------------------------------------------
    # HARD SUBJECT GATE
    # --------------------------------------------------------

    if subject["status"] == "FAIL":

        return {
            "question": question,
            "number": item["number"],
            "options": item["options"],
            "subject": subject,
            "clo": None,
            "plo": None,
            "bloom": None,
            "quality": quality,
            "decision": "REJECTED",
            "overall": 0,
            "reason": (
                "Subject relevance failed. Other scores "
                "cannot compensate for a subject mismatch."
            )
        }

    clo = calculate_clo_alignment(
        question,
        clos
    )

    plo = calculate_plo_alignment(
        question,
        plos
    )

    bloom = bloom_alignment(
        question,
        intended_bloom
    )

    # --------------------------------------------------------
    # NON-COMPENSATORY DECISION
    # --------------------------------------------------------

    if subject["status"] == "REVIEW":

        decision = "NEEDS REVIEW"

        reason = (
            "Subject evidence is insufficient for "
            "automatic approval."
        )

    elif clo["status"] == "FAIL":

        decision = "REJECTED"

        reason = (
            "The question does not sufficiently assess "
            "the selected CLO."
        )

    elif bloom["status"] == "FAIL":

        decision = "REJECTED"

        reason = (
            f"Bloom mismatch: entered "
            f"{intended_bloom}, detected "
            f"{bloom['detected']}."
        )

    elif plo["status"] == "FAIL":

        decision = "REJECTED"

        reason = (
            "The question does not demonstrate the "
            "capability represented by the selected PLO."
        )

    elif clo["status"] == "REVIEW":

        decision = "NEEDS REVIEW"

        reason = (
            "CLO alignment is only partial."
        )

    elif bloom["status"] == "REVIEW":

        decision = "NEEDS REVIEW"

        reason = (
            "Bloom alignment is uncertain."
        )

    elif plo["status"] == "REVIEW":

        decision = "NEEDS REVIEW"

        reason = (
            "PLO alignment is not sufficiently supported."
        )

    elif quality["status"] == "FAIL":

        decision = "NEEDS REVIEW"

        reason = (
            "The question has significant effectiveness "
            "problems."
        )

    else:

        decision = "APPROVED"

        reason = (
            "The question passed the subject, CLO, "
            "PLO and Bloom alignment gates."
        )

    overall = (
        subject["score"] * 0.30
        + clo["score"] * 0.25
        + plo["score"] * 0.15
        + bloom["score"] * 0.15
        + quality["score"] * 0.15
    )

    return {
        "question": question,
        "number": item["number"],
        "options": item["options"],
        "subject": subject,
        "clo": clo,
        "plo": plo,
        "bloom": bloom,
        "quality": quality,
        "decision": decision,
        "overall": round(
            overall,
            1
        ),
        "reason": reason
    }


# ============================================================
# CSV EXPORT
# ============================================================

def results_dataframe(results):
    rows = []

    for result in results:

        clo_id = ""

        if (
            result["clo"]
            and result["clo"].get(
                "matched"
            )
        ):
            clo_id = result[
                "clo"
            ]["matched"]["id"]

        plo_id = ""

        if (
            result["plo"]
            and result["plo"].get(
                "matched"
            )
        ):
            plo_id = result[
                "plo"
            ]["matched"]["id"]

        detected_bloom = ""

        if result["bloom"]:

            detected_bloom = result[
                "bloom"
            ].get(
                "detected",
                ""
            )

        rows.append(
            {
                "Question No": result[
                    "number"
                ],
                "Question": result[
                    "question"
                ],
                "Decision": result[
                    "decision"
                ],
                "Overall Score": result[
                    "overall"
                ],
                "Subject Status": result[
                    "subject"
                ]["status"],
                "Subject Score": result[
                    "subject"
                ]["score"],
                "Detected Subject": result[
                    "subject"
                ]["detected_domain"],
                "CLO": clo_id,
                "CLO Score": (
                    result["clo"]["score"]
                    if result["clo"]
                    else 0
                ),
                "PLO": plo_id,
                "PLO Score": (
                    result["plo"]["score"]
                    if result["plo"]
                    else 0
                ),
                "Entered Bloom": result.get(
                    "entered_bloom",
                    ""
                ),
                "Detected Bloom": detected_bloom,
                "Bloom Score": (
                    result["bloom"]["score"]
                    if result["bloom"]
                    else 0
                ),
                "Quality Score": result[
                    "quality"
                ]["score"],
                "Reason": result[
                    "reason"
                ]
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# UI
# ============================================================

st.title(
    "🎓 OBE Assessment Alignment Checker"
)

st.write(
    "Evaluate assessment questions against the selected "
    "course, CLO, PLO and Bloom's Taxonomy level."
)

st.info(
    "The system first removes document metadata and validates "
    "genuine questions. Scanned PDFs are automatically sent "
    "through OCR when normal PDF text extraction is insufficient."
)


# ============================================================
# CONTEXT
# ============================================================

st.subheader(
    "1. Assessment Context"
)

course_name = st.text_input(
    "Course / Subject Name",
    placeholder="Example: General Chemistry"
)

intended_bloom = st.selectbox(
    "Intended Bloom's Taxonomy Level",
    BLOOM_LEVELS
)


# ============================================================
# CLO / PLO
# ============================================================

col1, col2 = st.columns(2)

with col1:

    clo_text = st.text_area(
        "Enter CLOs",
        height=220,
        placeholder=(
            "CLO1: Explain the principles of chemical equilibrium.\n"
            "CLO2: Apply stoichiometric principles to solve problems."
        )
    )

with col2:

    plo_text = st.text_area(
        "Enter PLOs",
        height=220,
        placeholder=(
            "PLO1: Apply knowledge of mathematics and science.\n"
            "PLO2: Analyze and solve technical problems."
        )
    )


clos = parse_outcomes(
    clo_text,
    "CLO"
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)

if clos:

    st.success(
        f"{len(clos)} CLO(s) detected."
    )

else:

    st.warning(
        "No CLO detected. Use CLO1: description."
    )


if plos:

    st.success(
        f"{len(plos)} PLO(s) detected."
    )

else:

    st.warning(
        "No PLO detected. Use PLO1: description."
    )


# ============================================================
# FILE
# ============================================================

st.subheader(
    "2. Assessment File"
)

uploaded_file = st.file_uploader(
    "Upload complete assessment",
    type=[
        "pdf",
        "docx",
        "txt",
        "csv",
        "xlsx",
        "xls"
    ]
)

manual_text = st.text_area(
    "Or paste assessment text",
    height=220
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
            "Please enter the course / subject."
        )

        st.stop()

    if not clos:

        st.error(
            "Please enter at least one CLO."
        )

        st.stop()

    if uploaded_file:

        with st.spinner(
            "Reading assessment..."
        ):

            assessment_text, extraction_method = (
                read_uploaded_file(
                    uploaded_file
                )
            )

        if not assessment_text.strip():

            st.error(
                "The uploaded file could not be read."
            )

            st.warning(
                "If this is a scanned PDF, verify that "
                "Tesseract OCR is installed through packages.txt."
            )

            st.stop()

        st.success(
            f"File read successfully using "
            f"**{extraction_method}**."
        )

    elif manual_text.strip():

        assessment_text = manual_text
        extraction_method = "Pasted text"

    else:

        st.error(
            "Upload a file or paste the assessment."
        )

        st.stop()


    # --------------------------------------------------------
    # Detect course
    # --------------------------------------------------------

    detected_domain, confidence = (
        determine_course_domain(
            course_name,
            clo_text,
            plo_text,
            assessment_text
        )
    )


    # --------------------------------------------------------
    # Extract genuine questions
    # --------------------------------------------------------

    questions = extract_questions(
        assessment_text
    )

    if not questions:

        st.error(
            "No genuine assessment questions were detected."
        )

        st.info(
            "The file was read, but no question-like "
            "assessment content was found."
        )

        st.stop()


    # --------------------------------------------------------
    # Evaluate
    # --------------------------------------------------------

    results = []

    for item in questions:

        result = evaluate_question(
            item,
            detected_domain,
            clos,
            plos,
            intended_bloom
        )

        result[
            "entered_bloom"
        ] = intended_bloom

        results.append(
            result
        )


    st.session_state[
        "results"
    ] = results

    st.session_state[
        "assessment_text"
    ] = assessment_text

    st.session_state[
        "detected_domain"
    ] = detected_domain

    st.session_state[
        "confidence"
    ] = confidence

    st.session_state[
        "extraction_method"
    ] = extraction_method


# ============================================================
# RESULTS
# ============================================================

if "results" in st.session_state:

    results = st.session_state[
        "results"
    ]

    detected_domain = st.session_state[
        "detected_domain"
    ]

    confidence = st.session_state[
        "confidence"
    ]

    extraction_method = st.session_state[
        "extraction_method"
    ]


    st.divider()

    st.subheader(
        "3. Assessment Detection"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Detected Subject",
            detected_domain
        )

    with c2:

        st.metric(
            "Context Confidence",
            f"{confidence}%"
        )

    with c3:

        st.metric(
            "Questions Extracted",
            len(results)
        )

    with c4:

        st.metric(
            "Read Method",
            extraction_method
        )


    # ========================================================
    # EXTRACTED QUESTIONS
    # ========================================================

    st.subheader(
        "4. Validated Questions"
    )

    st.caption(
        "Only validated assessment questions are shown here. "
        "Page numbers, timestamps, headings, QuestionWell "
        "metadata and document headers are excluded."
    )

    extraction_rows = []

    for result in results:

        extraction_rows.append(
            {
                "No.": result[
                    "number"
                ],
                "Question": result[
                    "question"
                ]
            }
        )

    st.dataframe(
        pd.DataFrame(
            extraction_rows
        ),
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    st.subheader(
        "5. Evaluation Summary"
    )

    approved = sum(
        r["decision"] == "APPROVED"
        for r in results
    )

    rejected = sum(
        r["decision"] == "REJECTED"
        for r in results
    )

    review = sum(
        r["decision"] == "NEEDS REVIEW"
        for r in results
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Total",
            len(results)
        )

    with c2:
        st.metric(
            "Approved",
            approved
        )

    with c3:
        st.metric(
            "Rejected",
            rejected
        )

    with c4:
        st.metric(
            "Needs Review",
            review
        )


    # ========================================================
    # SUMMARY TABLE
    # ========================================================

    summary_rows = []

    for result in results:

        clo_id = ""

        if (
            result["clo"]
            and result["clo"].get(
                "matched"
            )
        ):
            clo_id = result[
                "clo"
            ]["matched"]["id"]

        plo_id = ""

        if (
            result["plo"]
            and result["plo"].get(
                "matched"
            )
        ):
            plo_id = result[
                "plo"
            ]["matched"]["id"]

        detected_bloom = ""

        if result["bloom"]:

            detected_bloom = result[
                "bloom"
            ].get(
                "detected",
                ""
            )

        summary_rows.append(
            {
                "No.": result[
                    "number"
                ],
                "Decision": result[
                    "decision"
                ],
                "Overall": result[
                    "overall"
                ],
                "Subject": result[
                    "subject"
                ]["status"],
                "CLO": clo_id,
                "CLO": clo_id,
                "CLO Alignment": (
                    result["clo"]["score"]
                    if result["clo"]
                    else 0
                ),
                "PLO": plo_id,
                "PLO Alignment": (
                    result["plo"]["score"]
                    if result["plo"]
                    else 0
                ),
                "Entered Bloom": result[
                    "entered_bloom"
                ],
                "Detected Bloom": detected_bloom,
                "Bloom Alignment": (
                    result["bloom"]["score"]
                    if result["bloom"]
                    else 0
                )
            }
        )

    st.dataframe(
        pd.DataFrame(
            summary_rows
        ),
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # DETAILED ANALYSIS
    # ========================================================

    st.subheader(
        "6. Detailed Question Analysis"
    )

    for index, result in enumerate(
        results,
        start=1
    ):

        number = (
            result["number"]
            or str(index)
        )

        with st.expander(
            f"Question {number} — "
            f"{result['decision']}"
        ):

            st.markdown(
                "### Question"
            )

            st.write(
                result["question"]
            )

            # ------------------------------------------------
            # SUBJECT
            # ------------------------------------------------

            st.markdown(
                "### Subject Relevance"
            )

            subject = result[
                "subject"
            ]

            if subject["status"] == "PASS":

                st.success(
                    f"PASS — "
                    f"{subject['score']}%"
                )

            elif subject["status"] == "FAIL":

                st.error(
                    "FAIL — 0%"
                )

            else:

                st.warning(
                    f"NEEDS REVIEW — "
                    f"{subject['score']}%"
                )

            st.write(
                "Detected subject: "
                + subject[
                    "detected_domain"
                ]
            )

            if subject["evidence"]:

                st.write(
                    "Evidence: "
                    + ", ".join(
                        subject[
                            "evidence"
                        ]
                    )
                )

            st.caption(
                subject["reason"]
            )


            # ------------------------------------------------
            # HARD SUBJECT STOP
            # ------------------------------------------------

            if subject["status"] == "FAIL":

                st.error(
                    "CLO, PLO and Bloom approval is blocked "
                    "because the subject gate failed."
                )

                st.error(
                    "FINAL: REJECTED"
                )

                continue


            # ------------------------------------------------
            # CLO
            # ------------------------------------------------

            st.markdown(
                "### CLO Alignment"
            )

            clo_result = result[
                "clo"
            ]

            if clo_result["status"] == "PASS":

                st.success(
                    f"PASS — "
                    f"{clo_result['score']}%"
                )

            elif clo_result["status"] == "FAIL":

                st.error(
                    f"FAIL — "
                    f"{clo_result['score']}%"
                )

            else:

                st.warning(
                    f"NEEDS REVIEW — "
                    f"{clo_result['score']}%"
                )

            if clo_result.get(
                "matched"
            ):

                st.write(
                    f"Matched CLO: "
                    f"**{clo_result['matched']['id']}**"
                )

                st.write(
                    clo_result[
                        "matched"
                    ]["text"]
                )

            st.write(
                "Content alignment: "
                f"**{clo_result['content_score']}%**"
            )

            st.write(
                "Action alignment: "
                f"**{clo_result['action_score']}%**"
            )

            if clo_result[
                "shared_content"
            ]:

                st.write(
                    "Shared content evidence: "
                    + ", ".join(
                        clo_result[
                            "shared_content"
                        ]
                    )
                )

            st.caption(
                clo_result["reason"]
            )


            # ------------------------------------------------
            # PLO
            # ------------------------------------------------

            st.markdown(
                "### PLO Alignment"
            )

            plo_result = result[
                "plo"
            ]

            if plo_result["status"] == "PASS":

                st.success(
                    f"PASS — "
                    f"{plo_result['score']}%"
                )

            elif plo_result["status"] == "FAIL":

                st.error(
                    f"FAIL — "
                    f"{plo_result['score']}%"
                )

            else:

                st.warning(
                    f"NEEDS REVIEW — "
                    f"{plo_result['score']}%"
                )

            if plo_result.get(
                "matched"
            ):

                st.write(
                    f"Matched PLO: "
                    f"**{plo_result['matched']['id']}**"
                )

                st.write(
                    plo_result[
                        "matched"
                    ]["text"]
                )

            if plo_result[
                "shared"
            ]:

                st.write(
                    "Capability evidence: "
                    + ", ".join(
                        plo_result[
                            "shared"
                        ]
                    )
                )

            st.caption(
                plo_result["reason"]
            )


            # ------------------------------------------------
            # BLOOM
            # ------------------------------------------------

            st.markdown(
                "### Bloom's Taxonomy"
            )

            bloom_result = result[
                "bloom"
            ]

            st.write(
                "Entered Bloom level: "
                f"**{result['entered_bloom']}**"
            )

            st.write(
                "Detected cognitive level: "
                f"**{bloom_result['detected']}**"
            )

            if bloom_result["status"] == "PASS":

                st.success(
                    f"PASS — "
                    f"{bloom_result['score']}%"
                )

            elif bloom_result["status"] == "FAIL":

                st.error(
                    f"FAIL — "
                    f"{bloom_result['score']}%"
                )

            else:

                st.warning(
                    f"NEEDS REVIEW — "
                    f"{bloom_result['score']}%"
                )

            if bloom_result[
                "evidence"
            ]:

                evidence = []

                for item in bloom_result[
                    "evidence"
                ]:

                    evidence.append(
                        f"{item['verb']} → "
                        f"{item['level']}"
                    )

                st.write(
                    "Cognitive evidence: "
                    + "; ".join(
                        evidence
                    )
                )

            st.caption(
                bloom_result["reason"]
            )


            # ------------------------------------------------
            # EFFECTIVENESS
            # ------------------------------------------------

            st.markdown(
                "### Question Effectiveness"
            )

            quality = result[
                "quality"
            ]

            q1, q2, q3, q4 = st.columns(4)

            with q1:
                st.metric(
                    "Overall",
                    f"{quality['score']}%"
                )

            with q2:
                st.metric(
                    "Clarity",
                    f"{quality['clarity']}%"
                )

            with q3:
                st.metric(
                    "Specificity",
                    f"{quality['specificity']}%"
                )

            with q4:
                st.metric(
                    "Measurability",
                    f"{quality['measurability']}%"
                )


            # ------------------------------------------------
            # FINAL
            # ------------------------------------------------

            st.markdown(
                "### Final Decision"
            )

            if result[
                "decision"
            ] == "APPROVED":

                st.success(
                    "APPROVED"
                )

            elif result[
                "decision"
            ] == "REJECTED":

                st.error(
                    "REJECTED"
                )

            else:

                st.warning(
                    "NEEDS REVIEW"
                )

            st.write(
                result["reason"]
            )


            # ------------------------------------------------
            # REVISION
            # ------------------------------------------------

            if result[
                "decision"
            ] != "APPROVED":

                matched_clo = None

                if result["clo"]:

                    matched_clo = result[
                        "clo"
                    ].get(
                        "matched"
                    )

                revised = revision_for_question(
                    result["question"],
                    matched_clo,
                    result[
                        "entered_bloom"
                    ]
                )

                st.markdown(
                    "### Direct Revision"
                )

                st.info(
                    revised
                )

                st.caption(
                    "The revision keeps the question focused on "
                    "the subject content and changes the cognitive "
                    "operation toward the entered Bloom level. "
                    "CLO/PLO statements are not inserted into the question."
                )


    # ========================================================
    # QUESTIONS REQUIRING ACTION
    # ========================================================

    st.subheader(
        "7. Questions Requiring Action"
    )

    action_items = [
        result
        for result in results
        if result[
            "decision"
        ] != "APPROVED"
    ]

    if action_items:

        for result in action_items:

            number = (
                result["number"]
                or "?"
            )

            st.markdown(
                f"**Question {number} — "
                f"{result['decision']}**"
            )

            st.write(
                result["reason"]
            )

    else:

        st.success(
            "All extracted questions passed the alignment gates."
        )


    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.subheader(
        "8. Detected Bloom Distribution"
    )

    bloom_counts = Counter()

    for result in results:

        if result["bloom"]:

            bloom_counts[
                result["bloom"].get(
                    "detected",
                    "Unknown"
                )
            ] += 1

    bloom_rows = []

    for level in BLOOM_LEVELS:

        bloom_rows.append(
            {
                "Bloom Level": level,
                "Questions": bloom_counts.get(
                    level,
                    0
                )
            }
        )

    bloom_rows.append(
        {
            "Bloom Level": "Unknown",
            "Questions": bloom_counts.get(
                "Unknown",
                0
            )
        }
    )

    st.dataframe(
        pd.DataFrame(
            bloom_rows
        ),
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # CLO COVERAGE
    # ========================================================

    st.subheader(
        "9. CLO Coverage"
    )

    coverage = Counter()

    for result in results:

        if (
            result["clo"]
            and result["clo"].get(
                "matched"
            )
        ):

            coverage[
                result[
                    "clo"
                ]["matched"]["id"]
            ] += 1

    coverage_rows = []

    for clo in clos:

        coverage_rows.append(
            {
                "CLO": clo["id"],
                "Questions": coverage.get(
                    clo["id"],
                    0
                ),
                "Description": clo[
                    "text"
                ]
            }
        )

    st.dataframe(
        pd.DataFrame(
            coverage_rows
        ),
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # EXPORT
    # ========================================================

    st.subheader(
        "10. Export"
    )

    export_df = results_dataframe(
        results
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Evaluation Results",
        data=csv_data,
        file_name=(
            "OBE_Assessment_Evaluation.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Evaluation Model"
    )

    st.markdown(
        """
### Evaluation sequence

**1. Read file**

Normal PDF extraction is attempted first.

**2. OCR fallback**

If the PDF is scanned, OCR is automatically used.

**3. Clean document**

The system removes:

- Page numbers
- Dates
- Times
- Headers
- Footers
- QuestionWell metadata
- Course headings
- Section headings

**4. Extract genuine questions**

Only substantive assessment questions are evaluated.

**5. Subject gate**

The question must belong to the selected course.

**6. CLO alignment**

The question is compared with the CLO's content and action.

**7. PLO alignment**

The capability demonstrated by the question is compared with the PLO.

**8. Bloom alignment**

The actual cognitive operation is compared with the Bloom level entered.

**9. Final decision**

A strong score in one category cannot compensate for a failed hard gate.

### Decision rules

**APPROVED**

All major alignment gates pass.

**REJECTED**

A major alignment requirement fails.

**NEEDS REVIEW**

Evidence is insufficient for automatic approval.

### Supported assessments

The evaluator is not restricted to MCQs.

It can process:

- MCQs
- Short-answer questions
- Essays
- Numerical problems
- Case studies
- True/False
- Analytical questions
- Practical questions
- Problem-solving questions
"""
    )
