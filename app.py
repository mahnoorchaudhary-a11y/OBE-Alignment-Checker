import io
import re
import textwrap
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# OBE QUIZ QUALITY & ALIGNMENT CHECKER
# Subject-independent assessment evaluation
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Quality & Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import fitz
except Exception:
    fitz = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None


# ============================================================
# BLOOM'S TAXONOMY
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
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "label", "select", "match"
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
        "examine", "compare", "contrast", "investigate",
        "infer", "relate"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "defend", "judge", "appraise", "validate",
        "argue", "recommend"
    ],
    "Create": [
        "create", "design", "develop", "formulate",
        "produce", "generate", "plan", "compose",
        "propose", "construct"
    ]
}


STOP_WORDS = set("""
a an the and or but if then than of to in on at for from
with by is are was were be been being this that these those
it its as into about through during before after above below
between which who whom whose what when where why how do does
did will would should could can may might must
""".split())


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\x00", " ")
    value = value.replace("\r\n", "\n")
    value = value.replace("\r", "\n")

    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def normalize_text(value):
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def tokens(value):
    words = normalize_text(value).split()

    return [
        word
        for word in words
        if len(word) > 2 and word not in STOP_WORDS
    ]


def token_set(value):
    return set(tokens(value))


def similarity(text_a, text_b):
    a = token_set(text_a)
    b = token_set(text_b)

    if not a or not b:
        return 0.0

    intersection = len(a & b)
    union = len(a | b)

    jaccard = intersection / union if union else 0
    coverage_a = intersection / len(a)
    coverage_b = intersection / len(b)

    score = (
        0.45 * jaccard
        + 0.35 * coverage_a
        + 0.20 * coverage_b
    )

    return round(min(score, 1.0) * 100, 1)


def meaningful_phrases(text):
    words = tokens(text)

    phrases = set(words)

    for size in [2, 3]:
        for i in range(len(words) - size + 1):
            phrases.add(
                " ".join(words[i:i + size])
            )

    return phrases


def concept_overlap(question, outcome):
    q = meaningful_phrases(question)
    o = meaningful_phrases(outcome)

    if not q or not o:
        return 0

    shared = q & o

    return round(
        min(
            len(shared) / max(1, len(o)),
            1
        ) * 100,
        1
    )


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf_pypdf(data):
    if PdfReader is None:
        return ""

    try:
        reader = PdfReader(
            io.BytesIO(data)
        )

        pages = []

        for page in reader.pages:
            try:
                text = page.extract_text() or ""

                if text.strip():
                    pages.append(text)

            except Exception:
                continue

        return clean_text(
            "\n".join(pages)
        )

    except Exception:
        return ""


def extract_pdf_pymupdf(data):
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
                text = page.get_text(
                    "text"
                ) or ""

                if text.strip():
                    pages.append(text)

            except Exception:
                continue

        document.close()

        return clean_text(
            "\n".join(pages)
        )

    except Exception:
        return ""


def extract_pdf_ocr(data):
    if (
        pytesseract is None
        or convert_from_bytes is None
    ):
        return ""

    try:
        images = convert_from_bytes(
            data,
            dpi=180
        )

        pages = []

        for image in images:
            try:
                text = pytesseract.image_to_string(
                    image
                )

                if text.strip():
                    pages.append(text)

            except Exception:
                continue

        return clean_text(
            "\n".join(pages)
        )

    except Exception:
        return ""


def extract_pdf_text(data):
    candidates = []

    text = extract_pdf_pypdf(data)

    candidates.append(
        (
            text,
            "PDF text extraction"
        )
    )

    text = extract_pdf_pymupdf(data)

    candidates.append(
        (
            text,
            "PyMuPDF extraction"
        )
    )

    # OCR is especially important for scanned PDFs.
    text = extract_pdf_ocr(data)

    candidates.append(
        (
            text,
            "OCR"
        )
    )

    candidates.sort(
        key=lambda x: len(x[0]),
        reverse=True
    )

    best_text, method = candidates[0]

    return best_text, method


# ============================================================
# DOCX EXTRACTION
# ============================================================

def extract_docx_text(data):
    if Document is None:
        return ""

    try:
        document = Document(
            io.BytesIO(data)
        )

        parts = []

        for paragraph in document.paragraphs:

            if paragraph.text.strip():
                parts.append(
                    paragraph.text
                )

        for table in document.tables:

            for row in table.rows:

                values = [
                    cell.text
                    for cell in row.cells
                ]

                line = " | ".join(
                    values
                )

                if line.strip():
                    parts.append(line)

        return clean_text(
            "\n".join(parts)
        )

    except Exception:
        return ""


# ============================================================
# EXCEL EXTRACTION
# ============================================================

def extract_excel_text(data):
    try:
        workbook = pd.ExcelFile(
            io.BytesIO(data)
        )

        parts = []

        for sheet in workbook.sheet_names:

            parts.append(
                f"--- SHEET: {sheet} ---"
            )

            try:
                df = pd.read_excel(
                    io.BytesIO(data),
                    sheet_name=sheet,
                    header=None
                )

                df = df.fillna("")

                for row in df.astype(str).values:

                    values = [
                        cell.strip()
                        for cell in row
                        if cell.strip()
                    ]

                    if values:
                        parts.append(
                            " | ".join(values)
                        )

            except Exception:
                continue

        return clean_text(
            "\n".join(parts)
        )

    except Exception:
        return ""


