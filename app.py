import io
import re
import textwrap
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# OPTIONAL PDF / DOCX LIBRARIES
# ============================================================

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from docx import Document
except Exception:
    Document = None


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
    level: i + 1 for i, level in enumerate(BLOOM_LEVELS)
}

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "label", "select"
    ],
    "Understand": [
        "explain", "describe", "summarize", "classify",
        "interpret", "paraphrase", "discuss", "illustrate"
    ],
    "Apply": [
        "apply", "calculate", "solve", "demonstrate",
        "use", "implement", "execute", "determine", "compute"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "distinguish",
        "examine", "compare", "contrast", "categorize",
        "investigate", "infer"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "defend", "judge", "appraise", "validate", "recommend"
    ],
    "Create": [
        "create", "design", "develop", "formulate",
        "produce", "generate", "construct", "plan",
        "compose", "propose"
    ]
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = set("""
a an the and or but if then than of to in on at for from with
by is are was were be been being this that these those it its
as into about through during before after above below between
which who whom whose what when where why how do does did will
would should could can may might must your their them they
you we our question questions following given use using used
appropriate relevant related
""".split())


# ============================================================
# SUBJECT DOMAINS
# ============================================================

DOMAIN_LEXICONS = {

    "Chemistry": """
    atom molecule element compound isotope ion electron proton neutron
    periodic table bonding ionic covalent metallic polarity electronegativity
    mole molarity concentration stoichiometry reaction reactant product
    equilibrium acid base pH buffer oxidation reduction redox catalyst
    kinetics rate activation energy thermodynamics enthalpy entropy organic
    hydrocarbon alkane alkene alkyne alcohol aldehyde ketone ester amine
    polymer spectroscopy chromatography solution solubility precipitate
    """,

    "Physics": """
    force motion velocity acceleration momentum energy work power mass
    gravity friction displacement projectile vector scalar torque rotation
    angular wave frequency wavelength amplitude optics lens mirror reflection
    refraction electricity voltage current resistance circuit charge magnetic
    field electromagnetic thermodynamics pressure temperature quantum
    """,

    "Mathematics": """
    equation algebra function derivative integral limit matrix vector
    probability statistics theorem proof set number polynomial logarithm
    exponential geometry trigonometry calculus sequence series slope
    coordinate graph variable coefficient inequality determinant
    """,

    "Computer Science": """
    algorithm programming code software computer data structure database
    network operating system process thread memory compiler recursion
    array linked list stack queue tree graph sorting searching complexity
    python java c++ class object inheritance polymorphism cybersecurity
    machine learning artificial intelligence api web
    """,

    "Biology": """
    cell tissue organ organism gene dna rna chromosome protein enzyme
    metabolism photosynthesis respiration evolution ecology population
    species genetics mutation mitosis meiosis membrane nucleus bacteria
    virus anatomy physiology homeostasis ecosystem biodiversity
    """,

    "English / Language": """
    reading writing paragraph essay thesis main idea topic sentence
    supporting detail pattern organization paraphrase summary tone purpose
    audience rhetoric grammar sentence vocabulary syntax morphology
    pronunciation listening speaking communication author style inference
    """,

    "Literature": """
    novel poem poetry drama fiction character setting plot theme narrator
    symbolism metaphor imagery irony tone perspective literary analysis
    author text stanza verse protagonist antagonist
    """,

    "Business / Management": """
    management organization leadership strategy planning marketing customer
    human resource operations decision making productivity performance
    organizational behavior entrepreneurship business model stakeholder
    supply chain competitive advantage
    """,

    "Accounting / Finance": """
    accounting ledger journal debit credit balance sheet income statement
    asset liability equity revenue expense cash flow audit taxation
    depreciation financial ratio investment portfolio risk return capital
    budgeting cost accounting
    """,

    "Economics": """
    economics demand supply market price inflation unemployment gdp
    fiscal monetary policy interest rate exchange rate elasticity consumer
    producer utility opportunity cost scarcity equilibrium trade tariff
    macroeconomics microeconomics
    """,

    "Engineering": """
    engineering design system material stress strain circuit machine
    structure fluid thermal manufacturing safety control sensor load
    mechanics electrical mechanical civil chemical process optimization
    """,

    "Psychology": """
    psychology behavior cognition memory learning perception motivation
    emotion personality development conditioning therapy mental process
    """,

    "Sociology": """
    society social culture institution class inequality family community
    identity norms values stratification socialization population
    """,

    "Education": """
    teaching learning pedagogy curriculum classroom assessment instruction
    student teacher education lesson plan learning theory formative
    summative rubric
    """,

    "History": """
    history historical empire colonialism revolution war treaty civilization
    dynasty independence migration chronology primary source historical
    event political social economic
    """,

    "Law": """
    law legal contract tort liability statute constitution court evidence
    crime criminal civil rights regulation case judgment jurisdiction
    """,

    "Pharmacy": """
    drug medicine dosage pharmacology prescription tablet capsule
    absorption distribution metabolism excretion adverse effect receptor
    therapeutic drug interaction formulation
    """,

    "Medical / Health Sciences": """
    patient diagnosis disease symptom treatment anatomy physiology clinical
    pathology infection organ blood tissue health nursing medical
    """,

    "Environmental Science": """
    environment pollution climate ecosystem sustainability waste water
    air biodiversity conservation carbon greenhouse renewable resource
    """
}


