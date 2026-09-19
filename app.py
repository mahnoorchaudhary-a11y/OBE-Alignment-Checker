import io
import re
import math
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
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
        "define",
        "identify",
        "name",
        "list",
        "state",
        "recall",
        "recognize",
        "label",
        "select",
        "match",
        "mention",
        "describe",
    },
    "Understand": {
        "explain",
        "summarize",
        "interpret",
        "classify",
        "compare",
        "contrast",
        "discuss",
        "illustrate",
        "paraphrase",
        "describe",
        "differentiate",
        "distinguish",
    },
    "Apply": {
        "calculate",
        "compute",
        "solve",
        "use",
        "apply",
        "demonstrate",
        "implement",
        "execute",
        "determine",
        "find",
        "perform",
        "construct",
    },
    "Analyze": {
        "analyze",
        "analyse",
        "examine",
        "differentiate",
        "organize",
        "organise",
        "investigate",
        "break",
        "categorize",
        "categorise",
        "compare",
        "contrast",
        "infer",
        "identify",
        "distinguish",
    },
    "Evaluate": {
        "evaluate",
        "judge",
        "justify",
        "critique",
        "assess",
        "defend",
        "appraise",
        "argue",
        "validate",
        "recommend",
        "select",
    },
    "Create": {
        "design",
        "create",
        "develop",
        "formulate",
        "construct",
        "produce",
        "propose",
        "plan",
        "generate",
        "devise",
        "develop",
    },
}


# ============================================================
# SUBJECT / DOMAIN KNOWLEDGE
# ============================================================

DOMAIN_LEXICONS = {
    "Chemistry": {
        "atom", "molecule", "element", "compound", "reaction",
        "equilibrium", "acid", "base", "ph", "molarity",
        "mole", "stoichiometry", "bond", "ionic", "covalent",
        "organic", "inorganic", "oxidation", "reduction",
        "redox", "catalyst", "kinetics", "thermodynamics",
        "enthalpy", "entropy", "solution", "concentration",
        "periodic", "electron", "proton", "neutron",
        "isotope", "spectroscopy", "titration", "precipitate",
        "solubility", "buffer", "electrochemistry",
    },

    "Physics": {
        "force", "motion", "velocity", "acceleration", "mass",
        "energy", "momentum", "gravity", "friction", "work",
        "power", "wave", "frequency", "wavelength", "electric",
        "magnetic", "voltage", "current", "resistance",
        "circuit", "charge", "field", "optics", "lens",
        "mirror", "pressure", "density", "thermodynamics",
        "kinematic", "newton", "quantum", "relativity",
    },

    "Mathematics": {
        "equation", "algebra", "matrix", "vector", "calculus",
        "derivative", "integral", "function", "limit",
        "probability", "statistics", "mean", "median", "variance",
        "geometry", "trigonometry", "logarithm", "polynomial",
        "theorem", "proof", "set", "sequence", "series",
        "differential", "linear", "quadratic", "graph",
    },

    "Computer Science": {
        "algorithm", "program", "programming", "code", "software",
        "hardware", "database", "sql", "network", "computer",
        "operating", "system", "memory", "processor", "cpu",
        "data", "structure", "array", "stack", "queue", "tree",
        "graph", "recursion", "class", "object", "inheritance",
        "python", "java", "javascript", "machine", "learning",
        "artificial", "intelligence", "compiler", "security",
    },

    "Biology": {
        "cell", "organism", "gene", "dna", "rna", "protein",
        "enzyme", "mitosis", "meiosis", "evolution", "species",
        "ecosystem", "photosynthesis", "respiration", "membrane",
        "chromosome", "genetics", "bacteria", "virus", "tissue",
        "organ", "metabolism", "homeostasis", "population",
        "ecology", "mutation", "transcription", "translation",
    },

    "English / Language": {
        "grammar", "sentence", "paragraph", "essay", "writing",
        "reading", "author", "tone", "purpose", "main",
        "idea", "paraphrase", "thesis", "argument", "rhetoric",
        "language", "communication", "vocabulary", "syntax",
        "morphology", "phonology", "semantics", "pragmatics",
        "listening", "speaking", "audience", "organization",
    },

    "Literature": {
        "novel", "poem", "poetry", "character", "plot", "theme",
        "symbolism", "metaphor", "narrator", "narrative",
        "author", "literary", "fiction", "drama", "tragedy",
        "irony", "imagery", "setting", "protagonist", "genre",
        "sonnet", "stanza", "verse", "interpretation",
    },

    "Business / Management": {
        "management", "manager", "organization", "leadership",
        "strategy", "marketing", "customer", "market", "business",
        "planning", "decision", "entrepreneur", "entrepreneurship",
        "human", "resource", "operations", "competitive",
        "stakeholder", "performance", "motivation", "management",
        "organizational", "organization",
    },

    "Accounting / Finance": {
        "accounting", "account", "ledger", "journal", "balance",
        "asset", "liability", "equity", "revenue", "expense",
        "profit", "loss", "financial", "statement", "audit",
        "debit", "credit", "cash", "budget", "investment",
        "capital", "ratio", "income", "tax", "cost",
    },

    "Economics": {
        "economics", "economic", "demand", "supply", "market",
        "price", "inflation", "unemployment", "gdp", "fiscal",
        "monetary", "policy", "elasticity", "utility", "consumer",
        "producer", "equilibrium", "scarcity", "opportunity",
        "trade", "exchange", "interest", "macroeconomic",
        "microeconomic",
    },

    "Engineering": {
        "engineering", "design", "machine", "mechanical",
        "electrical", "civil", "structure", "material",
        "circuit", "system", "load", "stress", "strain",
        "fluid", "thermodynamic", "control", "manufacturing",
        "prototype", "safety", "process", "technical",
    },

    "Psychology": {
        "psychology", "behavior", "behaviour", "cognition",
        "memory", "learning", "emotion", "personality",
        "development", "motivation", "perception", "therapy",
        "mental", "social", "cognitive", "psychological",
        "conditioning", "reinforcement", "intelligence",
    },

    "Sociology": {
        "society", "social", "culture", "class", "status",
        "institution", "family", "community", "inequality",
        "stratification", "norm", "value", "deviance",
        "socialization", "socialisation", "urbanization",
        "globalization", "group", "identity",
    },

    "Education": {
        "education", "teaching", "learning", "student",
        "curriculum", "pedagogy", "assessment", "classroom",
        "instruction", "teacher", "lesson", "learning",
        "outcome", "rubric", "evaluation", "educational",
        "methodology", "school", "instructional",
    },

    "History": {
        "history", "historical", "war", "empire", "king",
        "queen", "revolution", "colonial", "independence",
        "treaty", "civilization", "civilisation", "dynasty",
        "political", "ancient", "medieval", "modern",
        "movement", "colonialism",
    },

    "Law": {
        "law", "legal", "court", "contract", "tort", "crime",
        "criminal", "civil", "statute", "constitution",
        "judge", "judgment", "jurisdiction", "liability",
        "negligence", "evidence", "case", "plaintiff",
        "defendant", "rights",
    },

    "Pharmacy": {
        "drug", "medicine", "pharmacy", "pharmacology",
        "dose", "dosage", "tablet", "capsule", "prescription",
        "pharmacokinetics", "pharmacodynamics", "adverse",
        "drug", "patient", "therapeutic", "antibiotic",
        "formulation", "medication", "receptor",
    },

    "Medical / Health Sciences": {
        "patient", "disease", "diagnosis", "symptom", "treatment",
        "clinical", "medical", "health", "anatomy", "physiology",
        "pathology", "infection", "hospital", "therapy",
        "syndrome", "blood", "heart", "lung", "organ",
        "nursing", "clinical",
    },

    "Environmental Science": {
        "environment", "ecosystem", "pollution", "climate",
        "carbon", "waste", "water", "air", "soil", "biodiversity",
        "conservation", "sustainability", "greenhouse",
        "global", "warming", "renewable", "resource",
        "environmental",
    },
}


