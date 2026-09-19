import io
import re
import pandas as pd
import streamlit as st

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# BLOOM TAXONOMY
# ============================================================

BLOOM_ORDER = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "label", "select", "match"
    ],
    "Understand": [
        "explain", "describe", "summarize", "interpret",
        "classify", "discuss", "illustrate", "clarify"
    ],
    "Apply": [
        "apply", "calculate", "solve", "use", "demonstrate",
        "implement", "execute", "compute", "determine"
    ],
    "Analyze": [
        "analyze", "analyse", "compare", "contrast",
        "differentiate", "examine", "distinguish",
        "categorize", "deconstruct"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique",
        "judge", "defend", "validate", "appraise"
    ],
    "Create": [
        "design", "create", "develop", "construct",
        "formulate", "propose", "produce", "plan", "devise"
    ]
}

ALL_BLOOM_VERBS = set()

for verbs in BLOOM_VERBS.values():
    ALL_BLOOM_VERBS.update(verbs)


# ============================================================
# WORD LISTS
# ============================================================

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then",
    "of", "to", "in", "on", "for", "from", "with", "by",
    "as", "at", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its",
    "into", "about", "than", "through", "during", "after",
    "before", "between", "within", "using", "used", "use",
    "will", "would", "could", "should", "can", "may",
    "might", "your", "their", "our", "you", "they", "we",
    "he", "she", "which", "what", "when", "where", "why",
    "how", "given", "following", "following"
}

GENERIC_OUTCOME_WORDS = {
    "student", "students", "learner", "learners",
    "ability", "abilities", "knowledge", "understanding",
    "understand", "skill", "skills", "competence",
    "competencies", "demonstrate", "demonstrates",
    "develop", "development", "appropriate", "effectively",
    "discipline", "field", "area", "course", "courses",
    "program", "programs", "learning", "outcome", "outcomes",
    "capable", "capability", "proficiency", "proficient"
}

OBE_WORDS = {
    "clo", "clos", "plo", "plos", "bloom", "taxonomy",
    "attainment", "alignment", "aligned", "assessment",
    "assessments", "learning", "outcome", "outcomes"
}


# ============================================================
# TEXT FUNCTIONS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    text = text.replace("\x00", " ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def stem(word):
    word = word.lower().strip()

    if len(word) <= 4:
        return word

    suffixes = [
        "ingly",
        "edly",
        "ation",
        "ments",
        "ment",
        "ness",
        "ities",
        "ity",
        "ingly",
        "ing",
        "ers",
        "ies",
        "es",
        "ed",
        "s"
    ]

    for suffix in suffixes:
        if word.endswith(suffix):
            base = word[:-len(suffix)]

            if len(base) >= 4:
                return base

    return word


def tokens(text):
    words = normalize(text).split()

    result = []

    for word in words:
        if word in STOP_WORDS:
            continue

        if word in OBE_WORDS:
            continue

        if len(word) < 3:
            continue

        result.append(stem(word))

    return result


def token_set(text):
    return set(tokens(text))


def outcome_tokens(text):
    words = normalize(text).split()

    result = []

    for word in words:

        if word in STOP_WORDS:
            continue

        if word in OBE_WORDS:
            continue

        if word in GENERIC_OUTCOME_WORDS:
            continue

        if word in ALL_BLOOM_VERBS:
            continue

        if len(word) < 3:
            continue

        result.append(stem(word))

    return result


def unique_list(items):
    result = []
    seen = set()

    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


# ============================================================
# PUNCTUATION
# ============================================================

def finalize_question(text):
    text = clean_text(text)

    # Remove ALL terminal punctuation combinations.
    text = re.sub(r"[.!?]+$", "", text).strip()

    if not text:
        return ""

    return text + "?"


# ============================================================
# FILE READING
# ============================================================

def read_pdf(file):
    if not PDF_AVAILABLE:
        raise RuntimeError(
            "PyMuPDF is not installed. Add pymupdf to requirements."
        )

    data = file.read()

    document = fitz.open(
        stream=data,
        filetype="pdf"
    )

    pages = []

    for page in document:
        pages.append(page.get_text("text"))

    text = "\n".join(pages).strip()

    if len(text) < 100 and OCR_AVAILABLE:

        ocr_pages = []

        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        for page in document:

            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2)
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            try:
                ocr_pages.append(
                    pytesseract.image_to_string(image)
                )
            except Exception:
                pass

        text = "\n".join(ocr_pages).strip()

    return text


def read_docx(file):
    if not DOCX_AVAILABLE:
        raise RuntimeError(
            "python-docx is not installed."
        )

    document = Document(file)

    paragraphs = []

    for paragraph in document.paragraphs:
        value = clean_text(paragraph.text)

        if value:
            paragraphs.append(value)

    return "\n".join(paragraphs)


def read_excel(file):
    data = file.read()

    excel = pd.ExcelFile(
        io.BytesIO(data)
    )

    output = []

    for sheet in excel.sheet_names:

        df = pd.read_excel(
            io.BytesIO(data),
            sheet_name=sheet
        )

        output.append(
            f"Sheet: {sheet}\n"
            f"{df.fillna('').to_string(index=False)}"
        )

    return "\n\n".join(output)