RELATED_DOMAINS = {
    "Chemistry": {
        "Chemistry", "Engineering", "Pharmacy", "Environmental Science"
    },
    "Physics": {
        "Physics", "Engineering"
    },
    "Mathematics": {
        "Mathematics", "Physics", "Engineering", "Economics"
    },
    "Computer Science": {
        "Computer Science", "Engineering"
    },
    "Biology": {
        "Biology", "Medical / Health Sciences",
        "Pharmacy", "Environmental Science"
    },
    "English / Language": {
        "English / Language", "Literature", "Education"
    },
    "Literature": {
        "Literature", "English / Language", "History"
    },
    "Business / Management": {
        "Business / Management",
        "Accounting / Finance",
        "Economics",
        "Education"
    },
    "Accounting / Finance": {
        "Accounting / Finance",
        "Business / Management",
        "Economics"
    },
    "Economics": {
        "Economics",
        "Business / Management",
        "Accounting / Finance",
        "Mathematics"
    },
    "Engineering": {
        "Engineering",
        "Physics",
        "Mathematics",
        "Computer Science",
        "Chemistry"
    },
    "Psychology": {
        "Psychology",
        "Education",
        "Sociology"
    },
    "Sociology": {
        "Sociology",
        "Psychology",
        "History",
        "Education"
    },
    "Education": {
        "Education",
        "Psychology",
        "English / Language"
    },
    "History": {
        "History",
        "Sociology",
        "Literature"
    },
    "Law": {
        "Law",
        "History",
        "Business / Management"
    },
    "Pharmacy": {
        "Pharmacy",
        "Chemistry",
        "Biology",
        "Medical / Health Sciences"
    },
    "Medical / Health Sciences": {
        "Medical / Health Sciences",
        "Biology",
        "Pharmacy"
    },
    "Environmental Science": {
        "Environmental Science",
        "Biology",
        "Chemistry",
        "Engineering"
    }
}


# ============================================================
# TEXT FUNCTIONS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value).replace("\x00", " ")
    value = value.replace("\r\n", "\n")
    value = value.replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def normalize_text(value):
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(value):
    return [
        word
        for word in normalize_text(value).split()
        if len(word) > 2 and word not in STOP_WORDS
    ]


def stem_light(word):
    word = word.lower()

    for suffix in ["ing", "ed", "es", "s"]:
        if len(word) > 5 and word.endswith(suffix):
            return word[:-len(suffix)]

    return word


def content_tokens(value):
    return {
        stem_light(word)
        for word in tokens(value)
        if len(word) >= 4
    }


def overlap_score(text_a, text_b):
    a = content_tokens(text_a)
    b = content_tokens(text_b)

    if not a or not b:
        return 0

    shared = a & b

    precision = len(shared) / len(a)
    recall = len(shared) / len(b)

    if precision + recall == 0:
        return 0

    f1 = 2 * precision * recall / (precision + recall)

    return round(f1 * 100, 1)


# ============================================================
# FILE READING
# ============================================================

def read_pdf_pypdf(data):
    if PdfReader is None:
        return ""

    try:
        reader = PdfReader(io.BytesIO(data))

        pages = []

        for page in reader.pages:
            try:
                text = page.extract_text() or ""

                if text.strip():
                    pages.append(text)
            except Exception:
                pass

        return clean_text("\n".join(pages))

    except Exception:
        return ""


def read_pdf_fitz(data):
    if fitz is None:
        return ""

    try:
        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in document:
            try:
                text = page.get_text("text") or ""

                if text.strip():
                    pages.append(text)

            except Exception:
                pass

        document.close()

        return clean_text("\n".join(pages))

    except Exception:
        return ""


def read_docx(data):
    if Document is None:
        return ""

    try:
        document = Document(io.BytesIO(data))

        parts = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text)

        for table in document.tables:
            for row in table.rows:
                cells = [
                    cell.text.strip()
                    for cell in row.cells
                ]

                line = " | ".join(
                    value for value in cells if value
                )

                if line:
                    parts.append(line)

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def read_excel(data):
    try:
        workbook = pd.ExcelFile(
            io.BytesIO(data)
        )

        parts = []

        for sheet in workbook.sheet_names:

            frame = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            parts.append(
                f"--- SHEET: {sheet} ---"
            )

            for row in frame.fillna("").astype(str).values:

                line = " | ".join(
                    value.strip()
                    for value in row
                    if value.strip()
                )

                if line:
                    parts.append(line)

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def extract_file(uploaded_file):

    if uploaded_file is None:
        return "", "No file"

    data = uploaded_file.getvalue()

    extension = Path(
        uploaded_file.name
    ).suffix.lower()

    if extension == ".pdf":

        text_a = read_pdf_pypdf(data)
        text_b = read_pdf_fitz(data)

        candidates = [
            (text_a, "pypdf"),
            (text_b, "PyMuPDF")
        ]

        best = max(
            candidates,
            key=lambda x: len(x[0])
        )

        if best[0]:
            return best[0], best[1]

        return "", "PDF could not be read"

    if extension == ".docx":
        return read_docx(data), "DOCX"

    if extension in [".xlsx", ".xls"]:
        return read_excel(data), "Excel"

    if extension == ".csv":

        try:
            frame = pd.read_csv(
                io.BytesIO(data)
            )

            return (
                frame.to_string(index=False),
                "CSV"
            )

        except Exception:
            return "", "CSV could not be read"

    if extension in [".txt", ".md"]:

        return (
            data.decode(
                "utf-8",
                errors="ignore"
            ),
            "Text"
        )

    return "", f"Unsupported file type: {extension}"


# ============================================================
# CLO / PLO PARSER
# ============================================================