RELATED_DOMAINS = {
    "Chemistry": {
        "Pharmacy",
        "Environmental Science",
        "Engineering",
        "Biology",
    },
    "Physics": {
        "Engineering",
        "Mathematics",
        "Computer Science",
    },
    "Mathematics": {
        "Physics",
        "Engineering",
        "Economics",
        "Computer Science",
    },
    "Biology": {
        "Chemistry",
        "Pharmacy",
        "Medical / Health Sciences",
        "Environmental Science",
        "Psychology",
    },
    "Computer Science": {
        "Mathematics",
        "Engineering",
    },
    "Business / Management": {
        "Economics",
        "Accounting / Finance",
        "Education",
    },
    "Accounting / Finance": {
        "Business / Management",
        "Economics",
    },
    "Economics": {
        "Business / Management",
        "Accounting / Finance",
        "Mathematics",
    },
    "Pharmacy": {
        "Chemistry",
        "Biology",
        "Medical / Health Sciences",
    },
    "Medical / Health Sciences": {
        "Biology",
        "Pharmacy",
        "Chemistry",
    },
    "Environmental Science": {
        "Biology",
        "Chemistry",
        "Engineering",
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
    "applied physics": "Physics",

    "mathematics": "Mathematics",
    "math": "Mathematics",
    "calculus": "Mathematics",
    "linear algebra": "Mathematics",
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
    "english language": "English / Language",

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
    "cell biology": "Biology",

    "psychology": "Psychology",
    "sociology": "Sociology",
    "education": "Education",
    "educational psychology": "Education",
    "history": "History",
    "law": "Law",
    "pharmacy": "Pharmacy",
    "medical": "Medical / Health Sciences",
    "medicine": "Medical / Health Sciences",
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
    "into", "through", "using", "use", "given", "following",
    "according", "each", "any", "all", "some", "such",
    "question", "questions", "answer", "answers", "following",
}


# ============================================================
# GENERAL TEXT UTILITIES
# ============================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_token(token):
    token = token.lower()
    token = re.sub(r"[^a-z0-9]+", "", token)

    if len(token) <= 2:
        return ""

    if token in STOP_WORDS:
        return ""

    return token


def tokenize(text):
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", str(text).lower())
    result = []

    for word in words:
        cleaned = clean_token(word)

        if not cleaned:
            continue

        result.append(cleaned)

    return result


def word_set(text):
    return set(tokenize(text))


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
        if word.endswith(suffix) and len(word) > len(suffix) + 3:
            return word[:-len(suffix)]

    return word


def stem_set(text):
    return {
        simple_stem(x)
        for x in tokenize(text)
        if len(simple_stem(x)) > 2
    }


def overlap_score(text_a, text_b):
    a = stem_set(text_a)
    b = stem_set(text_b)

    if not a or not b:
        return 0.0

    intersection = len(a & b)

    precision = intersection / len(a)
    recall = intersection / len(b)

    if precision + recall == 0:
        return 0.0

    f1 = 2 * precision * recall / (precision + recall)

    return f1 * 100


# ============================================================
# METADATA / HEADER DETECTION
# ============================================================

def looks_like_date_or_time(text):
    value = normalize_text(text).lower()

    patterns = [
        r"^\d{1,2}/\d{1,2}/\d{2,4}$",
        r"^\d{1,2}-\d{1,2}-\d{2,4}$",
        r"^\d{1,2}:\d{2}\s*(am|pm)?$",
        r"^\d{1,2}/\d{1,2}$",
        r"^\d{1,2}:\d{2}\s*(am|pm)?\s+.*$",
        r"^\d{1,2}\s*(am|pm)$",
    ]

    return any(re.match(pattern, value) for pattern in patterns)


def looks_like_page_marker(text):
    value = normalize_text(text).lower()

    patterns = [
        r"^\d+\s*/\s*\d+$",
        r"^page\s+\d+$",
        r"^page\s+\d+\s+of\s+\d+$",
        r"^\d+\s+of\s+\d+$",
        r"^p\.\s*\d+$",
    ]

    return any(re.match(pattern, value) for pattern in patterns)


def looks_like_metadata(text):
    value = normalize_text(text)

    if not value:
        return True

    lower = value.lower()

    if looks_like_date_or_time(value):
        return True

    if looks_like_page_marker(value):
        return True

    metadata_patterns = [
        r"questionwell",
        r"question\s*set",
        r"generated\s+by",
        r"created\s+with",
        r"created\s+on",
        r"exported\s+on",
        r"downloaded\s+on",
        r"assessment\s+paper",
        r"quiz\s+paper",
        r"exam\s+paper",
        r"midterm\s+exam",
        r"final\s+exam",
        r"general\s+chemistry\s*\+",
        r"copyright",
        r"www\.",
        r"http://",
        r"https://",
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

    for pattern in metadata_patterns:
        if re.search(pattern, lower):
            return True

    # Pure numbering such as 1, 19/26, 01-02.
    if re.fullmatch(r"[\d\s./_-]+", value):
        return True

    # Very short headings without a question structure.
    words = value.split()

    if len(words) <= 5:
        if not value.endswith("?") and not re.match(
            r"^(q(uestion)?\s*)?\d+[\.\):\-]",
            lower,
        ):
            return True

    return False


def looks_like_heading(text):
    value = normalize_text(text)

    if not value:
        return True

    lower = value.lower()

    heading_phrases = [
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
        "clo",
        "plo",
        "assessment",
        "quiz",
        "midterm",
        "final examination",
        "examination",
        "answer key",
        "answers",
        "references",
        "chapter",
        "unit",
    ]

    if lower in heading_phrases:
        return True

    if lower.startswith("section ") and len(value.split()) <= 8:
        return True

    if lower.startswith("chapter ") and len(value.split()) <= 8:
        return True

    if lower.startswith("unit ") and len(value.split()) <= 8:
        return True

    if value.endswith(":") and len(value.split()) <= 12:
        return True

    # Headings are often title case and have no question/action structure.
    if (
        len(value.split()) <= 10
        and value == value.title()
        and not value.endswith("?")
    ):
        return True

    return False


# ============================================================
# QUESTION NUMBER / QUESTION STRUCTURE
# ============================================================

QUESTION_START_PATTERN = re.compile(
    r"^\s*"
    r"(?:"
    r"Q(?:uestion)?\s*)?"
    r"(?:\(?\d{1,3}\)?[\.\):\-])"
    r"\s+"
    r"(.*)$",
    re.IGNORECASE,
)


def extract_question_number(text):
    match = QUESTION_START_PATTERN.match(text)

    if match:
        prefix = text[:match.end(1)]
        number_match = re.search(r"\d{1,3}", prefix)

        if number_match:
            return number_match.group(0)

    q_match = re.match(
        r"^\s*Q(?:uestion)?\s*(\d{1,3})\s*[:\.\)\-]\s*",
        text,
        re.IGNORECASE,
    )

    if q_match:
        return q_match.group(1)

    return ""


def remove_question_prefix(text):
    value = normalize_text(text)

    patterns = [
        r"^\s*Q(?:uestion)?\s*\d{1,3}\s*[:\.\)\-]\s*",
        r"^\s*\(?\d{1,3}\)?\s*[\.\):\-]\s*",
        r"^\s*[IVXivx]{1,4}\s*[\.\):\-]\s*",
    ]

    for pattern in patterns:
        value = re.sub(pattern, "", value)

    return value.strip()


def has_substantive_question_content(text):
    value = remove_question_prefix(text)

    if not value:
        return False

    if looks_like_metadata(value):
        return False

    if looks_like_heading(value):
        return False

    words = tokenize(value)

    if len(words) < 5:
        return False

    # A genuine question normally has either:
    # 1. a question mark,
    # 2. a cognitive/action verb,
    # 3. an interrogative,
    # 4. a recognized assessment structure.
    lower = value.lower()

    has_question_mark = "?" in value

    has_bloom_verb = any(
        re.search(r"\b" + re.escape(verb) + r"\b", lower)
        for verbs in BLOOM_VERBS.values()
        for verb in verbs
    )

    has_interrogative = bool(
        re.search(
            r"\b(what|why|how|which|who|where|when|"
            r"explain|define|identify|calculate|compare|"
            r"analyze|analyse|evaluate|discuss|describe|"
            r"justify|design|solve)\b",
            lower,
        )
    )

    has_assessment_phrase = bool(
        re.search(
            r"\b(determine|find|calculate|solve|derive|"
            r"write|state|list|give|construct|draw|"
            r"interpret|classify|demonstrate|show|prove)\b",
            lower,
        )
    )

    return (
        has_question_mark
        or has_bloom_verb
        or has_interrogative
        or has_assessment_phrase
    )


# ============================================================
# OPTION DETECTION
# ============================================================

OPTION_PATTERN = re.compile(
    r"^\s*(?:[\(\[]?([A-Ha-h])[\)\].:\-])\s+(.*)$"
)


def is_option_line(text):
    return bool(OPTION_PATTERN.match(text))


def parse_options(lines):
    options = []

    for line in lines:
        match = OPTION_PATTERN.match(line)

        if match:
            label = match.group(1).upper()
            content = match.group(2).strip()

            if content:
                options.append(f"{label}. {content}")

    return options


# ============================================================
# HEADER / FOOTER REMOVAL
# ============================================================

def remove_repeated_headers_footers(lines):
    cleaned = []

    normalized_counts = Counter()

    for line in lines:
        value = normalize_text(line)

        if not value:
            continue

        if len(value) > 120:
            continue

        normalized = re.sub(r"\d+", "#", value.lower())

        normalized_counts[normalized] += 1

    repeated = {
        key
        for key, count in normalized_counts.items()
        if count >= 3
    }

    for line in lines:
        value = normalize_text(line)

        if not value:
            continue

        normalized = re.sub(r"\d+", "#", value.lower())

        if normalized in repeated:
            continue

        cleaned.append(value)

    return cleaned


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):
    text = normalize_text(text)

    if not text:
        return []

    raw_lines = [
        normalize_text(line)
        for line in text.splitlines()
        if normalize_text(line)
    ]

    raw_lines = remove_repeated_headers_footers(raw_lines)

    questions = []

    current = None

    def save_current():
        nonlocal current

        if not current:
            return

        question_text = normalize_text(current["text"])

        if not has_substantive_question_content(question_text):
            current = None
            return

        question_text = remove_question_prefix(question_text)

        options = current.get("options", [])

        if len(options) >= 2:
            question_text += "\n" + "\n".join(options)

        if len(question_text) >= 20:
            questions.append(
                {
                    "number": current.get("number", ""),
                    "text": question_text,
                    "options": options,
                }
            )

        current = None

    for line in raw_lines:

        # ----------------------------------------------------
        # Ignore obvious metadata.
        # ----------------------------------------------------
        if looks_like_metadata(line):
            continue

        # ----------------------------------------------------
        # Ignore obvious standalone headings.
        # ----------------------------------------------------
        if looks_like_heading(line):
            continue

        # ----------------------------------------------------
        # Explicit numbered question.
        # ----------------------------------------------------
        match = QUESTION_START_PATTERN.match(line)

        if match:
            candidate = match.group(1).strip()

            if has_substantive_question_content(candidate):
                save_current()

                current = {
                    "number": extract_question_number(line),
                    "text": candidate,
                    "options": [],
                }

                continue

        # ----------------------------------------------------
        # Question beginning with Q1, Q2, etc.
        # ----------------------------------------------------
        q_match = re.match(
            r"^\s*Q(?:uestion)?\s*(\d{1,3})\s*[:\.\)\-]\s*(.+)$",
            line,
            re.IGNORECASE,
        )

        if q_match:
            candidate = q_match.group(2).strip()

            if has_substantive_question_content(candidate):
                save_current()

                current = {
                    "number": q_match.group(1),
                    "text": candidate,
                    "options": [],
                }

                continue

        # ----------------------------------------------------
        # Option line.
        # ----------------------------------------------------
        if is_option_line(line) and current:
            current["options"].append(line)
            continue

        # ----------------------------------------------------
        # Standalone question sentence.
        # ----------------------------------------------------
        if line.endswith("?") and has_substantive_question_content(line):
            save_current()

            current = {
                "number": "",
                "text": line,
                "options": [],
            }

            continue

        # ----------------------------------------------------
        # Continuation of current question.
        # ----------------------------------------------------
        if current:
            lower = line.lower()

            # Avoid attaching obvious section headings.
            if not looks_like_heading(line):
                current["text"] += " " + line

                # If a sentence ends with ? save it.
                if line.endswith("?"):
                    save_current()

    save_current()

    # --------------------------------------------------------
    # Remove duplicates.
    # --------------------------------------------------------
    unique = []
    seen = set()

    for item in questions:
        key = re.sub(r"\s+", " ", item["text"].lower()).strip()

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# ============================================================
# FILE READING
# ============================================================

def read_pdf(file_bytes):
    text_parts = []

    # First attempt: pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))

        for page in reader.pages:
            page_text = page.extract_text() or ""

            if page_text.strip():
                text_parts.append(page_text)

        if text_parts:
            return "\n".join(text_parts)

    except Exception:
        pass

    # Second attempt: PyMuPDF
    try:
        import fitz

        document = fitz.open(stream=file_bytes, filetype="pdf")

        for page in document:
            page_text = page.get_text("text") or ""

            if page_text.strip():
                text_parts.append(page_text)

        document.close()

        if text_parts:
            return "\n".join(text_parts)

    except Exception:
        pass

    return ""


def read_docx(file_bytes):
    try:
        from docx import Document

        document = Document(io.BytesIO(file_bytes))

        parts = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text)

        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]

                if any(cells):
                    parts.append(" | ".join(cells))

        return "\n".join(parts)

    except Exception:
        return ""


