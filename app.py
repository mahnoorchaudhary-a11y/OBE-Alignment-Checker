import io
import re
from collections import Counter

import pandas as pd
import streamlit as st

# Optional libraries
try:
    import fitz
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

BLOOM_RANK = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}

BLOOM_VERBS = {
    "Remember": {
        "define", "list", "name", "identify", "state",
        "recall", "recognize", "select", "label", "match"
    },
    "Understand": {
        "explain", "describe", "summarize", "interpret",
        "classify", "discuss", "illustrate", "paraphrase",
        "clarify", "outline"
    },
    "Apply": {
        "calculate", "compute", "solve", "use", "apply",
        "demonstrate", "implement", "perform", "determine",
        "show"
    },
    "Analyze": {
        "analyze", "analyse", "compare", "contrast",
        "differentiate", "examine", "investigate",
        "categorize", "deconstruct", "relate"
    },
    "Evaluate": {
        "evaluate", "assess", "judge", "justify",
        "critique", "defend", "appraise", "argue",
        "validate", "recommend"
    },
    "Create": {
        "create", "design", "develop", "construct",
        "formulate", "produce", "propose", "generate",
        "compose", "plan", "invent"
    }
}

COMMAND_WORDS = set()

for values in BLOOM_VERBS.values():
    COMMAND_WORDS.update(values)

COMMAND_WORDS.update({
    "derive",
    "prove",
    "calculate",
    "determine",
    "distinguish",
    "interpret",
    "write",
    "discuss"
})


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because",
    "been", "being", "but", "by", "can", "could", "did",
    "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "here", "him", "his", "how", "i", "if",
    "in", "into", "is", "it", "its", "may", "might",
    "more", "most", "must", "of", "on", "or", "our",
    "should", "so", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this",
    "those", "to", "under", "was", "we", "were", "what",
    "when", "where", "which", "who", "why", "will",
    "with", "would", "you", "your", "using", "use",
    "given", "following"
}


# ============================================================
# SUBJECT LEXICONS
# ============================================================

