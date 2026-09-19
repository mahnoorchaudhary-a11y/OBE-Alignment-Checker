import io
import re
from collections import Counter
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


# ============================================================
# OPTIONAL LIBRARIES
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
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

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
    layout="wide",
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
        "define", "list", "name", "identify", "state",
        "recall", "recognize", "select", "label", "match",
        "mention", "give"
    },
    "Understand": {
        "explain", "describe", "summarize", "interpret",
        "classify", "discuss", "illustrate", "paraphrase",
        "clarify", "outline", "distinguish"
    },
    "Apply": {
        "calculate", "compute", "solve", "use", "apply",
        "demonstrate", "execute", "implement", "perform",
        "determine", "show"
    },
    "Analyze": {
        "analyze", "analyse", "compare", "contrast",
        "differentiate", "examine", "investigate",
        "categorize", "deconstruct", "relate", "separate"
    },
    "Evaluate": {
        "evaluate", "assess", "judge", "justify", "critique",
        "defend", "appraise", "argue", "validate", "recommend"
    },
    "Create": {
        "create", "design", "develop", "construct", "formulate",
        "produce", "propose", "generate", "compose", "plan",
        "invent"
    },
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because",
    "been", "being", "but", "by", "can", "could", "did",
    "do", "does", "for", "from", "had", "has", "have", "he",
    "her", "here", "him", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "may", "might", "more", "most",
    "must", "of", "on", "or", "our", "should", "so", "than",
    "that", "the", "their", "them", "then", "there", "these",
    "they", "this", "those", "to", "under", "was", "we",
    "were", "what", "when", "where", "which", "who", "why",
    "will", "with", "would", "you", "your", "using", "use",
    "following", "given"
}


# ============================================================
# SUBJECT LEXICONS
# ============================================================

DOMAIN_LEXICONS = {
    "Chemistry": {
        "atom", "molecule", "element", "compound", "ion", "bond",
        "ionic", "covalent", "molarity", "mole", "stoichiometry",
        "reaction", "equilibrium", "acid", "base", "ph", "buffer",
        "oxidation", "reduction", "redox", "enthalpy", "entropy",
        "thermodynamics", "organic", "inorganic", "alkane",
        "alkene", "alkyne", "benzene", "polymer", "periodic",
        "electron", "proton", "neutron", "isotope", "catalyst",
        "precipitate", "titration", "solution", "concentration",
        "solubility", "spectroscopy", "nmr", "infrared",
        "chromatography"
    },

    "Physics": {
        "force", "motion", "velocity", "acceleration", "momentum",
        "energy", "work", "power", "mass", "gravity", "friction",
        "wave", "frequency", "wavelength", "optics", "lens",
        "electric", "electricity", "voltage", "current",
        "resistance", "circuit", "magnetic", "field", "charge",
        "potential", "quantum", "relativity", "pressure",
        "density", "kinetic", "projectile"
    },

    "Mathematics": {
        "equation", "algebra", "calculus", "derivative", "integral",
        "function", "matrix", "vector", "probability", "statistics",
        "mean", "median", "variance", "deviation", "geometry",
        "trigonometry", "logarithm", "polynomial", "limit",
        "theorem", "proof", "sequence", "series", "differential",
        "linear", "quadratic"
    },

    "Computer Science": {
        "algorithm", "program", "programming", "code", "python",
        "java", "javascript", "database", "sql", "network",
        "computer", "software", "hardware", "operating", "system",
        "data", "structure", "array", "linked", "list", "stack",
        "queue", "tree", "graph", "recursion", "class", "object",
        "inheritance", "polymorphism", "compiler", "api",
        "machine", "learning", "artificial", "intelligence",
        "cybersecurity", "encryption", "binary", "computational"
    },

    "Biology": {
        "cell", "organism", "tissue", "organ", "gene", "genetic",
        "dna", "rna", "protein", "enzyme", "metabolism", "mitosis",
        "meiosis", "chromosome", "evolution", "species", "ecology",
        "ecosystem", "photosynthesis", "respiration", "membrane",
        "bacteria", "virus", "microbiology", "physiology",
        "anatomy", "homeostasis", "mutation", "heredity"
    },

    "English / Language": {
        "grammar", "sentence", "paragraph", "essay", "writing",
        "reading", "author", "tone", "purpose", "main", "idea",
        "thesis", "argument", "rhetorical", "audience",
        "vocabulary", "syntax", "morphology", "phonology",
        "semantics", "pragmatics", "paraphrase", "summarize",
        "composition", "communication", "language", "discourse",
        "pronunciation", "listening", "speaking", "literacy"
    },

    "Literature": {
        "novel", "poem", "poetry", "fiction", "character", "plot",
        "setting", "theme", "symbolism", "metaphor", "imagery",
        "narrator", "narrative", "protagonist", "antagonist",
        "drama", "tragedy", "sonnet", "literary", "interpretation",
        "literature", "genre"
    },

    "Business / Management": {
        "management", "manager", "leadership", "organization",
        "organizational", "strategy", "marketing", "market",
        "consumer", "customer", "business", "entrepreneur",
        "entrepreneurship", "planning", "decision", "stakeholder",
        "human", "resources", "motivation", "performance",
        "operations", "supply", "chain", "competitive",
        "advantage", "corporate", "culture"
    },

    "Accounting / Finance": {
        "accounting", "account", "ledger", "journal", "balance",
        "sheet", "income", "statement", "asset", "liability",
        "equity", "revenue", "expense", "profit", "depreciation",
        "audit", "financial", "cash", "flow", "budget", "tax",
        "investment", "portfolio", "interest", "present", "value",
        "capital", "ratio", "dividend"
    },

    "Economics": {
        "economics", "economic", "demand", "supply", "price",
        "market", "inflation", "unemployment", "gdp", "fiscal",
        "monetary", "policy", "elasticity", "utility", "consumer",
        "producer", "equilibrium", "macro", "micro", "trade",
        "exchange", "currency", "opportunity", "cost"
    },

    "Engineering": {
        "engineering", "design", "mechanical", "electrical",
        "civil", "structural", "material", "machine", "stress",
        "strain", "load", "beam", "circuit", "voltage", "current",
        "thermodynamics", "fluid", "control", "manufacturing",
        "prototype", "cad", "system", "process"
    },

    "Psychology": {
        "psychology", "behavior", "behaviour", "cognitive",
        "memory", "perception", "emotion", "personality",
        "learning", "development", "motivation", "psychological",
        "therapy", "conditioning", "reinforcement", "mental",
        "social", "attitude", "intelligence"
    },

    "Sociology": {
        "society", "social", "sociology", "culture", "community",
        "class", "inequality", "gender", "institution", "family",
        "socialization", "deviance", "norm", "status", "role",
        "population", "urbanization", "globalization"
    },

    "Education": {
        "education", "teaching", "learning", "pedagogy", "curriculum",
        "instruction", "assessment", "classroom", "teacher",
        "student", "lesson", "outcome", "rubric", "evaluation",
        "educational", "formative", "summative"
    },

    "History": {
        "history", "historical", "empire", "war", "revolution",
        "colonial", "colonialism", "independence", "treaty",
        "dynasty", "kingdom", "civilization", "ancient", "medieval",
        "movement", "era", "century", "migration"
    },

    "Law": {
        "law", "legal", "court", "contract", "tort", "crime",
        "criminal", "civil", "statute", "constitution",
        "constitutional", "judgment", "judge", "liability",
        "negligence", "case", "precedent", "plaintiff",
        "defendant", "jurisdiction", "legislation"
    },

    "Pharmacy": {
        "pharmacy", "drug", "medicine", "dosage", "dose",
        "pharmacology", "pharmacokinetics", "tablet", "capsule",
        "prescription", "therapeutic", "adverse", "formulation",
        "bioavailability", "receptor", "antibiotic", "interaction"
    },

    "Medical / Health Sciences": {
        "patient", "disease", "diagnosis", "symptom", "clinical",
        "medical", "health", "anatomy", "physiology", "pathology",
        "treatment", "therapy", "infection", "hospital", "nursing",
        "blood", "heart", "lung", "syndrome"
    },

    "Environmental Science": {
        "environment", "ecosystem", "pollution", "climate",
        "biodiversity", "conservation", "sustainability", "waste",
        "water", "air", "soil", "renewable", "carbon", "greenhouse",
        "ecology", "deforestation", "resource"
    }
}


