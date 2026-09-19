import io
import re
from collections import Counter
from typing import Dict, List, Tuple, Optional

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
        "define",
        "list",
        "name",
        "identify",
        "state",
        "recall",
        "recognize",
        "select",
        "label",
        "match",
        "mention",
        "give",
    },
    "Understand": {
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss",
        "illustrate",
        "paraphrase",
        "clarify",
        "outline",
        "distinguish",
    },
    "Apply": {
        "calculate",
        "compute",
        "solve",
        "use",
        "apply",
        "demonstrate",
        "execute",
        "implement",
        "perform",
        "determine",
        "show",
    },
    "Analyze": {
        "analyze",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "categorize",
        "break",
        "deconstruct",
        "relate",
        "separate",
    },
    "Evaluate": {
        "evaluate",
        "assess",
        "judge",
        "justify",
        "critique",
        "defend",
        "appraise",
        "argue",
        "validate",
        "recommend",
    },
    "Create": {
        "create",
        "design",
        "develop",
        "construct",
        "formulate",
        "produce",
        "propose",
        "generate",
        "compose",
        "plan",
        "invent",
    },
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "been",
    "being", "but", "by", "can", "could", "did", "do", "does",
    "for", "from", "had", "has", "have", "he", "her", "here",
    "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "may", "might", "more", "most", "must", "of", "on",
    "or", "our", "should", "so", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those",
    "to", "under", "was", "we", "were", "what", "when", "where",
    "which", "who", "why", "will", "with", "would", "you", "your",
    "using", "use", "following", "given", "following",
}


# ============================================================
# DOMAIN LEXICONS
# ============================================================