DOMAIN_LEXICONS = {
    "Chemistry": {
        "atom", "molecule", "element", "compound", "ion",
        "bond", "ionic", "covalent", "molarity", "mole",
        "stoichiometry", "reaction", "equilibrium", "acid",
        "base", "ph", "buffer", "oxidation", "reduction",
        "redox", "enthalpy", "entropy", "thermodynamics",
        "organic", "inorganic", "alkane", "alkene", "alkyne",
        "benzene", "polymer", "periodic", "electron", "proton",
        "neutron", "isotope", "catalyst", "precipitate",
        "titration", "solution", "concentration", "solubility",
        "spectroscopy", "nmr", "chromatography"
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
        "computer", "software", "hardware", "operating",
        "system", "data", "structure", "array", "linked",
        "list", "stack", "queue", "tree", "graph", "recursion",
        "class", "object", "inheritance", "polymorphism",
        "compiler", "api", "machine", "learning",
        "artificial", "intelligence", "cybersecurity",
        "encryption", "binary"
    },

    "Biology": {
        "cell", "organism", "tissue", "organ", "gene",
        "genetic", "dna", "rna", "protein", "enzyme",
        "metabolism", "mitosis", "meiosis", "chromosome",
        "evolution", "species", "ecology", "ecosystem",
        "photosynthesis", "respiration", "membrane",
        "bacteria", "virus", "microbiology", "physiology",
        "anatomy", "homeostasis", "mutation", "heredity"
    },

    "English / Language": {
        "grammar", "sentence", "paragraph", "essay", "writing",
        "reading", "author", "tone", "purpose", "main", "idea",
        "thesis", "argument", "rhetorical", "audience",
        "vocabulary", "syntax", "morphology", "phonology",
        "semantics", "pragmatics", "paraphrase", "composition",
        "communication", "language", "discourse", "pronunciation",
        "listening", "speaking", "literacy"
    },

    "Literature": {
        "novel", "poem", "poetry", "fiction", "character",
        "plot", "setting", "theme", "symbolism", "metaphor",
        "imagery", "narrator", "narrative", "protagonist",
        "antagonist", "drama", "tragedy", "sonnet", "literary",
        "interpretation", "literature", "genre"
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
        "investment", "portfolio", "interest", "capital",
        "ratio", "dividend"
    },

    "Economics": {
        "economics", "economic", "demand", "supply", "price",
        "market", "inflation", "unemployment", "gdp", "fiscal",
        "monetary", "policy", "elasticity", "utility", "consumer",
        "producer", "equilibrium", "macro", "micro", "trade",
        "exchange", "currency", "opportunity", "cost"
    },

    "Engineering": {
        "engineering", "mechanical", "electrical", "civil",
        "structural", "material", "machine", "stress", "strain",
        "load", "beam", "circuit", "voltage", "current",
        "thermodynamics", "fluid", "control", "manufacturing",
        "prototype", "cad", "system", "process"
    },

    "Psychology": {
        "psychology", "behavior", "behaviour", "cognitive",
        "memory", "perception", "emotion", "personality",
        "learning", "development", "motivation", "psychological",
        "therapy", "conditioning", "reinforcement", "mental",
        "attitude", "intelligence"
    },

    "Sociology": {
        "society", "social", "sociology", "culture", "community",
        "class", "inequality", "gender", "institution", "family",
        "socialization", "deviance", "norm", "status", "role",
        "population", "urbanization", "globalization"
    },

    "Education": {
        "education", "teaching", "learning", "pedagogy",
        "curriculum", "instruction", "assessment", "classroom",
        "teacher", "student", "lesson", "outcome", "rubric",
        "evaluation", "educational", "formative", "summative"
    },

    "History": {
        "history", "historical", "empire", "war", "revolution",
        "colonial", "colonialism", "independence", "treaty",
        "dynasty", "kingdom", "civilization", "ancient",
        "medieval", "movement", "era", "century", "migration"
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
        "bioavailability", "receptor", "antibiotic"
    },

    "Medical / Health Sciences": {
        "patient", "disease", "diagnosis", "symptom", "clinical",
        "medical", "health", "anatomy", "physiology", "pathology",
        "treatment", "therapy", "infection", "hospital", "nursing",
        "blood", "heart", "lung", "syndrome"
    },

    "Environmental Science": {
        "environment", "ecosystem", "pollution", "climate",
        "biodiversity", "conservation", "sustainability",
        "waste", "water", "air", "soil", "renewable",
        "carbon", "greenhouse", "ecology", "deforestation",
        "resource"
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
    "environmental science": "Environmental Science"
}


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\ufeff", "")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def normalize(text):
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def stem(word):
    word = word.lower()

    if len(word) <= 4:
        return word

    suffixes = [
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
        "s"
    ]

    for suffix in suffixes:
        if word.endswith(suffix):
            if len(word) - len(suffix) >= 4:
                return word[:-len(suffix)]

    return word


def content_tokens(text):
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


def read_pdf(data):
    if fitz is None:
        return "", "PyMuPDF is not installed.", {}

    try:
        document = fitz.open(
            stream=data,
            filetype="pdf"
        )
    except Exception as exc:
        return "", f"Could not open PDF: {exc}", {}

    pages = []
    text_pages = 0
    ocr_pages = 0
    failed_pages = 0

    for page in document:
        try:
            text = page.get_text("text") or ""
        except Exception:
            text = ""

        text = clean_text(text)

        if len(re.sub(r"\s+", "", text)) >= 25:
            pages.append(text)
            text_pages += 1
        else:
            pages.append("")

    for index, page_text in enumerate(pages):

        if page_text:
            continue

        if not tesseract_available():
            failed_pages += 1
            continue

        image = render_page(
            document[index]
        )

        if image is None:
            failed_pages += 1
            continue

        try:
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6"
            )

            text = clean_text(text)

            if len(re.sub(r"\s+", "", text)) >= 15:
                pages[index] = text
                ocr_pages += 1
            else:
                failed_pages += 1

        except Exception:
            failed_pages += 1

    parts = []

    for index, page_text in enumerate(pages):
        if page_text:
            parts.append(
                f"--- PAGE {index + 1} ---\n{page_text}"
            )

    combined = "\n\n".join(parts)

    diagnostics = {
        "pages": len(document),
        "text_pages": text_pages,
        "ocr_pages": ocr_pages,
        "failed_pages": failed_pages
    }

    if not combined:
        if not tesseract_available():
            return (
                "",
                "This PDF appears to be scanned, but OCR is not "
                "available. Install Tesseract using packages.txt.",
                diagnostics
            )

        return (
            "",
            "The PDF opened successfully, but no readable text "
            "was detected.",
            diagnostics
        )

    return combined, "", diagnostics


def read_docx(data):
    if Document is None:
        return "", "python-docx is not installed.", {}

    try:
        document = Document(
            io.BytesIO(data)
        )

        parts = []

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()

            if text:
                parts.append(text)

        for table in document.tables:
            for row in table.rows:
                values = []

                for cell in row.cells:
                    value = cell.text.strip()

                    if value:
                        values.append(value)

                if values:
                    parts.append(
                        " | ".join(values)
                    )

        return "\n".join(parts), "", {}

    except Exception as exc:
        return "", f"Could not read DOCX: {exc}", {}