def read_excel(file_bytes, filename):
    try:
        workbook = pd.ExcelFile(io.BytesIO(file_bytes))

        parts = []

        for sheet in workbook.sheet_names:
            dataframe = pd.read_excel(
                io.BytesIO(file_bytes),
                sheet_name=sheet,
                header=None,
            )

            parts.append(f"Sheet: {sheet}")

            for row in dataframe.fillna("").values.tolist():
                row_text = " ".join(
                    str(value).strip()
                    for value in row
                    if str(value).strip()
                )

                if row_text:
                    parts.append(row_text)

        return "\n".join(parts)

    except Exception:
        return ""


def read_uploaded_file(uploaded_file):
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    if filename.endswith(".pdf"):
        return read_pdf(file_bytes)

    if filename.endswith(".docx"):
        return read_docx(file_bytes)

    if filename.endswith((".xlsx", ".xls")):
        return read_excel(file_bytes, filename)

    if filename.endswith(".csv"):
        try:
            dataframe = pd.read_csv(io.BytesIO(file_bytes), header=None)

            return "\n".join(
                " ".join(
                    str(value).strip()
                    for value in row
                    if str(value).strip()
                )
                for row in dataframe.fillna("").values.tolist()
            )

        except Exception:
            return ""

    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, prefix):
    outcomes = []

    if not text:
        return outcomes

    lines = text.splitlines()

    pattern = re.compile(
        rf"^\s*{prefix}\s*[-_ ]?(\d+)\s*[:\-\)]\s*(.+)$",
        re.IGNORECASE,
    )

    for line in lines:
        match = pattern.match(line.strip())

        if match:
            number = match.group(1)
            description = normalize_text(match.group(2))

            if description:
                outcomes.append(
                    {
                        "id": f"{prefix.upper()}{number}",
                        "text": description,
                    }
                )

    # Fallback for semicolon-separated outcomes.
    if not outcomes:
        for part in re.split(r";|\n", text):
            part = normalize_text(part)

            if not part:
                continue

            if len(part.split()) >= 4:
                outcomes.append(
                    {
                        "id": f"{prefix.upper()}?",
                        "text": part,
                    }
                )

    return outcomes


# ============================================================
# COURSE DOMAIN DETECTION
# ============================================================