# ============================================================
# UNIVERSAL FILE READER
# ============================================================

def extract_uploaded_file(uploaded_file):

    if uploaded_file is None:
        return "", "No file"

    data = uploaded_file.getvalue()

    extension = Path(
        uploaded_file.name
    ).suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(data)

    if extension == ".docx":
        return (
            extract_docx_text(data),
            "DOCX extraction"
        )

    if extension in [
        ".xlsx",
        ".xls",
        ".csv"
    ]:

        return (
            extract_excel_text(data),
            "Excel extraction"
        )

    if extension in [
        ".txt",
        ".md"
    ]:

        try:
            text = data.decode(
                "utf-8",
                errors="ignore"
            )

            return (
                clean_text(text),
                "Text extraction"
            )

        except Exception:
            return "", "Text decoding failed"

    return (
        "",
        f"Unsupported file type: {extension}"
    )


# ============================================================
# CLO / PLO PARSER
# ============================================================

def remove_bullet_prefix(text):

    return re.sub(
        r"^\s*[-*•▪◦]+\s*",
        "",
        text
    ).strip()


def parse_learning_outcomes(
    text,
    outcome_type
):

    if not text:
        return []

    text = clean_text(text)

    results = []

    lines = text.splitlines()

    # --------------------------------------------------------
    # Flexible line formats
    # --------------------------------------------------------

    pattern = re.compile(
        rf"""
        ^\s*
        (?:[-*•▪◦]\s*)?
        {outcome_type}
        \s*
        [-_–—]?
        \s*
        (\d+)
        \s*
        (?:
            :
            |
            \.
            |
            \)
            |
            -
            |
            _
            |
            – 
            |
            —
            |
            \s+
        )
        \s*
        (.+?)
        \s*$
        """,
        re.IGNORECASE |
        re.VERBOSE
    )

    for line in lines:

        line = remove_bullet_prefix(
            line.strip()
        )

        if not line:
            continue

        match = pattern.match(line)

        if not match:
            continue

        number = match.group(1)

        description = match.group(2).strip()

        description = description.strip(
            " :-–—.)"
        )

        if len(description) < 3:
            continue

        results.append(
            {
                "id": f"{outcome_type}{number}",
                "text": description
            }
        )

    # --------------------------------------------------------
    # Inline fallback
    # --------------------------------------------------------

    if not results:

        inline_pattern = re.compile(
            rf"""
            \b
            {outcome_type}
            \s*
            [-_–—]?
            \s*
            (\d+)
            \s*
            (?:
                :
                |
                \.
                |
                \)
                |
                -
                |
                _
                |
                \s+
            )
            \s*
            (.+?)
            (?=
                \s+
                {outcome_type}
                \s*
                [-_–—]?
                \s*
                \d+
                \b
                |
                $
            )
            """,
            re.IGNORECASE |
            re.VERBOSE |
            re.DOTALL
        )

        for match in inline_pattern.finditer(text):

            number = match.group(1)

            description = clean_text(
                match.group(2)
            )

            description = description.strip(
                " :-–—.)"
            )

            if len(description) >= 3:

                results.append(
                    {
                        "id": f"{outcome_type}{number}",
                        "text": description
                    }
                )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique = []
    seen = set()

    for item in results:

        key = (
            item["id"].lower(),
            normalize_text(
                item["text"]
            )
        )

        if key not in seen:

            seen.add(key)

            unique.append(item)

    return unique