def read_csv(file):
    data = file.read()

    df = pd.read_csv(
        io.BytesIO(data),
        encoding_errors="ignore"
    )

    return df.fillna("").to_string(
        index=False
    )


def read_txt(file):
    data = file.read()

    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode(
            "latin-1",
            errors="ignore"
        )


def read_uploaded_file(file):

    name = file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(file)

    if name.endswith(".docx"):
        return read_docx(file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return read_excel(file)

    if name.endswith(".csv"):
        return read_csv(file)

    if name.endswith(".txt"):
        return read_txt(file)

    raise ValueError(
        "Unsupported file format."
    )


# ============================================================
# OUTCOME PARSER
# ============================================================

def parse_outcomes(text, prefix):

    if not text:
        return []

    lines = [
        clean_text(x)
        for x in str(text).splitlines()
        if clean_text(x)
    ]

    results = []

    explicit_pattern = re.compile(
        rf"^\s*{prefix}\s*[-:]?\s*\d+\s*[\)\.\-:\u2013]?\s*(.+)$",
        re.IGNORECASE
    )

    for line in lines:

        match = explicit_pattern.match(line)

        if match:

            value = clean_text(
                match.group(1)
            )

            if value:
                results.append(value)

    if results:
        return results

    # Fallback for numbered lists.
    number_pattern = re.compile(
        r"^\s*\d+\s*[\)\.\-:\u2013]\s*(.+)$"
    )

    for line in lines:

        match = number_pattern.match(line)

        if match:

            value = clean_text(
                match.group(1)
            )

            if value:
                results.append(value)

    return unique_list(results)


# ============================================================
# OUTCOME CONCEPT EXTRACTION
# ============================================================

def outcome_phrase(outcome, limit=5):

    words = normalize(outcome).split()

    selected = []
    seen = set()

    for word in words:

        if word in STOP_WORDS:
            continue

        if word in OBE_WORDS:
            continue

        if word in GENERIC_OUTCOME_WORDS:
            continue

        if word in ALL_BLOOM_VERBS:
            continue

        if len(word) < 3:
            continue

        s = stem(word)

        if s in seen:
            continue

        seen.add(s)
        selected.append(word)

        if len(selected) >= limit:
            break

    return " ".join(selected)


# ============================================================
# BLOOM
# ============================================================

def detect_bloom(question):

    normalized = normalize(question)

    priority = [
        "Create",
        "Evaluate",
        "Analyze",
        "Apply",
        "Understand",
        "Remember"
    ]

    for level in priority:

        for verb in BLOOM_VERBS[level]:

            if re.search(
                rf"\b{re.escape(verb)}\w*\b",
                normalized
            ):
                return level

    if normalized.startswith(("why ", "how ")):
        return "Understand"

    if normalized.startswith(
        ("what ", "who ", "when ", "where ")
    ):
        return "Remember"

    return "Understand"


def bloom_alignment(question, target):

    actual = detect_bloom(question)

    actual_number = BLOOM_ORDER.get(
        actual,
        2
    )

    target_number = BLOOM_ORDER.get(
        target,
        2
    )

    if actual == target:
        return 100.0

    # Higher cognitive level can demonstrate a lower target.
    if actual_number > target_number:
        return 95.0

    if actual_number == target_number - 1:
        return 82.0

    if actual_number == target_number - 2:
        return 65.0

    return 40.0


def outcome_action_level(outcome):

    normalized = normalize(outcome)

    levels = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                rf"\b{re.escape(verb)}\w*\b",
                normalized
            ):
                levels.append(
                    BLOOM_ORDER[level]
                )

    if not levels:
        return None

    return max(levels)


def action_alignment(question, outcome):

    question_level = detect_bloom(question)

    q_number = BLOOM_ORDER.get(
        question_level,
        2
    )

    o_number = outcome_action_level(
        outcome
    )

    if o_number is None:
        return 100.0

    if q_number == o_number:
        return 100.0

    if q_number > o_number:
        return 95.0

    difference = o_number - q_number

    if difference == 1:
        return 80.0

    if difference == 2:
        return 65.0

    return 45.0


# ============================================================
# COURSE CONCEPT MATCHING
# ============================================================

def overlap_metrics(question, reference):

    q = token_set(question)
    r = token_set(reference)

    if not q or not r:
        return {
            "coverage": 0.0,
            "precision": 0.0,
            "overlap": 0
        }

    overlap = q.intersection(r)

    coverage = (
        len(overlap)
        / max(1, len(r))
    ) * 100

    precision = (
        len(overlap)
        / max(1, len(q))
    ) * 100

    return {
        "coverage": min(100.0, coverage),
        "precision": min(100.0, precision),
        "overlap": len(overlap)
    }


def subject_score(
    question,
    course_name,
    course_content
):

    reference = (
        f"{course_name} "
        f"{course_content}"
    )

    metrics = overlap_metrics(
        question,
        reference
    )

    coverage = metrics["coverage"]
    precision = metrics["precision"]

    # Subject relevance is question-specific.
    score = (
        coverage * 0.65
        + precision * 0.35
    )

    # Small domain evidence bonus.
    q_domain, q_score = detect_domain(
        question
    )

    r_domain, r_score = detect_domain(
        reference
    )

    if (
        q_domain
        and r_domain
        and q_domain == r_domain
    ):
        score += 10

    return min(100.0, max(0.0, score))