def determine_course_domain(course_name, clos, plos, assessment_text):
    combined = " ".join(
        [
            course_name or "",
            clos or "",
            plos or "",
        ]
    ).lower()

    # Explicit course alias gets highest priority.
    for alias, domain in sorted(
        COURSE_ALIASES.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    ):
        if alias in combined:
            return domain, 100

    # Domain evidence from course/CLO/PLO.
    scores = {}

    for domain, lexicon in DOMAIN_LEXICONS.items():
        hits = 0

        for term in lexicon:
            if re.search(
                r"\b" + re.escape(term) + r"\b",
                combined,
            ):
                hits += 1

        scores[domain] = hits

    if scores:
        best_domain = max(scores, key=scores.get)
        best_score = scores[best_domain]

        if best_score >= 3:
            confidence = min(95, 50 + best_score * 10)
            return best_domain, confidence

    # Assessment text is only a fallback.
    text_scores = {}

    for domain, lexicon in DOMAIN_LEXICONS.items():
        hits = 0

        for term in lexicon:
            if re.search(
                r"\b" + re.escape(term) + r"\b",
                assessment_text.lower(),
            ):
                hits += 1

        text_scores[domain] = hits

    if text_scores:
        best_domain = max(text_scores, key=text_scores.get)
        best_score = text_scores[best_domain]

        if best_score >= 4:
            confidence = min(80, 40 + best_score * 8)
            return best_domain, confidence

    return "Unknown", 0


# ============================================================
# QUESTION SUBJECT ANALYSIS
# ============================================================

def domain_hits(text, domain):
    hits = []

    if domain not in DOMAIN_LEXICONS:
        return hits

    lower = text.lower()

    for term in DOMAIN_LEXICONS[domain]:
        if re.search(
            r"\b" + re.escape(term) + r"\b",
            lower,
        ):
            hits.append(term)

    return sorted(set(hits))


def all_domain_scores(text):
    scores = {}

    for domain in DOMAIN_LEXICONS:
        scores[domain] = len(domain_hits(text, domain))

    return scores


def question_subject_check(question, expected_domain):
    if expected_domain == "Unknown":
        return {
            "status": "REVIEW",
            "score": 40,
            "detected_domain": "Unknown",
            "evidence": [],
            "reason": "The expected course domain could not be established reliably.",
        }

    scores = all_domain_scores(question)

    expected_hits = scores.get(expected_domain, 0)

    sorted_domains = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    strongest_domain = sorted_domains[0][0]
    strongest_score = sorted_domains[0][1]

    related = RELATED_DOMAINS.get(expected_domain, set())

    related_score = max(
        [scores.get(domain, 0) for domain in related] or [0]
    )

    evidence = domain_hits(question, expected_domain)

    # Strong contradictory evidence.
    if (
        strongest_domain != expected_domain
        and strongest_domain not in related
        and strongest_score >= 3
        and strongest_score >= expected_hits + 2
    ):
        return {
            "status": "FAIL",
            "score": 0,
            "detected_domain": strongest_domain,
            "evidence": domain_hits(question, strongest_domain),
            "reason": (
                f"The question contains stronger evidence for "
                f"{strongest_domain} than for {expected_domain}."
            ),
        }

    # Strong expected-domain evidence.
    if expected_hits >= 3:
        return {
            "status": "PASS",
            "score": 100,
            "detected_domain": expected_domain,
            "evidence": evidence,
            "reason": (
                f"The question contains clear {expected_domain} "
                f"content evidence."
            ),
        }

    if expected_hits >= 1 and related_score == 0:
        return {
            "status": "PASS",
            "score": 80,
            "detected_domain": expected_domain,
            "evidence": evidence,
            "reason": (
                f"The question contains identifiable {expected_domain} "
                f"content."
            ),
        }

    if related_score >= 2:
        related_domain = max(
            related,
            key=lambda x: scores.get(x, 0),
        )

        return {
            "status": "REVIEW",
            "score": 60,
            "detected_domain": related_domain,
            "evidence": domain_hits(question, related_domain),
            "reason": (
                f"The question appears related to {related_domain}, "
                f"but the match with {expected_domain} is not strong "
                f"enough for automatic approval."
            ),
        }

    # No subject evidence.
    return {
        "status": "REVIEW",
        "score": 30,
        "detected_domain": strongest_domain if strongest_score else "Unknown",
        "evidence": (
            domain_hits(question, strongest_domain)
            if strongest_score
            else []
        ),
        "reason": (
            f"There is insufficient subject-specific evidence to confirm "
            f"that the question belongs to {expected_domain}."
        ),
    }


# ============================================================
# ACTION / BLOOM ANALYSIS
# ============================================================

def detect_bloom(question):
    lower = question.lower()

    detected = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                lower,
            ):
                detected.append(
                    {
                        "level": level,
                        "verb": verb,
                    }
                )

    # Numerical indicators strongly suggest Apply.
    if re.search(
        r"\b(calculate|compute|solve|determine|find the value|"
        r"how much|how many|what is the value)\b",
        lower,
    ):
        detected.append(
            {
                "level": "Apply",
                "verb": "calculation/problem solving",
            }
        )

    # Evidence-based judgment.
    if re.search(
        r"\b(justify|defend|evaluate|critique|assess|"
        r"recommend|argue)\b",
        lower,
    ):
        detected.append(
            {
                "level": "Evaluate",
                "verb": "judgment/justification",
            }
        )

    # Design/production.
    if re.search(
        r"\b(design|develop|create|formulate|propose|"
        r"construct|devise)\b",
        lower,
    ):
        detected.append(
            {
                "level": "Create",
                "verb": "design/creation",
            }
        )

    # Remove duplicates.
    unique = []
    seen = set()

    for item in detected:
        key = (item["level"], item["verb"])

        if key not in seen:
            seen.add(key)
            unique.append(item)

    if not unique:
        return {
            "level": "Unknown",
            "confidence": 0,
            "evidence": [],
        }

    # Strongest cognitive demand wins.
    strongest_rank = max(
        BLOOM_RANK[item["level"]]
        for item in unique
    )

    strongest = [
        item
        for item in unique
        if BLOOM_RANK[item["level"]] == strongest_rank
    ]

    return {
        "level": strongest[0]["level"],
        "confidence": min(
            100,
            60 + len(strongest) * 10,
        ),
        "evidence": strongest,
    }


def bloom_alignment(question, intended):
    detected = detect_bloom(question)

    if intended not in BLOOM_LEVELS:
        return {
            "status": "REVIEW",
            "score": 40,
            "detected": detected["level"],
            "evidence": detected["evidence"],
            "reason": "No valid intended Bloom level was provided.",
        }

    if detected["level"] == "Unknown":
        return {
            "status": "REVIEW",
            "score": 40,
            "detected": "Unknown",
            "evidence": [],
            "reason": (
                "The question does not contain enough evidence to "
                "determine its cognitive operation reliably."
            ),
        }

    intended_rank = BLOOM_RANK[intended]
    actual_rank = BLOOM_RANK[detected["level"]]

    difference = actual_rank - intended_rank

    if difference == 0:
        return {
            "status": "PASS",
            "score": 100,
            "detected": detected["level"],
            "evidence": detected["evidence"],
            "reason": (
                f"The question's cognitive operation is consistent "
                f"with {intended}."
            ),
        }

    if abs(difference) == 1:
        return {
            "status": "REVIEW",
            "score": 55,
            "detected": detected["level"],
            "evidence": detected["evidence"],
            "reason": (
                f"The question appears to operate at "
                f"{detected['level']}, while {intended} was entered."
            ),
        }

    return {
        "status": "FAIL",
        "score": 0,
        "detected": detected["level"],
        "evidence": detected["evidence"],
        "reason": (
            f"The question operates at {detected['level']}, "
            f"which does not match the entered Bloom level {intended}."
        ),
    }


# ============================================================
# CLO ACTION ANALYSIS
# ============================================================

def detect_outcome_action(text):
    lower = text.lower()

    matches = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                lower,
            ):
                matches.append(
                    {
                        "level": level,
                        "verb": verb,
                    }
                )

    if not matches:
        return {
            "level": "Unknown",
            "verbs": [],
        }

    strongest_rank = max(
        BLOOM_RANK[item["level"]]
        for item in matches
    )

    strongest = [
        item
        for item in matches
        if BLOOM_RANK[item["level"]] == strongest_rank
    ]

    return {
        "level": strongest[0]["level"],
        "verbs": [x["verb"] for x in strongest],
    }


def extract_action_and_content(text):
    action = detect_outcome_action(text)

    content_tokens = stem_set(text)

    action_words = set()

    for verbs in BLOOM_VERBS.values():
        action_words.update(
            simple_stem(v)
            for v in verbs
        )

    content_tokens = {
        token
        for token in content_tokens
        if token not in action_words
    }

    return {
        "action_level": action["level"],
        "action_verbs": action["verbs"],
        "content_tokens": content_tokens,
    }