DOMAIN_LEXICONS = {
    "Chemistry": {
        "atom", "molecule", "element", "compound", "ion", "bond",
        "ionic", "covalent", "molarity", "mole", "stoichiometry",
        "reaction", "equilibrium", "acid", "base", "ph", "buffer",
        "oxidation", "reduction", "redox", "enthalpy", "entropy",
        "thermodynamics", "organic", "inorganic", "alkane", "alkene",
        "alkyne", "benzene", "polymer", "periodic", "electron",
        "proton", "neutron", "isotope", "catalyst", "precipitate",
        "titration", "solution", "concentration", "solubility",
        "spectroscopy", "nmr", "infrared", "chromatography",
    },

    "Physics": {
        "force", "motion", "velocity", "acceleration", "momentum",
        "energy", "work", "power", "mass", "gravity", "friction",
        "wave", "frequency", "wavelength", "optics", "lens",
        "electric", "electricity", "voltage", "current", "resistance",
        "circuit", "magnetic", "field", "charge", "potential",
        "quantum", "relativity", "thermodynamic", "pressure",
        "density", "kinetic", "potential", "projectile",
    },

    "Mathematics": {
        "equation", "algebra", "calculus", "derivative", "integral",
        "function", "matrix", "vector", "probability", "statistics",
        "mean", "median", "variance", "standard", "deviation",
        "geometry", "trigonometry", "logarithm", "polynomial",
        "limit", "theorem", "proof", "set", "number", "sequence",
        "series", "differential", "linear", "quadratic",
    },

    "Computer Science": {
        "algorithm", "program", "programming", "code", "python",
        "java", "c++", "javascript", "database", "sql", "network",
        "computer", "software", "hardware", "operating", "system",
        "data", "structure", "array", "linked", "list", "stack",
        "queue", "tree", "graph", "recursion", "class", "object",
        "inheritance", "polymorphism", "compiler", "api",
        "machine", "learning", "artificial", "intelligence",
        "cybersecurity", "encryption", "binary", "computational",
    },

    "Biology": {
        "cell", "organism", "tissue", "organ", "gene", "genetic",
        "dna", "rna", "protein", "enzyme", "metabolism", "mitosis",
        "meiosis", "chromosome", "evolution", "species", "ecology",
        "ecosystem", "photosynthesis", "respiration", "membrane",
        "bacteria", "virus", "microbiology", "physiology",
        "anatomy", "homeostasis", "mutation", "heredity",
    },

    "English / Language": {
        "grammar", "sentence", "paragraph", "essay", "writing",
        "reading", "author", "tone", "purpose", "main", "idea",
        "thesis", "argument", "rhetorical", "audience", "vocabulary",
        "syntax", "morphology", "phonology", "semantics", "pragmatics",
        "paraphrase", "summarize", "composition", "communication",
        "language", "discourse", "pronunciation", "listening",
        "speaking", "literacy",
    },

    "Literature": {
        "novel", "poem", "poetry", "fiction", "character", "plot",
        "setting", "theme", "symbolism", "metaphor", "imagery",
        "narrator", "narrative", "protagonist", "antagonist",
        "drama", "tragedy", "sonnet", "author", "literary",
        "interpretation", "literature", "genre",
    },

    "Business / Management": {
        "management", "manager", "leadership", "organization",
        "organizational", "strategy", "marketing", "market",
        "consumer", "customer", "business", "entrepreneur",
        "entrepreneurship", "planning", "decision", "stakeholder",
        "human", "resources", "hr", "motivation", "performance",
        "operations", "supply", "chain", "competitive", "advantage",
        "corporate", "culture",
    },

    "Accounting / Finance": {
        "accounting", "account", "ledger", "journal", "balance",
        "sheet", "income", "statement", "asset", "liability",
        "equity", "revenue", "expense", "profit", "depreciation",
        "audit", "financial", "cash", "flow", "budget", "tax",
        "investment", "portfolio", "interest", "present", "value",
        "capital", "ratio", "dividend",
    },

    "Economics": {
        "economics", "economic", "demand", "supply", "price",
        "market", "inflation", "unemployment", "gdp", "fiscal",
        "monetary", "policy", "elasticity", "utility", "consumer",
        "producer", "equilibrium", "macro", "micro", "trade",
        "exchange", "currency", "opportunity", "cost",
    },

    "Engineering": {
        "engineering", "design", "mechanical", "electrical",
        "civil", "structural", "material", "machine", "stress",
        "strain", "load", "beam", "circuit", "voltage", "current",
        "thermodynamics", "fluid", "fluid mechanics", "control",
        "manufacturing", "prototype", "cad", "system", "process",
    },

    "Psychology": {
        "psychology", "behavior", "behaviour", "cognitive",
        "memory", "perception", "emotion", "personality",
        "learning", "development", "motivation", "psychological",
        "therapy", "conditioning", "reinforcement", "mental",
        "social", "attitude", "intelligence",
    },

    "Sociology": {
        "society", "social", "sociology", "culture", "community",
        "class", "inequality", "gender", "institution", "family",
        "socialization", "deviance", "norm", "status", "role",
        "population", "urbanization", "globalization",
    },

    "Education": {
        "education", "teaching", "learning", "pedagogy", "curriculum",
        "instruction", "assessment", "classroom", "teacher", "student",
        "lesson", "learning", "outcome", "rubric", "evaluation",
        "educational", "didactic", "formative", "summative",
    },

    "History": {
        "history", "historical", "empire", "war", "revolution",
        "colonial", "colonialism", "independence", "treaty",
        "dynasty", "kingdom", "civilization", "ancient", "medieval",
        "political", "movement", "era", "century", "migration",
    },

    "Law": {
        "law", "legal", "court", "contract", "tort", "crime",
        "criminal", "civil", "statute", "constitution",
        "constitutional", "judgment", "judge", "liability",
        "negligence", "case", "precedent", "plaintiff", "defendant",
        "jurisdiction", "legislation",
    },

    "Pharmacy": {
        "pharmacy", "drug", "medicine", "dosage", "dose",
        "pharmacology", "pharmacokinetics", "tablet", "capsule",
        "prescription", "therapeutic", "adverse", "drug",
        "formulation", "bioavailability", "receptor", "antibiotic",
        "drug interaction",
    },

    "Medical / Health Sciences": {
        "patient", "disease", "diagnosis", "symptom", "clinical",
        "medical", "health", "anatomy", "physiology", "pathology",
        "treatment", "therapy", "infection", "hospital", "nursing",
        "blood", "heart", "lung", "clinical", "syndrome",
    },

    "Environmental Science": {
        "environment", "ecosystem", "pollution", "climate",
        "climate change", "biodiversity", "conservation",
        "sustainability", "waste", "water", "air", "soil",
        "renewable", "carbon", "greenhouse", "ecology",
        "deforestation", "resource",
    },
}