def read_excel(data):
    try:
        workbook = pd.ExcelFile(
            io.BytesIO(data)
        )

        parts = []

        for sheet in workbook.sheet_names:

            parts.append(
                f"--- SHEET: {sheet} ---"
            )

            frame = pd.read_excel(
                workbook,
                sheet_name=sheet,
                header=None
            )

            for row in frame.fillna("").astype(str).values:

                values = [
                    value.strip()
                    for value in row
                    if value.strip()
                ]

                if values:
                    parts.append(
                        " | ".join(values)
                    )

        return "\n".join(parts), "", {}

    except Exception as exc:
        return "", f"Could not read Excel file: {exc}", {}


def read_csv(data):
    try:
        frame = pd.read_csv(
            io.BytesIO(data),
            header=None
        )

        parts = []

        for row in frame.fillna("").astype(str).values:

            values = [
                value.strip()
                for value in row
                if value.strip()
            ]

            if values:
                parts.append(
                    " | ".join(values)
                )

        return "\n".join(parts), "", {}

    except Exception:

        try:
            return (
                data.decode(
                    "utf-8",
                    errors="ignore"
                ),
                "",
                {}
            )
        except Exception as exc:
            return "", str(exc), {}


def read_file(uploaded_file):
    filename = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if filename.endswith(".pdf"):
        return read_pdf(data)

    if filename.endswith(".docx"):
        return read_docx(data)

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return read_excel(data)

    if filename.endswith(".csv"):
        return read_csv(data)

    if filename.endswith(".txt"):
        return (
            data.decode(
                "utf-8",
                errors="ignore"
            ),
            "",
            {}
        )

    return (
        "",
        "Unsupported file type.",
        {}
    )


# ============================================================
# CLO / PLO PARSER
# ============================================================

def parse_outcomes(text, prefix):
    outcomes = {}

    pattern = re.compile(
        rf"^\s*({prefix}\s*\d+)\s*[:\-\)]\s*(.+?)\s*$",
        re.IGNORECASE
    )

    for line in text.splitlines():

        line = clean_text(line)

        match = pattern.match(line)

        if match:
            key = re.sub(
                r"\s+",
                "",
                match.group(1).upper()
            )

            outcomes[key] = match.group(2).strip()

    return outcomes


# ============================================================
# QUESTION EXTRACTION
# ============================================================

PAGE_MARKER_RE = re.compile(
    r"^\s*(?:page\s*)?\d+\s*(?:/|of)\s*\d+\s*$",
    re.IGNORECASE
)

TIME_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*$",
    re.IGNORECASE
)

DATE_RE = re.compile(
    r"^\s*(?:"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r"|"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r")\s*$"
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
    r"^\s*(?:"
    r"\(?[A-Da-d]\)"
    r"|"
    r"[A-Da-d][\.\:]"
    r"|"
    r"\(?[1-4]\)"
    r")\s+.+$"
)


def is_metadata(line):
    line = clean_text(line)

    if not line:
        return True

    if PAGE_MARKER_RE.match(line):
        return True

    if TIME_RE.match(line):
        return True

    if DATE_RE.match(line):
        return True

    lowered = line.lower()

    blocked_phrases = [
        "questionwell",
        "question set",
        "generated by",
        "answer key",
        "student name",
        "roll number",
        "registration number",
        "course code:",
        "course title:",
        "instructor:",
        "date:",
        "time:"
    ]

    for phrase in blocked_phrases:
        if phrase in lowered:
            return True

    # Examples such as /19/26
    if re.fullmatch(
        r"[/\\\d\-\s]+",
        line
    ):
        return True

    return False


def is_question_candidate(text):
    text = clean_text(text)

    if not text:
        return False

    if is_metadata(text):
        return False

    words = normalize(text).split()

    if len(words) < 5:
        return False

    # Direct question
    if text.endswith("?"):
        return True

    # Direct assessment command
    if words[0] in COMMAND_WORDS:
        return True

    # Question word
    if words[0] in {
        "what",
        "why",
        "how",
        "which",
        "when",
        "where",
        "who"
    }:
        return True

    return False


def remove_mcq_options(text):
    lines = text.splitlines()

    kept = []

    for line in lines:

        if OPTION_RE.match(line):
            continue

        kept.append(line)

    return clean_text(
        " ".join(kept)
    )