# ============================================================
# DOMAIN DETECTION
# ============================================================

DOMAIN_KEYWORDS = {
    "chemistry": {
        "atom", "molecule", "chemical", "reaction",
        "bond", "acid", "base", "electron",
        "compound", "solution", "molarity",
        "oxidation", "reduction", "organic"
    },

    "physics": {
        "force", "motion", "energy", "momentum",
        "velocity", "acceleration", "electric",
        "magnetic", "wave", "optics", "mass",
        "gravity", "current", "voltage"
    },

    "mathematics": {
        "equation", "function", "matrix",
        "integral", "derivative", "probability",
        "statistics", "algebra", "geometry",
        "calculus", "vector", "limit"
    },

    "biology": {
        "cell", "gene", "protein", "organism",
        "enzyme", "biology", "dna", "rna",
        "metabolism", "evolution", "tissue"
    },

    "computer science": {
        "algorithm", "programming", "software",
        "database", "network", "computer",
        "code", "python", "java", "data",
        "system", "function", "variable"
    },

    "english": {
        "writing", "reading", "essay", "paragraph",
        "grammar", "tone", "purpose", "main",
        "idea", "organization", "communication",
        "language", "author"
    },

    "business": {
        "marketing", "finance", "management",
        "business", "customer", "organization",
        "accounting", "strategy", "market",
        "investment", "leadership"
    }
}


def detect_domain(text):

    t = token_set(text)

    best_domain = None
    best_score = 0

    for domain, words in DOMAIN_KEYWORDS.items():

        stems = {
            stem(word)
            for word in words
        }

        score = len(
            t.intersection(stems)
        )

        if score > best_score:
            best_score = score
            best_domain = domain

    return best_domain, best_score


# ============================================================
# CLO ALIGNMENT
# ============================================================

def clo_alignment(
    question,
    clo,
    course_name,
    course_content
):

    q_tokens = token_set(question)
    clo_tokens = set(
        outcome_tokens(clo)
    )

    course_tokens = token_set(
        f"{course_name} {course_content}"
    )

    # --------------------------------------------
    # Concept coverage
    # --------------------------------------------

    if clo_tokens:

        overlap = q_tokens.intersection(
            clo_tokens
        )

        coverage = (
            len(overlap)
            / max(1, len(clo_tokens))
        ) * 100

        # Question must also devote reasonable
        # space to CLO concepts.
        precision = (
            len(overlap)
            / max(1, len(q_tokens))
        ) * 100

        concept_score = (
            coverage * 0.75
            + precision * 0.25
        )

    else:
        # Generic CLO:
        # use course evidence instead.
        concept_metrics = overlap_metrics(
            question,
            f"{course_name} {course_content}"
        )

        concept_score = (
            concept_metrics["coverage"] * 0.70
            + concept_metrics["precision"] * 0.30
        )

    # --------------------------------------------
    # Action alignment
    # --------------------------------------------

    action_score = action_alignment(
        question,
        clo
    )

    # --------------------------------------------
    # Course-specific evidence
    # --------------------------------------------

    course_metrics = overlap_metrics(
        question,
        f"{course_name} {course_content}"
    )

    course_score = (
        course_metrics["coverage"] * 0.60
        + course_metrics["precision"] * 0.40
    )

    score = (
        concept_score * 0.70
        + action_score * 0.20
        + course_score * 0.10
    )

    return min(
        100.0,
        max(0.0, score)
    )


# ============================================================
# PLO ALIGNMENT
# ============================================================

def plo_alignment(
    question,
    plo,
    course_name,
    course_content
):

    q_tokens = token_set(question)
    plo_tokens = set(
        outcome_tokens(plo)
    )

    # --------------------------------------------
    # PLO concept evidence
    # --------------------------------------------

    if plo_tokens:

        overlap = q_tokens.intersection(
            plo_tokens
        )

        coverage = (
            len(overlap)
            / max(1, len(plo_tokens))
        ) * 100

        precision = (
            len(overlap)
            / max(1, len(q_tokens))
        ) * 100

        concept_score = (
            coverage * 0.70
            + precision * 0.30
        )

    else:
        concept_score = 0.0

    # --------------------------------------------
    # PLO action
    # --------------------------------------------

    action_score = action_alignment(
        question,
        plo
    )

    # --------------------------------------------
    # Discipline evidence
    # --------------------------------------------

    discipline_metrics = overlap_metrics(
        question,
        f"{course_name} {course_content}"
    )

    discipline_score = (
        discipline_metrics["coverage"] * 0.60
        + discipline_metrics["precision"] * 0.40
    )

    # Generic PLO:
    #
    # "Apply knowledge of the discipline"
    #
    # should be evaluated through:
    # 1. cognitive action
    # 2. actual course concepts
    # rather than requiring the word "discipline".

    if len(plo_tokens) <= 1:

        score = (
            action_score * 0.65
            + discipline_score * 0.35
        )

    else:

        score = (
            concept_score * 0.50
            + action_score * 0.30
            + discipline_score * 0.20
        )

    return min(
        100.0,
        max(0.0, score)
    )