def parse_outcomes(text, prefix):

    if not text:
        return []

    results = []

    pattern = re.compile(
        rf"^\s*(?:[-*•]\s*)?"
        rf"{prefix}\s*[-_–—]?\s*(\d+)"
        rf"\s*(?:[:.)\-–—]\s*|\s+)"
        rf"(.+?)$",
        re.I
    )

    for line in clean_text(text).splitlines():

        line = line.strip()

        match = pattern.match(line)

        if match:

            description = clean_text(
                match.group(2)
            ).strip(" :-–—.)")

            if len(description) >= 4:

                results.append({
                    "id": f"{prefix}{match.group(1)}",
                    "text": description
                })

    return results


# ============================================================
# QUESTION EXTRACTION
# ============================================================

QUESTION_NUMBER = re.compile(
    r"(?im)^\s*(?:question\s*)?"
    r"(\d{1,3})\s*[\.\):\-–—]\s+"
)


def split_options(text):

    pattern = re.compile(
        r"(?im)(?:^|\n)\s*"
        r"[\(\[]?([A-H])[\)\]\.:]\s+"
    )

    matches = list(
        pattern.finditer(text)
    )

    if not matches:
        return text.strip(), []

    question_text = text[
        :matches[0].start()
    ].strip()

    options = []

    for index, match in enumerate(matches):

        start = match.end()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        option_text = clean_text(
            text[start:end]
        )

        if option_text:

            options.append({
                "label": match.group(1).upper(),
                "text": option_text
            })

    return question_text, options


def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    questions = []

    matches = list(
        QUESTION_NUMBER.finditer(text)
    )

    if matches:

        for index, match in enumerate(matches):

            start = match.end()

            if index + 1 < len(matches):
                end = matches[index + 1].start()
            else:
                end = len(text)

            block = text[start:end].strip()

            if not block:
                continue

            question_text, options = split_options(
                block
            )

            question_text = re.sub(
                r"(?im)^\s*"
                r"(answer|correct answer|key)"
                r"\s*[:\-].*$",
                "",
                question_text
            ).strip()

            if len(question_text) >= 8:

                questions.append({
                    "number": len(questions) + 1,
                    "text": clean_text(question_text),
                    "options": options
                })

    # Fallback for non-numbered questions
    if not questions:

        paragraphs = re.split(
            r"\n{2,}",
            text
        )

        for paragraph in paragraphs:

            paragraph = clean_text(
                paragraph
            )

            if len(paragraph) < 10:
                continue

            if re.match(
                r"(?i)^(identify|define|explain|"
                r"describe|analyze|analyse|evaluate|"
                r"compare|contrast|calculate|determine|"
                r"apply|discuss|what|which|why|how)\b",
                paragraph
            ):

                question_text, options = split_options(
                    paragraph
                )

                questions.append({
                    "number": len(questions) + 1,
                    "text": clean_text(question_text),
                    "options": options
                })

    # Final fallback for sentences ending in ?
    if not questions:

        sentences = re.split(
            r"(?<=\?)\s+",
            text
        )

        for sentence in sentences:

            sentence = clean_text(sentence)

            if len(sentence) >= 12 and "?" in sentence:

                questions.append({
                    "number": len(questions) + 1,
                    "text": sentence,
                    "options": []
                })

    return questions


# ============================================================
# SUBJECT DETECTION
# ============================================================

COURSE_ALIASES = {

    "chemistry": "Chemistry",
    "organic chemistry": "Chemistry",
    "inorganic chemistry": "Chemistry",

    "physics": "Physics",

    "mathematics": "Mathematics",
    "math": "Mathematics",
    "calculus": "Mathematics",

    "computer science": "Computer Science",
    "programming": "Computer Science",
    "data structures": "Computer Science",
    "database": "Computer Science",

    "biology": "Biology",

    "english": "English / Language",
    "english i": "English / Language",
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
    "nursing": "Medical / Health Sciences",

    "environmental science": "Environmental Science"
}


def domain_hits(text):

    normalized = normalize_text(text)

    results = {}

    for domain, vocabulary in DOMAIN_LEXICONS.items():

        terms = set(
            normalize_text(vocabulary).split()
        )

        hits = set()

        for term in terms:

            if len(term) < 4:
                continue

            if re.search(
                rf"\b{re.escape(term)}\b",
                normalized
            ):
                hits.add(term)

        results[domain] = hits

    return results


def determine_course_domain(
    course_name,
    clos,
    plos,
    assessment_text
):

    course = normalize_text(
        course_name
    )

    # Course name is strongest evidence.
    for alias, domain in sorted(
        COURSE_ALIASES.items(),
        key=lambda x: len(x[0]),
        reverse=True
    ):

        if re.search(
            rf"\b{re.escape(alias)}\b",
            course
        ):
            return domain, 100

    combined = " ".join(
        [course_name] +
        [item["text"] for item in clos] +
        [item["text"] for item in plos]
    )

    hits = domain_hits(combined)

    ranked = sorted(
        [
            (domain, len(words))
            for domain, words in hits.items()
        ],
        key=lambda x: x[1],
        reverse=True
    )

    if not ranked or ranked[0][1] == 0:

        hits = domain_hits(
            assessment_text
        )

        ranked = sorted(
            [
                (domain, len(words))
                for domain, words in hits.items()
            ],
            key=lambda x: x[1],
            reverse=True
        )

    if not ranked or ranked[0][1] == 0:
        return "Unknown", 0

    domain, count = ranked[0]

    confidence = min(
        95,
        45 + count * 8
    )

    return domain, confidence