def extract_questions(text):
    text = text.replace(
        "\r\n",
        "\n"
    ).replace(
        "\r",
        "\n"
    )

    raw_lines = []

    for line in text.split("\n"):

        line = clean_text(line)

        if line:
            raw_lines.append(line)

    # Remove repeated headers and footers
    counts = Counter(
        normalize(line)
        for line in raw_lines
        if len(normalize(line)) > 5
    )

    repeated_lines = {
        value
        for value, count in counts.items()
        if count >= 3
    }

    lines = []

    for line in raw_lines:

        if line.startswith("--- PAGE"):
            continue

        if normalize(line) in repeated_lines:
            continue

        lines.append(line)

    questions = []

    current = []
    current_number = None

    def finalize():

        nonlocal current
        nonlocal current_number

        if not current:
            return

        candidate = clean_text(
            " ".join(current)
        )

        candidate = remove_mcq_options(
            candidate
        )

        if is_question_candidate(candidate):

            questions.append({
                "number": current_number,
                "text": candidate
            })

        current = []
        current_number = None

    for line in lines:

        if is_metadata(line):
            continue

        numbered = NUMBERED_QUESTION_RE.match(
            line
        )

        if numbered:

            number = int(
                numbered.group(1)
            )

            body = clean_text(
                numbered.group(2)
            )

            if is_question_candidate(body):

                finalize()

                current_number = number
                current = [body]

                continue

        # Ignore answer options
        if OPTION_RE.match(line):

            if current:
                continue

        # If there is an active question,
        # this is probably its continuation.
        if current:

            current.append(line)

        else:

            # Unnumbered question
            if is_question_candidate(line):

                current = [line]
                current_number = None

    finalize()

    # Deduplicate
    final_questions = []
    seen = set()

    for question in questions:

        value = normalize(
            question["text"]
        )

        if len(value) < 20:
            continue

        if value in seen:
            continue

        seen.add(value)

        # Extra safety filters
        if PAGE_MARKER_RE.match(
            question["text"]
        ):
            continue

        if TIME_RE.match(
            question["text"]
        ):
            continue

        if "questionwell" in value:
            continue

        final_questions.append(
            question
        )

    return final_questions


# ============================================================
# DOMAIN DETECTION
# ============================================================

def detect_domain(
    course_name,
    clos,
    plos,
    reference_text=""
):
    combined = " ".join([
        course_name or "",
        " ".join(clos.values()),
        " ".join(plos.values()),
        reference_text or ""
    ])

    normalized = normalize(
        combined
    )

    scores = {
        domain: 0
        for domain in DOMAIN_LEXICONS
    }

    # Course-name aliases have stronger weight
    for alias, domain in DOMAIN_ALIASES.items():

        if alias in normalized:
            scores[domain] += 8

    combined_tokens = content_tokens(
        combined
    )

    for domain, lexicon in DOMAIN_LEXICONS.items():

        lexicon_stems = {
            stem(term)
            for term in lexicon
        }

        hits = combined_tokens.intersection(
            lexicon_stems
        )

        scores[domain] += len(hits)

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    best_domain, best_score = ranked[0]

    if best_score == 0:
        return "Unknown", 0

    second_score = (
        ranked[1][1]
        if len(ranked) > 1
        else 0
    )

    confidence = 55

    if best_score >= 5:
        confidence += 15

    if best_score >= second_score + 2:
        confidence += 15

    course_normalized = normalize(
        course_name
    )

    for alias, domain in DOMAIN_ALIASES.items():

        if alias in course_normalized:
            if domain == best_domain:
                confidence += 15

    return (
        best_domain,
        min(confidence, 100)
    )


def check_subject(
    question,
    expected_domain
):
    if expected_domain == "Unknown":
        return (
            "REVIEW",
            0,
            "The course subject could not be established."
        )

    question_tokens = content_tokens(
        question
    )

    expected_terms = {
        stem(x)
        for x in DOMAIN_LEXICONS.get(
            expected_domain,
            set()
        )
    }

    expected_hits = question_tokens.intersection(
        expected_terms
    )

    other_matches = []

    for domain, lexicon in DOMAIN_LEXICONS.items():

        if domain == expected_domain:
            continue

        domain_terms = {
            stem(x)
            for x in lexicon
        }

        hits = question_tokens.intersection(
            domain_terms
        )

        if hits:
            other_matches.append(
                (domain, len(hits))
            )

    other_matches.sort(
        key=lambda x: x[1],
        reverse=True
    )

    strongest_other = (
        other_matches[0]
        if other_matches
        else None
    )

    if len(expected_hits) >= 2:

        if (
            strongest_other
            and strongest_other[1] >= 3
        ):
            return (
                "REVIEW",
                60,
                "The question contains mixed subject evidence."
            )

        return (
            "PASS",
            min(
                95,
                70 + len(expected_hits) * 5
            ),
            f"Strong {expected_domain} evidence detected."
        )

    if len(expected_hits) == 1:

        return (
            "REVIEW",
            60,
            "Only limited subject-specific evidence was detected."
        )

    if (
        strongest_other
        and strongest_other[1] >= 2
    ):
        return (
            "FAIL",
            15,
            f"The question appears more related to "
            f"{strongest_other[0]}."
        )

    return (
        "FAIL",
        20,
        f"No reliable {expected_domain} evidence was detected."
    )