def extract_clos_and_plos(text):

    return (
        parse_learning_outcomes(
            text,
            "CLO"
        ),
        parse_learning_outcomes(
            text,
            "PLO"
        )
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

NUMBERED_QUESTION = re.compile(
    r"""
    (?im)
    ^\s*
    (?:
        question\s*
    )?
    (\d{1,3})
    \s*
    [\.\):\-–—]
    \s+
    """,
    re.VERBOSE
)


COMMAND_QUESTION = re.compile(
    r"""
    (?i)
    ^\s*
    (
        identify|
        define|
        state|
        list|
        name|
        explain|
        describe|
        summarize|
        discuss|
        analyze|
        analyse|
        compare|
        contrast|
        differentiate|
        distinguish|
        evaluate|
        assess|
        justify|
        examine|
        interpret|
        apply|
        calculate|
        determine|
        solve|
        demonstrate|
        illustrate|
        classify|
        select|
        choose|
        write|
        rewrite|
        paraphrase|
        develop|
        design|
        create|
        formulate|
        construct|
        what|
        which|
        why|
        how|
        when|
        where|
        who|
        whose
    )
    \b
    """,
    re.VERBOSE
)


def split_options(text):

    pattern = re.compile(
        r"""
        (?im)
        (?:^|\n)
        \s*
        [\(\[]?
        ([A-H])
        [\)\]\.:]
        \s+
        """,
        re.VERBOSE
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

    for i, match in enumerate(matches):

        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        option_text = text[
            start:end
        ].strip()

        if option_text:

            options.append(
                {
                    "label": match.group(1).upper(),
                    "text": option_text
                }
            )

    return question_text, options


def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    questions = []

    # --------------------------------------------------------
    # Method 1: numbered questions
    # --------------------------------------------------------

    matches = list(
        NUMBERED_QUESTION.finditer(
            text
        )
    )

    for i, match in enumerate(matches):

        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        block = text[
            start:end
        ].strip()

        if not block:
            continue

        question_text, options = split_options(
            block
        )

        # Remove answer-key lines.
        question_text = re.sub(
            r"(?im)"
            r"^\s*"
            r"(answer|correct answer|key)"
            r"\s*[:\-].*$",
            "",
            question_text
        ).strip()

        if len(question_text) >= 8:

            questions.append(
                {
                    "number": len(questions) + 1,
                    "text": clean_text(
                        question_text
                    ),
                    "options": options
                }
            )

    # --------------------------------------------------------
    # Method 2: command-style questions
    # --------------------------------------------------------

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

            if COMMAND_QUESTION.match(
                paragraph
            ):

                question_text, options = split_options(
                    paragraph
                )

                questions.append(
                    {
                        "number": len(questions) + 1,
                        "text": clean_text(
                            question_text
                        ),
                        "options": options
                    }
                )

    # --------------------------------------------------------
    # Method 3: question-mark fallback
    # --------------------------------------------------------

    if not questions:

        sentences = re.split(
            r"(?<=\?)\s+",
            text
        )

        for sentence in sentences:

            sentence = clean_text(
                sentence
            )

            if (
                len(sentence) >= 12
                and "?" in sentence
            ):

                questions.append(
                    {
                        "number": len(questions) + 1,
                        "text": sentence,
                        "options": []
                    }
                )

    return questions


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    normalized = normalize_text(
        question
    )

    first_words = normalized.split()[:15]

    detected = []

    for level in BLOOM_LEVELS:

        for verb in BLOOM_VERBS[level]:

            if verb in first_words:
                detected.append(level)
                break

    if detected:

        return max(
            detected,
            key=lambda x: BLOOM_RANK[x]
        )

    for level in BLOOM_LEVELS:

        for verb in BLOOM_VERBS[level]:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                normalized
            ):
                return level

    return "Needs Review"


def bloom_alignment(
    detected,
    intended
):

    if detected == "Needs Review":
        return 40.0

    distance = abs(
        BLOOM_RANK[detected]
        - BLOOM_RANK[intended]
    )

    if distance == 0:
        return 100.0

    if distance == 1:
        return 70.0

    if distance == 2:
        return 50.0

    return 30.0


# ============================================================
# QUESTION QUALITY METRICS
# ============================================================

def clarity_score(question):

    words = question.split()

    if len(words) < 5:
        return 35

    score = 75

    if question.count("?") == 1:
        score += 10

    if re.search(
        r"\b("
        r"what|which|why|how|identify|explain|"
        r"analyze|analyse|evaluate|calculate|"
        r"determine|compare|describe|select"
        r")\b",
        question,
        re.I
    ):
        score += 10

    if len(words) > 80:
        score -= 20

    return max(
        0,
        min(100, score)
    )


def specificity_score(question):

    words = tokens(
        question
    )

    if len(words) < 5:
        return 40

    score = 65

    context_terms = [
        "given",
        "following",
        "scenario",
        "case",
        "data",
        "paragraph",
        "example",
        "equation",
        "diagram",
        "table",
        "according to"
    ]

    if any(
        term in normalize_text(question)
        for term in context_terms
    ):
        score += 15

    if len(words) >= 10:
        score += 10

    return min(
        100,
        score
    )


def measurability_score(question):

    normalized = normalize_text(
        question
    )

    measurable = [
        "identify",
        "define",
        "calculate",
        "determine",
        "select",
        "explain",
        "analyze",
        "analyse",
        "compare",
        "evaluate",
        "justify",
        "classify",
        "solve",
        "describe",
        "construct",
        "design"
    ]

    if any(
        word in normalized.split()
        for word in measurable
    ):
        return 95

    if "?" in question:
        return 75

    return 55


def evaluate_options(options):

    if not options:

        return {
            "score": 65.0,
            "feedback":
                "No MCQ options were detected."
        }

    score = 100.0
    feedback = []

    if len(options) < 3:

        score -= 30

        feedback.append(
            "Fewer than three options were detected."
        )

    if len(options) > 6:

        score -= 10

        feedback.append(
            "More than six options were detected."
        )

    normalized_options = [
        normalize_text(
            option["text"]
        )
        for option in options
    ]

    if len(normalized_options) != len(
        set(normalized_options)
    ):

        score -= 25

        feedback.append(
            "Duplicate options may be present."
        )

    lengths = [
        len(option.split())
        for option in normalized_options
        if option
    ]

    if lengths:

        if max(lengths) - min(lengths) > 25:

            score -= 10

            feedback.append(
                "Option lengths vary substantially."
            )

    if not feedback:

        feedback.append(
            "The detected option structure is reasonable."
        )

    return {
        "score": max(
            0,
            min(100, score)
        ),
        "feedback": " ".join(
            feedback
        )
    }


# ============================================================
# BEST CLO / PLO MATCH
# ============================================================

def best_outcome_match(
    question,
    outcomes
):

    if not outcomes:
        return None, 0

    scored = []

    for outcome in outcomes:

        lexical = similarity(
            question,
            outcome["text"]
        )

        phrase = concept_overlap(
            question,
            outcome["text"]
        )

        score = round(
            lexical * 0.70
            + phrase * 0.30,
            1
        )

        scored.append(
            (
                outcome,
                score
            )
        )

    scored.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scored[0]


# ============================================================
# COMPLETE QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos,
    intended_bloom
):

    clo_match, clo_score = best_outcome_match(
        question["text"],
        clos
    )

    plo_match, plo_score = best_outcome_match(
        question["text"],
        plos
    )

    detected_bloom = detect_bloom(
        question["text"]
    )

    bloom_score = bloom_alignment(
        detected_bloom,
        intended_bloom
    )

    clarity = clarity_score(
        question["text"]
    )

    specificity = specificity_score(
        question["text"]
    )

    measurability = measurability_score(
        question["text"]
    )

    clo_text = (
        clo_match["text"]
        if clo_match
        else ""
    )

    plo_text = (
        plo_match["text"]
        if plo_match
        else ""
    )

    relevance = round(
        (
            clo_score * 0.65
            + plo_score * 0.35
        ),
        1
    ) if plos else clo_score

    mcq = evaluate_options(
        question["options"]
    )

    overall = round(
        clo_score * 0.20
        + plo_score * 0.15
        + bloom_score * 0.20
        + clarity * 0.10
        + specificity * 0.10
        + measurability * 0.10
        + relevance * 0.05
        + mcq["score"] * 0.10,
        1
    )

    feedback = []

    if clo_score < 60:

        feedback.append(
            "The question has weak or unclear alignment with the matched learning outcome."
        )

    if plos and plo_score < 60:

        feedback.append(
            "The question has weak or unclear alignment with the matched program outcome."
        )

    if detected_bloom == "Needs Review":

        feedback.append(
            "The cognitive level cannot be identified confidently from the wording."
        )

    elif detected_bloom != intended_bloom:

        feedback.append(
            f"The detected cognitive level is {detected_bloom}, "
            f"while the intended level is {intended_bloom}."
        )

    if clarity < 70:

        feedback.append(
            "The wording should be made more direct and unambiguous."
        )

    if specificity < 70:

        feedback.append(
            "Additional context, conditions, data, or a specific task may be needed."
        )

    if measurability < 70:

        feedback.append(
            "Use a clearly observable action that can be assessed consistently."
        )

    if mcq["score"] < 80:

        feedback.append(
            mcq["feedback"]
        )

    if not feedback:

        feedback.append(
            "The question meets the current automated quality thresholds."
        )

    return {
        "number": question["number"],
        "question": question["text"],
        "options": question["options"],
        "clo_id": clo_match["id"]
        if clo_match else "Not identified",
        "clo_text": clo_text,
        "clo_score": clo_score,
        "plo_id": plo_match["id"]
        if plo_match else "Not identified",
        "plo_text": plo_text,
        "plo_score": plo_score,
        "bloom": detected_bloom,
        "bloom_score": bloom_score,
        "clarity": clarity,
        "specificity": specificity,
        "measurability": measurability,
        "relevance": relevance,
        "mcq_score": mcq["score"],
        "overall": overall,
        "feedback": feedback
    }