DOMAIN_ALIASES = {
    "chem": "Chemistry",
    "chemistry": "Chemistry",
    "general chemistry": "Chemistry",
    "organic chemistry": "Chemistry",
    "physical chemistry": "Chemistry",
    "inorganic chemistry": "Chemistry",

    "physics": "Physics",
    "mathematics": "Mathematics",
    "math": "Mathematics",
    "statistics": "Mathematics",
    "calculus": "Mathematics",

    "computer science": "Computer Science",
    "cs": "Computer Science",
    "programming": "Computer Science",
    "software engineering": "Computer Science",
    "information technology": "Computer Science",
    "it": "Computer Science",

    "biology": "Biology",
    "botany": "Biology",
    "zoology": "Biology",

    "english": "English / Language",
    "english i": "English / Language",
    "english language": "English / Language",
    "linguistics": "English / Language",
    "language": "English / Language",

    "literature": "Literature",
    "english literature": "Literature",

    "business": "Business / Management",
    "management": "Business / Management",
    "marketing": "Business / Management",
    "hr": "Business / Management",
    "human resource": "Business / Management",

    "accounting": "Accounting / Finance",
    "finance": "Accounting / Finance",

    "economics": "Economics",

    "engineering": "Engineering",
    "mechanical engineering": "Engineering",
    "electrical engineering": "Engineering",
    "civil engineering": "Engineering",

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
# SYNONYMS / NORMALIZATION
# ============================================================

SYNONYMS = {
    "calculate": {"calculate", "compute", "solve", "determine"},
    "explain": {"explain", "describe", "clarify", "interpret"},
    "compare": {"compare", "contrast", "differentiate"},
    "analyze": {"analyze", "analyse", "examine", "investigate"},
    "evaluate": {"evaluate", "assess", "judge", "critique"},
    "create": {"create", "design", "develop", "construct", "formulate"},
    "identify": {"identify", "recognize", "name", "state"},
    "apply": {"apply", "use", "implement", "demonstrate"},
}


COMMAND_VERBS = set()
for values in BLOOM_VERBS.values():
    COMMAND_VERBS.update(values)

QUESTION_START_WORDS = {
    "what",
    "why",
    "how",
    "which",
    "when",
    "where",
    "who",
    "define",
    "identify",
    "explain",
    "describe",
    "discuss",
    "calculate",
    "solve",
    "compare",
    "contrast",
    "analyze",
    "analyse",
    "evaluate",
    "assess",
    "justify",
    "design",
    "develop",
    "derive",
    "determine",
    "state",
    "list",
    "name",
    "distinguish",
    "interpret",
    "apply",
    "demonstrate",
    "illustrate",
    "critique",
    "construct",
    "formulate",
    "propose",
    "compute",
    "examine",
    "investigate",
    "show",
    "prove",
}


# ============================================================
# TEXT UTILITIES
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
    text = re.sub(r"\n[ \t]+", "\n", text)

    return text.strip()


def normalize_for_matching(text: str) -> str:
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def simple_stem(token: str) -> str:
    token = token.lower().strip()

    if len(token) <= 4:
        return token

    for suffix in (
        "ization",
        "ational",
        "fulness",
        "ousness",
        "iveness",
        "ments",
        "ment",
        "ingly",
        "edly",
        "ation",
        "ions",
        "tion",
        "ing",
        "ers",
        "ies",
        "es",
        "ed",
        "ly",
        "s",
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]

    return token


def content_tokens(text: str) -> List[str]:
    normalized = normalize_for_matching(text)
    tokens = normalized.split()

    result = []

    for token in tokens:
        if token in STOP_WORDS:
            continue

        if len(token) < 3:
            continue

        result.append(simple_stem(token))

    return result


def unique_content_tokens(text: str) -> set:
    return set(content_tokens(text))


def extract_phrases(text: str) -> List[str]:
    normalized = normalize_for_matching(text)
    tokens = normalized.split()

    phrases = []

    for n in (2, 3):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i + n])

            if all(t not in STOP_WORDS for t in tokens[i:i + n]):
                phrases.append(phrase)

    return phrases