# ============================================================
# CLO / PLO ALIGNMENT
# ============================================================

def outcome_score(question, outcome):

    q_tokens = content_tokens(
        question
    )

    o_tokens = content_tokens(
        outcome
    )

    if not q_tokens or not o_tokens:
        return (
            0,
            "No meaningful terms were available."
        )

    overlap = q_tokens.intersection(
        o_tokens
    )

    if not overlap:
        return (
            0,
            "No meaningful content overlap."
        )

    precision = (
        len(overlap)
        / max(len(q_tokens), 1)
    )

    recall = (
        len(overlap)
        / max(len(o_tokens), 1)
    )

    if precision + recall == 0:
        f1 = 0
    else:
        f1 = (
            2 * precision * recall
            / (precision + recall)
        )

    score = min(
        100,
        round(f1 * 100)
    )

    if score >= 70:
        explanation = "Strong content alignment."
    elif score >= 50:
        explanation = "Partial content alignment."
    else:
        explanation = "Weak content alignment."

    return score, explanation


def best_outcome(question, outcomes):

    if not outcomes:
        return (
            "-",
            0,
            "No outcomes supplied."
        )

    matches = []

    for key, outcome in outcomes.items():

        score, explanation = outcome_score(
            question,
            outcome
        )

        matches.append(
            (
                score,
                key,
                explanation
            )
        )

    matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    score, key, explanation = matches[0]

    return (
        key,
        score,
        explanation
    )


# ============================================================
# BLOOM
# ============================================================

def detect_bloom(question):

    words = normalize(
        question
    ).split()

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

    level, score = ranked[0]

    if score > 0:
        return level, 100

    if not words:
        return "Unknown", 0

    first = words[0]

    if first in {
        "what",
        "who",
        "when",
        "where"
    }:
        return "Remember", 65

    if first == "why":
        return "Understand", 65

    if first == "how":
        return "Apply", 60

    return "Unknown", 0


def bloom_score(
    question,
    intended
):
    detected, confidence = detect_bloom(
        question
    )

    if intended == "Auto-detect":

        return (
            detected,
            confidence,
            "Bloom level was automatically detected."
        )

    if detected == intended:

        return (
            detected,
            100,
            "Bloom level matches the selected level."
        )

    if detected == "Unknown":

        return (
            detected,
            20,
            "No reliable Bloom operation was detected."
        )

    distance = abs(
        BLOOM_RANK[detected]
        - BLOOM_RANK[intended]
    )

    if distance == 1:

        return (
            detected,
            60,
            f"Detected {detected}; expected {intended}."
        )

    return (
        detected,
        20,
        f"Detected {detected}; expected {intended}."
    )


# ============================================================
# QUALITY
# ============================================================

def quality_score(question):

    score = 100

    words = normalize(
        question
    ).split()

    if len(words) < 6:
        score -= 20

    if len(words) > 80:
        score -= 15

    if re.search(
        r"\b(etc|something|anything|and so on)\b",
        question.lower()
    ):
        score -= 15

    if (
        not question.endswith("?")
        and not any(
            word in COMMAND_WORDS
            for word in words
        )
    ):
        score -= 15

    return max(
        0,
        min(score, 100)
    )