DOMAIN_ALIASES = {
    "chemistry": "Chemistry",
    "general chemistry": "Chemistry",
    "organic chemistry": "Chemistry",
    "physics": "Physics",
    "mathematics": "Mathematics",
    "math": "Mathematics",
    "statistics": "Mathematics",
    "calculus": "Mathematics",
    "computer science": "Computer Science",
    "programming": "Computer Science",
    "software engineering": "Computer Science",
    "information technology": "Computer Science",
    "english": "English / Language",
    "english i": "English / Language",
    "english language": "English / Language",
    "linguistics": "English / Language",
    "literature": "Literature",
    "business": "Business / Management",
    "management": "Business / Management",
    "marketing": "Business / Management",
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
    "environmental science": "Environmental Science",
}


# ============================================================
# TEXT FUNCTIONS
# ============================================================

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\ufeff", "")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def stem(word: str) -> str:
    word = word.lower()

    if len(word) <= 4:
        return word

    suffixes = [
        "ization", "ational", "fulness", "ousness",
        "iveness", "ments", "ment", "ingly", "edly",
        "ation", "ions", "tion", "ing", "ers", "ies",
        "es", "ed", "ly", "s"
    ]

    for suffix in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[:-len(suffix)]

    return word


def tokens(text: str) -> set:
    result = set()

    for word in normalize(text).split():
        if word in STOP_WORDS:
            continue

        if len(word) < 3:
            continue

        result.add(stem(word))

    return result


# ============================================================
# FILE READING
# ============================================================

def check_tesseract():
    if pytesseract is None:
        return False

    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def render_for_ocr(page):
    if fitz is None or Image is None:
        return None

    try:
        matrix = fitz.Matrix(2.5, 2.5)
        pix = page.get_pixmap(
            matrix=matrix,
            alpha=False,
            colorspace=fitz.csRGB
        )

        image = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

        if ImageOps is not None:
            image = ImageOps.grayscale(image)
            image = ImageOps.autocontrast(image)

        return image

    except Exception:
        return None


def extract_pdf(file_bytes: bytes):
    if fitz is None:
        return "", "PyMuPDF is not installed.", {}

    try:
        doc = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )
    except Exception as exc:
        return "", f"Could not open PDF: {exc}", {}

    page_text = []
    text_pages = 0
    ocr_pages = 0
    failed_ocr = 0

    for page in doc:
        try:
            text = page.get_text("text") or ""
        except Exception:
            text = ""

        text = clean_text(text)

        if len(re.sub(r"\s+", "", text)) >= 25:
            page_text.append(text)
            text_pages += 1
        else:
            page_text.append("")

    for index, text in enumerate(page_text):
        if text:
            continue

        if not check_tesseract():
            failed_ocr += 1
            continue

        image = render_for_ocr(doc[index])

        if image is None:
            failed_ocr += 1
            continue

        try:
            ocr = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6"
            )

            ocr = clean_text(ocr)

            if len(re.sub(r"\s+", "", ocr)) >= 15:
                page_text[index] = ocr
                ocr_pages += 1
            else:
                failed_ocr += 1

        except Exception:
            failed_ocr += 1

    parts = []

    for i, text in enumerate(page_text):
        if text:
            parts.append(
                f"--- PAGE {i + 1} ---\n{text}"
            )

    combined = "\n\n".join(parts)

    diagnostics = {
        "pages": len(doc),
        "text_pages": text_pages,
        "ocr_pages": ocr_pages,
        "failed_ocr": failed_ocr,
        "method": (
            "Text extraction + OCR"
            if ocr_pages
            else "Text extraction"
        )
    }

    if not combined:
        if not check_tesseract():
            return (
                "",
                "The PDF is scanned/image-based and OCR is unavailable. "
                "Install Tesseract using packages.txt.",
                diagnostics
            )

        return (
            "",
            "The PDF was opened but no readable text was detected.",
            diagnostics
        )

    return combined, "", diagnostics