# ============================================================
# PDF + OCR
# ============================================================

def check_tesseract() -> Tuple[bool, str]:
    if pytesseract is None:
        return False, "pytesseract is not installed."

    try:
        version = pytesseract.get_tesseract_version()
        return True, str(version)
    except Exception as exc:
        return False, f"Tesseract engine unavailable: {exc}"


def render_page_for_ocr(page):
    if fitz is None or Image is None:
        return None

    try:
        matrix = fitz.Matrix(2.5, 2.5)
        pix = page.get_pixmap(
            matrix=matrix,
            alpha=False,
            colorspace=fitz.csRGB,
        )

        image = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples,
        )

        if ImageOps is not None:
            image = ImageOps.grayscale(image)
            image = ImageOps.autocontrast(image)

        return image

    except Exception:
        return None


def ocr_image(image) -> str:
    if pytesseract is None:
        return ""

    try:
        return pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 6",
        )
    except Exception:
        return ""


def extract_pdf_text(file_bytes: bytes) -> Tuple[str, str, Dict]:
    diagnostics = {
        "method": "",
        "total_pages": 0,
        "text_pages": 0,
        "ocr_pages": 0,
        "ocr_failed_pages": 0,
    }

    if fitz is None:
        return "", "PyMuPDF is not installed.", diagnostics

    try:
        document = fitz.open(
            stream=file_bytes,
            filetype="pdf",
        )
    except Exception as exc:
        return "", f"Could not open PDF: {exc}", diagnostics

    diagnostics["total_pages"] = len(document)

    page_texts = []

    for page_number, page in enumerate(document):
        try:
            text = page.get_text("text") or ""
        except Exception:
            text = ""

        text = clean_text(text)

        compact = re.sub(r"\s+", "", text)

        if len(compact) >= 25:
            page_texts.append(text)
            diagnostics["text_pages"] += 1
        else:
            page_texts.append("")

    pages_needing_ocr = [
        i for i, value in enumerate(page_texts)
        if not value
    ]

    if pages_needing_ocr:
        available, _ = check_tesseract()

        if available:
            for page_index in pages_needing_ocr:
                try:
                    image = render_page_for_ocr(
                        document[page_index]
                    )

                    if image is None:
                        diagnostics["ocr_failed_pages"] += 1
                        continue

                    ocr_text = clean_text(
                        ocr_image(image)
                    )

                    if len(re.sub(r"\s+", "", ocr_text)) >= 15:
                        page_texts[page_index] = ocr_text
                        diagnostics["ocr_pages"] += 1
                    else:
                        diagnostics["ocr_failed_pages"] += 1

                except Exception:
                    diagnostics["ocr_failed_pages"] += 1
        else:
            diagnostics["ocr_failed_pages"] = len(
                pages_needing_ocr
            )

    output_parts = []

    for i, page_text in enumerate(page_texts):
        if page_text.strip():
            output_parts.append(
                f"--- PAGE {i + 1} ---\n{page_text}"
            )

    combined = "\n\n".join(output_parts)

    if diagnostics["ocr_pages"] > 0:
        diagnostics["method"] = "Text extraction + OCR"
    else:
        diagnostics["method"] = "Text extraction"

    if not combined.strip():
        available, detail = check_tesseract()

        if not available:
            return (
                "",
                "The PDF appears to be scanned/image-based and OCR "
                "is unavailable. Install Tesseract OCR using the "
                "packages.txt file provided below.",
                diagnostics,
            )

        return (
            "",
            "The PDF could be opened, but no readable text was detected.",
            diagnostics,
        )

    return combined, "", diagnostics


# ============================================================
# OTHER FILE READERS
# ============================================================

def extract_docx_text(file_bytes: bytes) -> Tuple[str, str]:
    if Document is None:
        return "", "python-docx is not installed."

    try:
        document = Document(io.BytesIO(file_bytes))

        parts = []

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()

            if text:
                parts.append(text)

        for table in document.tables:
            for row in table.rows:
                row_values = []

                for cell in row.cells:
                    cell_text = cell.text.strip()

                    if cell_text:
                        row_values.append(cell_text)

                if row_values:
                    parts.append(" | ".join(row_values))

        return "\n".join(parts), ""

    except Exception as exc:
        return "", f"Could not read DOCX: {exc}"