# ============================================================
# COMPLETE QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    course_domain,
    clos,
    plos,
    intended_bloom
):

    subject_status, subject_score, subject_reason = (
        check_subject(
            question,
            course_domain
        )
    )

    result = {
        "Question": question,
        "Subject": subject_score,
        "Subject Status": subject_status,
        "Subject Reason": subject_reason,
        "CLO": 0,
        "CLO ID": "-",
        "CLO Reason": "",
        "PLO": None,
        "PLO ID": "N/A",
        "PLO Reason": "",
        "Bloom": 0,
        "Detected Bloom": "-",
        "Bloom Reason": "",
        "Quality": 0,
        "Decision": "REJECTED",
        "Reason": "",
        "Alignment Attained": False
    }

    # SUBJECT IS A HARD GATE
    if subject_status != "PASS":

        result["Reason"] = (
            "Subject relevance failed. "
            "CLO, PLO and Bloom scores are not trusted "
            "for approval."
        )

        return result

    clo_id, clo_score, clo_reason = best_outcome(
        question,
        clos
    )

    result["CLO"] = clo_score
    result["CLO ID"] = clo_id
    result["CLO Reason"] = clo_reason

    if plos:

        plo_id, plo_score, plo_reason = best_outcome(
            question,
            plos
        )

        result["PLO"] = plo_score
        result["PLO ID"] = plo_id
        result["PLO Reason"] = plo_reason

    detected, bloom, bloom_reason = bloom_score(
        question,
        intended_bloom
    )

    result["Bloom"] = bloom
    result["Detected Bloom"] = detected
    result["Bloom Reason"] = bloom_reason

    result["Quality"] = quality_score(
        question
    )

    # HARD CLO GATE
    if clo_score < 60:

        result["Decision"] = "REJECTED"

        result["Reason"] = (
            "CLO alignment is below 60%."
        )

        return result

    # HARD BLOOM GATE
    if (
        intended_bloom != "Auto-detect"
        and bloom < 80
    ):

        result["Decision"] = "REJECTED"

        result["Reason"] = (
            f"The question does not adequately match "
            f"the selected Bloom level: {intended_bloom}."
        )

        return result

    # PLO SUPPORTING GATE
    if (
        result["PLO"] is not None
        and result["PLO"] < 45
    ):

        result["Decision"] = "NEEDS REVIEW"

        result["Reason"] = (
            "CLO and Bloom conditions pass, but "
            "PLO alignment is weak."
        )

        return result

    # QUALITY
    if result["Quality"] < 60:

        result["Decision"] = "NEEDS REVIEW"

        result["Reason"] = (
            "Question clarity or structure needs improvement."
        )

        return result

    result["Decision"] = "APPROVED"

    result["Reason"] = (
        "The question satisfies the required "
        "subject, CLO and Bloom alignment conditions."
    )

    result["Alignment Attained"] = True

    return result


# ============================================================
# DIRECT REVISION
# ============================================================

def clo_topic(clo_text):

    text = re.sub(
        r"^\s*CLO\s*\d+\s*[:\-\)]\s*",
        "",
        clo_text,
        flags=re.IGNORECASE
    )

    words = normalize(
        text
    ).split()

    all_bloom_words = set()

    for values in BLOOM_VERBS.values():
        all_bloom_words.update(values)

    topic = [
        word
        for word in words
        if word not in all_bloom_words
        and word not in STOP_WORDS
    ]

    if topic:
        return " ".join(
            topic[:12]
        )

    return text


def make_revision(
    result,
    clos,
    intended_bloom
):

    clo_id = result.get(
        "CLO ID",
        "-"
    )

    if clo_id == "-" or clo_id not in clos:

        return (
            "No reliable CLO was matched, so a direct "
            "revision cannot be generated safely."
        )

    topic = clo_topic(
        clos[clo_id]
    )

    if intended_bloom == "Auto-detect":

        detected, _ = detect_bloom(
            result["Question"]
        )

        if detected == "Unknown":
            intended_bloom = "Understand"
        else:
            intended_bloom = detected

    if intended_bloom == "Remember":

        return (
            f"Define {topic} and state its main characteristics."
        )

    if intended_bloom == "Understand":

        return (
            f"Explain {topic} in your own words and "
            f"describe its main characteristics."
        )

    if intended_bloom == "Apply":

        return (
            f"Apply {topic} to solve the following problem "
            f"and show the steps used to obtain your answer."
        )

    if intended_bloom == "Analyze":

        return (
            f"Analyze {topic} by identifying its key components "
            f"and explaining their relationship."
        )

    if intended_bloom == "Evaluate":

        return (
            f"Evaluate {topic} using relevant evidence and "
            f"justify your conclusion."
        )

    if intended_bloom == "Create":

        return (
            f"Design a solution using {topic} and explain "
            f"how the proposed solution works."
        )

    return (
        f"Explain {topic} and describe its main characteristics."
    )


# ============================================================
# THREE-DIMENSIONAL GRAPH
# ============================================================