def question_subject_check(
    question,
    expected_domain
):

    hits = domain_hits(question)

    counts = {
        domain: len(words)
        for domain, words in hits.items()
    }

    expected_hits = counts.get(
        expected_domain,
        0
    )

    ranked = sorted(
        counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    strongest_domain = "Unknown"
    strongest_count = 0

    if ranked and ranked[0][1] > 0:

        strongest_domain = ranked[0][0]
        strongest_count = ranked[0][1]

    related = RELATED_DOMAINS.get(
        expected_domain,
        {expected_domain}
    )

    related_hits = sum(
        counts.get(domain, 0)
        for domain in related
    )

    # --------------------------------------------------------
    # HARD SUBJECT MISMATCH
    # --------------------------------------------------------

    if (
        strongest_domain != "Unknown"
        and strongest_domain not in related
        and strongest_count >= 2
        and strongest_count > expected_hits
    ):

        return {
            "score": 0,
            "status": "FAIL",
            "detected": strongest_domain,
            "reason": (
                f"The question contains stronger subject-specific "
                f"evidence for {strongest_domain} than for "
                f"{expected_domain}."
            )
        }

    # --------------------------------------------------------
    # STRONG EXPECTED SUBJECT EVIDENCE
    # --------------------------------------------------------

    if expected_hits >= 2:

        score = min(
            100,
            60 + expected_hits * 10
        )

        return {
            "score": score,
            "status": "PASS",
            "detected": strongest_domain,
            "reason": (
                f"The question contains {expected_hits} "
                f"subject-specific term(s) consistent with "
                f"{expected_domain}."
            )
        }

    # Related subject evidence
    if related_hits >= 2:

        return {
            "score": 75,
            "status": "PASS",
            "detected": strongest_domain,
            "reason": (
                "The question contains terminology from the "
                "expected or closely related disciplinary domain."
            )
        }

    # Unknown subject cannot be automatically approved.
    return {
        "score": 40,
        "status": "REVIEW",
        "detected": strongest_domain,
        "reason": (
            "The question does not contain enough subject-specific "
            "evidence to confirm its disciplinary relevance."
        )
    }


# ============================================================
# OUTCOME MATCHING
# ============================================================

def best_outcome_match(
    question,
    outcomes
):

    if not outcomes:
        return None, 0

    scores = []

    q_tokens = content_tokens(
        question
    )

    for outcome in outcomes:

        outcome_tokens = content_tokens(
            outcome["text"]
        )

        shared = (
            q_tokens & outcome_tokens
        )

        if outcome_tokens:

            coverage = (
                len(shared) /
                len(outcome_tokens)
            )

        else:
            coverage = 0

        question_coverage = (
            len(shared) /
            max(1, len(q_tokens))
        )

        score = (
            coverage * 70 +
            question_coverage * 30
        ) * 100

        scores.append(
            (
                outcome,
                round(
                    min(100, score),
                    1
                )
            )
        )

    scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scores[0]


def calculate_clo_alignment(
    question,
    clo
):

    if not clo:
        return 0

    q = content_tokens(
        question
    )

    c = content_tokens(
        clo
    )

    if not c:
        return 0

    shared = q & c

    coverage = (
        len(shared) /
        len(c)
    )

    question_coverage = (
        len(shared) /
        max(1, len(q))
    )

    score = (
        coverage * 70 +
        question_coverage * 30
    ) * 100

    return round(
        min(100, score),
        1
    )


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    normalized = normalize_text(
        question
    )

    words = normalized.split()

    found = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if verb in words:

                found.append(level)
                break

    if not found:

        return "Needs Review"

    return max(
        found,
        key=lambda x: BLOOM_RANK[x]
    )


def calculate_bloom_alignment(
    detected,
    intended
):

    if detected == "Needs Review":
        return 40

    distance = abs(
        BLOOM_RANK[detected] -
        BLOOM_RANK[intended]
    )

    if distance == 0:
        return 100

    if distance == 1:
        return 70

    if distance == 2:
        return 45

    return 20


# ============================================================
# QUESTION QUALITY
# ============================================================

def clarity_score(question):

    words = question.split()

    if len(words) < 5:
        return 40

    score = 70

    if "?" in question:
        score += 10

    if len(words) > 80:
        score -= 20

    if re.search(
        r"\b(identify|define|explain|describe|"
        r"analyze|analyse|evaluate|calculate|"
        r"determine|compare|discuss|select)\b",
        question,
        re.I
    ):
        score += 10

    return max(
        0,
        min(100, score)
    )


def specificity_score(question):

    words = tokens(question)

    if len(words) < 5:
        return 40

    score = 65

    if len(words) >= 10:
        score += 10

    if any(
        item in normalize_text(question)
        for item in [
            "given",
            "following",
            "scenario",
            "case",
            "data",
            "paragraph",
            "example",
            "equation",
            "diagram",
            "table"
        ]
    ):
        score += 15

    return min(
        100,
        score
    )


def measurability_score(question):

    words = normalize_text(
        question
    ).split()

    verbs = {
        verb
        for values in BLOOM_VERBS.values()
        for verb in values
    }

    if any(
        word in verbs
        for word in words
    ):
        return 95

    if "?" in question:
        return 75

    return 55


def evaluate_mcq(options):

    if not options:

        return {
            "score": None,
            "feedback": "Not an MCQ."
        }

    score = 100
    feedback = []

    if len(options) < 3:

        score -= 30

        feedback.append(
            "Fewer than three options detected."
        )

    if len(options) > 6:

        score -= 10

        feedback.append(
            "More than six options detected."
        )

    normalized = [
        normalize_text(
            option["text"]
        )
        for option in options
    ]

    if len(normalized) != len(set(normalized)):

        score -= 30

        feedback.append(
            "Duplicate options detected."
        )

    if not feedback:

        feedback.append(
            "Option structure is acceptable."
        )

    return {
        "score": max(
            0,
            score
        ),
        "feedback": " ".join(feedback)
    }


# ============================================================
# MAIN EVALUATOR
# ============================================================

def evaluate_question(
    question,
    course_domain,
    clos,
    plos,
    intended_bloom
):

    text = question["text"]

    subject = question_subject_check(
        text,
        course_domain
    )

    clo_match, clo_match_score = (
        best_outcome_match(
            text,
            clos
        )
    )

    if clo_match:

        clo_score = calculate_clo_alignment(
            text,
            clo_match["text"]
        )

    else:

        clo_score = 0

    plo_match, plo_score = (
        best_outcome_match(
            text,
            plos
        )
    )

    detected_bloom = detect_bloom(
        text
    )

    bloom_score = calculate_bloom_alignment(
        detected_bloom,
        intended_bloom
    )

    clarity = clarity_score(text)

    specificity = specificity_score(
        text
    )

    measurability = measurability_score(
        text
    )

    mcq = evaluate_mcq(
        question["options"]
    )

    quality_components = [
        clarity,
        specificity,
        measurability
    ]

    if mcq["score"] is not None:
        quality_components.append(
            mcq["score"]
        )

    quality = round(
        sum(quality_components) /
        len(quality_components),
        1
    )

    # ========================================================
    # NON-COMPENSATORY GATES
    # ========================================================

    if subject["status"] == "FAIL":

        decision = "REJECTED"

        reason = (
            f"SUBJECT MISMATCH: The course is "
            f"{course_domain}, but the question shows stronger "
            f"evidence for {subject['detected']}."
        )

    elif subject["status"] == "REVIEW":

        decision = "NEEDS REVIEW"

        reason = (
            "SUBJECT RELEVANCE COULD NOT BE CONFIRMED. "
            "There is insufficient disciplinary evidence."
        )

    elif clo_score < 60:

        decision = "REJECTED"

        reason = (
            "CLO MISALIGNMENT: The question does not directly "
            "assess enough of the content specified by the matched CLO."
        )

    elif bloom_score < 70:

        decision = "REJECTED"

        reason = (
            f"BLOOM MISALIGNMENT: The question appears to require "
            f"{detected_bloom}, while the intended level is "
            f"{intended_bloom}."
        )

    elif plos and plo_score < 50:

        decision = "NEEDS REVIEW"

        reason = (
            "PLO ALIGNMENT IS WEAK: The question does not provide "
            "enough evidence that the selected PLO is actually demonstrated."
        )

    elif quality < 70:

        decision = "NEEDS REVIEW"

        reason = (
            "QUESTION QUALITY: The question requires improvement "
            "in clarity, specificity, measurability, or structure."
        )

    else:

        decision = "APPROVED"

        reason = (
            "The question passed the mandatory subject, CLO, "
            "Bloom, and quality gates."
        )

    # Overall is only an indicator.
    # It NEVER changes the decision.
    plo_component = (
        plo_score
        if plos
        else 100
    )

    overall = round(
        subject["score"] * 0.30 +
        clo_score * 0.25 +
        plo_component * 0.15 +
        bloom_score * 0.15 +
        quality * 0.15,
        1
    )

    feedback = []

    if subject["status"] == "FAIL":

        feedback.append(
            "SUBJECT ERROR: " +
            subject["reason"]
        )

    elif subject["status"] == "REVIEW":

        feedback.append(
            "SUBJECT REVIEW: " +
            subject["reason"]
        )

    if clo_score < 60:

        feedback.append(
            "CLO ERROR: The question does not directly assess "
            "the key content of the matched CLO."
        )

    if plos and plo_score < 50:

        feedback.append(
            "PLO REVIEW: The selected PLO is not clearly "
            "demonstrated by the question."
        )

    if bloom_score < 70:

        feedback.append(
            f"BLOOM ERROR: Detected level = {detected_bloom}; "
            f"intended level = {intended_bloom}."
        )

    if clarity < 70:

        feedback.append(
            "CLARITY: Make the required task explicit."
        )

    if specificity < 70:

        feedback.append(
            "SPECIFICITY: State the required object, condition, "
            "case, data, or scope."
        )

    if measurability < 70:

        feedback.append(
            "MEASURABILITY: Use a response that can be "
            "clearly assessed."
        )

    if (
        mcq["score"] is not None
        and mcq["score"] < 80
    ):

        feedback.append(
            "MCQ QUALITY: " +
            mcq["feedback"]
        )

    if not feedback:

        feedback.append(
            "No major automated problem was detected."
        )

    return {
        "number": question["number"],
        "question": text,
        "options": question["options"],

        "expected_subject": course_domain,
        "detected_subject": subject["detected"],
        "subject_score": subject["score"],
        "subject_status": subject["status"],
        "subject_reason": subject["reason"],

        "clo_id": (
            clo_match["id"]
            if clo_match
            else "Not identified"
        ),

        "clo_text": (
            clo_match["text"]
            if clo_match
            else ""
        ),

        "clo_score": clo_score,

        "plo_id": (
            plo_match["id"]
            if plo_match
            else "Not identified"
        ),

        "plo_text": (
            plo_match["text"]
            if plo_match
            else ""
        ),

        "plo_score": plo_score,

        "expected_bloom": intended_bloom,
        "detected_bloom": detected_bloom,
        "bloom_score": bloom_score,

        "clarity": clarity,
        "specificity": specificity,
        "measurability": measurability,

        "mcq_score": mcq["score"],
        "quality": quality,

        "overall": overall,

        "decision": decision,
        "decision_reason": reason,
        "feedback": feedback
    }


# ============================================================
# DIRECT QUESTION REVISION
# ============================================================

def generate_revision(
    result,
    intended_bloom
):

    clo = result["clo_text"].strip()

    if not clo:
        return None

    content = re.sub(
        r"^(to\s+)?"
        r"(identify|define|explain|describe|apply|"
        r"analyze|analyse|evaluate|assess|design|"
        r"develop|create|understand|demonstrate)"
        r"\s+",
        "",
        clo,
        flags=re.I
    )

    content = content.strip(
        " ."
    )

    if not content:
        content = clo

    if intended_bloom == "Remember":

        return (
            f"Identify the main concepts or components "
            f"of {content}."
        )

    if intended_bloom == "Understand":

        return (
            f"Explain {content} in your own words."
        )

    if intended_bloom == "Apply":

        return (
            f"Given a relevant situation involving {content}, "
            f"apply the appropriate principle to determine "
            f"the correct result."
        )

    if intended_bloom == "Analyze":

        return (
            f"Analyze the given information about {content} "
            f"and identify the factors that explain the result."
        )

    if intended_bloom == "Evaluate":

        return (
            f"Evaluate the given case involving {content} "
            f"and justify your conclusion using relevant evidence."
        )

    return (
        f"Design a suitable solution for a problem involving "
        f"{content} and explain how the solution meets "
        f"the stated requirements."
    )


# ============================================================
# SESSION STATE
# ============================================================

if "assessment_text" not in st.session_state:
    st.session_state.assessment_text = ""

if "analysis" not in st.session_state:
    st.session_state.analysis = None


# ============================================================
# UI
# ============================================================

st.title(
    "🎓 OBE Assessment Alignment Checker"
)

st.write(
    "Evaluate assessment questions for actual subject relevance, "
    "CLO alignment, PLO alignment, Bloom's level, and question quality."
)

st.info(
    "IMPORTANT: Subject mismatch is a hard failure. "
    "A question from another subject cannot be approved merely "
    "because it has a strong Bloom's verb, CLO match, PLO match, "
    "or good wording."
)


# ============================================================
# COURSE
# ============================================================

st.header("1. Course / Assessment")

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder="Example: Chemistry"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment",
        placeholder="Example: Quiz 1"
    )