def extract_excel_text(file_bytes: bytes) -> Tuple[str, str]:
    try:
        workbook = pd.ExcelFile(io.BytesIO(file_bytes))

        parts = []

        for sheet in workbook.sheet_names:
            try:
                frame = pd.read_excel(
                    workbook,
                    sheet_name=sheet,
                    header=None,
                )

                parts.append(
                    f"--- SHEET: {sheet} ---"
                )

                for row in frame.fillna("").astype(str).values:
                    values = [
                        value.strip()
                        for value in row
                        if value.strip()
                    ]

                    if values:
                        parts.append(" | ".join(values))

            except Exception as exc:
                parts.append(
                    f"[Could not read sheet {sheet}: {exc}]"
                )

        return "\n".join(parts), ""

    except Exception as exc:
        return "", f"Could not read Excel file: {exc}"


def extract_csv_text(file_bytes: bytes) -> Tuple[str, str]:
    try:
        frame = pd.read_csv(
            io.BytesIO(file_bytes),
            header=None,
        )

        parts = []

        for row in frame.fillna("").astype(str).values:
            values = [
                value.strip()
                for value in row
                if value.strip()
            ]

            if values:
                parts.append(" | ".join(values))

        return "\n".join(parts), ""

    except Exception:
        try:
            return (
                file_bytes.decode(
                    "utf-8",
                    errors="ignore",
                ),
                "",
            )
        except Exception as exc:
            return "", f"Could not read CSV: {exc}"


def extract_text_file(file_bytes: bytes) -> Tuple[str, str]:
    try:
        return (
            file_bytes.decode(
                "utf-8",
                errors="ignore",
            ),
            "",
        )
    except Exception as exc:
        return "", f"Could not read text file: {exc}"


def extract_file_text(uploaded_file) -> Tuple[str, str, Dict]:
    file_name = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    diagnostics = {}

    if file_name.endswith(".pdf"):
        return extract_pdf_text(file_bytes)

    if file_name.endswith(".docx"):
        text, error = extract_docx_text(file_bytes)
        diagnostics["method"] = "DOCX text extraction"
        return text, error, diagnostics

    if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        text, error = extract_excel_text(file_bytes)
        diagnostics["method"] = "Excel extraction"
        return text, error, diagnostics

    if file_name.endswith(".csv"):
        text, error = extract_csv_text(file_bytes)
        diagnostics["method"] = "CSV extraction"
        return text, error, diagnostics

    if file_name.endswith(".txt"):
        text, error = extract_text_file(file_bytes)
        diagnostics["method"] = "Text extraction"
        return text, error, diagnostics

    return (
        "",
        "Unsupported file type. Upload PDF, DOCX, TXT, CSV, XLSX, or XLS.",
        diagnostics,
    )


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text: str, prefix: str) -> Dict[str, str]:
    outcomes = {}

    if not text:
        return outcomes

    pattern = re.compile(
        rf"^\s*({re.escape(prefix)}\s*\d+)\s*[:\-\)]\s*(.+?)\s*$",
        re.IGNORECASE,
    )

    for raw_line in text.splitlines():
        line = clean_text(raw_line)

        match = pattern.match(line)

        if match:
            key = re.sub(
                r"\s+",
                "",
                match.group(1).upper(),
            )

            value = match.group(2).strip()

            if value:
                outcomes[key] = value

    return outcomes


# ============================================================
# QUESTION FILTERING
# ============================================================

PAGE_MARKER_RE = re.compile(
    r"^\s*(?:page\s*)?\d+\s*(?:/|of)\s*\d+\s*$",
    re.IGNORECASE,
)

TIME_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*$",
    re.IGNORECASE,
)

DATE_RE = re.compile(
    r"^\s*(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r"|\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*$"
)

QUESTION_NUMBER_RE = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})"
    r"\s*[\.\):\-]\s*(.+?)\s*$",
    re