# ============================================================
# SPECIFICITY
# ============================================================

def specificity_score(question):

    q = normalize(question)
    words = q.split()

    if not words:
        return 0.0

    score = 55.0

    # Clear cognitive verb
    if any(
        re.search(
            rf"\b{re.escape(verb)}\w*\b",
            q
        )
        for verb in ALL_BLOOM_VERBS
    ):
        score += 15

    # Reasonable length
    count = len(words)

    if 7 <= count <= 30:
        score += 15

    elif 31 <= count <= 40:
        score += 8

    elif count < 5:
        score -= 25

    elif count > 50:
        score -= 10

    # Practical/contextual evidence
    context_words = {
        "case", "scenario", "situation",
        "problem", "data", "example",
        "experiment", "result", "given"
    }

    if any(
        word in q
        for word in context_words
    ):
        score += 8

    # Explicit task requirement
    if any(
        phrase in q
        for phrase in [
            "justify",
            "compare",
            "explain how",
            "determine",
            "identify",
            "calculate",
            "design"
        ]
    ):
        score += 7

    return min(
        100.0,
        max(0.0, score)
    )


# ============================================================
# QUALITY
# ============================================================

def quality_score(question):

    q = clean_text(question)
    n = normalize(q)

    if not q:
        return 0.0

    score = 70.0

    # Proper question mark
    if q.endswith("?"):
        score += 10

    # Duplicate punctuation
    if re.search(
        r"[.!?]{2,}$",
        q
    ):
        score -= 30

    # OBE jargon should not appear
    # in student-facing question.
    if any(
        term in n
        for term in [
            "clo",
            "plo",
            "learning outcome",
            "attainment",
            "alignment",
            "bloom taxonomy"
        ]
    ):
        score -= 30

    # Vague wording
    vague = [
        "tell me about",
        "write something about",
        "discuss everything",
        "explain the learning outcome",
        "according to the clo",
        "according to the plo"
    ]

    for phrase in vague:
        if phrase in n:
            score -= 25

    # Multiple task verbs can indicate a multi-part
    # but still specific question.
    task_count = 0

    for verb in ALL_BLOOM_VERBS:
        if re.search(
            rf"\b{re.escape(verb)}\w*\b",
            n
        ):
            task_count += 1

    if task_count >= 1:
        score += 5

    if 5 <= len(n.split()) <= 35:
        score += 5

    return min(
        100.0,
        max(0.0, score)
    )


# ============================================================
# FIND BEST CLO / PLO
# ============================================================

def find_best_clo(
    question,
    clos,
    course_name,
    course_content
):

    if not clos:
        return "", 0.0

    scores = []

    for clo in clos:

        score = clo_alignment(
            question,
            clo,
            course_name,
            course_content
        )

        scores.append(
            (clo, score)
        )

    scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scores[0]


def find_best_plo(
    question,
    plos,
    course_name,
    course_content
):

    if not plos:
        return "", 0.0

    scores = []

    for plo in plos:

        score = plo_alignment(
            question,
            plo,
            course_name,
            course_content
        )

        scores.append(
            (plo, score)
        )

    scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scores[0]


# ============================================================
# COMPLETE QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    course_name,
    course_content,
    clos,
    plos,
    target_bloom
):

    question = clean_text(question)

    subject = subject_score(
        question,
        course_name,
        course_content
    )

    matched_clo, clo = find_best_clo(
        question,
        clos,
        course_name,
        course_content
    )

    matched_plo, plo = find_best_plo(
        question,
        plos,
        course_name,
        course_content
    )

    bloom = bloom_alignment(
        question,
        target_bloom
    )

    specificity = specificity_score(
        question
    )

    quality = quality_score(
        question
    )

    # ========================================================
    # WEIGHTED SCORE
    # ========================================================

    overall = (
        subject * 0.20
        + clo * 0.20
        + plo * 0.20
        + bloom * 0.15
        + specificity * 0.10
        + quality * 0.05
        + (
            # CLO action evidence
            action_alignment(
                question,
                matched_clo
            ) * 0.10
        )
    )

    overall = round(
        min(100.0, max(0.0, overall)),
        1
    )

    # ========================================================
    # STRICT ATTAINMENT
    # ========================================================

    attained = (
        overall >= 80
        and subject >= 80
        and clo >= 80
        and plo >= 80
        and bloom >= 80
        and specificity >= 70
        and quality >= 70
    )

    if attained:
        status = "Alignment Attained"
    elif overall >= 60:
        status = "Needs Revision"
    else:
        status = "Not Aligned"

    return {
        "question": question,
        "overall": overall,
        "subject": round(subject, 1),
        "clo": round(clo, 1),
        "plo": round(plo, 1),
        "bloom": round(bloom, 1),
        "specificity": round(specificity, 1),
        "quality": round(quality, 1),
        "actual_bloom": detect_bloom(question),
        "target_bloom": target_bloom,
        "matched_clo": matched_clo,
        "matched_plo": matched_plo,
        "status": status
    }


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    if not text:
        return []

    text = text.replace(
        "\r\n",
        "\n"
    )

    lines = text.splitlines()

    questions = []

    current = ""

    for line in lines:

        line = clean_text(line)

        if not line:
            continue

        numbered = re.match(
            r"^\s*(?:Q(?:uestion)?\s*)?\d+\s*[\)\.\-:]\s*(.+)",
            line,
            re.IGNORECASE
        )

        if numbered:

            if current:
                questions.append(
                    current
                )

            current = numbered.group(1)
            continue

        if "?" in line:

            if current:
                current += " " + line
            else:
                current = line

            questions.append(
                current
            )

            current = ""

        elif current:

            current += " " + line

    if current:
        questions.append(
            current
        )

    # Remove obvious non-question headings.
    final = []

    for q in questions:

        q = clean_text(q)

        if len(q.split()) < 4:
            continue

        if normalize(q) in {
            "course description",
            "course objectives",
            "learning outcomes",
            "answer key",
            "instructions",
            "rubric"
        }:
            continue

        final.append(q)

    return unique_list(final)