# ============================================================
# SUGGESTION GENERATOR
# ============================================================

def outcome_topic(
    outcome_text
):

    words = tokens(
        outcome_text
    )

    if not words:
        return "the specified topic"

    return " ".join(
        words[:12]
    )


def generate_suggestions(
    outcome,
    bloom
):

    topic = outcome_topic(
        outcome
    )

    if bloom == "Remember":

        suggestions = [
            f"Identify the key concept or principle related to {topic}.",
            f"Define the central concept associated with {topic}.",
            f"Which statement correctly describes the main concept represented by {topic}?"
        ]

    elif bloom == "Understand":

        suggestions = [
            f"Explain the main concept involved in {topic} in your own words.",
            f"Describe how the key concept related to {topic} can be understood.",
            f"Which explanation best describes the important ideas involved in {topic}?"
        ]

    elif bloom == "Apply":

        suggestions = [
            f"Given a situation involving {topic}, determine how the relevant principle should be applied.",
            f"Use the relevant principle associated with {topic} to determine the correct solution.",
            f"Consider the following situation involving {topic}. Select the response that correctly applies the relevant concept."
        ]

    elif bloom == "Analyze":

        suggestions = [
            f"Analyze the given information related to {topic} and determine the relationship among its key elements.",
            f"Examine the information related to {topic} and identify the factors that explain the observed result.",
            f"Analyze the following situation involving {topic} and justify the conclusion supported by the evidence."
        ]

    elif bloom == "Evaluate":

        suggestions = [
            f"Evaluate the proposed approach related to {topic} and determine whether it is supported by the available evidence.",
            f"Assess the alternatives related to {topic} and justify the conclusion best supported by the given information.",
            f"Critically evaluate the following case involving {topic} and justify your conclusion using relevant evidence."
        ]

    else:

        suggestions = [
            f"Design an appropriate solution that addresses the requirements associated with {topic}.",
            f"Develop a suitable approach for addressing the given problem involving {topic}.",
            f"Formulate a solution for the following situation involving {topic} and explain how it meets the stated requirements."
        ]

    # Never include CLO/PLO labels in generated questions.
    cleaned = []

    for question in suggestions:

        question = re.sub(
            r"\bCLO\s*[-_]?\s*\d*\b",
            "",
            question,
            flags=re.I
        )

        question = re.sub(
            r"\bPLO\s*[-_]?\s*\d*\b",
            "",
            question,
            flags=re.I
        )

        question = re.sub(
            r"\s{2,}",
            " ",
            question
        ).strip()

        cleaned.append(
            question
        )

    return cleaned