# ============================================================
# CLO ALIGNMENT
# ============================================================

def calculate_clo_alignment(question, clos):
    if not clos:
        return {
            "status": "REVIEW",
            "score": 40,
            "matched": None,
            "reason": "No CLO was provided.",
            "content_score": 0,
            "action_score": 0,
        }

    q_info = extract_action_and_content(question)

    best = None

    for clo in clos:
        clo_info = extract_action_and_content(clo["text"])

        content_intersection = (
            q_info["content_tokens"]
            & clo_info["content_tokens"]
        )

        if q_info["content_tokens"] and clo_info["content_tokens"]:
            content_precision = (
                len(content_intersection)
                / len(q_info["content_tokens"])
            )

            content_recall = (
                len(content_intersection)
                / len(clo_info["content_tokens"])
            )

            if content_precision + content_recall:
                content_f1 = (
                    2
                    * content_precision
                    * content_recall
                    / (content_precision + content_recall)
                )
            else:
                content_f1 = 0
        else:
            content_f1 = 0

        clo_level = clo_info["action_level"]
        question_level = q_info["action_level"]

        action_score = 0

        if (
            clo_level != "Unknown"
            and question_level != "Unknown"
        ):
            difference = abs(
                BLOOM_RANK[clo_level]
                - BLOOM_RANK[question_level]
            )

            if difference == 0:
                action_score = 100
            elif difference == 1:
                action_score = 60
            else:
                action_score = 20
        else:
            action_score = 50

        combined = (
            content_f1 * 70
            + action_score * 0.30
        )

        candidate = {
            "clo": clo,
            "score": combined,
            "content_score": content_f1 * 100,
            "action_score": action_score,
            "question_action": question_level,
            "clo_action": clo_level,
            "shared_content": sorted(content_intersection),
        }

        if best is None or candidate["score"] > best["score"]:
            best = candidate

    if best is None:
        return {
            "status": "REVIEW",
            "score": 40,
            "matched": None,
            "reason": "No reliable CLO match was found.",
            "content_score": 0,
            "action_score": 0,
        }

    score = best["score"]

    if score >= 70:
        status = "PASS"
        reason = (
            f"The question assesses content associated with "
            f"{best['clo']['id']} and its action is reasonably "
            f"consistent with the CLO."
        )
    elif score >= 50:
        status = "REVIEW"
        reason = (
            f"The question has partial content/action alignment "
            f"with {best['clo']['id']}."
        )
    else:
        status = "FAIL"
        reason = (
            f"The question does not sufficiently assess "
            f"{best['clo']['id']}."
        )

    return {
        "status": status,
        "score": round(score, 1),
        "matched": best["clo"],
        "reason": reason,
        "content_score": round(best["content_score"], 1),
        "action_score": round(best["action_score"], 1),
        "shared_content": best["shared_content"],
        "question_action": best["question_action"],
        "clo_action": best["clo_action"],
    }


# ============================================================
# PLO CAPABILITY ANALYSIS
# ============================================================

PLO_CAPABILITY_TERMS = {
    "knowledge": {
        "knowledge",
        "understand",
        "principle",
        "concept",
        "theory",
        "fundamental",
        "information",
    },

    "problem_solving": {
        "solve",
        "problem",
        "solution",
        "calculate",
        "apply",
        "application",
        "determine",
        "engineering",
        "technical",
    },

    "analysis": {
        "analyze",
        "analyse",
        "analysis",
        "examine",
        "investigate",
        "interpret",
        "evaluate",
        "data",
        "evidence",
    },

    "communication": {
        "communicate",
        "communication",
        "write",
        "writing",
        "present",
        "presentation",
        "explain",
        "report",
        "document",
    },

    "teamwork": {
        "team",
        "group",
        "collaborate",
        "collaboration",
        "cooperate",
        "teamwork",
    },

    "ethics": {
        "ethical",
        "ethics",
        "professional",
        "responsibility",
        "responsible",
        "integrity",
        "society",
    },

    "design": {
        "design",
        "develop",
        "create",
        "formulate",
        "prototype",
        "solution",
        "plan",
    },

    "technology": {
        "technology",
        "software",
        "tool",
        "computer",
        "digital",
        "technology",
        "technical",
    },

    "lifelong_learning": {
        "learning",
        "learn",
        "research",
        "independent",
        "self",
        "development",
        "lifelong",
    },

    "professionalism": {
        "professional",
        "practice",
        "career",
        "responsibility",
        "standards",
    },
}


def infer_plo_capabilities(text):
    tokens = stem_set(text)

    capabilities = []

    for capability, terms in PLO_CAPABILITY_TERMS.items():
        normalized_terms = {
            simple_stem(term)
            for term in terms
        }

        hits = tokens & normalized_terms

        if hits:
            capabilities.append(
                {
                    "capability": capability,
                    "hits": sorted(hits),
                    "count": len(hits),
                }
            )

    return sorted(
        capabilities,
        key=lambda x: x["count"],
        reverse=True,
    )


def question_capabilities(question):
    lower = question.lower()

    capabilities = set()

    if re.search(
        r"\b(calculate|compute|solve|determine|apply|"
        r"find|derive)\b",
        lower,
    ):
        capabilities.add("problem_solving")

    if re.search(
        r"\b(analyze|analyse|examine|interpret|"
        r"investigate|compare|contrast)\b",
        lower,
    ):
        capabilities.add("analysis")

    if re.search(
        r"\b(explain|describe|summarize|discuss)\b",
        lower,
    ):
        capabilities.add("communication")

    if re.search(
        r"\b(design|develop|create|formulate|"
        r"construct|propose)\b",
        lower,
    ):
        capabilities.add("design")

    if re.search(
        r"\b(justify|evaluate|critique|assess|defend)\b",
        lower,
    ):
        capabilities.add("analysis")

    if re.search(
        r"\b(ethical|professional|responsible|ethics)\b",
        lower,
    ):
        capabilities.add("ethics")

    if re.search(
        r"\b(team|group|collaborate|cooperate)\b",
        lower,
    ):
        capabilities.add("teamwork")

    if not capabilities:
        capabilities.add("knowledge")

    return capabilities


def calculate_plo_alignment(question, plos):
    if not plos:
        return {
            "status": "NOT ASSESSED",
            "score": 100,
            "matched": None,
            "reason": "No PLO was provided.",
            "shared": [],
        }

    q_capabilities = question_capabilities(question)

    best = None

    for plo in plos:
        inferred = infer_plo_capabilities(plo["text"])

        plo_capabilities = {
            item["capability"]
            for item in inferred
        }

        shared_capabilities = q_capabilities & plo_capabilities

        semantic_overlap = overlap_score(
            question,
            plo["text"],
        )

        capability_score = 100 if shared_capabilities else 0

        combined = (
            capability_score * 0.70
            + semantic_overlap * 0.30
        )

        candidate = {
            "plo": plo,
            "score": combined,
            "shared": sorted(shared_capabilities),
        }

        if best is None or candidate["score"] > best["score"]:
            best = candidate

    if best["score"] >= 65:
        status = "PASS"
        reason = (
            f"The question demonstrates capability associated "
            f"with {best['plo']['id']}."
        )
    elif best["score"] >= 40:
        status = "REVIEW"
        reason = (
            f"The question has some evidence of alignment with "
            f"{best['plo']['id']}, but the capability evidence "
            f"is not strong enough for automatic approval."
        )
    else:
        status = "FAIL"
        reason = (
            f"The question does not demonstrate the capability "
            f"described in {best['plo']['id']} strongly enough."
        )

    return {
        "status": status,
        "score": round(best["score"], 1),
        "matched": best["plo"],
        "reason": reason,
        "shared": best["shared"],
    }


# ============================================================
# QUESTION QUALITY
# ============================================================