# ============================================================
# CLO
# ============================================================

st.header("2. Course Learning Outcomes")

clo_text = st.text_area(
    "Enter CLOs",
    height=160,
    placeholder=(
        "CLO1: Explain the principles of chemical equilibrium.\n"
        "CLO2: Apply appropriate methods to solve equilibrium problems.\n"
        "CLO3: Analyze experimental results using relevant concepts."
    )
)

clos = parse_outcomes(
    clo_text,
    "CLO"
)


# ============================================================
# PLO
# ============================================================

st.header("3. Program Learning Outcomes")

plo_text = st.text_area(
    "Enter PLOs",
    height=150,
    placeholder=(
        "PLO1: Apply knowledge of science and mathematics.\n"
        "PLO2: Analyze problems using appropriate methods.\n"
        "PLO3: Communicate solutions effectively."
    )
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)


# ============================================================
# BLOOM
# ============================================================

st.header("4. Intended Bloom's Level")

intended_bloom = st.selectbox(
    "Select intended Bloom's level",
    BLOOM_LEVELS,
    index=1
)


# ============================================================
# FILE
# ============================================================

st.header("5. Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload complete assessment",
    type=[
        "pdf",
        "docx",
        "txt",
        "xlsx",
        "xls",
        "csv"
    ]
)