def extract_docx(file_bytes: bytes):
    if Document is None:
        return "", "python-docx is not installed.", {}

    try:
        doc = Document(io.BytesIO(file_bytes))
        parts = []

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()

            if text:
                parts.append(text)

        for table in doc.tables:
            for row in table.rows:
                values = []

                for cell in row.cells:
                    value = cell.text.strip()

                    if value:
                        values.append(value)

                if values:
                    parts.append(" | ".join(values))

        return "\n".join(parts), "", {
            "method": "DOCX extraction"
        }

    except Exception as exc:
        return "", f"Could not read DOCX: {exc}", {}


def extract_excel(file_bytes: bytes):
    try:
        book = pd.ExcelFile(io.BytesIO(file_bytes))
        parts = []

        for sheet in book.sheet_names:
            parts.append(f"--- SHEET: {sheet} ---")

            frame = pd.read_excel(
                book,
                sheet_name=sheet,
                header=None
            )

            for row in frame.fillna("").astype(str).values:
                values = [
                    x.strip()
                    for x in row
                    if x.strip()
                ]

                if values:
                    parts.append(" | ".join(values))

        return "\n".join(parts), "", {
            "method": "Excel extraction"
        }

    except Exception as exc:
        return "", f"Could not read Excel file: {exc}", {}


def extract_csv(file_bytes: bytes):
    try:
        frame = pd.read_csv(
            io.BytesIO(file_bytes),
            header=None
        )

        parts = []

        for row in frame.fillna("").astype(str).values:
            values = [
                x.strip()
                for x in row
                if x.strip()
            ]

            if values:
                parts.append(" | ".join(values))

        return "\n".join(parts), "", {
            "method": "CSV extraction"
        }

    except Exception:
        try:
            return file_bytes.decode(
                "utf-8",
                errors="ignore"
            ), "", {
                "method": "Text extraction"
            }
        except Exception as exc:
            return "", str(exc), {}


def extract_file(uploaded_file):
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        return extract_pdf(data)

    if name.endswith(".docx"):
        return extract_docx(data)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return extract_excel(data)

    if name.endswith(".csv"):
        return extract_csv(data)

    if name.endswith(".txt"):
        return (
            data.decode("utf-8", errors="ignore"),
            "",
            {"method": "Text extraction"}
        )

    return (
        "",
        "Unsupported file. Use PDF, DOCX, TXT, CSV, XLSX, or XLS.",
        {}
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

PAGE_RE = re.compile(
    r"^\s*(?:page\s*)?\d+\s*(?:/|of)\s*\d+\s*$",
    re.I
)

TIME_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*$",
    re.I
)

DATE_RE = re.compile(
    r"^\s*(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r"|\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*$"
)

NUMBERED_RE = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})"
    r"\s*[\.\):\-]\s*(.+)$",
    re.I
)

OPTION_RE = re.compile(
    r"^\s*(?:\(?[A-Da-d]\)|[A-Da-d][\.\:]|"
    r"\(?[1-4]\))\s+.+$"
)

COMMAND_WORDS = set()

for level_words in BLOOM_VERBS.values():
    COMMAND_WORDS.update(level_words)

COMMAND_WORDS.update({
    "define", "explain", "describe", "discuss",
    "calculate", "solve", "compare", "contrast",
    "analyze", "analyse", "evaluate", "assess",
    "justify", "design", "develop", "derive",
    "determine", "state", "list", "name",
    "identify", "distinguish", "interpret",
    "apply", "demonstrate", "illustrate",
    "critique", "construct", "formulate",
    "propose", "compute", "examine",
    "investigate", "show", "prove"
})


def looks_like_metadata(line: str) -> bool:
    text = clean_text(line)

    if not text:
        return True

    if PAGE_RE.match(text):
        return True

    if TIME_RE.match(text):
        return True

    if DATE_RE.match(text):
        return True

    lowered = text.lower()

    bad_phrases = [
        "questionwell",
        "question set",
        "generated by",
        "answer key",
        "general chemistry + questionwell",
        "page ",
        "student name",
        "roll number",
        "registration number",
        "date:",
        "time:",
        "course code:",
        "course title:",
        "instructor:",
    ]

    for phrase in bad_phrases:
        if phrase in lowered:
            return True

    if re.fullmatch(r"[/\\\d\-\s]+", text):
        return True

    return False


def valid_question_start(text: str) -> bool:
    text = clean_text(text)

    if not text:
        return False

    if looks_like_metadata(text):
        return False

    words = normalize(text).split()

    if len(words) < 5:
        return False

    if text.endswith("?"):
        return True

    first = words[0] if words else ""

    if first in COMMAND_WORDS:
        return True

    if first in {
        "what", "why", "how", "which",
        "when", "where", "who"
    }:
        return True

    return False


def remove_options(text: str) -> str:
    lines = text.splitlines()
    kept = []

    for line in lines:
        if OPTION_RE.match(line):
            continue

        kept.append(line)

    return clean_text(" ".join(kept))


def extract_questions(text: str):
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    raw_lines = [
        clean_text(x)
        for x in text.split("\n")
    ]

    raw_lines = [
        x for x in raw_lines
        if x
    ]

    # Remove repeated headers/footers.
    counts = Counter(
        normalize(x)
        for x in raw_lines
        if len(normalize(x)) > 5
    )

    repeated = {
        value
        for value, count in counts.items()
        if count >= 3
    }

    lines = []

    for line in raw_lines:
        normalized = normalize(line)

        if normalized in repeated:
            continue

        if line.startswith("--- PAGE"):
            continue

        lines.append(line)

    questions = []
    current = []
    current_number = None

    def finalize():
        nonlocal current, current_number

        if not current:
            return

        candidate = clean_text(
            " ".join(current)
        )

        candidate = remove_options(candidate)

        if valid_question_start(candidate):
            questions.append({
                "number": current_number,
                "text": candidate
            })

        current = []
        current_number = None

    for line in lines:
        if looks_like_metadata(line):
            continue

        match = NUMBERED_RE.match(line)

        if match:
            body = clean_text(
                match.group(2)
            )

            if valid_question_start(body):
                finalize()

                current_number = int(
                    match.group(1)
                )

                current = [body]
                continue

        if current:
            if OPTION_RE.match(line):
                continue

            current.append(line)

        else:
            if valid_question_start(line):
                current = [line]
                current_number = None

    finalize()

    # Remove duplicates.
    unique = []
    seen = set()

    for item in questions:
        key = normalize(item["text"])

        if len(key) < 20:
            continue

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    # Safety filter.
    final_questions = []

    for item in unique:
        q = item["text"]

        if PAGE_RE.match(q):
            continue

        if TIME_RE.match(q):
            continue

        if DATE_RE.match(q):
            continue

        if "questionwell" in q.lower():
            continue

        if "question set" in q.lower() and "?" not in q:
            continue

        if len(tokens(q)) < 4:
            continue

        final_questions.append(item)

    return final_questions