# ============================================================
# REVISION TOPIC
# ============================================================

def choose_topic(
    course_name,
    course_content,
    matched_clo,
    matched_plo
):

    # Try to find concepts shared with CLO/PLO.
    course_sentences = re.split(
        r"[.\n;]+",
        clean_text(course_content)
    )

    course_sentences = [
        clean_text(x)
        for x in course_sentences
        if len(clean_text(x).split()) >= 2
    ]

    clo_terms = set(
        outcome_tokens(matched_clo)
    )

    plo_terms = set(
        outcome_tokens(matched_plo)
    )

    best = ""
    best_score = -1

    for sentence in course_sentences:

        sentence_terms = token_set(
            sentence
        )

        score = (
            len(
                sentence_terms.intersection(
                    clo_terms
                )
            ) * 5
            +
            len(
                sentence_terms.intersection(
                    plo_terms
                )
            ) * 4
            +
            min(
                len(sentence_terms),
                10
            )
        )

        if score > best_score:
            best_score = score
            best = sentence

    if not best:
        best = (
            outcome_phrase(
                matched_clo,
                5
            )
            or outcome_phrase(
                matched_plo,
                5
            )
            or course_name
            or "the given topic"
        )

    words = best.split()

    if len(words) > 10:
        best = " ".join(
            words[:10]
        )

    return best


# ============================================================
# REVISION GENERATION
# ============================================================

def generate_candidates(
    original_question,
    course_name,
    course_content,
    matched_clo,
    matched_plo,
    target_bloom
):

    topic = choose_topic(
        course_name,
        course_content,
        matched_clo,
        matched_plo
    )

    clo_phrase = outcome_phrase(
        matched_clo,
        4
    )

    plo_phrase = outcome_phrase(
        matched_plo,
        4
    )

    if not clo_phrase:
        clo_phrase = topic

    if not plo_phrase:
        plo_phrase = topic

    candidates = []

    if target_bloom == "Remember":

        candidates = [
            f"Define {topic} and identify its key features",
            f"Define {clo_phrase} in the context of {topic}",
            f"Identify the main features of {topic} related to {clo_phrase}",
            f"List the key characteristics of {topic} and identify {clo_phrase}",
            f"State the main elements of {topic} associated with {clo_phrase}"
        ]

    elif target_bloom == "Understand":

        candidates = [
            f"Explain {topic} and describe how {clo_phrase} relates to it",
            f"Describe {topic} and explain the role of {clo_phrase}",
            f"Explain the relationship between {topic} and {clo_phrase}",
            f"Explain {clo_phrase} using {topic} as the context",
            f"Describe the main features of {topic} and explain {clo_phrase}"
        ]

    elif target_bloom == "Apply":

        candidates = [
            f"Given a practical problem involving {topic}, apply {clo_phrase} to solve it",
            f"Apply {clo_phrase} to solve a practical problem involving {topic}",
            f"Use {clo_phrase} to determine the correct solution to a problem involving {topic}",
            f"Given a case involving {topic}, apply {clo_phrase} and determine the result",
            f"Apply {clo_phrase} to a practical situation involving {topic}"
        ]

    elif target_bloom == "Analyze":

        candidates = [
            f"Analyze {topic} by examining how {clo_phrase} affects its components",
            f"Analyze the relationship between {topic} and {clo_phrase}",
            f"Analyze {topic} and distinguish its major components related to {clo_phrase}",
            f"Examine {topic} and analyze the effect of {clo_phrase}",
            f"Compare the major components of {topic} and analyze their relationship to {clo_phrase}"
        ]

    elif target_bloom == "Evaluate":

        candidates = [
            f"Evaluate {topic} using {clo_phrase} as a criterion and justify your conclusion",
            f"Assess {topic} using criteria related to {clo_phrase} and justify your judgment",
            f"Evaluate the effectiveness of {topic} with reference to {clo_phrase} and justify your conclusion",
            f"Critique {topic} using evidence related to {clo_phrase} and justify your conclusion",
            f"Evaluate a solution involving {topic} and justify the decision using {clo_phrase}"
        ]

    else:

        candidates = [
            f"Design a practical solution for {topic} using {clo_phrase} and {plo_phrase}",
            f"Develop a solution to a problem involving {topic} using {clo_phrase}",
            f"Create a practical approach to {topic} using {clo_phrase}",
            f"Design a solution involving {topic} that integrates {clo_phrase} and {plo_phrase}",
            f"Develop a practical model for {topic} using {clo_phrase}"
        ]

    return unique_list([
        finalize_question(x)
        for x in candidates
    ])