if uploaded_file:

    st.caption(
        f"Selected file: {uploaded_file.name}"
    )

    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):

        with st.spinner(
            "Reading assessment..."
        ):

            text, method = extract_file(
                uploaded_file
            )

        st.session_state.assessment_text = text

        if text:

            st.success(
                f"Assessment read successfully using {method}. "
                f"{len(text):,} characters extracted."
            )

        else:

            st.error(
                "The assessment could not be read. "
                "If the PDF is scanned, it requires OCR."
            )


if st.session_state.assessment_text:

    with st.expander(
        "Preview extracted assessment"
    ):

        st.text(
            st.session_state.assessment_text[
                :30000
            ]
        )


# ============================================================
# ANALYZE
# ============================================================

st.header("6. Evaluate Assessment")

if st.button(
    "🔍 Evaluate Complete Assessment",
    type="primary",
    use_container_width=True
):

    if not course_name.strip():

        st.error(
            "Enter the course / subject."
        )

        st.stop()

    if not clos:

        st.error(
            "Enter at least one CLO."
        )

        st.stop()

    if not st.session_state.assessment_text:

        if uploaded_file:

            text, method = extract_file(
                uploaded_file
            )

            st.session_state.assessment_text = text

        else:

            st.error(
                "Upload an assessment file first."
            )

            st.stop()

    if not st.session_state.assessment_text:

        st.error(
            "No assessment text was extracted."
        )

        st.stop()

    questions = extract_questions(
        st.session_state.assessment_text
    )

    if not questions:

        st.error(
            "No questions were detected."
        )

        st.stop()

    course_domain, confidence = (
        determine_course_domain(
            course_name,
            clos,
            plos,
            st.session_state.assessment_text
        )
    )

    with st.spinner(
        "Evaluating subject relevance and OBE alignment..."
    ):

        results = []

        for question in questions:

            results.append(
                evaluate_question(
                    question,
                    course_domain,
                    clos,
                    plos,
                    intended_bloom
                )
            )

    st.session_state.analysis = {
        "results": results,
        "course_domain": course_domain,
        "confidence": confidence
    }

    st.success(
        f"Evaluation completed for {len(results)} question(s)."
    )