def assess_question_quality(question, options):
    text = remove_question_prefix(question)
    lower = text.lower()

    clarity = 100
    specificity = 100
    measurability = 100

    if len(text.split()) < 6:
        clarity -= 30

    if len(text.split()) > 100:
        clarity -= 15

    if text.count("?") > 1:
        clarity -= 10

    vague_phrases = [
        "discuss everything",
        "write something",
        "say something",
        "tell me about",
        "what do you know about",
        "explain everything",
        "discuss in detail",
        "give a brief note",
    ]

    for phrase in vague_phrases:
        if phrase in lower:
            specificity -= 30

    if re.search(
        r"\b(something|anything|everything|various things)\b",
        lower,
    ):
        specificity -= 15

    if not re.search(
        r"\b(define|identify|explain|describe|calculate|"
        r"solve|analyze|analyse|evaluate|compare|justify|"
        r"design|develop|determine|interpret|classify|"
        r"construct|derive|discuss)\b",
        lower,
    ):
        measurability -= 20

    if options:
        if len(options) >= 3:
            option_texts = [
                normalize_text(
                    re.sub(
                        r"^\s*[A-Ha-h][\)\].:\-]\s*",
                        "",
                        option,
                    )
                )
                for option in options
            ]

            if len(set(option_texts)) != len(option_texts):
                specificity -= 25

        else:
            specificity -= 15

    clarity = max(0, clarity)
    specificity = max(0, specificity)
    measurability = max(0, measurability)

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
        "score": round(score, 1),
        "clarity": clarity,
        "specificity": specificity,
        "measurability": measurability,
    }


# ============================================================
# DIRECT REVISION GENERATION
# ============================================================

def get_core_content(question, clo_text):
    q_tokens = stem_set(question)
    clo_tokens = stem_set(clo_text)

    shared = q_tokens & clo_tokens

    if shared:
        words = sorted(shared)

        if len(words) > 6:
            words = words[:6]

        return " ".join(words)

    return normalize_text(
        remove_question_prefix(clo_text)
    )


def direct_revision(question, clo, intended_bloom):
    original = remove_question_prefix(question)

    clo_text = clo["text"] if clo else ""

    content = get_core_content(
        original,
        clo_text,
    )

    # Try to preserve concrete technical terms from the
    # original question.
    original_words = [
        word
        for word in re.findall(
            r"\b[A-Za-z][A-Za-z0-9-]+\b",
            original,
        )
        if word.lower() not in STOP_WORDS
    ]

    if original_words:
        technical_phrase = " ".join(original_words[:10])
    else:
        technical_phrase = content

    if intended_bloom == "Remember":
        return (
            f"Identify the key concept, principle, or component "
            f"shown in the question about {technical_phrase}."
        )

    if intended_bloom == "Understand":
        return (
            f"Explain how {technical_phrase} works and why it "
            f"produces the stated result."
        )

    if intended_bloom == "Apply":
        return (
            f"Using the information provided, calculate or "
            f"determine the required result for {technical_phrase}."
        )

    if intended_bloom == "Analyze":
        return (
            f"Analyze the information provided for {technical_phrase} "
            f"and identify the factors responsible for the result."
        )

    if intended_bloom == "Evaluate":
        return (
            f"Evaluate the result for {technical_phrase} and "
            f"justify your conclusion using relevant evidence."
        )

    if intended_bloom == "Create":
        return (
            f"Design a suitable solution for the problem involving "
            f"{technical_phrase} and explain how your solution works."
        )

    return original


# ============================================================
# FINAL QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question_item,
    expected_domain,
    clos,
    plos,
    intended_bloom,
):
    question = question_item["text"]

    subject = question_subject_check(
        question,
        expected_domain,
    )

    # --------------------------------------------------------
    # HARD SUBJECT GATE
    # --------------------------------------------------------
    if subject["status"] == "FAIL":
        return {
            "question": question,
            "number": question_item["number"],
            "options": question_item["options"],
            "subject": subject,
            "clo": None,
            "plo": None,
            "bloom": None,
            "quality": assess_question_quality(
                question,
                question_item["options"],
            ),
            "decision": "REJECTED",
            "overall": 0,
            "reason": (
                "Subject relevance failed. CLO, PLO and Bloom "
                "alignment cannot compensate for a subject mismatch."
            ),
        }

    # --------------------------------------------------------
    # CLO
    # --------------------------------------------------------
    clo_result = calculate_clo_alignment(
        question,
        clos,
    )

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------
    plo_result = calculate_plo_alignment(
        question,
        plos,
    )

    # --------------------------------------------------------
    # BLOOM
    # --------------------------------------------------------
    bloom_result = bloom_alignment(
        question,
        intended_bloom,
    )

    # --------------------------------------------------------
    # QUALITY
    # --------------------------------------------------------
    quality_result = assess_question_quality(
        question,
        question_item["options"],
    )

    # --------------------------------------------------------
    # HARD GATES
    # --------------------------------------------------------

    if subject["status"] == "REVIEW":
        decision = "NEEDS REVIEW"
        reason = (
            "The question may belong to the selected subject, "
            "but subject evidence is not strong enough for automatic approval."
        )

    elif clo_result["status"] == "FAIL":
        decision = "REJECTED"
        reason = (
            "CLO alignment failed. The question does not sufficiently "
            "assess the selected learning outcome."
        )

    elif bloom_result["status"] == "FAIL":
        decision = "REJECTED"
        reason = (
            f"Bloom alignment failed. Entered level: "
            f"{intended_bloom}; detected level: "
            f"{bloom_result['detected']}."
        )

    elif plo_result["status"] == "FAIL":
        decision = "REJECTED"
        reason = (
            "PLO alignment failed. The question does not demonstrate "
            "the capability represented by the selected PLO."
        )

    elif clo_result["status"] == "REVIEW":
        decision = "NEEDS REVIEW"
        reason = (
            "CLO alignment is only partial. The question should be "
            "reviewed before approval."
        )

    elif bloom_result["status"] == "REVIEW":
        decision = "NEEDS REVIEW"
        reason = (
            f"Bloom alignment is uncertain. Entered level: "
            f"{intended_bloom}; detected level: "
            f"{bloom_result['detected']}."
        )

    elif plo_result["status"] == "REVIEW":
        decision = "NEEDS REVIEW"
        reason = (
            "PLO alignment is not sufficiently supported by the "
            "evidence in the question."
        )

    elif quality_result["status"] == "FAIL":
        decision = "NEEDS REVIEW"
        reason = (
            "The question has significant clarity, specificity, "
            "or measurability problems."
        )

    else:
        decision = "APPROVED"
        reason = (
            "The question passed the subject, CLO, Bloom and PLO "
            "alignment gates."
        )

    overall = (
        subject["score"] * 0.30
        + clo_result["score"] * 0.25
        + plo_result["score"] * 0.15
        + bloom_result["score"] * 0.15
        + quality_result["score"] * 0.15
    )

    return {
        "question": question,
        "number": question_item["number"],
        "options": question_item["options"],
        "subject": subject,
        "clo": clo_result,
        "plo": plo_result,
        "bloom": bloom_result,
        "quality": quality_result,
        "decision": decision,
        "overall": round(overall, 1),
        "reason": reason,
    }


# ============================================================
# CLEAN DOCUMENT PREVIEW
# ============================================================

def clean_document_for_preview(text):
    lines = []

    for line in text.splitlines():
        value = normalize_text(line)

        if not value:
            continue

        if looks_like_metadata(value):
            continue

        lines.append(value)

    return "\n".join(lines)


# ============================================================
# CSV EXPORT
# ============================================================