# ============================================================
# REVISION VALIDATION
# ============================================================

def revision_passes(result):

    return (
        result["overall"] >= 80
        and result["subject"] >= 80
        and result["clo"] >= 80
        and result["plo"] >= 80
        and result["bloom"] >= 80
        and result["specificity"] >= 70
        and result["quality"] >= 70
    )


def revision_rank(result):

    # Weakest metric is the most important.
    weakest = min(
        result["subject"],
        result["clo"],
        result["plo"],
        result["bloom"]
    )

    average = (
        result["overall"]
        + result["subject"]
        + result["clo"]
        + result["plo"]
        + result["bloom"]
        + result["specificity"]
        + result["quality"]
    ) / 7

    return (
        weakest,
        average,
        result["overall"]
    )


def create_revision(
    original_question,
    course_name,
    course_content,
    clos,
    plos,
    target_bloom
):

    if not clos or not plos:
        return {
            "attained": False,
            "question": "",
            "result": None,
            "message": "CLO and PLO are both required."
        }

    original_clo, _ = find_best_clo(
        original_question,
        clos,
        course_name,
        course_content
    )

    original_plo, _ = find_best_plo(
        original_question,
        plos,
        course_name,
        course_content
    )

    candidates = generate_candidates(
        original_question,
        course_name,
        course_content,
        original_clo,
        original_plo,
        target_bloom
    )

    tested = []

    for candidate in candidates:

        # Ensure punctuation is clean.
        candidate = finalize_question(
            candidate
        )

        result = evaluate_question(
            candidate,
            course_name,
            course_content,
            clos,
            plos,
            target_bloom
        )

        tested.append(
            (
                candidate,
                result
            )
        )

        # ====================================================
        # ACCEPT ONLY A REAL PASS
        # ====================================================

        if revision_passes(result):

            return {
                "attained": True,
                "question": candidate,
                "result": result,
                "message": "Alignment achieved after revision."
            }

    # ========================================================
    # If none passes, show the strongest actual revision.
    # Do NOT fake an 80 score.
    # ========================================================

    if tested:

        best_question, best_result = max(
            tested,
            key=lambda item:
                revision_rank(item[1])
        )

        return {
            "attained": False,
            "question": best_question,
            "result": best_result,
            "message": (
                "No generated revision passed all 80% "
                "requirements. The strongest tested revision "
                "is displayed with its actual score."
            )
        }

    return {
        "attained": False,
        "question": "",
        "result": None,
        "message": "No revision could be generated."
    }


# ============================================================
# SCORE DISPLAY
# ============================================================

def score_icon(value):

    if value >= 80:
        return "🟢"

    if value >= 60:
        return "🟡"

    return "🔴"


def show_scores(result):

    columns = st.columns(7)

    metrics = [
        ("Overall", result["overall"]),
        ("Subject", result["subject"]),
        ("CLO", result["clo"]),
        ("PLO", result["plo"]),
        ("Bloom", result["bloom"]),
        ("Specificity", result["specificity"]),
        ("Quality", result["quality"])
    ]

    for column, (label, value) in zip(
        columns,
        metrics
    ):

        with column:

            st.metric(
                label,
                f"{value:.1f}/100"
            )

            st.caption(
                score_icon(value)
            )


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = []

if "revisions" not in st.session_state:
    st.session_state.revisions = {}


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎓 OBE Assessment Alignment Checker"
)

st.caption(
    "Question-specific CLO, PLO, Bloom and assessment-quality evaluation"
)


# ============================================================
# COURSE INPUT
# ============================================================

course_name = st.text_input(
    "Course / Subject Name",
    placeholder="e.g., Chemistry, English I, Programming Fundamentals"
)

course_content = st.text_area(
    "Course Content / Syllabus",
    height=180,
    placeholder=(
        "Enter course topics, chapters, concepts, or syllabus content."
    )
)


# ============================================================
# CLO / PLO
# ============================================================

col1, col2 = st.columns(2)

with col1:

    clo_text = st.text_area(
        "CLOs",
        height=180,
        placeholder=(
            "CLO 1: Explain the principles of chemical bonding\n"
            "CLO 2: Apply chemical bonding principles to solve problems"
        )
    )

with col2:

    plo_text = st.text_area(
        "PLOs",
        height=180,
        placeholder=(
            "PLO 1: Apply knowledge of the discipline\n"
            "PLO 2: Analyze problems and develop appropriate solutions"
        )
    )


# ============================================================
# TARGET BLOOM
# ============================================================

target_bloom = st.selectbox(
    "Target Bloom's Level",
    list(BLOOM_ORDER.keys()),
    index=2
)


# ============================================================
# FILE
# ============================================================

st.markdown("---")

st.subheader("📄 Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload PDF, DOCX, XLSX, XLS, CSV or TXT",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt"
    ]
)

uploaded_text = ""