def alignment_graph(results):

    valid = [
        r for r in results
        if r["Subject Status"] == "PASS"
    ]

    if not valid:
        return

    clo = sum(
        r["CLO"]
        for r in valid
    ) / len(valid)

    plo_values = [
        r["PLO"]
        for r in valid
        if r["PLO"] is not None
    ]

    plo = (
        sum(plo_values)
        / len(plo_values)
        if plo_values
        else 0
    )

    bloom = sum(
        r["Bloom"]
        for r in valid
    ) / len(valid)

    st.subheader(
        "📊 Three-Dimensional Alignment"
    )

    st.caption(
        "CLO, PLO and Bloom alignment across questions "
        "whose subject relevance passed."
    )

    try:

        import matplotlib.pyplot as plt
        import numpy as np

        labels = [
            "CLO",
            "PLO",
            "Bloom"
        ]

        values = [
            clo,
            plo,
            bloom
        ]

        angles = np.linspace(
            0,
            2 * np.pi,
            3,
            endpoint=False
        )

        values_closed = (
            values
            + values[:1]
        )

        angles_closed = (
            list(angles)
            + [angles[0]]
        )

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

        ax.set_theta_direction(
            -1
        )

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

        ax.set_xticks(
            angles
        )

        ax.set_xticklabels(
            labels
        )

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
            "CLO / PLO / Bloom Alignment",
            pad=25
        )

        st.pyplot(
            fig
        )

        plt.close(fig)

    except Exception:

        chart = pd.DataFrame({
            "Dimension": [
                "CLO",
                "PLO",
                "Bloom"
            ],
            "Alignment": [
                round(clo),
                round(plo),
                round(bloom)
            ]
        })

        st.bar_chart(
            chart.set_index(
                "Dimension"
            )
        )


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = []

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
    "CLO alignment, PLO alignment and Bloom's Taxonomy."
)

st.divider()


# ============================================================
# COURSE INPUT
# ============================================================

st.subheader(
    "1. Course Information"
)

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
    ]
)

reference_text = ""

if reference_file:

    reference_text, reference_error, _ = (
        read_file(
            reference_file
        )
    )

    if reference_error:

        st.warning(
            reference_error
        )

    else:

        st.success(
            "Course reference loaded."
        )


col1, col2 = st.columns(2)

with col1:

    clo_input = st.text_area(
        "Course Learning Outcomes (CLOs)",
        height=180,
        placeholder=(
            "CLO1: Explain the principles of chemical bonding.\n"
            "CLO2: Calculate molarity and concentration.\n"
            "CLO3: Analyze chemical reactions."
        )
    )

with col2:

    plo_input = st.text_area(
        "Program Learning Outcomes (PLOs)",
        height=180,
        placeholder=(
            "PLO1: Apply knowledge to solve problems.\n"
            "PLO2: Analyze information critically.\n"
            "PLO3: Communicate findings effectively."
        )
    )


# ============================================================
# ASSESSMENT SETTINGS
# ============================================================

st.subheader(
    "2. Assessment Settings"
)

bloom_level = st.selectbox(
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
            "Please enter the course / subject name."
        )

        st.stop()

    if not clo_input.strip():

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
        clo_input,
        "CLO"
    )

    plos = parse_outcomes(
        plo_input,
        "PLO"
    )

    if not clos:

        st.error(
            "No valid CLOs were detected. "
            "Use format such as CLO1: Explain..."
        )

        st.stop()

    with st.spinner(
        "Reading and evaluating assessment..."
    ):

        assessment_text, file_error, diagnostics = (
            read_file(
                assessment_file
            )
        )

    if file_error:

        st.error(
            file_error
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
            "The evaluator filters page numbers, dates, times, "
            "document headings, QuestionWell metadata and "
            "other non-question text."
        )

        with st.expander(
            "View extracted text"
        ):

            st.text(
                assessment_text[:10000]
            )

        st.stop()

    course_domain, confidence = detect_domain(
        course_name,
        clos,
        plos,
        reference_text
    )

    evaluated = []

    for question in questions:

        result = evaluate_question(
            question["text"],
            course_domain,
            clos,
            plos,
            bloom_level
        )

        result["Question Number"] = (
            question["number"]
        )

        evaluated.append(
            result
        )

    st.session_state.results = evaluated
    st.session_state.revised_results = {}


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.results