# ============================================================
# DOMAIN DETECTION
# ============================================================

def detect_domain(course_name: str, clos: Dict, plos: Dict, reference_text=""):
    combined = " ".join([
        course_name or "",
        " ".join(clos.values()),
        " ".join(plos.values()),
        reference_text or ""
    ])

    normalized = normalize(combined)

    alias_scores = {}

    for alias, domain in DOMAIN_ALIASES.items():
        if alias in normalized:
            alias_scores[domain] = (
                alias_scores.get(domain, 0) + 5
            )

    lexical_scores = {}

    text_words = tokens(combined)

    for domain, lexicon in DOMAIN_LEXICONS.items():
        score = len(
            text_words.intersection(
                {stem(x) for x in lexicon}
            )
        )

        lexical_scores[domain] = score

    combined_scores = {}

    for domain in DOMAIN_LEXICONS:
        combined_scores[domain] = (
            alias_scores.get(domain, 0)
            + lexical_scores.get(domain, 0)
        )

    if not combined_scores:
        return "Unknown", 0

    ranked = sorted(
        combined_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    best_domain, best_score = ranked[0]

    if best_score <= 0:
        return "Unknown", 0

    second_score = ranked[1][1] if len(ranked) > 1 else 0

    confidence = 60

    if best_score >= 5:
        confidence += 15

    if best_score >= second_score + 2:
        confidence += 15

    if course_name:
        normalized_course = normalize(course_name)

        for alias, domain in DOMAIN_ALIASES.items():
            if alias in normalized_course:
                if domain == best_domain:
                    confidence += 10

    return best_domain, min(confidence, 100)


def subject_check(question: str, expected_domain: str):
    if expected_domain == "Unknown":
        return "REVIEW", 0, "Course domain could not be established."

    q_tokens = tokens(question)

    expected_terms = {
        stem(x)
        for x in DOMAIN_LEXICONS.get(
            expected_domain,
            set()
        )
    }

    expected_hits = q_tokens.intersection(
        expected_terms
    )

    other_domains = []

    for domain, lexicon in DOMAIN_LEXICONS.items():
        if domain == expected_domain:
            continue

        domain_terms = {
            stem(x)
            for x in lexicon
        }

        hits = q_tokens.intersection(domain_terms)

        if hits:
            other_domains.append(
                (domain, len(hits), hits)
            )

    other_domains.sort(
        key=lambda x: x[1],
        reverse=True
    )

    strongest_other = (
        other_domains[0]
        if other_domains
        else None
    )

    # Strong expected evidence.
    if len(expected_hits) >= 2:
        if strongest_other and strongest_other[1] >= 3:
            return (
                "REVIEW",
                60,
                f"Expected subject evidence exists, but "
                f"{strongest_other[0]} terminology is also present."
            )

        return (
            "PASS",
            min(95, 70 + len(expected_hits) * 5),
            f"Detected {len(expected_hits)} "
            f"{expected_domain} term(s)."
        )

    # One distinctive subject term.
    if len(expected_hits) == 1:
        if strongest_other and strongest_other[1] >= 2:
            return (
                "REVIEW",
                50,
                f"Subject evidence is mixed with "
                f"{strongest_other[0]} terminology."
            )

        return (
            "REVIEW",
            65,
            "Only limited subject-specific evidence was detected."
        )

    # No expected subject evidence.
    if strongest_other and strongest_other[1] >= 2:
        return (
            "FAIL",
            15,
            f"Question contains stronger evidence for "
            f"{strongest_other[0]} than {expected_domain}."
        )

    return (
        "FAIL",
        20,
        f"No reliable {expected_domain} terminology was detected."
    )


# ============================================================
# OUTCOME MATCHING
# ============================================================

def outcome_alignment(question: str, outcome: str):
    q_tokens = tokens(question)
    o_tokens = tokens(outcome)

    if not q_tokens or not o_tokens:
        return 0, "No meaningful terms available."

    intersection = q_tokens.intersection(o_tokens)

    if not intersection:
        return 0, "No meaningful CLO/PLO content overlap."

    precision = len(intersection) / max(
        len(q_tokens), 1
    )

    recall = len(intersection) / max(
        len(o_tokens), 1
    )

    if precision + recall == 0:
        f1 = 0
    else:
        f1 = (
            2 * precision * recall
            / (precision + recall)
        )

    action_score = 0

    for level, verbs in BLOOM_VERBS.items():
        q_hits = set(
            normalize(question).split()
        ).intersection(verbs)

        o_hits = set(
            normalize(outcome).split()
        ).intersection(verbs)

        if q_hits and o_hits:
            action_score = 20
            break

    score = min(
        100,
        round(
            f1 * 85 + action_score
        )
    )

    if score >= 70:
        explanation = "Strong content and skill alignment."
    elif score >= 50:
        explanation = "Partial alignment; review recommended."
    else:
        explanation = "Weak alignment."

    return score, explanation


def best_outcome(question: str, outcomes: Dict):
    if not outcomes:
        return None, 0, "No outcomes supplied."

    results = []

    for key, outcome in outcomes.items():
        score, explanation = outcome_alignment(
            question,
            outcome
        )

        results.append(
            (score, key, outcome, explanation)
        )

    results.sort(
        key=lambda x: x[0],
        reverse=True
    )

    score, key, outcome, explanation = results[0]

    return key, score, explanation


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question: str):
    words = normalize(question).split()

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    for level, verbs in BLOOM_VERBS.items():
        for word in words:
            if word in verbs:
                scores[level] += 1

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    best_level, best_score = ranked[0]

    if best_score > 0:
        return best_level, 100

    if not words:
        return "Unknown", 0

    first = words[0]

    if first in {"what", "who", "when", "where"}:
        return "Remember", 70

    if first == "why":
        return "Understand", 70

    if first == "how":
        return "Apply", 60

    return "Unknown", 0