def results_to_dataframe(results):
    rows = []

    for result in results:
        clo_id = ""
        clo_score = 0

        if result["clo"]:
            if result["clo"].get("matched"):
                clo_id = result["clo"]["matched"]["id"]

            clo_score = result["clo"].get("score", 0)

        plo_id = ""
        plo_score = 0

        if result["plo"]:
            if result["plo"].get("matched"):
                plo_id = result["plo"]["matched"]["id"]

            plo_score = result["plo"].get("score", 0)

        bloom_detected = ""

        if result["bloom"]:
            bloom_detected = result["bloom"].get(
                "detected",
                "",
            )

        rows.append(
            {
                "Question No": result["number"],
                "Question": result["question"],
                "Decision": result["decision"],
                "Overall Score": result["overall"],
                "Subject Status": result["subject"]["status"],
                "Subject Score": result["subject"]["score"],
                "Detected Subject": result["subject"]["detected_domain"],
                "CLO": clo_id,
                "CLO Score": clo_score,
                "PLO": plo_id,
                "PLO Score": plo_score,
                "Entered Bloom": "",
                "Detected Bloom": bloom_detected,
                "Bloom Score": (
                    result["bloom"]["score"]
                    if result["bloom"]
                    else 0
                ),
                "Quality Score": result["quality"]["score"],
                "Reason": result["reason"],
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# APPLICATION UI
# ============================================================

st.title("🎓 OBE Assessment Alignment Checker")

st.write(
    "Evaluate assessment questions against the selected subject, "
    "CLO, PLO and Bloom's Taxonomy level."
)

st.info(
    "The evaluator first validates whether extracted text is a genuine "
    "assessment question. Page numbers, dates, times, headings, metadata "
    "and document headers are excluded before alignment is calculated."
)


# ============================================================
# COURSE INFORMATION
# ============================================================

st.subheader("1. Assessment Context")

course_name = st.text_input(
    "Course / Subject Name",
    placeholder="Example: General Chemistry",
)

intended_bloom = st.selectbox(
    "Intended Bloom's Taxonomy Level",
    BLOOM_LEVELS,
    index=1,
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
            "CLO2: Apply stoichiometric principles to solve chemical problems."
        ),
    )

with col2:
    plo_text = st.text_area(
        "Enter PLOs",
        height=220,
        placeholder=(
            "PLO1: Apply knowledge of mathematics and science.\n"
            "PLO2: Analyze and solve technical problems."
        ),
    )


clos = parse_outcomes(clo_text, "CLO")
plos = parse_outcomes(plo_text, "PLO")


if clos:
    st.success(
        f"{len(clos)} CLO(s) detected."
    )
else:
    st.warning(
        "No CLO was detected. Use the format CLO1: description."
    )


if plos:
    st.success(
        f"{len(plos)} PLO(s) detected."
    )
else:
    st.warning(
        "No PLO was detected. Use the format PLO1: description."
    )


# ============================================================
# INPUT SOURCE
# ============================================================

st.subheader("2. Assessment File")

uploaded_file = st.file_uploader(
    "Upload the complete assessment",
    type=[
        "pdf",
        "docx",
        "txt",
        "csv",
        "xlsx",
        "xls",
    ],
)

manual_text = st.text_area(
    "Or paste assessment text",
    height=250,
    placeholder="Paste the complete assessment here...",
)


# ============================================================
# EVALUATION
# ============================================================

if st.button(
    "🔍 Evaluate Assessment",
    type="primary",
    use_container_width=True,
):

    if not course_name.strip():
        st.error(
            "Please enter the course / subject name."
        )
        st.stop()

    if not clos:
        st.error(
            "Please enter at least one CLO."
        )
        st.stop()

    if uploaded_file:
        assessment_text = read_uploaded_file(
            uploaded_file
        )

        if not assessment_text.strip():
            st.error(
                "The uploaded file could not be read. "
                "For scanned PDFs, OCR is required."
            )
            st.stop()

    elif manual_text.strip():
        assessment_text = manual_text

    else:
        st.error(
            "Upload an assessment file or paste the assessment text."
        )
        st.stop()

    assessment_text = normalize_text(
        assessment_text
    )

    # --------------------------------------------------------
    # Course detection
    # --------------------------------------------------------

    detected_domain, confidence = determine_course_domain(
        course_name,
        clo_text,
        plo_text,
        assessment_text,
    )

    st.session_state["assessment_text"] = assessment_text
    st.session_state["detected_domain"] = detected_domain
    st.session_state["confidence"] = confidence

    # --------------------------------------------------------
    # Question extraction
    # --------------------------------------------------------

    questions = extract_questions(
        assessment_text
    )

    st.session_state["questions"] = questions

    if not questions:
        st.error(
            "No genuine assessment questions were detected."
        )

        st.warning(
            "The document may contain scanned images, "
            "unusual formatting, or questions that are not "
            "extractable as text."
        )

        st.stop()

    # --------------------------------------------------------
    # Evaluate
    # --------------------------------------------------------

    results = []

    for question_item in questions:
        result = evaluate_question(
            question_item,
            detected_domain,
            clos,
            plos,
            intended_bloom,
        )

        result["entered_bloom"] = intended_bloom

        results.append(result)

    st.session_state["results"] = results


# ============================================================
# DISPLAY RESULTS
# ============================================================

if "results" in st.session_state:

    results = st.session_state["results"]

    detected_domain = st.session_state.get(
        "detected_domain",
        "Unknown",
    )

    confidence = st.session_state.get(
        "confidence",
        0,
    )

    st.divider()

    st.subheader("3. Assessment Context Detection")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Detected Subject",
            detected_domain,
        )

    with c2:
        st.metric(
            "Context Confidence",
            f"{confidence}%",
        )

    with c3:
        st.metric(
            "Questions Extracted",
            len(results),
        )


    # ========================================================
    # EXTRACTION VALIDATION
    # ========================================================

    st.subheader("4. Extracted Questions")

    st.caption(
        "Only text that passes the question-validation rules is "
        "evaluated. Metadata such as '19/26', '5:27 AM', "
        "'QuestionWell General Chemistry Question Set', "
        "and standalone headings are excluded."
    )

    extraction_rows = []

    for result in results:
        extraction_rows.append(
            {
                "No.": result["number"],
                "Question": result["question"],
            }
        )

    extraction_df = pd.DataFrame(
        extraction_rows
    )

    st.dataframe(
        extraction_df,
        use_container_width=True,
        hide_index=True,
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    st.subheader("5. Evaluation Summary")

    approved = sum(
        1
        for result in results
        if result["decision"] == "APPROVED"
    )

    rejected = sum(
        1
        for result in results
        if result["decision"] == "REJECTED"
    )

    review = sum(
        1
        for result in results
        if result["decision"] == "NEEDS REVIEW"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Questions",
            len(results),
        )

    with col2:
        st.metric(
            "Approved",
            approved,
        )

    with col3:
        st.metric(
            "Rejected",
            rejected,
        )

    with col4:
        st.metric(
            "Needs Review",
            review,
        )


    # ========================================================
    # SUMMARY TABLE
    # ========================================================

    summary_rows = []

    for result in results:

        clo_id = ""

        if result["clo"] and result["clo"].get("matched"):
            clo_id = result["clo"]["matched"]["id"]

        plo_id = ""

        if result["plo"] and result["plo"].get("matched"):
            plo_id = result["plo"]["matched"]["id"]

        bloom_detected = ""

        if result["bloom"]:
            bloom_detected = result["bloom"].get(
                "detected",
                "",
            )

        summary_rows.append(
            {
                "No.": result["number"],
                "Decision": result["decision"],
                "Overall": result["overall"],
                "Subject": result["subject"]["status"],
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
                "Entered Bloom": result["entered_bloom"],
                "Detected Bloom": bloom_detected,
                "Bloom Alignment": (
                    result["bloom"]["score"]
                    if result["bloom"]
                    else 0
                ),
            }
        )

    summary_df = pd.DataFrame(
        summary_rows
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
    )


    # ========================================================
    # DETAILED EVALUATION
    # ========================================================

    st.subheader("6. Detailed Alignment Analysis")

    for index, result in enumerate(results, start=1):

        number = result["number"] or str(index)

        with st.expander(
            f"Question {number} — {result['decision']}",
            expanded=False,
        ):

            st.markdown("### Question")

            st.write(
                result["question"]
            )

            if result["options"]:
                st.markdown("**Options detected:**")

                for option in result["options"]:
                    st.write(option)


            # ------------------------------------------------
            # SUBJECT
            # ------------------------------------------------

            st.markdown("### Subject Relevance")

            subject = result["subject"]

            if subject["status"] == "PASS":
                st.success(
                    f"PASS — {subject['score']}%"
                )

            elif subject["status"] == "FAIL":
                st.error(
                    "FAIL — 0%"
                )

            else:
                st.warning(
                    f"NEEDS REVIEW — {subject['score']}%"
                )

            st.write(
                f"Detected subject: "
                f"**{subject['detected_domain']}**"
            )

            if subject["evidence"]:
                st.write(
                    "Evidence: "
                    + ", ".join(
                        subject["evidence"]
                    )
                )

            st.caption(
                subject["reason"]
            )


            # ------------------------------------------------
            # STOP DOWNSTREAM ANALYSIS IF SUBJECT FAILS
            # ------------------------------------------------

            if subject["status"] == "FAIL":

                st.error(
                    "Downstream CLO/PLO/Bloom approval is blocked "
                    "because the subject gate failed."
                )

                st.error(
                    f"Final Decision: {result['decision']}"
                )

                continue


            # ------------------------------------------------
            # CLO
            # ------------------------------------------------

            st.markdown("### CLO Alignment")

            clo_result = result["clo"]

            if clo_result["status"] == "PASS":
                st.success(
                    f"PASS — {clo_result['score']}%"
                )

            elif clo_result["status"] == "FAIL":
                st.error(
                    f"FAIL — {clo_result['score']}%"
                )

            else:
                st.warning(
                    f"NEEDS REVIEW — {clo_result['score']}%"
                )

            if clo_result.get("matched"):
                st.write(
                    f"Matched: **{clo_result['matched']['id']}**"
                )

                st.write(
                    clo_result["matched"]["text"]
                )

            st.write(
                f"Content alignment: "
                f"**{clo_result.get('content_score', 0)}%**"
            )

            st.write(
                f"Action alignment: "
                f"**{clo_result.get('action_score', 0)}%**"
            )

            if clo_result.get("shared_content"):
                st.write(
                    "Shared content evidence: "
                    + ", ".join(
                        clo_result["shared_content"]
                    )
                )

            st.caption(
                clo_result["reason"]
            )


            # ------------------------------------------------
            # PLO
            # ------------------------------------------------

            st.markdown("### PLO Alignment")

            plo_result = result["plo"]

            if plo_result["status"] == "PASS":
                st.success(
                    f"PASS — {plo_result['score']}%"
                )

            elif plo_result["status"] == "FAIL":
                st.error(
                    f"FAIL — {plo_result['score']}%"
                )

            else:
                st.warning(
                    f"NEEDS REVIEW — {plo_result['score']}%"
                )

            if plo_result.get("matched"):
                st.write(
                    f"Matched: **{plo_result['matched']['id']}**"
                )

                st.write(
                    plo_result["matched"]["text"]
                )

            if plo_result.get("shared"):
                st.write(
                    "Capability evidence: "
                    + ", ".join(
                        plo_result["shared"]
                    )
                )

            st.caption(
                plo_result["reason"]
            )


            # ------------------------------------------------
            # BLOOM
            # ------------------------------------------------

            st.markdown("### Bloom's Taxonomy")

            bloom_result = result["bloom"]

            st.write(
                f"Entered level: "
                f"**{result['entered_bloom']}**"
            )

            st.write(
                f"Detected level: "
                f"**{bloom_result['detected']}**"
            )

            if bloom_result["status"] == "PASS":
                st.success(
                    f"PASS — {bloom_result['score']}%"
                )

            elif bloom_result["status"] == "FAIL":
                st.error(
                    f"FAIL — {bloom_result['score']}%"
                )

            else:
                st.warning(
                    f"NEEDS REVIEW — {bloom_result['score']}%"
                )

            if bloom_result.get("evidence"):
                evidence_text = []

                for item in bloom_result["evidence"]:
                    evidence_text.append(
                        f"{item['verb']} → {item['level']}"
                    )

                st.write(
                    "Cognitive evidence: "
                    + "; ".join(evidence_text)
                )

            st.caption(
                bloom_result["reason"]
            )


            # ------------------------------------------------
            # QUESTION QUALITY
            # ------------------------------------------------

            st.markdown("### Question Effectiveness")

            quality = result["quality"]

            q1, q2, q3, q4 = st.columns(4)

            with q1:
                st.metric(
                    "Overall",
                    f"{quality['score']}%",
                )

            with q2:
                st.metric(
                    "Clarity",
                    f"{quality['clarity']}%",
                )

            with q3:
                st.metric(
                    "Specificity",
                    f"{quality['specificity']}%",
                )

            with q4:
                st.metric(
                    "Measurability",
                    f"{quality['measurability']}%",
                )


            # ------------------------------------------------
            # FINAL DECISION
            # ------------------------------------------------

            st.markdown("### Final Decision")

            if result["decision"] == "APPROVED":
                st.success(
                    "APPROVED"
                )

            elif result["decision"] == "REJECTED":
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
            # DIRECT REVISION
            # ------------------------------------------------

            if result["decision"] != "APPROVED":

                st.markdown(
                    "### Direct Revision"
                )

                matched_clo = None

                if result["clo"]:
                    matched_clo = result["clo"].get(
                        "matched"
                    )

                if matched_clo:

                    revised = direct_revision(
                        result["question"],
                        matched_clo,
                        result["entered_bloom"],
                    )

                    st.info(
                        revised
                    )

                    st.caption(
                        "The revision preserves the subject/content "
                        "while changing the question to target the "
                        "entered Bloom level. It does not insert CLO "
                        "or PLO wording into the question."
                    )


    # ========================================================
    # QUESTIONS REQUIRING ACTION
    # ========================================================

    st.subheader("7. Questions Requiring Action")

    action_results = [
        result
        for result in results
        if result["decision"] != "APPROVED"
    ]

    if action_results:

        for result in action_results:

            number = (
                result["number"]
                if result["number"]
                else "?"
            )

            st.markdown(
                f"**Question {number}: "
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

    st.subheader("8. Bloom's Taxonomy Distribution")

    bloom_counts = Counter()

    for result in results:

        if result["bloom"]:
            detected = result["bloom"].get(
                "detected",
                "Unknown",
            )

            bloom_counts[detected] += 1

    bloom_table = pd.DataFrame(
        [
            {
                "Bloom Level": level,
                "Questions": bloom_counts.get(
                    level,
                    0,
                ),
            }
            for level in BLOOM_LEVELS
        ]
        + [
            {
                "Bloom Level": "Unknown",
                "Questions": bloom_counts.get(
                    "Unknown",
                    0,
                ),
            }
        ]
    )

    st.dataframe(
        bloom_table,
        use_container_width=True,
        hide_index=True,
    )


    # ========================================================
    # CLO COVERAGE
    # ========================================================

    st.subheader("9. CLO Coverage")

    clo_coverage = Counter()

    for result in results:

        if result["clo"] and result["clo"].get("matched"):
            clo_coverage[
                result["clo"]["matched"]["id"]
            ] += 1

    if clo_coverage:

        clo_rows = []

        for clo in clos:
            clo_rows.append(
                {
                    "CLO": clo["id"],
                    "Questions": clo_coverage.get(
                        clo["id"],
                        0,
                    ),
                    "CLO Description": clo["text"],
                }
            )

        st.dataframe(
            pd.DataFrame(clo_rows),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "No reliable CLO coverage could be established."
        )


    # ========================================================
    # DOWNLOAD RESULTS
    # ========================================================

    st.subheader("10. Export Results")

    export_df = results_to_dataframe(
        results
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Evaluation Results",
        data=csv_data,
        file_name="OBE_Assessment_Evaluation.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ============================================================
# INFORMATION PANEL
# ============================================================

with st.sidebar:

    st.header("Evaluation Logic")

    st.markdown(
        """
### Hard Gates

**1. Subject Relevance**
    
The question must belong to the selected subject.

**2. CLO Alignment**

The question must assess the content and action represented by the CLO.

**3. Bloom Alignment**

The actual cognitive operation must match the Bloom level entered.

**4. PLO Alignment**

The question must demonstrate the capability represented by the PLO.

### Important Rule

A high score in one category cannot compensate for failure in another.

For example:

**Subject FAIL + CLO 95% + PLO 95% = REJECTED**

### Question Extraction

The tool excludes:

- Page numbers
- Dates
- Times
- File metadata
- Repeated headers
- Repeated footers
- Section headings
- QuestionWell headings
- Standalone course titles
- Standalone numbers

Only validated assessment questions are evaluated.

### Assessment Types

The extractor is not limited to MCQs.

It can process:

- MCQs
- Short-answer questions
- Long-answer questions
- Essays
- Numerical problems
- Case studies
- True/False
- Practical questions
- Problem-solving questions
- Analytical questions
"""
    )