def reevaluate_suggestion(
    question,
    outcome,
    plos,
    intended_bloom
):

    clo_score = similarity(
        question,
        outcome
    )

    if plos:

        _, plo_score = best_outcome_match(
            question,
            plos
        )

    else:
        plo_score = 100

    detected = detect_bloom(
        question
    )

    bloom_score = bloom_alignment(
        detected,
        intended_bloom
    )

    clarity = clarity_score(
        question
    )

    specificity = specificity_score(
        question
    )

    measurability = measurability_score(
        question
    )

    overall = round(
        clo_score * 0.30
        + plo_score * 0.20
        + bloom_score * 0.30
        + clarity * 0.08
        + specificity * 0.06
        + measurability * 0.06,
        1
    )

    return {
        "CLO Alignment": clo_score,
        "PLO Alignment": plo_score,
        "Bloom Alignment": bloom_score,
        "Detected Bloom": detected,
        "Clarity": clarity,
        "Specificity": specificity,
        "Measurability": measurability,
        "Overall": overall
    }


# ============================================================
# SESSION STATE
# ============================================================

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "extraction_method" not in st.session_state:
    st.session_state.extraction_method = ""

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "uploaded_clos" not in st.session_state:
    st.session_state.uploaded_clos = []

if "uploaded_plos" not in st.session_state:
    st.session_state.uploaded_plos = []


# ============================================================
# TITLE
# ============================================================

st.title(
    "🎓 OBE Quiz Quality & Alignment Checker"
)

st.write(
    "Evaluate quiz questions from diverse subjects using "
    "the actual learning outcomes and assessment requirements."
)

st.info(
    "The tool evaluates question alignment and quality. "
    "It does not calculate student attainment without student marks."
)


# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.header(
    "1. Assessment Information"
)

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder="e.g., Chemistry, English I, Data Structures"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment",
        placeholder="e.g., Quiz 1"
    )


# ============================================================
# CLO INPUT
# ============================================================

st.header(
    "2. Course Learning Outcomes"
)

clo_input = st.text_area(
    "Enter or paste CLOs",
    height=180,
    placeholder=(
        "CLO1: Explain the principles of chemical equilibrium.\n"
        "CLO2: Apply appropriate methods to solve related problems.\n"
        "CLO3: Analyze experimental results using relevant concepts."
    )
)

st.caption(
    "Supported formats include CLO1:, CLO 1:, CLO-1:, "
    "CLO_1:, CLO1 -, CLO1), and CLO1 followed by text."
)

manual_clos = parse_learning_outcomes(
    clo_input,
    "CLO"
)


# ============================================================
# PLO INPUT
# ============================================================

st.header(
    "3. Program Learning Outcomes"
)

plo_input = st.text_area(
    "Enter or paste PLOs",
    height=180,
    placeholder=(
        "PLO1: Apply knowledge of mathematics and science.\n"
        "PLO2: Analyze problems using appropriate methods.\n"
        "PLO3: Communicate solutions effectively."
    )
)

manual_plos = parse_learning_outcomes(
    plo_input,
    "PLO"
)


# ============================================================
# BLOOM
# ============================================================

st.header(
    "4. Intended Bloom's Level"
)