# ============================================================
# RESULTS
# ============================================================

analysis = st.session_state.analysis

if analysis:

    results = analysis["results"]

    course_domain = analysis[
        "course_domain"
    ]

    confidence = analysis[
        "confidence"
    ]

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

    subject_avg = round(
        sum(
            r["subject_score"]
            for r in results
        ) / len(results),
        1
    )

    clo_avg = round(
        sum(
            r["clo_score"]
            for r in results
        ) / len(results),
        1
    )

    plo_avg = round(
        sum(
            r["plo_score"]
            for r in results
        ) / len(results),
        1
    ) if plos else 0

    bloom_avg = round(
        sum(
            r["bloom_score"]
            for r in results
        ) / len(results),
        1
    )

    quality_avg = round(
        sum(
            r["quality"]
            for r in results
        ) / len(results),
        1
    )

    overall_avg = round(
        sum(
            r["overall"]
            for r in results
        ) / len(results),
        1
    )


    # ========================================================
    # DOMAIN
    # ========================================================

    st.header(
        "7. Detected Course Domain"
    )

    d1, d2 = st.columns(2)

    d1.metric(
        "Course Domain",
        course_domain
    )

    d2.metric(
        "Domain Confidence",
        f"{confidence}%"
    )


    # ========================================================
    # STATUS
    # ========================================================

    st.header(
        "8. Final Decisions"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "APPROVED",
        approved
    )

    c2.metric(
        "REJECTED",
        rejected
    )

    c3.metric(
        "NEEDS REVIEW",
        review
    )


    # ========================================================
    # METRICS
    # ========================================================

    st.header(
        "9. Alignment Metrics"
    )

    metric_df = pd.DataFrame({
        "Metric": [
            "Subject Relevance",
            "CLO Alignment",
            "PLO Alignment",
            "Bloom Alignment",
            "Question Quality",
            "Overall Indicator"
        ],
        "Score": [
            subject_avg,
            clo_avg,
            plo_avg if plos else None,
            bloom_avg,
            quality_avg,
            overall_avg
        ]
    }).dropna()

    st.bar_chart(
        metric_df.set_index(
            "Metric"
        )["Score"],
        use_container_width=True
    )

    st.caption(
        "The Overall Indicator is informational only. "
        "It cannot override a failed mandatory gate."
    )


    # ========================================================
    # TABLE
    # ========================================================

    st.header(
        "10. Question-by-Question Decision Table"
    )

    summary = pd.DataFrame([

        {
            "Question": f"Q{r['number']}",
            "Decision": r["decision"],
            "Expected Subject": r["expected_subject"],
            "Detected Subject": r["detected_subject"],
            "Subject": r["subject_score"],
            "CLO": r["clo_score"],
            "PLO": (
                r["plo_score"]
                if plos
                else None
            ),
            "Expected Bloom": r["expected_bloom"],
            "Detected Bloom": r["detected_bloom"],
            "Bloom": r["bloom_score"],
            "Quality": r["quality"],
            "Overall": r["overall"]
        }

        for r in results
    ])

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # DETAILED QUESTION REVIEW
    # ========================================================

    st.header(
        "11. Detailed Evaluation"
    )

    labels = [

        f"Q{r['number']} — "
        f"{textwrap.shorten(r['question'], width=100)}"

        for r in results
    ]

    selected_index = st.selectbox(
        "Select question",
        range(len(results)),
        format_func=lambda i: labels[i]
    )

    r = results[
        selected_index
    ]


    if r["decision"] == "APPROVED":

        st.success(
            f"Q{r['number']} — APPROVED"
        )

    elif r["decision"] == "REJECTED":

        st.error(
            f"Q{r['number']} — REJECTED"
        )

    else:

        st.warning(
            f"Q{r['number']} — NEEDS REVIEW"
        )


    st.subheader(
        "Question"
    )

    st.write(
        r["question"]
    )


    if r["options"]:

        st.subheader(
            "Options"
        )

        for option in r["options"]:

            st.write(
                f"**{option['label']}.** "
                f"{option['text']}"
            )


    st.subheader(
        "Alignment Evidence"
    )

    a1, a2, a3, a4 = st.columns(4)

    a1.metric(
        "Subject",
        f"{r['subject_score']}%"
    )

    a2.metric(
        "CLO",
        f"{r['clo_score']}%"
    )

    a3.metric(
        "PLO",
        (
            f"{r['plo_score']}%"
            if plos
            else "N/A"
        )
    )

    a4.metric(
        "Bloom",
        f"{r['bloom_score']}%"
    )


    st.write(
        f"**Expected Subject:** "
        f"{r['expected_subject']}"
    )

    st.write(
        f"**Detected Subject:** "
        f"{r['detected_subject']}"
    )

    st.write(
        f"**Subject Status:** "
        f"{r['subject_status']}"
    )

    st.write(
        f"**Subject Evidence:** "
        f"{r['subject_reason']}"
    )


    st.write(
        f"**Matched CLO:** "
        f"{r['clo_id']}"
    )

    if r["clo_text"]:

        st.write(
            f"**CLO:** "
            f"{r['clo_text']}"
        )


    if plos:

        st.write(
            f"**Matched PLO:** "
            f"{r['plo_id']}"
        )

        if r["plo_text"]:

            st.write(
                f"**PLO:** "
                f"{r['plo_text']}"
            )


    st.write(
        f"**Expected Bloom:** "
        f"{r['expected_bloom']}"
    )

    st.write(
        f"**Detected Bloom:** "
        f"{r['detected_bloom']}"
    )

    st.write(
        f"**Question Quality:** "
        f"{r['quality']}%"
    )


    # ========================================================
    # WHY?
    # ========================================================

    st.subheader(
        "Why did the tool make this decision?"
    )

    if r["decision"] == "REJECTED":

        st.error(
            r["decision_reason"]
        )

    elif r["decision"] == "NEEDS REVIEW":

        st.warning(
            r["decision_reason"]
        )

    else:

        st.success(
            r["decision_reason"]
        )


    if r["feedback"]:

        st.subheader(
            "Specific Issues"
        )

        for issue in r["feedback"]:

            st.write(
                f"• {issue}"
            )


    # ========================================================
    # DIRECT REVISION
    # ========================================================

    st.header(
        "12. Direct Revision"
    )

    if r["decision"] != "APPROVED":

        revised_question = generate_revision(
            r,
            intended_bloom
        )

        if revised_question:

            st.success(
                revised_question
            )

            st.caption(
                "The revision is based on the actual CLO content "
                "and intended Bloom level. It does not tell the "
                "teacher to insert CLO/PLO wording into the question."
            )

        else:

            st.warning(
                "A reliable direct revision could not be generated "
                "because a valid CLO match was not established."
            )

    else:

        st.success(
            "No revision is required."
        )


    # ========================================================
    # QUESTIONS REQUIRING ACTION
    # ========================================================

    st.header(
        "13. Questions Requiring Action"
    )

    action_questions = [
        r
        for r in results
        if r["decision"] != "APPROVED"
    ]

    if action_questions:

        action_df = pd.DataFrame([

            {
                "Question": f"Q{r['number']}",
                "Decision": r["decision"],
                "Main Issue": r["decision_reason"],
                "Detected Subject": r["detected_subject"],
                "CLO": r["clo_id"],
                "Bloom": r["detected_bloom"]
            }

            for r in action_questions
        ])

        st.dataframe(
            action_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "No questions require action."
        )


    # ========================================================
    # CLO SUMMARY
    # ========================================================

    st.header(
        "14. CLO Coverage"
    )

    for clo in clos:

        matching = [

            r
            for r in results
            if r["clo_id"] == clo["id"]

        ]

        if matching:

            average = round(
                sum(
                    r["clo_score"]
                    for r in matching
                ) / len(matching),
                1
            )

            st.write(
                f"**{clo['id']} — {clo['text']}**"
            )

            st.metric(
                "Alignment",
                f"{average}%"
            )

        else:

            st.warning(
                f"{clo['id']} has no question matched to it."
            )


    # ========================================================
    # PLO SUMMARY
    # ========================================================

    if plos:

        st.header(
            "15. PLO Coverage"
        )

        for plo in plos:

            matching = [

                r
                for r in results
                if r["plo_id"] == plo["id"]

            ]

            if matching:

                average = round(
                    sum(
                        r["plo_score"]
                        for r in matching
                    ) / len(matching),
                    1
                )

                st.write(
                    f"**{plo['id']} — {plo['text']}**"
                )

                st.metric(
                    "Alignment",
                    f"{average}%"
                )

            else:

                st.warning(
                    f"{plo['id']} has no question matched to it."
                )


    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.header(
        "16. Bloom's Taxonomy Distribution"
    )

    bloom_df = pd.DataFrame([

        {
            "Bloom Level": level,
            "Questions": sum(
                r["detected_bloom"] == level
                for r in results
            )
        }

        for level in BLOOM_LEVELS
    ])

    st.bar_chart(
        bloom_df.set_index(
            "Bloom Level"
        )["Questions"],
        use_container_width=True
    )


    # ========================================================
    # EXPORT
    # ========================================================

    st.header(
        "17. Export Evaluation"
    )

    export_df = pd.DataFrame([

        {
            "Question": f"Q{r['number']}",
            "Question Text": r["question"],
            "Decision": r["decision"],
            "Decision Reason": r["decision_reason"],

            "Expected Subject": r["expected_subject"],
            "Detected Subject": r["detected_subject"],
            "Subject Score": r["subject_score"],

            "CLO": r["clo_id"],
            "CLO Alignment": r["clo_score"],

            "PLO": r["plo_id"],
            "PLO Alignment": (
                r["plo_score"]
                if plos
                else None
            ),

            "Expected Bloom": r["expected_bloom"],
            "Detected Bloom": r["detected_bloom"],
            "Bloom Alignment": r["bloom_score"],

            "Clarity": r["clarity"],
            "Specificity": r["specificity"],
            "Measurability": r["measurability"],
            "Question Quality": r["quality"],

            "Overall Indicator": r["overall"],

            "Feedback": " | ".join(
                r["feedback"]
            )
        }

        for r in results
    ])

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Complete Evaluation CSV",
        data=csv_data,
        file_name="obe_assessment_evaluation.csv",
        mime="text/csv",
        use_container_width=True
    )


    # ========================================================
    # FINAL STATUS
    # ========================================================

    st.header(
        "18. Final Assessment Status"
    )

    if rejected:

        st.error(
            f"{rejected} question(s) are rejected. "
            "A failed subject or CLO gate cannot be compensated "
            "by other scores."
        )

    elif review:

        st.warning(
            f"{review} question(s) require review before approval."
        )

    else:

        st.success(
            "All questions passed the automated alignment gates."
        )

    st.info(
        "Decision logic: Subject → CLO → Bloom → PLO/Quality. "
        "Subject mismatch is a mandatory rejection and cannot be "
        "offset by a high numerical score elsewhere."
    )