def bloom_alignment(question: str, intended: str):
    detected, confidence = detect_bloom(question)

    if intended == "Auto-detect":
        return detected, confidence, "Auto-detected."

    if detected == "Unknown":
        return (
            detected,
            25,
            "No reliable cognitive operation was detected."
        )

    if detected == intended:
        return (
            detected,
            100,
            "Cognitive level matches the selected Bloom level."
        )

    difference = abs(
        BLOOM_RANK[detected]
        - BLOOM_RANK[intended]
    )

    if difference == 1:
        return (
            detected,
            60,
            f"Detected {detected}; selected level is {intended}."
        )

    return (
        detected,
        25,
        f"Detected {detected}; selected level is {intended}."
    )


# ============================================================
# QUESTION QUALITY
# ============================================================

def question_quality(question: str):
    score = 100
    reasons = []

    words = normalize(question).split()

    if len(words) < 6:
        score -= 20
        reasons.append("Question is very short.")

    if len(words) > 80:
        score -= 15
        reasons.append("Question is unnecessarily long.")

    if question.count("?") > 1:
        score -= 5
        reasons.append("Multiple question marks detected.")

    if re.search(
        r"\b(etc|and so on|something|anything)\b",
        question.lower()
    ):
        score -= 10
        reasons.append("Question contains vague wording.")

    if not any(
        word in COMMAND_WORDS
        for word in words
    ) and not question.endswith("?"):
        score -= 15
        reasons.append(
            "The required task is not clearly stated."
        )

    score = max(0, min(100, score))

    if not reasons:
        reasons.append("Question is direct and sufficiently clear.")

    return score, reasons


# ============================================================
# EVALUATION
# ============================================================

def evaluate_question(
    question: str,
    course_domain: str,
    clos: Dict,
    plos: Dict,
    intended_bloom: str
):
    subject_status, subject_score, subject_reason = subject_check(
        question,
        course_domain
    )

    result = {
        "Question": question,
        "Subject": subject_score,
        "Subject Status": subject_status,
        "Subject Reason": subject_reason,
        "CLO": 0,
        "CLO ID": "-",
        "CLO Reason": "",
        "PLO": 0,
        "PLO ID": "-",
        "PLO Reason": "",
        "Bloom": 0,
        "Detected Bloom": "-",
        "Bloom Reason": "",
        "Quality": 0,
        "Decision": "REJECTED",
        "Reason": "",
        "Alignment Attained": False,
    }

    # HARD GATE:
    # Do not calculate trusted downstream alignment
    # when subject relevance fails.
    if subject_status != "PASS":
        result["Reason"] = (
            "Subject relevance did not pass. "
            "CLO, PLO, and Bloom results are not trusted "
            "for approval."
        )
        return result

    clo_id, clo_score, clo_reason = best_outcome(
        question,
        clos
    )

    result["CLO"] = clo_score
    result["CLO ID"] = clo_id or "-"
    result["CLO Reason"] = clo_reason

    if plos:
        plo_id, plo_score, plo_reason = best_outcome(
            question,
            plos
        )

        result["PLO"] = plo_score
        result["PLO ID"] = plo_id or "-"
        result["PLO Reason"] = plo_reason
    else:
        plo_score = None
        result["PLO"] = None
        result["PLO ID"] = "N/A"
        result["PLO Reason"] = "No PLOs supplied."

    detected_bloom, bloom_score, bloom_reason = bloom_alignment(
        question,
        intended_bloom
    )

    result["Bloom"] = bloom_score
    result["Detected Bloom"] = detected_bloom
    result["Bloom Reason"] = bloom_reason

    quality, quality_reasons = question_quality(
        question
    )

    result["Quality"] = quality

    # --------------------------------------------------------
    # HARD DECISION LOGIC
    # --------------------------------------------------------

    if clo_score < 60:
        result["Decision"] = "REJECTED"
        result["Reason"] = (
            "CLO alignment is below the required threshold."
        )
        return result

    if intended_bloom != "Auto-detect" and bloom_score < 80:
        result["Decision"] = "REJECTED"
        result["Reason"] = (
            f"Bloom alignment does not match the selected "
            f"{intended_bloom} level."
        )
        return result

    if plo_score is not None and plo_score < 45:
        result["Decision"] = "NEEDS REVIEW"
        result["Reason"] = (
            "CLO and Bloom conditions pass, but PLO alignment "
            "is weak."
        )
        return result

    if quality < 60:
        result["Decision"] = "NEEDS REVIEW"
        result["Reason"] = (
            "The question needs improvement in clarity or structure."
        )
        return result

    result["Decision"] = "APPROVED"
    result["Reason"] = (
        "Subject relevance, CLO alignment, Bloom alignment, "
        "and required supporting conditions are satisfied."
    )
    result["Alignment Attained"] = True

    return result


# ============================================================
# ALIGNMENT INDEX
# ============================================================

def alignment_index(result):
    subject = result.get("Subject", 0)
    clo = result.get("CLO", 0)
    plo = result.get("PLO")
    bloom = result.get("Bloom", 0)
    quality = result.get("Quality", 0)

    if result["Subject Status"] != "PASS":
        return 0

    if plo is None:
        value = (
            subject * 0.35
            + clo * 0.35
            + bloom * 0.20
            + quality * 0.10
        )
    else:
        value = (
            subject * 0.30
            + clo * 0.30
            + plo * 0.15
            + bloom * 0.15
            + quality * 0.10
        )

    return round(value)


# ============================================================
# DIRECT REVISION GENERATION
# ============================================================

def extract_topic_from_clo(clo_text: str):
    text = clean_text(clo_text)

    text = re.sub(
        r"^\s*CLO\s*\d+\s*[:\-)]\s*",
        "",
        text,
        flags=re.I
    )

    words = normalize(text).split()

    action_words = set()

    for values in BLOOM_VERBS.values():
        action_words.update(values)

    topic_words = [
        word
        for word in words
        if word not in action_words
        and word not in STOP_WORDS
    ]

    if not topic_words:
        return text

    return " ".join(topic_words[:12])