intended_bloom = st.selectbox(
    "Select the intended cognitive level",
    BLOOM_LEVELS,
    index=1
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.header(
    "5. Upload Complete Quiz / Course Document"
)

uploaded_file = st.file_uploader(
    "Upload your file",
    type=[
        "pdf",
        "docx",
        "txt",
        "xlsx",
        "xls",
        "csv"
    ],
    help=(
        "The file may contain CLOs, PLOs, questions, "
        "MCQ options, or assessment information."
    )
)


# ============================================================
# READ FILE
# ============================================================

if uploaded_file is not None:

    if st.button(
        "📖 Read Uploaded File",
        use_container_width=True
    ):

        with st.spinner(
            "Reading the uploaded file..."
        ):

            extracted, method = extract_uploaded_file(
                uploaded_file
            )

        st.session_state.extracted_text = extracted
        st.session_state.extraction_method = method

        if extracted:

            clos, plos = extract_clos_and_plos(
                extracted
            )

            st.session_state.uploaded_clos = clos
            st.session_state.uploaded_plos = plos

            st.success(
                f"File successfully read using {method}."
            )

            st.write(
                f"**Characters extracted:** "
                f"{len(extracted):,}"
            )

            if clos:

                st.success(
                    f"Detected {len(clos)} CLO(s)."
                )

            else:

                st.warning(
                    "No labelled CLOs were detected in the file. "
                    "You can enter them manually above."
                )

            if plos:

                st.success(
                    f"Detected {len(plos)} PLO(s)."
                )

            else:

                st.warning(
                    "No labelled PLOs were detected in the file. "
                    "You can enter them manually above."
                )

            with st.expander(
                "🔎 View Extracted Text"
            ):

                st.text_area(
                    "Extracted content",
                    extracted[:50000],
                    height=400
                )

        else:

            st.error(
                "No readable text was extracted from this file."
            )

            st.warning(
                "If this is a scanned PDF, OCR requires "
                "Tesseract and PDF image-conversion support "
                "on the Streamlit environment."
            )


# ============================================================
# DETERMINE FINAL CLO/PLO LIST
# ============================================================

final_clos = manual_clos

final_plos = manual_plos

if (
    not final_clos
    and st.session_state.uploaded_clos
):

    final_clos = (
        st.session_state.uploaded_clos
    )

if (
    not final_plos
    and st.session_state.uploaded_plos
):

    final_plos = (
        st.session_state.uploaded_plos
    )


# ============================================================
# SHOW DETECTED OUTCOMES
# ============================================================

if final_clos:

    with st.expander(
        f"✅ CLOs available for evaluation "
        f"({len(final_clos)})",
        expanded=True
    ):

        for clo in final_clos:

            st.write(
                f"**{clo['id']}** — {clo['text']}"
            )


if final_plos:

    with st.expander(
        f"✅ PLOs available for evaluation "
        f"({len(final_plos)})"
    ):

        for plo in final_plos:

            st.write(
                f"**{plo['id']}** — {plo['text']}"
            )


# ============================================================
# ANALYSIS
# ============================================================

st.header(
    "6. Perform Complete Quiz Evaluation"
)

if st.button(
    "🔍 Analyze Complete Quiz",
    type="primary",
    use_container_width=True
):

    # --------------------------------------------------------
    # Validate CLOs
    # --------------------------------------------------------

    if not final_clos:

        st.error(
            "No CLOs could be identified. "
            "Please enter CLOs manually or upload a document "
            "containing labelled CLO statements."
        )

        st.stop()

    # --------------------------------------------------------
    # Validate file
    # --------------------------------------------------------

    extracted_text = (
        st.session_state.extracted_text
    )

    if not extracted_text:

        if uploaded_file is not None:

            extracted_text, method = (
                extract_uploaded_file(
                    uploaded_file
                )
            )

            st.session_state.extracted_text = (
                extracted_text
            )

            st.session_state.extraction_method = (
                method
            )

        else:

            st.error(
                "Please upload the complete quiz."
            )

            st.stop()

    if not extracted_text:

        st.error(
            "The uploaded file could not be read."
        )

        st.stop()

    # --------------------------------------------------------
    # Extract questions
    # --------------------------------------------------------

    questions = extract_questions(
        extracted_text
    )

    if not questions:

        st.error(
            "No questions could be detected."
        )

        with st.expander(
            "🔎 View extracted text"
        ):

            st.text(
                extracted_text[:50000]
            )

        st.info(
            "Make sure the document contains numbered questions "
            "such as Q1., Q2., 1., 2., or clearly written questions."
        )

        st.stop()

    # --------------------------------------------------------
    # Evaluate
    # --------------------------------------------------------

    with st.spinner(
        "Evaluating all questions..."
    ):

        evaluation_results = []

        for question in questions:

            result = evaluate_question(
                question,
                final_clos,
                final_plos,
                intended_bloom
            )

            evaluation_results.append(
                result
            )

        st.session_state.analysis_results = (
            evaluation_results
        )

    st.success(
        f"Evaluation completed for "
        f"{len(evaluation_results)} question(s)."
    )


# ============================================================
# RESULTS
# ============================================================

results = (
    st.session_state.analysis_results
)

if results:

    # ========================================================
    # OVERALL GRAPH
    # ========================================================

    st.header(
        "7. Overall Graphical Evaluation"
    )

    clo_avg = round(
        sum(
            r["clo_score"]
            for r in results
        ) / len(results),
        1
    )

    plo_avg = (
        round(
            sum(
                r["plo_score"]
                for r in results
            ) / len(results),
            1
        )
        if final_plos
        else 0
    )

    bloom_avg = round(
        sum(
            r["bloom_score"]
            for r in results
        ) / len(results),
        1
    )

    clarity_avg = round(
        sum(
            r["clarity"]
            for r in results
        ) / len(results),
        1
    )

    specificity_avg = round(
        sum(
            r["specificity"]
            for r in results
        ) / len(results),
        1
    )

    measurability_avg = round(
        sum(
            r["measurability"]
            for r in results
        ) / len(results),
        1
    )

    mcq_avg = round(
        sum(
            r["mcq_score"]
            for r in results
        ) / len(results),
        1
    )

    overall = round(
        sum(
            r["overall"]
            for r in results
        ) / len(results),
        1
    )

    graph_df = pd.DataFrame(
        {
            "Evaluation Area": [
                "CLO Alignment",
                "PLO Alignment",
                "Bloom Alignment",
                "Clarity",
                "Specificity",
                "Measurability",
                "MCQ Quality",
                "Overall Quality"
            ],
            "Score": [
                clo_avg,
                plo_avg,
                bloom_avg,
                clarity_avg,
                specificity_avg,
                measurability_avg,
                mcq_avg,
                overall
            ]
        }
    )

    st.bar_chart(
        graph_df.set_index(
            "Evaluation Area"
        )["Score"],
        use_container_width=True
    )

    metric1, metric2, metric3, metric4 = (
        st.columns(4)
    )

    metric1.metric(
        "CLO Alignment",
        f"{clo_avg}%"
    )

    metric2.metric(
        "PLO Alignment",
        f"{plo_avg}%"
        if final_plos
        else "N/A"
    )

    metric3.metric(
        "Bloom Alignment",
        f"{bloom_avg}%"
    )

    metric4.metric(
        "Overall Quality",
        f"{overall}%"
    )

    st.caption(
        "These scores represent automated assessment-quality "
        "and alignment checks. They are not student attainment scores."
    )


    # ========================================================
    # ONE CLO AT A TIME
    # ========================================================

    st.header(
        "8. CLO Analysis — One CLO at a Time"
    )

    clo_labels = [
        f"{clo['id']} — {clo['text']}"
        for clo in final_clos
    ]

    selected_clo_index = st.selectbox(
        "Select one CLO",
        range(len(clo_labels)),
        format_func=lambda i: clo_labels[i]
    )

    selected_clo = final_clos[
        selected_clo_index
    ]

    clo_results = [
        r
        for r in results
        if r["clo_id"]
        == selected_clo["id"]
    ]

    st.write(
        f"**Selected outcome:** "
        f"{selected_clo['text']}"
    )

    if clo_results:

        clo_score = round(
            sum(
                r["clo_score"]
                for r in clo_results
            ) / len(clo_results),
            1
        )

        st.metric(
            "Alignment",
            f"{clo_score}%"
        )

        table = pd.DataFrame(
            [
                {
                    "Question":
                        f"Q{r['number']}",
                    "CLO Alignment":
                        r["clo_score"],
                    "Bloom":
                        r["bloom"],
                    "Overall":
                        r["overall"]
                }
                for r in clo_results
            ]
        )

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "No question was primarily matched to this CLO."
        )


    # ========================================================
    # ONE PLO AT A TIME
    # ========================================================

    if final_plos:

        st.header(
            "9. PLO Analysis — One PLO at a Time"
        )

        plo_labels = [
            f"{plo['id']} — {plo['text']}"
            for plo in final_plos
        ]

        selected_plo_index = st.selectbox(
            "Select one PLO",
            range(len(plo_labels)),
            format_func=lambda i: plo_labels[i]
        )

        selected_plo = final_plos[
            selected_plo_index
        ]

        plo_results = [
            r
            for r in results
            if r["plo_id"]
            == selected_plo["id"]
        ]

        st.write(
            f"**Selected outcome:** "
            f"{selected_plo['text']}"
        )

        if plo_results:

            plo_score = round(
                sum(
                    r["plo_score"]
                    for r in plo_results
                ) / len(plo_results),
                1
            )

            st.metric(
                "Alignment",
                f"{plo_score}%"
            )

            table = pd.DataFrame(
                [
                    {
                        "Question":
                            f"Q{r['number']}",
                        "PLO Alignment":
                            r["plo_score"],
                        "Bloom":
                            r["bloom"],
                        "Overall":
                            r["overall"]
                    }
                    for r in plo_results
                ]
            )

            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "No question was primarily matched to this PLO."
            )


    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.header(
        "10. Bloom's Taxonomy Analysis"
    )

    bloom_rows = []

    for level in BLOOM_LEVELS:

        matching = [
            r
            for r in results
            if r["bloom"] == level
        ]

        bloom_rows.append(
            {
                "Bloom Level":
                    level,
                "Questions":
                    len(matching),
                "Percentage":
                    round(
                        len(matching)
                        / len(results)
                        * 100,
                        1
                    )
            }
        )

    bloom_df = pd.DataFrame(
        bloom_rows
    )

    st.dataframe(
        bloom_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # QUESTION TABLE
    # ========================================================

    st.header(
        "11. Question-by-Question Evaluation"
    )

    rows = []

    for r in results:

        rows.append(
            {
                "Question":
                    f"Q{r['number']}",
                "CLO":
                    r["clo_id"],
                "CLO Alignment":
                    r["clo_score"],
                "PLO":
                    r["plo_id"],
                "PLO Alignment":
                    r["plo_score"]
                    if final_plos
                    else None,
                "Bloom":
                    r["bloom"],
                "Bloom Alignment":
                    r["bloom_score"],
                "Clarity":
                    r["clarity"],
                "Specificity":
                    r["specificity"],
                "Measurability":
                    r["measurability"],
                "MCQ Quality":
                    r["mcq_score"],
                "Overall":
                    r["overall"]
            }
        )

    result_df = pd.DataFrame(
        rows
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # DETAILED QUESTION REVIEW
    # ========================================================

    st.header(
        "12. Detailed Question Review"
    )

    question_labels = [
        (
            f"Q{r['number']}: "
            f"{textwrap.shorten("
                r['question'],
                width=100
            )}"
        )
        for r in results
    ]

    selected_question_index = st.selectbox(
        "Select one question",
        range(len(question_labels)),
        format_func=lambda i:
            question_labels[i]
    )

    selected = results[
        selected_question_index
    ]

    st.subheader(
        f"Question {selected['number']}"
    )

    st.write(
        selected["question"]
    )

    if selected["options"]:

        st.write(
            "**Detected options:**"
        )

        for option in selected["options"]:

            st.write(
                f"**{option['label']}.** "
                f"{option['text']}"
            )

    st.write(
        f"**Matched CLO:** "
        f"{selected['clo_id']}"
    )

    if selected["clo_text"]:

        st.write(
            f"**CLO:** "
            f"{selected['clo_text']}"
        )

    st.write(
        f"**CLO Alignment:** "
        f"{selected['clo_score']}%"
    )

    if final_plos:

        st.write(
            f"**Matched PLO:** "
            f"{selected['plo_id']}"
        )

        if selected["plo_text"]:

            st.write(
                f"**PLO:** "
                f"{selected['plo_text']}"
            )

        st.write(
            f"**PLO Alignment:** "
            f"{selected['plo_score']}%"
        )

    st.write(
        f"**Detected Bloom's Level:** "
        f"{selected['bloom']}"
    )

    st.write(
        f"**Bloom Alignment:** "
        f"{selected['bloom_score']}%"
    )

    q1, q2, q3, q4, q5 = st.columns(5)

    q1.metric(
        "Clarity",
        f"{selected['clarity']}%"
    )

    q2.metric(
        "Specificity",
        f"{selected['specificity']}%"
    )

    q3.metric(
        "Measurability",
        f"{selected['measurability']}%"
    )

    q4.metric(
        "MCQ Quality",
        f"{selected['mcq_score']}%"
    )

    q5.metric(
        "Overall",
        f"{selected['overall']}%"
    )

    st.subheader(
        "Feedback"
    )

    for feedback in selected["feedback"]:

        st.write(
            f"• {feedback}"
        )


    # ========================================================
    # THREE IMPROVED QUESTIONS
    # ========================================================

    needs_revision = (
        selected["overall"] < 80
        or selected["clo_score"] < 70
        or selected["bloom_score"] < 70
        or selected["clarity"] < 70
    )

    if needs_revision:

        st.header(
            "13. Three Improved Question Alternatives"
        )

        selected_outcome = (
            selected["clo_text"]
        )

        if not selected_outcome:

            selected_outcome = (
                final_clos[0]["text"]
            )

        suggestions = generate_suggestions(
            selected_outcome,
            intended_bloom
        )

        for number, suggestion in enumerate(
            suggestions,
            start=1
        ):

            st.subheader(
                f"Alternative {number}"
            )

            st.write(
                suggestion
            )

            reevaluated = (
                reevaluate_suggestion(
                    suggestion,
                    selected_outcome,
                    final_plos,
                    intended_bloom
                )
            )

            s1, s2, s3, s4, s5 = st.columns(5)

            s1.metric(
                "CLO Alignment",
                f"{reevaluated['CLO Alignment']}%"
            )

            s2.metric(
                "PLO Alignment",
                f"{reevaluated['PLO Alignment']}%"
                if final_plos
                else "N/A"
            )

            s3.metric(
                "Bloom",
                reevaluated[
                    "Detected Bloom"
                ]
            )

            s4.metric(
                "Bloom Alignment",
                f"{reevaluated['Bloom Alignment']}%"
            )

            s5.metric(
                "Overall",
                f"{reevaluated['Overall']}%"
            )

            if (
                reevaluated["Overall"] >= 80
                and reevaluated["CLO Alignment"] >= 70
                and reevaluated["Bloom Alignment"] >= 70
            ):

                st.success(
                    "This alternative satisfies the defined target thresholds."
                )

            else:

                st.warning(
                    "This alternative still requires human academic review."
                )


    # ========================================================
    # WEAK QUESTIONS
    # ========================================================

    st.header(
        "14. Questions Requiring Revision"
    )

    weak_questions = [
        r
        for r in results
        if (
            r["overall"] < 80
            or r["clo_score"] < 70
            or r["bloom_score"] < 70
            or r["clarity"] < 70
        )
    ]

    if weak_questions:

        weak_df = pd.DataFrame(
            [
                {
                    "Question":
                        f"Q{r['number']}",
                    "Overall":
                        r["overall"],
                    "CLO Alignment":
                        r["clo_score"],
                    "Bloom Alignment":
                        r["bloom_score"],
                    "Main Issue":
                        r["feedback"][0]
                        if r["feedback"]
                        else "Review required"
                }
                for r in weak_questions
            ]
        )

        st.dataframe(
            weak_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "No questions fell below the current revision thresholds."
        )


    # ========================================================
    # EXPORT
    # ========================================================

    st.header(
        "15. Export Evaluation"
    )

    export_df = pd.DataFrame(
        [
            {
                "Question":
                    r["number"],
                "Question Text":
                    r["question"],
                "CLO":
                    r["clo_id"],
                "CLO Alignment":
                    r["clo_score"],
                "PLO":
                    r["plo_id"],
                "PLO Alignment":
                    r["plo_score"],
                "Detected Bloom":
                    r["bloom"],
                "Bloom Alignment":
                    r["bloom_score"],
                "Clarity":
                    r["clarity"],
                "Specificity":
                    r["specificity"],
                "Measurability":
                    r["measurability"],
                "Relevance":
                    r["relevance"],
                "MCQ Quality":
                    r["mcq_score"],
                "Overall Quality":
                    r["overall"],
                "Feedback":
                    " | ".join(
                        r["feedback"]
                    )
            }
            for r in results
        ]
    )

    csv_data = (
        export_df
        .to_csv(index=False)
        .encode("utf-8")
    )

    st.download_button(
        "⬇️ Download Complete Evaluation",
        data=csv_data,
        file_name="obe_quiz_evaluation.csv",
        mime="text/csv",
        use_container_width=True
    )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.header(
        "16. Final Evaluation Summary"
    )

    f1, f2, f3, f4 = st.columns(4)

    f1.metric(
        "Questions Evaluated",
        len(results)
    )

    f2.metric(
        "CLO Alignment",
        f"{clo_avg}%"
    )

    f3.metric(
        "Bloom Alignment",
        f"{bloom_avg}%"
    )

    f4.metric(
        "Overall Quality",
        f"{overall}%"
    )

    if weak_questions:

        st.warning(
            f"{len(weak_questions)} question(s) "
            "require revision or human review."
        )

    else:

        st.success(
            "All questions meet the current automated review thresholds."
        )

    st.info(
        "Automated analysis is a screening aid. Final academic "
        "validation should consider the complete CLO wording, "
        "course content, assessment purpose, expected evidence, "
        "and discipline-specific requirements."
    )