if results:

    st.divider()

    st.header(
        "📈 Results"
    )

    clos = parse_outcomes(
        clo_input,
        "CLO"
    )

    plos = parse_outcomes(
        plo_input,
        "PLO"
    )

    course_domain, confidence = detect_domain(
        course_name,
        clos,
        plos,
        reference_text
    )

    top1, top2, top3 = st.columns(3)

    with top1:

        st.metric(
            "Detected Subject",
            course_domain
        )

    with top2:

        st.metric(
            "Subject Confidence",
            f"{confidence}%"
        )

    with top3:

        st.metric(
            "Questions",
            len(results)
        )

    # ========================================================
    # GRAPH AT TOP OF RESULTS
    # ========================================================

    alignment_graph(
        results
    )

    st.divider()

    # ========================================================
    # COUNTS
    # ========================================================

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
            "Needs Review",
            review
        )

    with c4:
        st.metric(
            "Rejected",
            rejected
        )

    # ========================================================
    # TABLE
    # ========================================================

    st.subheader(
        "Assessment Alignment Results"
    )

    rows = []

    for index, result in enumerate(
        results,
        start=1
    ):

        rows.append({
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
                if (
                    result["PLO"] is not None
                    and result["Subject Status"] == "PASS"
                )
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

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # DETAILED QUESTIONS
    # ========================================================

    st.subheader(
        "Detailed Evaluation"
    )

    for index, result in enumerate(
        results,
        start=1
    ):

        if result["Decision"] == "APPROVED":
            icon = "✅"
        elif result["Decision"] == "NEEDS REVIEW":
            icon = "⚠️"
        else:
            icon = "❌"

        with st.expander(
            f"{icon} Question {index}"
        ):

            st.write(
                f"**Question:** {result['Question']}"
            )

            if result["Subject Status"] != "PASS":

                st.error(
                    f"Subject Gate: {result['Subject Reason']}"
                )

                st.warning(
                    "This question cannot be approved because "
                    "subject relevance is a mandatory gate."
                )

            else:

                m1, m2, m3, m4 = st.columns(4)

                with m1:
                    st.metric(
                        "Subject",
                        f"{result['Subject']}%"
                    )

                with m2:
                    st.metric(
                        "CLO",
                        f"{result['CLO']}%"
                    )

                with m3:
                    st.metric(
                        "PLO",
                        (
                            f"{result['PLO']}%"
                            if result["PLO"] is not None
                            else "N/A"
                        )
                    )

                with m4:
                    st.metric(
                        "Bloom",
                        f"{result['Bloom']}%"
                    )

                st.write(
                    f"**Matched CLO:** {result['CLO ID']}"
                )

                if result["CLO ID"] in clos:

                    st.caption(
                        clos[result["CLO ID"]]
                    )

                st.write(
                    f"**CLO:** {result['CLO Reason']}"
                )

                if result["PLO"] is not None:

                    st.write(
                        f"**Matched PLO:** {result['PLO ID']}"
                    )

                    st.write(
                        f"**PLO:** {result['PLO Reason']}"
                    )

                st.write(
                    f"**Detected Bloom:** "
                    f"{result['Detected Bloom']}"
                )

                st.write(
                    f"**Bloom:** {result['Bloom Reason']}"
                )

                st.write(
                    f"**Decision:** "
                    f"{result['Decision']}"
                )

                st.write(
                    f"**Reason:** "
                    f"{result['Reason']}"
                )

                # =================================================
                # REVISION
                # =================================================

                if result["Decision"] != "APPROVED":

                    st.markdown(
                        "### 🔧 Direct Revision"
                    )

                    revision = make_revision(
                        result,
                        clos,
                        bloom_level
                    )

                    st.info(
                        revision
                    )

                    if st.button(
                        "🔍 Test Revised Question",
                        key=f"test_revision_{index}"
                    ):

                        revised = evaluate_question(
                            revision,
                            course_domain,
                            clos,
                            plos,
                            bloom_level
                        )

                        st.session_state.revised_results[
                            index
                        ] = revised

                        st.rerun()

                # =================================================
                # REVISED QUESTION RESULT
                # =================================================

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
                                if (
                                    revised["PLO"] is not None
                                    and revised["Subject Status"] == "PASS"
                                )
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

                    # =============================================
                    # ACTUAL ALIGNMENT ATTAINED
                    # =============================================

                    if revised["Alignment Attained"]:

                        st.success(
                            "🎉 ALIGNMENT ATTAINED"
                        )

                        st.write(
                            "The revised question now satisfies "
                            "the required alignment conditions."
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

                        if bloom_level != "Auto-detect":

                            st.success(
                                "✓ Bloom alignment attained"
                            )

                        # Celebration ONLY after actual success.
                        st.balloons()

                    else:

                        st.warning(
                            "⚠️ Alignment has not yet been fully attained."
                        )

                        st.write(
                            f"**Reason:** {revised['Reason']}"
                        )


# ============================================================
# EXPORT
# ============================================================

if results:

    st.divider()

    st.subheader(
        "📥 Export Results"
    )

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
            "Decision": result["Decision"],
            "Reason": result["Reason"]
        })

    export_df = pd.DataFrame(
        export_rows
    )

    csv = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Results CSV",
        data=csv,
        file_name="obe_alignment_results.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# OCR INFORMATION
# ============================================================

with st.expander(
    "ℹ️ File Reading / OCR Information"
):

    st.write(
        "Supported files: PDF, DOCX, TXT, CSV, XLSX and XLS."
    )

    st.write(
        "For scanned PDFs, PyMuPDF renders pages and "
        "Tesseract OCR extracts the text."
    )

    st.write(
        "The question extractor deliberately ignores "
        "page numbers, dates, times, repeated headers, "
        "document titles and QuestionWell metadata."
    )