def revision_from_clo(
    clo_text: str,
    intended_bloom: str,
    original_question: str
):
    topic = extract_topic_from_clo(
        clo_text
    )

    if not topic:
        topic = "the specified concept"

    if intended_bloom == "Auto-detect":
        detected, _ = detect_bloom(
            original_question
        )

        if detected != "Unknown":
            intended_bloom = detected
        else:
            intended_bloom = "Understand"

    if intended_bloom == "Remember":
        return (
            f"Define {topic} and state its main characteristics."
        )

    if intended_bloom == "Understand":
        return (
            f"Explain {topic} in your own words and describe "
            f"its main characteristics."
        )

    if intended_bloom == "Apply":
        return (
            f"Apply {topic} to solve the following problem and "
            f"show the steps used to obtain your answer."
        )

    if intended_bloom == "Analyze":
        return (
            f"Analyze {topic} by identifying its key components "
            f"and explaining how they are related."
        )

    if intended_bloom == "Evaluate":
        return (
            f"Evaluate {topic} using relevant evidence and "
            f"justify your conclusion."
        )

    if intended_bloom == "Create":
        return (
            f"Design a solution using {topic} and explain "
            f"how your proposed solution works."
        )

    return (
        f"Explain {topic} and describe its main characteristics."
    )


def generate_revision(
    result,
    clos: Dict,
    intended_bloom: str
):
    clo_id = result.get("CLO ID")

    if not clo_id or clo_id == "-":
        return (
            "Enter a specific CLO so a direct revision can "
            "be generated."
        )

    clo_text = clos.get(clo_id, "")

    if not clo_text:
        return (
            "The matched CLO text is unavailable."
        )

    return revision_from_clo(
        clo_text,
        intended_bloom,
        result["Question"]
    )


# ============================================================
# GRAPH
# ============================================================

def show_three_dimension_graph(
    results: List[Dict],
    title="Three-Dimensional Alignment"
):
    if not results:
        return

    approved = [
        r for r in results
        if r.get("Subject Status") == "PASS"
    ]

    if not approved:
        st.info(
            "The 3-dimensional alignment graph will appear "
            "when subject relevance has been established."
        )
        return

    clo = sum(
        r["CLO"] for r in approved
    ) / len(approved)

    plo_values = [
        r["PLO"]
        for r in approved
        if r["PLO"] is not None
    ]

    plo = (
        sum(plo_values) / len(plo_values)
        if plo_values else 0
    )

    bloom = sum(
        r["Bloom"] for r in approved
    ) / len(approved)

    st.subheader("📊 Three-Dimensional Alignment")

    st.caption(
        "Average alignment across the evaluated questions. "
        "Subject relevance is used as a gate and is not "
        "presented as a substitute for CLO/PLO/Bloom alignment."
    )

    try:
        import matplotlib.pyplot as plt
        import numpy as np

        labels = [
            "CLO Alignment",
            "PLO Alignment",
            "Bloom Alignment"
        ]

        values = [
            clo,
            plo,
            bloom
        ]

        angles = np.linspace(
            0,
            2 * np.pi,
            len(labels),
            endpoint=False
        ).tolist()

        values_closed = values + values[:1]
        angles_closed = angles + angles[:1]

        fig = plt.figure(
            figsize=(7, 5)
        )

        ax = fig.add_subplot(
            111,
            polar=True
        )

        ax.set_theta_offset(
            np.pi / 2
        )

        ax.set_theta_direction(-1)

        ax.plot(
            angles_closed,
            values_closed,
            linewidth=2
        )

        ax.fill(
            angles_closed,
            values_closed,
            alpha=0.20
        )

        ax.set_xticks(angles)

        ax.set_xticklabels(labels)

        ax.set_ylim(
            0,
            100
        )

        ax.set_yticks([
            20,
            40,
            60,
            80,
            100
        ])

        ax.set_title(
            title,
            pad=25
        )

        st.pyplot(
            fig,
            use_container_width=False
        )

        plt.close(fig)

    except Exception:
        # Fallback if matplotlib/numpy is unavailable.
        chart = pd.DataFrame({
            "Dimension": [
                "CLO Alignment",
                "PLO Alignment",
                "Bloom Alignment"
            ],
            "Alignment": [
                round(clo),
                round(plo),
                round(bloom)
            ]
        })

        st.bar_chart(
            chart.set_index("Dimension")
        )


# ============================================================
# SESSION STATE
# ============================================================

if "evaluated_results" not in st.session_state:
    st.session_state.evaluated_results = []

if "revised_results" not in st.session_state:
    st.session_state.revised_results = {}

if "alignment_confetti" not in st.session_state:
    st.session_state.alignment_confetti = False


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Assessment Alignment Checker")

st.write(
    "Evaluate assessment questions for subject relevance, "
    "CLO alignment, PLO alignment, and Bloom's Taxonomy."
)

st.divider()


# ============================================================
# INPUTS
# ============================================================

st.subheader("1. Course Information")

course_name = st.text_input(
    "Course / Subject Name",
    placeholder="Example: General Chemistry"
)

reference_file = st.file_uploader(
    "Optional Course Content / Syllabus",
    type=[
        "pdf",
        "docx",
        "txt",
        "csv",
        "xlsx",
        "xls"
    ],
    help=(
        "Recommended when the course title alone is not enough "
        "to verify subject relevance."
    )
)

reference_text = ""

if reference_file:
    ref_text, ref_error, ref_diag = extract_file_text(
        reference_file
    )

    if ref_error:
        st.warning(
            f"Course reference could not be read: {ref_error}"
        )
    else:
        reference_text = ref_text
        st.success(
            "Course reference loaded successfully."
        )


col1, col2 = st.columns(2)

with col1:
    clo_text = st.text_area(
        "Course Learning Outcomes (CLOs)",
        height=180,
        placeholder=(
            "CLO1: Explain the basic principles of chemical bonding.\n"
            "CLO2: Calculate molarity and concentration.\n"
            "CLO3: Analyze chemical reactions."
        )
    )

with col2:
    plo_text = st.text_area(
        "Program Learning Outcomes (PLOs)",
        height=180,
        placeholder=(
            "PLO1: Apply knowledge to solve problems.\n"
            "PLO2: Analyze information critically.\n"
            "PLO3: Communicate findings effectively."
        )
    )


st.subheader("2. Assessment Settings")

bloom = st.selectbox(
    "Expected Bloom's Taxonomy Level",
    ["Auto-detect"] + BLOOM_LEVELS
)

assessment_file = st.file_uploader(
    "Upload Assessment File",
    type=[
        "pdf",
        "docx",
        "txt",
        "csv",
        "xlsx",
        "xls"
    ],
    help=(
        "PDFs can be text-based or scanned. "
        "Scanned PDFs are processed using OCR."
    )
)