if uploaded_file:

    try:

        uploaded_text = read_uploaded_file(
            uploaded_file
        )

        st.success(
            f"File successfully read: {uploaded_file.name}"
        )

        with st.expander(
            "View extracted text"
        ):

            st.text(
                uploaded_text[:12000]
            )

    except Exception as error:

        st.error(
            f"Could not read file: {error}"
        )


# ============================================================
# MANUAL QUESTION
# ============================================================

st.subheader("✍️ Manual Question")

manual_question = st.text_area(
    "Enter a question manually if required",
    height=120,
    placeholder="Enter assessment question..."
)


# ============================================================
# QUESTIONS
# ============================================================

file_questions = extract_questions(
    uploaded_text
)

questions = []

for question in file_questions:
    questions.append(question)

if manual_question.strip():
    questions.append(
        clean_text(manual_question)
    )

questions = unique_list(
    questions
)

if file_questions:

    st.info(
        f"{len(file_questions)} question(s) detected from the uploaded file."
    )


# ============================================================
# PARSE OUTCOMES
# ============================================================

clos = parse_outcomes(
    clo_text,
    "CLO"
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)


# ============================================================
# ANALYZE
# ============================================================

st.markdown("---")

analyze = st.button(
    "🔍 Evaluate Questions",
    type="primary",
    use_container_width=True
)