# ============================================================
# EVALUATION BUTTON
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

    if not assessment_file:
        st.error(
            "Please upload an assessment file."
        )
        st.stop()

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
            "No valid CLOs were detected. Use format such as "
            "CLO1: Explain the principles of..."
        )
        st.stop()

    with st.spinner(
        "Reading and evaluating the assessment..."
    ):
        assessment_text, file_error, diagnostics = (
            extract_file_text(
                assessment_file
            )
        )

    if file_error:
        st.error(file_error)

        if assessment_file.name.lower().endswith(".pdf"):
            st.info(
                "For scanned PDFs, make sure Tesseract OCR is "
                "installed through packages.txt."
            )

        st.stop()

    if not assessment_text.strip():
        st.error(
            "No readable content was found in the uploaded file."
        )
        st.stop()

    questions = extract_questions(
        assessment_text
    )

    if not questions:
        st.error(
            "No valid assessment questions were detected."
        )

        st.info(
            "The evaluator intentionally ignores page numbers, "
            "dates, times, document titles, QuestionWell headers, "
            "answer-key headings, and other metadata."
        )

        with st.expander("Extracted text preview"):
            st.text(
                assessment_text[:10000]
            )

        st.stop()

    course_domain, domain_confidence = detect_domain(
        course_name,
        clos,
        plos,
        reference_text
    )

    results = []

    for item in questions:
        result = evaluate_question(
            item["text"],
            course_domain,
            clos,
            plos,
            bloom
        )

        result["Number"] = item["number"]

        results.append(result)

    st.session_state.evaluated_results = results
    st.session_state.revised_results = {}
    st.session_state.alignment_confetti = False


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.evaluated_results