if analyze:

    if not course_name.strip():
        st.error(
            "Please enter the course/subject name."
        )
        st.stop()

    if not course_content.strip():
        st.error(
            "Please enter course content."
        )
        st.stop()

    if not clos:
        st.error(
            "Please enter at least one CLO."
        )
        st.stop()

    if not plos:
        st.error(
            "Please enter at least one PLO."
        )
        st.stop()

    if not questions:
        st.error(
            "Please upload an assessment or enter a question manually."
        )
        st.stop()

    results = []

    progress = st.progress(0)

    for index, question in enumerate(
        questions
    ):

        result = evaluate_question(
            question,
            course_name,
            course_content,
            clos,
            plos,
            target_bloom
        )

        results.append(result)

        progress.progress(
            (index + 1) / len(questions)
        )

    progress.empty()

    st.session_state.results = results

    # Clear old revisions.
    st.session_state.revisions = {}

    st.success(
        f"Evaluation completed for {len(results)} question(s)."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.results:

    st.markdown("---")

    st.header(
        "📊 Question-by-Question Evaluation"
    )

    # ========================================================
    # SUMMARY TABLE
    # ========================================================

    summary = []

    for i, result in enumerate(
        st.session_state.results,
        1
    ):

        summary.append({
            "Question": f"Q{i}",
            "Overall": result["overall"],
            "Subject": result["subject"],
            "CLO": result["clo"],
            "PLO": result["plo"],
            "Bloom": result["bloom"],
            "Specificity": result["specificity"],
            "Quality": result["quality"],
            "Status": result["status"]
        })

    summary_df = pd.DataFrame(
        summary
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # INDIVIDUAL QUESTIONS
    # ========================================================

    for index, result in enumerate(
        st.session_state.results
    ):

        number = index + 1

        with st.expander(
            f"Q{number} — "
            f"{result['status']} — "
            f"{result['overall']:.1f}/100"
        ):

            st.markdown(
                "### Original Question"
            )

            st.write(
                result["question"]
            )

            st.markdown(
                "### Original Scores"
            )

            show_scores(
                result
            )

            st.markdown(
                "### Alignment Evidence"
            )

            ec1, ec2 = st.columns(2)

            with ec1:

                st.write(
                    "**Matched CLO:**"
                )

                st.info(
                    result["matched_clo"]
                )

            with ec2:

                st.write(
                    "**Matched PLO:**"
                )

                st.info(
                    result["matched_plo"]
                )

            st.write(
                f"**Detected Bloom:** "
                f"{result['actual_bloom']}"
            )

            st.write(
                f"**Target Bloom:** "
                f"{result['target_bloom']}"
            )

            # =================================================
            # REVISION
            # =================================================

            st.markdown("---")

            st.markdown(
                "### 🔧 Revision"
            )

            revision_key = f"revision_{index}"

            generate = st.button(
                "Generate Validated Revision",
                key=f"generate_revision_{index}"
            )

            if generate:

                with st.spinner(
                    "Generating multiple revisions and testing each one..."
                ):

                    revision = create_revision(
                        result["question"],
                        course_name,
                        course_content,
                        clos,
                        plos,
                        target_bloom
                    )

                st.session_state.revisions[
                    revision_key
                ] = revision

            # =================================================
            # SHOW REVISION
            # =================================================

            if revision_key in st.session_state.revisions:

                revision = st.session_state.revisions[
                    revision_key
                ]

                if revision["question"]:

                    if revision["attained"]:

                        st.success(
                            "🎯 ALIGNMENT ACHIEVED AFTER REVISION"
                        )

                    else:

                        st.warning(
                            revision["message"]
                        )

                    st.markdown(
                        "#### Revised Question"
                    )

                    revised_question = finalize_question(
                        revision["question"]
                    )

                    st.write(
                        revised_question
                    )

                    if revision["result"]:

                        revised_result = revision[
                            "result"
                        ]

                        st.markdown(
                            "#### Revised Scores"
                        )

                        show_scores(
                            revised_result
                        )

                        # =====================================
                        # DIRECT COMPARISON
                        # =====================================

                        st.markdown(
                            "#### Before vs After"
                        )

                        comparison = pd.DataFrame([
                            {
                                "Metric": "Overall",
                                "Before": result["overall"],
                                "After": revised_result["overall"],
                                "Change": round(
                                    revised_result["overall"]
                                    - result["overall"],
                                    1
                                )
                            },
                            {
                                "Metric": "Subject",
                                "Before": result["subject"],
                                "After": revised_result["subject"],
                                "Change": round(
                                    revised_result["subject"]
                                    - result["subject"],
                                    1
                                )
                            },
                            {
                                "Metric": "CLO",
                                "Before": result["clo"],
                                "After": revised_result["clo"],
                                "Change": round(
                                    revised_result["clo"]
                                    - result["clo"],
                                    1
                                )
                            },
                            {
                                "Metric": "PLO",
                                "Before": result["plo"],
                                "After": revised_result["plo"],
                                "Change": round(
                                    revised_result["plo"]
                                    - result["plo"],
                                    1
                                )
                            },
                            {
                                "Metric": "Bloom",
                                "Before": result["bloom"],
                                "After": revised_result["bloom"],
                                "Change": round(
                                    revised_result["bloom"]
                                    - result["bloom"],
                                    1
                                )
                            },
                            {
                                "Metric": "Specificity",
                                "Before": result["specificity"],
                                "After": revised_result["specificity"],
                                "Change": round(
                                    revised_result["specificity"]
                                    - result["specificity"],
                                    1
                                )
                            },
                            {
                                "Metric": "Quality",
                                "Before": result["quality"],
                                "After": revised_result["quality"],
                                "Change": round(
                                    revised_result["quality"]
                                    - result["quality"],
                                    1
                                )
                            }
                        ])

                        st.dataframe(
                            comparison,
                            use_container_width=True,
                            hide_index=True
                        )

                        # =====================================
                        # FINAL VALIDATION
                        # =====================================

                        if revision["attained"]:

                            st.success(
                                "✅ This revision passed the strict "
                                "80% validation criteria."
                            )

                            st.markdown(
                                f"""
**Overall:** {revised_result['overall']:.1f}/100  
**Subject:** {revised_result['subject']:.1f}/100  
**CLO:** {revised_result['clo']:.1f}/100  
**PLO:** {revised_result['plo']:.1f}/100  
**Bloom:** {revised_result['bloom']:.1f}/100
"""
                            )

                        else:

                            failed = []

                            if revised_result["overall"] < 80:
                                failed.append(
                                    f"Overall {revised_result['overall']:.1f}"
                                )

                            if revised_result["subject"] < 80:
                                failed.append(
                                    f"Subject {revised_result['subject']:.1f}"
                                )

                            if revised_result["clo"] < 80:
                                failed.append(
                                    f"CLO {revised_result['clo']:.1f}"
                                )

                            if revised_result["plo"] < 80:
                                failed.append(
                                    f"PLO {revised_result['plo']:.1f}"
                                )

                            if revised_result["bloom"] < 80:
                                failed.append(
                                    f"Bloom {revised_result['bloom']:.1f}"
                                )

                            st.error(
                                "The revision was not falsely marked as "
                                "attained. Metrics below 80: "
                                + ", ".join(failed)
                            )

                else:

                    st.error(
                        revision["message"]
                    )


# ============================================================
# EXPORT
# ============================================================

if st.session_state.results:

    st.markdown("---")

    st.header(
        "📥 Export Results"
    )

    export_rows = []

    for index, original in enumerate(
        st.session_state.results
    ):

        revision = st.session_state.revisions.get(
            f"revision_{index}"
        )

        row = {
            "Question": f"Q{index + 1}",
            "Original Question": original["question"],
            "Original Overall": original["overall"],
            "Original Subject": original["subject"],
            "Original CLO": original["clo"],
            "Original PLO": original["plo"],
            "Original Bloom": original["bloom"],
            "Original Specificity": original["specificity"],
            "Original Quality": original["quality"],
            "Original Status": original["status"],
            "Revised Question": "",
            "Revised Overall": "",
            "Revised Subject": "",
            "Revised CLO": "",
            "Revised PLO": "",
            "Revised Bloom": "",
            "Revised Specificity": "",
            "Revised Quality": "",
            "Revision Attained": ""
        }

        if revision and revision.get(
            "result"
        ):

            rr = revision["result"]

            row["Revised Question"] = finalize_question(
                revision["question"]
            )

            row["Revised Overall"] = rr["overall"]
            row["Revised Subject"] = rr["subject"]
            row["Revised CLO"] = rr["clo"]
            row["Revised PLO"] = rr["plo"]
            row["Revised Bloom"] = rr["bloom"]
            row["Revised Specificity"] = rr["specificity"]
            row["Revised Quality"] = rr["quality"]

            row["Revision Attained"] = (
                "YES"
                if revision["attained"]
                else "NO"
            )

        export_rows.append(
            row
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv_bytes = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Evaluation Report",
        data=csv_bytes,
        file_name="OBE_Alignment_Evaluation.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "OBE Assessment Alignment Checker — "
    "Question-specific evidence-based scoring"
)