if results:

    st.divider()

    st.header("📈 Results")

    # --------------------------------------------------------
    # DOMAIN INFORMATION
    # --------------------------------------------------------

    course_domain, domain_confidence = detect_domain(
        course_name,
        parse_outcomes(clo_text, "CLO"),
        parse_outcomes(plo_text, "PLO"),
        reference_text
    )

    d1, d2, d3 = st.columns(3)

    with d1:
        st.metric(
            "Detected Subject",
            course_domain
        )

    with d2:
        st.metric(
            "Subject Confidence",
            f"{domain_confidence}%"
        )

    with d3:
        st.metric(
            "Questions Detected",
            len(results)
        )

    # --------------------------------------------------------
    # THREE DIMENSION GRAPH AT TOP
    # --------------------------------------------------------

    show_three_dimension_graph(
        results,
        "CLO / PLO / Bloom Alignment"
    )

    st.divider()

    # --------------------------------------------------------
    # SUMMARY COUNTS
    # --------------------------------------------------------

    approved = sum(
        r["Decision"] == "APPROVED"
        for r in results
    )

    review = sum(
        r["Decision"] == "NEEDS REVIEW"
        for r in results
    )

    rejected = sum(
        r["Decision"] == "REJECTED"
        for r in results
    )

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        st.metric(
            "Total Questions",
            len(results)
        )

    with s2:
        st.metric(
            "Approved",
            approved
        )

    with s3:
        st.metric(
            "Needs Review",
            review
        )

    with s4:
        st.metric(
            "Rejected",
            rejected
        )

    # --------------------------------------------------------
    # ALIGNMENT AVERAGES
    # --------------------------------------------------------

    valid_results = [
        r for r in results
        if r["Subject Status"] == "PASS"
    ]

    if valid_results:

        avg_clo = round(
            sum(r["CLO"] for r in valid_results)
            / len(valid_results)
        )

        plo_values = [
            r["PLO"]
            for r in valid_results
            if r["PLO"] is not None
        ]

        avg_plo = (
            round(
                sum(plo_values)
                / len(plo_values)
            )
            if plo_values
            else 0
        )

        avg_bloom = round(
            sum(r["Bloom"] for r in valid_results)
            / len(valid_results)
        )

        a1, a2, a3 = st.columns(3)

        with a1:
            st.metric(
                "Average CLO Alignment",
                f"{avg_clo}%"
            )

        with a2:
            st.metric(
                "Average PLO Alignment",
                f"{avg_plo}%"
            )

        with a3:
            st.metric(
                "Average Bloom Alignment",
                f"{avg_bloom}%"
            )

    # --------------------------------------------------------
    # RESULTS TABLE
    # --------------------------------------------------------

    st.subheader("Assessment Alignment Results")

    table_rows = []

    for index, result in enumerate(results, start=1):
        table_rows.append({
            "Q": index,
            "Question": result["Question"],
            "Subject": f'{result["Subject"]}%',
            "CLO": (
                f'{result["CLO"]}%'
                if result["Subject Status"] == "PASS"
                else "Not trusted"
            ),
            "PLO": (
                f'{result["PLO"]}%'
                if result["Subject Status"] == "PASS"
                and result["PLO"] is not None
                else "Not trusted"
            ),
            "Bloom": (
                f'{result["Bloom"]}%'
                if result["Subject Status"] == "PASS"
                else "Not trusted"
            ),
            "Detected Bloom": result["Detected Bloom"],
            "Decision": result["Decision"]
        })

    result_df = pd.DataFrame(
        table_rows
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # DETAILED RESULTS
    # --------------------------------------------------------

    st.subheader("Detailed Evaluation")

    clos = parse_outcomes(
        clo_text,
        "CLO"
    )

    for index, result in enumerate(
        results,
        start=1
    ):

        decision = result["Decision"]

        if decision == "APPROVED":
            icon = "✅"
        elif decision == "NEEDS REVIEW":
            icon = "⚠️"
        else:
            icon = "❌"

        with st.expander(
            f"{icon} Question {index}: "
            f"{result['Question'][:100]}"
        ):

            st.write(
                f"**Question:** {result['Question']}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                st.metric(
                    "Subject",
                    f"{result['Subject']}%"
                )

            with c2:
                st.metric(
                    "CLO",
                    (
                        f"{result['CLO']}%"
                        if result["Subject Status"] == "PASS"
                        else "Not trusted"
                    )
                )

            with c3:
                st.metric(
                    "Bloom",
                    (
                        f"{result['Bloom']}%"
                        if result["Subject Status"] == "PASS"
                        else "Not trusted"
                    )
                )

            if result["Subject Status"] != "PASS":
                st.error(
                    f"Subject gate failed: "
                    f"{result['Subject Reason']}"
                )

                st.warning(
                    "The question is not approved because "
                    "subject relevance is a mandatory gate."
                )

            else:
                st.write(
                    f"**Matched CLO:** {result['CLO ID']}"
                )

                if result["CLO ID"] in clos:
                    st.caption(
                        clos[result["CLO ID"]]
                    )

                st.write(
                    f"**CLO assessment:** "
                    f"{result['CLO Reason']}"
                )

                if result["PLO"] is not None:
                    st.write(
                        f"**Matched PLO:** {result['PLO ID']} "
                        f"({result['PLO']}%)"
                    )

                    st.write(
                        f"**PLO assessment:** "
                        f"{result['PLO Reason']}"
                    )

                st.write(
                    f"**Detected Bloom:** "
                    f"{result['Detected Bloom']}"
                )

                st.write(
                    f"**Bloom assessment:** "
                    f"{result['Bloom Reason']}"
                )

                st.write(
                    f"**Decision:** "
                    f"{result['Decision']}"
                )

                st.write(
                    f"**Reason:** "
                    f"{result['Reason']}"
                )

                if result["Decision"] != "APPROVED":

                    st.markdown(
                        "### 🔧 Direct Revision"
                    )

                    revision = generate_revision(
                        result,
                        clos,
                        bloom
                    )

                    st.write(
                        revision
                    )

                    revision_key = f"revision_{index}"

                    st.session_state[
                        revision_key
                    ] = revision

                    if st.button(
                        "🔍 Test Revised Question",
                        key=f"test_revision_{index}"
                    ):

                        revised_result = evaluate_question(
                            revision,
                            course_domain,
                            clos,
                            parse_outcomes(
                                plo_text,
                                "PLO"
                            ),
                            bloom
                        )

                        st.session_state.revised_results[
                            index
                        ] = revised_result

                        if revised_result[
                            "Alignment Attained"
                        ]:
                            st.session_state.alignment_confetti = True

                        st.rerun()

                # ------------------------------------------------
                # REVISED RESULT
                # ------------------------------------------------

                if index in st.session_state.revised_results:

                    revised = (
                        st.session_state.revised_results[
                            index
                        ]
                    )

                    st.markdown(
                        "### 🔄 Revised Question Result"
                    )

                    st.write(
                        f"**Revised Question:** "
                        f"{revised['Question']}"
                    )

                    r1, r2, r3, r4 = st.columns(4)

                    with r1:
                        st.metric(
                            "Subject",
                            f"{revised['Subject']}%"
                        )

                    with r2:
                        st.metric(
                            "CLO",
                            (
                                f"{revised['CLO']}%"
                                if revised["Subject Status"] == "PASS"
                                else "Not trusted"
                            )
                        )

                    with r3:
                        st.metric(
                            "PLO",
                            (
                                f"{revised['PLO']}%"
                                if revised["PLO"] is not None
                                and revised["Subject Status"] == "PASS"
                                else "Not trusted"
                            )
                        )

                    with r4:
                        st.metric(
                            "Bloom",
                            (
                                f"{revised['Bloom']}%"
                                if revised["Subject Status"] == "PASS"
                                else "Not trusted"
                            )
                        )

                    if revised["Alignment Attained"]:

                        st.success(
                            "🎉 ALIGNMENT ATTAINED"
                        )

                        st.write(
                            "The revised question satisfies the "
                            "required alignment gates."
                        )

                        st.success(
                            "✓ Subject relevance attained"
                        )

                        st.success(
                            "✓ CLO alignment attained"
                        )

                        if revised["PLO"] is not None:
                            st.success(
                                "✓ PLO alignment attained"
                            )

                        if bloom != "Auto-detect":
                            st.success(
                                "✓ Bloom alignment attained"
                            )

                        # Confetti ONLY after actual attainment.
                        st.balloons()

                    else:

                        if revised["Subject Status"] != "PASS":
                            st.error(
                                "❌ Alignment not attained: "
                                "subject relevance still fails."
                            )

                        elif revised["CLO"] < 60:
                            st.error(
                                "❌ Alignment not attained: "
                                "CLO alignment is still below "
                                "the required threshold."
                            )

                        elif (
                            bloom != "Auto-detect"
                            and revised["Bloom"] < 80
                        ):
                            st.error(
                                "❌ Alignment not attained: "
                                "Bloom level still does not match."
                            )

                        elif (
                            revised["PLO"] is not None
                            and revised["PLO"] < 45
                        ):
                            st.warning(
                                "⚠️ Alignment not fully attained: "
                                "PLO alignment remains weak."
                            )

                        else:
                            st.warning(
                                "⚠️ Alignment requires further review."
                            )


# ============================================================
# DOWNLOAD RESULTS
# ============================================================

if results:

    st.divider()

    st.subheader("📥 Export Results")

    export_rows = []

    for index, result in enumerate(
        results,
        start=1
    ):
        export_rows.append({
            "Question No": index,
            "Question": result["Question"],
            "Subject Score": result["Subject"],
            "Subject Status": result["Subject Status"],
            "CLO": result["CLO ID"],
            "CLO Alignment": result["CLO"],
            "PLO": result["PLO ID"],
            "PLO Alignment": result["PLO"],
            "Detected Bloom": result["Detected Bloom"],
            "Bloom Alignment": result["Bloom"],
            "Question Quality": result["Quality"],
            "Decision": result["Decision"],
            "Reason": result["Reason"]
        })

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Evaluation CSV",
        data=csv_data,
        file_name="obe_alignment_results.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# OCR INFORMATION
# ============================================================

with st.expander("ℹ️ Supported file formats and OCR"):

    st.write(
        "Supported assessment formats:"
    )

    st.write(
        "PDF • DOCX • TXT • CSV • XLSX • XLS"
    )

    st.write(
        "For scanned/image-based PDFs, the application first "
        "attempts normal PDF text extraction. Pages without "
        "usable text are then rendered and processed through "
        "Tesseract OCR."
    )

    st.write(
        "The evaluator also filters common PDF artifacts such "
        "as page numbers, dates, times, repeated headers, "
        "document titles, and QuestionWell metadata before "
        "identifying assessment questions."
    )
