import io
import re
import pandas as pd
import streamlit as st

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

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
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Quality & Alignment Checker",
    page_icon="🎓",
    layout="wide"
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
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "recognise",
        "select",
        "match"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "summarise",
        "interpret",
        "classify",
        "discuss",
        "illustrate",
        "paraphrase"
    ],

    "Apply": [
        "apply",
        "use",
        "demonstrate",
        "solve",
        "calculate",
        "implement",
        "construct",
        "perform"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "examine",
        "distinguish",
        "investigate",
        "compare",
        "contrast",
        "organize",
        "organise",
        "break down"
    ],

    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "judge",
        "defend",
        "appraise",
        "recommend"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "formulate",
        "produce",
        "compose",
        "propose",
        "generate",
        "construct"
    ]
}


STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to",
    "in", "on", "for", "with", "by", "from",
    "at", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "into",
    "about", "which", "what", "how", "why",
    "when", "where", "who", "can", "could",
    "should", "would", "will", "may", "might",
    "do", "does", "did", "your", "their",
    "his", "her", "our", "you", "we",
    "they", "them", "than", "then",
    "through", "using", "used", "given",
    "following", "according", "also"
}


# ============================================================
# CONCEPT GROUPS
# ============================================================

CONCEPT_GROUPS = {

    "main idea": [
        "main idea",
        "central idea",
        "main point",
        "central point"
    ],

    "patterns of organization": [
        "pattern of organization",
        "organizational pattern",
        "organization",
        "organisation",
        "cause and effect",
        "compare and contrast",
        "comparison",
        "contrast",
        "chronological",
        "sequence",
        "problem solution",
        "problem-solution"
    ],

    "paraphrasing": [
        "paraphrase",
        "paraphrasing",
        "rewrite",
        "rewriting",
        "own words"
    ],

    "author purpose": [
        "author purpose",
        "author's purpose",
        "writer purpose",
        "writer's purpose"
    ],

    "author tone": [
        "author tone",
        "author's tone",
        "writer tone",
        "writer's tone"
    ],

    "writing": [
        "writing",
        "write",
        "essay",
        "paragraph",
        "composition"
    ],

    "reading comprehension": [
        "reading",
        "comprehension",
        "passage",
        "reading comprehension"
    ],

    "critical thinking": [
        "critical thinking",
        "reasoning",
        "evidence",
        "argument",
        "claim",
        "analysis"
    ],

    "communication": [
        "communication",
        "communicate",
        "speaking",
        "listening",
        "presentation"
    ],

    "grammar": [
        "grammar",
        "sentence",
        "verb",
        "noun",
        "tense",
        "syntax"
    ],

    "vocabulary": [
        "vocabulary",
        "word meaning",
        "synonym",
        "antonym"
    ],

    "research": [
        "research",
        "source",
        "citation",
        "reference"
    ],

    "problem solving": [
        "problem solving",
        "problem-solving",
        "problem",
        "solution",
        "solve"
    ]
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def tokenize(text):

    words = normalize_text(text).split()

    return {
        word
        for word in words
        if len(word) > 2
        and word not in STOP_WORDS
    }


# ============================================================
# CONCEPT DETECTION
# ============================================================

def detect_concept(text):

    normalized = normalize_text(text)

    best_concept = ""
    best_score = 0

    for concept, keywords in CONCEPT_GROUPS.items():

        score = 0

        for keyword in keywords:

            if normalize_text(keyword) in normalized:
                score += 1

        if score > best_score:

            best_score = score
            best_concept = concept

    return best_concept


def extract_topic(text):

    concept = detect_concept(text)

    if concept:
        return concept

    words = list(tokenize(text))

    if words:
        return " ".join(words[:6])

    return "the stated topic"


# ============================================================
# TEXT SIMILARITY
# ============================================================

def text_similarity(
    question,
    outcome
):

    q_words = tokenize(question)
    o_words = tokenize(outcome)

    if not q_words or not o_words:
        return 0

    overlap = len(
        q_words.intersection(o_words)
    )

    score = (
        overlap /
        max(1, len(o_words))
    )

    q_concept = detect_concept(question)
    o_concept = detect_concept(outcome)

    if (
        q_concept
        and o_concept
        and q_concept == o_concept
    ):

        score += 0.45

    return round(
        min(100, score * 100),
        1
    )


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    text = normalize_text(question)

    detected = []

    for level in BLOOM_LEVELS:

        for verb in BLOOM_VERBS[level]:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                text
            ):

                detected.append(level)

    if not detected:
        return "Needs Review"

    # Return highest detected cognitive demand
    return max(
        detected,
        key=lambda x: BLOOM_RANK[x]
    )


def bloom_alignment(
    intended,
    detected
):

    if detected == "Needs Review":
        return 40

    difference = abs(
        BLOOM_RANK[intended]
        -
        BLOOM_RANK[detected]
    )

    if difference == 0:
        return 100

    if difference == 1:
        return 70

    if difference == 2:
        return 50

    return 30


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_pdf_text(data):

    extracted = ""

    if PdfReader is not None:

        try:

            reader = PdfReader(
                io.BytesIO(data)
            )

            pages = []

            for page in reader.pages:

                try:

                    value = (
                        page.extract_text()
                        or ""
                    )

                    if value.strip():

                        pages.append(value)

                except Exception:
                    continue

            extracted = "\n".join(
                pages
            )

        except Exception:
            extracted = ""

    # OCR fallback
    if (
        len(extracted.strip()) < 50
        and pytesseract is not None
        and convert_from_bytes is not None
    ):

        try:

            images = convert_from_bytes(
                data,
                dpi=160
            )

            pages = []

            for image in images:

                try:

                    value = pytesseract.image_to_string(
                        image
                    )

                    if value.strip():
                        pages.append(value)

                except Exception:
                    continue

            if pages:
                extracted = "\n".join(pages)

        except Exception:
            pass

    return extracted


def extract_docx_text(data):

    if Document is None:
        return ""

    try:

        document = Document(
            io.BytesIO(data)
        )

        parts = []

        for paragraph in document.paragraphs:

            value = paragraph.text.strip()

            if value:
                parts.append(value)

        for table in document.tables:

            for row in table.rows:

                values = []

                for cell in row.cells:

                    value = cell.text.strip()

                    if value:
                        values.append(value)

                if values:
                    parts.append(
                        " ".join(values)
                    )

        return "\n".join(parts)

    except Exception:
        return ""


def extract_excel_text(data):

    try:

        excel = pd.ExcelFile(
            io.BytesIO(data)
        )

        parts = []

        for sheet in excel.sheet_names:

            df = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            for row in (
                df
                .fillna("")
                .astype(str)
                .values
            ):

                line = " ".join(
                    str(value).strip()
                    for value in row
                    if str(value).strip()
                )

                if line:
                    parts.append(line)

        return "\n".join(parts)

    except Exception:
        return ""


@st.cache_data(
    show_spinner=False
)
def extract_uploaded_file(
    file_bytes,
    file_name
):

    name = file_name.lower()

    if name.endswith(".txt"):

        return file_bytes.decode(
            "utf-8",
            errors="ignore"
        )

    if name.endswith(".pdf"):

        return extract_pdf_text(
            file_bytes
        )

    if name.endswith(".docx"):

        return extract_docx_text(
            file_bytes
        )

    if (
        name.endswith(".xlsx")
        or name.endswith(".xls")
    ):

        return extract_excel_text(
            file_bytes
        )

    return ""


# ============================================================
# QUESTION PARSING
# ============================================================

def clean_question_text(text):

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    text = re.sub(
        r"^(?:question|ques|q)?\s*\d+\s*[\.\:\)\-]\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


def extract_options(text):

    options = []

    pattern = re.compile(
        r"(?:^|\s)"
        r"\(?([A-Da-d])\)?"
        r"[\.\:\)]"
        r"\s+"
        r"(.+?)"
        r"(?=\s+\(?[A-Da-d]\)?[\.\:\)]\s+|$)",
        flags=re.DOTALL
    )

    matches = pattern.findall(text)

    for letter, value in matches:

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        if value:

            options.append(
                f"{letter.upper()}. {value}"
            )

    return options


def extract_questions(text):

    if not text:
        return []

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    if not lines:
        return []

    # --------------------------------------------------------
    # NUMBERED QUESTIONS
    # --------------------------------------------------------

    question_pattern = re.compile(
        r"""
        ^
        \s*
        (?:
            question\s*\d+
            |
            ques\s*\d+
            |
            q\s*\d+
            |
            \d+
        )
        \s*
        [\.\:\)\-]
        \s*
        (.*)
        $
        """,
        flags=re.IGNORECASE | re.VERBOSE
    )

    blocks = []

    current_number = None
    current_lines = []

    for line in lines:

        match = question_pattern.match(
            line
        )

        if match:

            if current_lines:

                blocks.append(
                    (
                        current_number,
                        " ".join(
                            current_lines
                        )
                    )
                )

            number_match = re.search(
                r"\d+",
                line
            )

            current_number = (
                int(number_match.group())
                if number_match
                else len(blocks) + 1
            )

            current_lines = []

            content = (
                match.group(1)
                .strip()
            )

            if content:
                current_lines.append(
                    content
                )

        else:

            if current_number is not None:

                # Preserve options for MCQs
                current_lines.append(
                    line
                )

    if current_lines:

        blocks.append(
            (
                current_number,
                " ".join(
                    current_lines
                )
            )
        )

    results = []

    for number, content in blocks:

        content = clean_question_text(
            content
        )

        options = extract_options(
            content
        )

        # Remove options from question text
        question_only = re.split(
            r"\s+\(?[A-Da-d]\)?[\.\:\)]\s+",
            content,
            maxsplit=1
        )[0]

        question_only = re.sub(
            r"\s+",
            " ",
            question_only
        ).strip()

        if len(question_only.split()) >= 3:

            results.append(
                {
                    "number": number,
                    "text": question_only,
                    "options": options
                }
            )

    if results:
        return results

    # --------------------------------------------------------
    # QUESTION MARK QUESTIONS
    # --------------------------------------------------------

    joined = " ".join(lines)

    sentences = re.findall(
        r"[^?]{8,}\?",
        joined
    )

    results = []

    for sentence in sentences:

        sentence = clean_question_text(
            sentence
        )

        if len(sentence.split()) >= 3:

            results.append(
                {
                    "number": len(results) + 1,
                    "text": sentence,
                    "options": []
                }
            )

    if results:
        return results

    # --------------------------------------------------------
    # COMMAND QUESTIONS
    # --------------------------------------------------------

    starters = (
        "identify ",
        "define ",
        "state ",
        "list ",
        "name ",
        "explain ",
        "describe ",
        "summarize ",
        "summarise ",
        "discuss ",
        "analyze ",
        "analyse ",
        "compare ",
        "contrast ",
        "differentiate ",
        "distinguish ",
        "evaluate ",
        "assess ",
        "justify ",
        "examine ",
        "interpret ",
        "apply ",
        "calculate ",
        "determine ",
        "solve ",
        "demonstrate ",
        "illustrate ",
        "classify ",
        "select ",
        "choose ",
        "write ",
        "rewrite ",
        "paraphrase ",
        "develop ",
        "design ",
        "create ",
        "formulate ",
        "construct "
    )

    results = []

    for line in lines:

        lower = line.lower()

        if (
            len(line.split()) >= 4
            and lower.startswith(starters)
        ):

            results.append(
                {
                    "number": len(results) + 1,
                    "text": line,
                    "options": []
                }
            )

    return results


# ============================================================
# CLO/PLO PARSER
# ============================================================

def parse_outcomes(
    text,
    prefix
):

    outcomes = {}

    if not text:
        return outcomes

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    lines = text.split("\n")

    pattern = re.compile(
        rf"^\s*"
        rf"{prefix}"
        rf"\s*[-_]?\s*"
        rf"(\d+)"
        rf"\s*"
        rf"(?:[\:\-\)\.]|\s)"
        rf"\s*"
        rf"(.+?)"
        rf"\s*$",
        flags=re.IGNORECASE
    )

    for line in lines:

        line = line.strip()

        if not line:
            continue

        match = pattern.match(
            line
        )

        if match:

            number = match.group(1)

            description = (
                match.group(2)
                .strip()
            )

            if description:

                code = (
                    f"{prefix.upper()}{number}"
                )

                outcomes[code] = description

    # Inline fallback
    if not outcomes:

        inline_pattern = re.compile(
            rf"{prefix}"
            rf"\s*[-_]?\s*(\d+)"
            rf"\s*[\:\-\)\.]"
            rf"\s*"
            rf"(.*?)(?="
            rf"{prefix}"
            rf"\s*[-_]?\s*\d+"
            rf"\s*[\:\-\)\.]"
            rf"|$)",
            flags=re.IGNORECASE | re.DOTALL
        )

        matches = inline_pattern.findall(
            text
        )

        for number, description in matches:

            description = re.sub(
                r"\s+",
                " ",
                description
            ).strip()

            if description:

                code = (
                    f"{prefix.upper()}{number}"
                )

                outcomes[code] = description

    return outcomes


# ============================================================
# MCQ QUALITY
# ============================================================

def evaluate_mcq_options(
    question,
    options
):

    if not options:
        return {
            "score": 70,
            "feedback": "No multiple-choice options were detected."
        }

    score = 100
    feedback = []

    if len(options) < 4:

        score -= 20

        feedback.append(
            "Fewer than four answer options were detected."
        )

    if len(options) > 5:

        score -= 5

        feedback.append(
            "More than five answer options may increase unnecessary complexity."
        )

    normalized = [
        normalize_text(option)
        for option in options
    ]

    duplicates = (
        len(normalized)
        != len(set(normalized))
    )

    if duplicates:

        score -= 30

        feedback.append(
            "Duplicate or highly similar answer choices were detected."
        )

    lengths = [
        len(option.split())
        for option in options
    ]

    if lengths:

        maximum = max(lengths)
        minimum = min(lengths)

        if (
            maximum >= 3 * max(1, minimum)
        ):

            score -= 10

            feedback.append(
                "The answer choices differ considerably in length."
            )

    if not feedback:

        feedback.append(
            "The detected answer choices have a reasonable basic structure."
        )

    return {
        "score": max(0, score),
        "feedback": " ".join(feedback)
    }


# ============================================================
# QUESTION QUALITY
# ============================================================

def evaluate_clarity(question):

    words = question.split()

    score = 100
    issues = []

    if len(words) < 5:

        score -= 20

        issues.append(
            "The question may be too brief to provide sufficient context."
        )

    if len(words) > 60:

        score -= 15

        issues.append(
            "The question is relatively long and may benefit from more concise wording."
        )

    repeated = re.search(
        r"\b(\w+)\s+\1\b",
        question.lower()
    )

    if repeated:

        score -= 15

        issues.append(
            "Repeated wording was detected."
        )

    if (
        "??" in question
        or "!!" in question
    ):

        score -= 5

        issues.append(
            "Punctuation should be reviewed."
        )

    if not issues:

        issues.append(
            "The wording is generally clear and readable."
        )

    return max(0, score), " ".join(issues)


def evaluate_specificity(question):

    vague_terms = [
        "discuss",
        "talk about",
        "say something about",
        "write about",
        "what do you think",
        "in your opinion"
    ]

    normalized = question.lower()

    found = [
        term
        for term in vague_terms
        if term in normalized
    ]

    score = 100

    if found:

        score -= 20

        feedback = (
            "The task may be broad because it uses "
            "less specific wording such as "
            + ", ".join(found)
            + "."
        )

    else:

        feedback = (
            "The task has a reasonably specific action."
        )

    return score, feedback


def evaluate_measurability(question):

    measurable_verbs = []

    normalized = question.lower()

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                normalized
            ):

                measurable_verbs.append(
                    verb
                )

    if measurable_verbs:

        return (
            100,
            "The question contains a recognizable, assessable action."
        )

    return (
        65,
        "The intended student action is not sufficiently explicit."
    )


def evaluate_relevance(
    question,
    clo_text
):

    similarity = text_similarity(
        question,
        clo_text
    )

    if similarity >= 70:
        feedback = (
            "The question is strongly connected to the stated learning outcome."
        )

    elif similarity >= 45:
        feedback = (
            "The question has a moderate connection to the stated learning outcome."
        )

    else:
        feedback = (
            "The question has a weak direct connection to the stated learning outcome."
        )

    return similarity, feedback


# ============================================================
# COMPLETE QUESTION EVALUATION
# ============================================================

def evaluate_question_quality(
    question,
    clos,
    plos,
    intended_bloom
):

    text = question["text"]

    # --------------------------------------------------------
    # CLO
    # --------------------------------------------------------

    best_clo = ""
    best_clo_score = 0

    for code, description in clos.items():

        score = text_similarity(
            text,
            description
        )

        if score > best_clo_score:

            best_clo_score = score
            best_clo = code

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------

    best_plo = ""
    best_plo_score = 0

    for code, description in plos.items():

        score = text_similarity(
            text,
            description
        )

        if score > best_plo_score:

            best_plo_score = score
            best_plo = code

    # --------------------------------------------------------
    # BLOOM
    # --------------------------------------------------------

    detected_bloom = detect_bloom(
        text
    )

    bloom_score = bloom_alignment(
        intended_bloom,
        detected_bloom
    )

    # --------------------------------------------------------
    # QUALITY DIMENSIONS
    # --------------------------------------------------------

    clarity_score, clarity_feedback = (
        evaluate_clarity(text)
    )

    specificity_score, specificity_feedback = (
        evaluate_specificity(text)
    )

    measurable_score, measurable_feedback = (
        evaluate_measurability(text)
    )

    relevance_score, relevance_feedback = (
        evaluate_relevance(
            text,
            clos.get(best_clo, "")
        )
    )

    mcq_result = evaluate_mcq_options(
        question,
        question.get("options", [])
    )

    # --------------------------------------------------------
    # COGNITIVE DEMAND
    # --------------------------------------------------------

    cognitive_score = bloom_score

    # --------------------------------------------------------
    # OVERALL QUALITY
    # --------------------------------------------------------

    overall = (
        best_clo_score * 0.20
        +
        best_plo_score * 0.15
        +
        bloom_score * 0.20
        +
        clarity_score * 0.10
        +
        specificity_score * 0.10
        +
        measurable_score * 0.10
        +
        relevance_score * 0.05
        +
        mcq_result["score"] * 0.10
    )

    overall = round(
        min(100, overall),
        1
    )

    return {
        "Question No.": question["number"],
        "Question": text,
        "Options": question.get(
            "options",
            []
        ),
        "Best CLO": best_clo,
        "CLO Alignment %": round(
            best_clo_score,
            1
        ),
        "Best PLO": best_plo,
        "PLO Alignment %": round(
            best_plo_score,
            1
        ),
        "Intended Bloom": intended_bloom,
        "Detected Bloom": detected_bloom,
        "Bloom Alignment %": round(
            bloom_score,
            1
        ),
        "Clarity %": clarity_score,
        "Specificity %": specificity_score,
        "Measurability %": measurable_score,
        "Relevance %": relevance_score,
        "MCQ Quality %": mcq_result["score"],
        "Overall Quality %": overall,
        "Clarity Feedback": clarity_feedback,
        "Specificity Feedback": specificity_feedback,
        "Measurability Feedback": measurable_feedback,
        "Relevance Feedback": relevance_feedback,
        "MCQ Feedback": mcq_result["feedback"]
    }


# ============================================================
# SUGGESTION GENERATOR
# ============================================================

def generate_suggestions(
    clo_text,
    bloom
):

    concept = detect_concept(
        clo_text
    )

    topic = extract_topic(
        clo_text
    )

    # --------------------------------------------------------
    # PATTERNS OF ORGANIZATION
    # --------------------------------------------------------

    if concept == "patterns of organization":

        if bloom == "Remember":

            return [
                "Identify the pattern of organization used in the given paragraph.",
                "Name the organizational pattern used to arrange the ideas in the paragraph.",
                "Recognize the pattern used to structure the information in the given paragraph."
            ]

        if bloom == "Understand":

            return [
                "Explain how the organizational pattern helps the reader understand the ideas in the paragraph.",
                "Describe the organizational pattern used in the paragraph and explain its role in presenting the information.",
                "Explain how the arrangement of ideas contributes to the clarity and meaning of the paragraph."
            ]

        if bloom == "Apply":

            return [
                "Apply your knowledge of organizational patterns to identify the structure used in the given paragraph.",
                "Use the characteristics of organizational patterns to classify the structure of the given paragraph.",
                "Examine the given paragraph and determine which organizational pattern best describes the arrangement of its ideas."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the given paragraph by identifying its pattern of organization and examining how the arrangement of ideas supports the writer's purpose.",
                "Examine the relationship among the ideas in the paragraph, identify the organizational pattern, and justify your response with evidence from the text.",
                "Analyze how the writer organizes the ideas in the paragraph and explain how this structure contributes to the development of the central message."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate whether the organizational pattern effectively supports the writer's purpose and justify your response with evidence.",
                "Assess the effectiveness of the paragraph's organization and explain how the arrangement of ideas affects clarity and meaning.",
                "Evaluate the writer's choice of organizational pattern and defend your judgment using specific evidence from the paragraph."
            ]

        return [
            "Design an alternative organizational structure for the paragraph that would communicate the ideas more effectively and explain your choice.",
            "Develop a revised organization for the paragraph and explain how the new structure improves clarity and coherence.",
            "Create an alternative arrangement of the ideas and justify how it would improve the effectiveness of the paragraph."
        ]

    # --------------------------------------------------------
    # MAIN IDEA
    # --------------------------------------------------------

    if concept == "main idea":

        if bloom == "Remember":

            return [
                "Identify the main idea of the given paragraph.",
                "State the central idea presented in the paragraph.",
                "Select the statement that best expresses the main idea of the paragraph."
            ]

        if bloom == "Understand":

            return [
                "Explain the main idea of the given paragraph in your own words.",
                "Describe the central idea communicated by the paragraph.",
                "Summarize the main point of the paragraph in a clear statement."
            ]

        if bloom == "Apply":

            return [
                "Use the supporting details in the paragraph to determine its central idea.",
                "Apply an appropriate reading strategy to identify the statement that best expresses the paragraph's main idea.",
                "Use the information provided in the paragraph to identify its central idea."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the supporting details in the paragraph and explain how they contribute to its main idea.",
                "Examine the relationship among the paragraph's details and identify the central idea they collectively support.",
                "Analyze the paragraph and explain how its key details establish the main idea."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate which statement most accurately represents the main idea and justify your choice using supporting details.",
                "Assess whether the proposed main idea is fully supported by the information presented in the paragraph.",
                "Evaluate the relationship between the central idea and supporting details and justify your conclusion."
            ]

        return [
            "Develop a concise statement that clearly communicates the central idea of the paragraph.",
            "Create a central statement that integrates the key information presented in the paragraph.",
            "Formulate a clear main-idea statement that accurately represents the most important information."
        ]

    # --------------------------------------------------------
    # PARAPHRASING
    # --------------------------------------------------------

    if concept == "paraphrasing":

        if bloom == "Remember":

            return [
                "Identify the essential meaning that should be preserved when rewriting the passage.",
                "Recognize the key idea that must remain unchanged in an accurate paraphrase.",
                "Identify the central meaning of the passage before rewriting it."
            ]

        if bloom == "Understand":

            return [
                "Explain the meaning of the given passage in your own words.",
                "Describe the central message of the passage without changing its original meaning.",
                "Summarize the meaning of the passage using clear and original wording."
            ]

        if bloom == "Apply":

            return [
                "Rewrite the given passage in your own words while preserving its original meaning.",
                "Paraphrase the following passage using your own wording and sentence structure without changing its meaning.",
                "Read the passage and produce an accurate paraphrase that retains the central meaning while using substantially different wording."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the original passage and explain how its central meaning can be retained while its wording and sentence structure are changed.",
                "Examine the passage and distinguish the essential meaning from the wording that can be changed in an effective paraphrase.",
                "Analyze the passage and produce a paraphrase that preserves its key ideas while demonstrating substantial changes in wording and structure."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate the accuracy of the given paraphrase by comparing it with the original passage and identifying any changes in meaning.",
                "Assess whether the paraphrase preserves the essential meaning of the original passage and justify your evaluation.",
                "Evaluate the effectiveness of the paraphrase in retaining the original message while using sufficiently different wording."
            ]

        return [
            "Create an accurate paraphrase of the passage using original wording and sentence structure while preserving its meaning.",
            "Develop a clear paraphrase that communicates the original ideas without copying the original wording.",
            "Produce a well-constructed paraphrase that retains the essential meaning while substantially changing the language and structure."
        ]

    # --------------------------------------------------------
    # AUTHOR PURPOSE
    # --------------------------------------------------------

    if concept == "author purpose":

        if bloom == "Remember":

            return [
                "Identify the author's primary purpose in writing the passage.",
                "State the main purpose the writer intends to achieve through the passage.",
                "Recognize the purpose that best describes the author's intention."
            ]

        if bloom == "Understand":

            return [
                "Explain the author's purpose in writing the passage.",
                "Describe the writer's main intention and explain how the passage communicates it.",
                "Summarize the author's purpose using evidence from the passage."
            ]

        if bloom == "Apply":

            return [
                "Use evidence from the passage to determine the author's primary purpose.",
                "Apply appropriate reading strategies to identify the writer's purpose.",
                "Use the information in the passage to classify the author's purpose."
            ]

        if bloom == "Analyze":

            return [
                "Analyze the author's purpose by examining the ideas, language, and supporting details used in the passage.",
                "Examine how the writer's choice of information and language reveals the purpose of the passage.",
                "Analyze the relationship between the author's purpose and the evidence used to communicate that purpose."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate whether the author's choice of language and evidence effectively supports the intended purpose.",
                "Assess how effectively the passage achieves the author's purpose and justify your response with textual evidence.",
                "Evaluate the strength of the evidence used to communicate the author's purpose."
            ]

        return [
            "Develop an alternative approach that could communicate the author's purpose more effectively.",
            "Create a revised version of the passage that strengthens its intended purpose while maintaining its central message.",
            "Design an alternative presentation of the ideas that would communicate the intended purpose more effectively."
        ]

    # --------------------------------------------------------
    # AUTHOR TONE
    # --------------------------------------------------------

    if concept == "author tone":

        if bloom == "Remember":

            return [
                "Identify the tone conveyed by the author in the passage.",
                "State the tone that best describes the author's attitude.",
                "Recognize the tone expressed through the writer's language."
            ]

        if bloom == "Understand":

            return [
                "Explain the author's tone and describe the language that creates it.",
                "Describe the attitude conveyed by the writer in the passage.",
                "Explain how the writer's choice of words communicates a particular tone."
            ]

        if bloom == "Apply":

            return [
                "Use evidence from the passage to determine the author's tone.",
                "Apply appropriate reading strategies to identify the tone conveyed by the writer.",
                "Use the writer's language choices to classify the tone of the passage."
            ]

        if bloom == "Analyze":

            return [
                "Analyze how specific words and expressions contribute to the author's tone.",
                "Examine the writer's language choices and analyze how they communicate the author's attitude.",
                "Analyze the relationship between the author's word choice and the tone developed throughout the passage."
            ]

        if bloom == "Evaluate":

            return [
                "Evaluate whether the author's choice of language effectively establishes the intended tone and justify your response.",
                "Assess how effectively the writer's language communicates the intended attitude.",
                "Evaluate the evidence for the tone identified in the passage and justify your conclusion."
            ]

        return [
            "Create a revised passage that communicates the same central idea using a different tone.",
            "Develop an alternative version of the passage that deliberately establishes a different tone while preserving its main message.",
            "Design a revised presentation of the ideas that creates a clearly different tone."
        ]

    # --------------------------------------------------------
    # GENERIC
    # --------------------------------------------------------

    if bloom == "Remember":

        return [
            f"Identify the key concept associated with {topic}.",
            f"Define the central concept related to {topic}.",
            f"State the essential feature of {topic}."
        ]

    if bloom == "Understand":

        return [
            f"Explain the central concept related to {topic} in your own words.",
            f"Describe the key features of {topic} and explain their significance.",
            f"Summarize the main concept involved in {topic}."
        ]

    if bloom == "Apply":

        return [
            f"Apply the relevant principles of {topic} to the given situation.",
            f"Use your understanding of {topic} to solve the given problem.",
            f"Demonstrate how the principles of {topic} can be applied in the given context."
        ]

    if bloom == "Analyze":

        return [
            f"Analyze the given situation and explain how the principles of {topic} are reflected in it.",
            f"Examine the components of the given situation and analyze their relationship to {topic}.",
            f"Analyze the available information and determine how it demonstrates the key principles of {topic}."
        ]

    if bloom == "Evaluate":

        return [
            f"Evaluate the effectiveness of the approach used in the given situation and justify your response using evidence related to {topic}.",
            f"Assess the given situation using relevant principles of {topic} and justify your conclusion.",
            f"Evaluate the available evidence and defend your judgment using appropriate principles related to {topic}."
        ]

    return [
        f"Design a solution that applies the key principles of {topic} to the given situation.",
        f"Develop an approach that effectively addresses the given situation using principles of {topic}.",
        f"Create a practical solution that demonstrates effective application of {topic}."
    ]


# ============================================================
# SUGGESTION RE-EVALUATION
# ============================================================

def evaluate_suggested_question(
    suggestion,
    clo_text,
    plo_text,
    intended_bloom
):

    clo_score = text_similarity(
        suggestion,
        clo_text
    )

    plo_score = text_similarity(
        suggestion,
        plo_text
    )

    detected = detect_bloom(
        suggestion
    )

    bloom_score = bloom_alignment(
        intended_bloom,
        detected
    )

    clarity, _ = evaluate_clarity(
        suggestion
    )

    specificity, _ = evaluate_specificity(
        suggestion
    )

    measurability, _ = evaluate_measurability(
        suggestion
    )

    total = (
        clo_score * 0.30
        +
        plo_score * 0.20
        +
        bloom_score * 0.30
        +
        clarity * 0.08
        +
        specificity * 0.06
        +
        measurability * 0.06
    )

    return {
        "CLO": round(clo_score, 1),
        "PLO": round(plo_score, 1),
        "Bloom": round(bloom_score, 1),
        "Clarity": round(clarity, 1),
        "Specificity": round(specificity, 1),
        "Measurability": round(measurability, 1),
        "Target Alignment": round(
            min(100, total),
            1
        ),
        "Detected Bloom": detected
    }


# ============================================================
# QUALITY LABEL
# ============================================================

def quality_label(score):

    if score >= 90:
        return "Strongly aligned"

    if score >= 80:
        return "Well aligned"

    if score >= 70:
        return "Acceptable with minor revision"

    if score >= 60:
        return "Needs revision"

    return "Requires substantial revision"


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = None

if "questions" not in st.session_state:
    st.session_state.questions = []

if "clos" not in st.session_state:
    st.session_state.clos = {}

if "plos" not in st.session_state:
    st.session_state.plos = {}

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎓 OBE Quiz Quality & Alignment Checker"
)

st.write(
    "Evaluate quiz questions for learning-outcome alignment, "
    "Bloom's cognitive level, clarity, specificity, "
    "measurability, relevance, and overall assessment quality."
)


# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.header(
    "1. Assessment Information"
)

c1, c2 = st.columns(2)

with c1:

    course_name = st.text_input(
        "Course Name",
        placeholder="English I"
    )

with c2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="Quiz 1"
    )


# ============================================================
# CLO INPUT
# ============================================================

st.header(
    "2. Course Learning Outcomes"
)

clo_input = st.text_area(
    "Enter CLOs",
    height=160,
    placeholder=(
        "CLO1: Identify the main idea of a paragraph.\n"
        "CLO2: Analyze patterns of organization.\n"
        "CLO3: Apply paraphrasing techniques."
    )
)


# ============================================================
# PLO INPUT
# ============================================================

st.header(
    "3. Program Learning Outcomes"
)

plo_input = st.text_area(
    "Enter PLOs",
    height=160,
    placeholder=(
        "PLO1: Demonstrate effective communication skills.\n"
        "PLO2: Apply critical thinking skills.\n"
        "PLO3: Demonstrate problem-solving abilities."
    )
)


# ============================================================
# BLOOM INPUT
# ============================================================

st.header(
    "4. Intended Bloom's Level"
)

intended_bloom = st.selectbox(
    "Select the intended cognitive level for this quiz",
    BLOOM_LEVELS,
    index=2
)


# ============================================================
# UPLOAD
# ============================================================

st.header(
    "5. Upload Complete Quiz"
)

uploaded_file = st.file_uploader(
    "Upload the complete quiz",
    type=[
        "pdf",
        "docx",
        "txt",
        "xlsx",
        "xls"
    ]
)


# ============================================================
# ANALYZE BUTTON
# ============================================================

if st.button(
    "🔍 Perform Complete Quiz Evaluation",
    type="primary",
    use_container_width=True
):

    if not course_name.strip():

        st.warning(
            "Please enter the course name."
        )

        st.stop()

    if not assessment_name.strip():

        st.warning(
            "Please enter the assessment name."
        )

        st.stop()

    clos = parse_outcomes(
        clo_input,
        "CLO"
    )

    if not clos:

        st.error(
            "No CLOs could be detected. "
            "Use a format such as "
            "CLO1: Identify the main idea."
        )

        st.stop()

    plos = parse_outcomes(
        plo_input,
        "PLO"
    )

    if not plos:

        st.error(
            "No PLOs could be detected. "
            "Use a format such as "
            "PLO1: Communication Skills."
        )

        st.stop()

    if uploaded_file is None:

        st.warning(
            "Please upload your complete quiz."
        )

        st.stop()

    file_bytes = uploaded_file.getvalue()

    with st.spinner(
        "Reading your quiz..."
    ):

        quiz_text = extract_uploaded_file(
            file_bytes,
            uploaded_file.name
        )

    if not quiz_text.strip():

        st.error(
            "The file was uploaded, but no readable "
            "text could be extracted."
        )

        with st.expander(
            "Troubleshooting"
        ):

            st.write(
                "For a scanned PDF, OCR support may be required. "
                "If extraction fails, save the quiz as DOCX or TXT "
                "and upload that version."
            )

        st.stop()

    questions = extract_questions(
        quiz_text
    )

    if not questions:

        st.error(
            "No questions could be detected."
        )

        with st.expander(
            "🔎 View extracted text"
        ):

            st.text(
                quiz_text[:30000]
            )

        st.stop()

    with st.spinner(
        "Evaluating question quality and OBE alignment..."
    ):

        results = []

        for question in questions:

            result = evaluate_question_quality(
                question,
                clos,
                plos,
                intended_bloom
            )

            results.append(result)

    st.session_state.results = results
    st.session_state.questions = questions
    st.session_state.clos = clos
    st.session_state.plos = plos
    st.session_state.analysis_done = True

    st.success(
        f"{len(results)} question(s) evaluated successfully."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis_done:

    results = st.session_state.results
    questions = st.session_state.questions
    clos = st.session_state.clos
    plos = st.session_state.plos

    st.divider()

    st.header(
        "📊 Overall Quiz Evaluation"
    )

    # ========================================================
    # OVERALL SCORES
    # ========================================================

    overall = round(
        sum(
            r["Overall Quality %"]
            for r in results
        )
        /
        len(results),
        1
    )

    clo_avg = round(
        sum(
            r["CLO Alignment %"]
            for r in results
        )
        /
        len(results),
        1
    )

    plo_avg = round(
        sum(
            r["PLO Alignment %"]
            for r in results
        )
        /
        len(results),
        1
    )

    bloom_avg = round(
        sum(
            r["Bloom Alignment %"]
            for r in results
        )
        /
        len(results),
        1
    )

    clarity_avg = round(
        sum(
            r["Clarity %"]
            for r in results
        )
        /
        len(results),
        1
    )

    specificity_avg = round(
        sum(
            r["Specificity %"]
            for r in results
        )
        /
        len(results),
        1
    )

    measurability_avg = round(
        sum(
            r["Measurability %"]
            for r in results
        )
        /
        len(results),
        1
    )

    mcq_avg = round(
        sum(
            r["MCQ Quality %"]
            for r in results
        )
        /
        len(results),
        1
    )

    # ========================================================
    # TOP GRAPH
    # ========================================================

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

    st.subheader(
        "📈 Quiz Quality and OBE Alignment"
    )

    st.bar_chart(
        graph_df.set_index(
            "Evaluation Area"
        )["Score"],
        use_container_width=True
    )

    # ========================================================
    # SCORE CARDS
    # ========================================================

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Overall Quality",
            f"{overall}%"
        )

    with c2:
        st.metric(
            "CLO Alignment",
            f"{clo_avg}%"
        )

    with c3:
        st.metric(
            "PLO Alignment",
            f"{plo_avg}%"
        )

    with c4:
        st.metric(
            "Bloom Alignment",
            f"{bloom_avg}%"
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Clarity",
            f"{clarity_avg}%"
        )

    with c2:
        st.metric(
            "Specificity",
            f"{specificity_avg}%"
        )

    with c3:
        st.metric(
            "Measurability",
            f"{measurability_avg}%"
        )

    with c4:
        st.metric(
            "MCQ Quality",
            f"{mcq_avg}%"
        )

    st.info(
        "These percentages evaluate the quality and alignment "
        "of the assessment questions. They are not student "
        "attainment percentages. Student attainment requires "
        "student marks."
    )

    # ========================================================
    # CLO ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "🎯 CLO Analysis"
    )

    selected_clo = st.selectbox(
        "Select ONE CLO",
        list(clos.keys()),
        format_func=lambda x:
            f"{x}: {clos[x]}",
        key="selected_clo"
    )

    clo_questions = [
        r
        for r in results
        if r["Best CLO"] == selected_clo
    ]

    if clo_questions:

        clo_score = round(
            sum(
                r["CLO Alignment %"]
                for r in clo_questions
            )
            /
            len(clo_questions),
            1
        )

    else:

        clo_score = 0

    st.metric(
        f"{selected_clo} Alignment",
        f"{clo_score}%"
    )

    st.write(
        f"**Learning Outcome:** {clos[selected_clo]}"
    )

    if clo_questions:

        for r in clo_questions:

            st.write(
                f"**Q{r['Question No.']}** — "
                f"{r['Question']}"
            )

            st.caption(
                f"CLO Alignment: "
                f"{r['CLO Alignment %']}%"
            )

    else:

        st.warning(
            "No question is strongly associated with this CLO."
        )

        st.write(
            "### Suggested assessment questions"
        )

        suggestions = generate_suggestions(
            clos[selected_clo],
            intended_bloom
        )

        for i, suggestion in enumerate(
            suggestions,
            1
        ):

            st.info(
                f"**Suggested Question {i}**\n\n"
                f"{suggestion}"
            )

    # ========================================================
    # PLO ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "🎯 PLO Analysis"
    )

    selected_plo = st.selectbox(
        "Select ONE PLO",
        list(plos.keys()),
        format_func=lambda x:
            f"{x}: {plos[x]}",
        key="selected_plo"
    )

    plo_questions = [
        r
        for r in results
        if r["Best PLO"] == selected_plo
    ]

    if plo_questions:

        plo_score = round(
            sum(
                r["PLO Alignment %"]
                for r in plo_questions
            )
            /
            len(plo_questions),
            1
        )

    else:

        plo_score = 0

    st.metric(
        f"{selected_plo} Alignment",
        f"{plo_score}%"
    )

    st.write(
        f"**Program Outcome:** {plos[selected_plo]}"
    )

    if plo_questions:

        for r in plo_questions:

            st.write(
                f"**Q{r['Question No.']}** — "
                f"{r['Question']}"
            )

    else:

        st.warning(
            "No question is strongly associated with this PLO."
        )

    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "🧠 Bloom's Taxonomy Analysis"
    )

    bloom_rows = []

    for level in BLOOM_LEVELS:

        selected = [
            r
            for r in results
            if r["Detected Bloom"] == level
        ]

        bloom_rows.append(
            {
                "Bloom Level": level,
                "Questions": len(selected),
                "Alignment %": round(
                    sum(
                        r["Bloom Alignment %"]
                        for r in selected
                    )
                    /
                    max(
                        1,
                        len(selected)
                    ),
                    1
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
    # QUESTION-BY-QUESTION
    # ========================================================

    st.divider()

    st.header(
        "📝 Question-by-Question Quality Evaluation"
    )

    display_columns = [
        "Question No.",
        "Question",
        "Best CLO",
        "CLO Alignment %",
        "Best PLO",
        "PLO Alignment %",
        "Intended Bloom",
        "Detected Bloom",
        "Bloom Alignment %",
        "Clarity %",
        "Specificity %",
        "Measurability %",
        "Relevance %",
        "MCQ Quality %",
        "Overall Quality %"
    ]

    display_df = pd.DataFrame(
        results
    )[display_columns]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # DETAILED QUESTION REVIEW
    # ========================================================

    st.divider()

    st.header(
        "🔎 Detailed Question Review"
    )

    selected_index = st.selectbox(
        "Choose a question",
        range(len(results)),
        format_func=lambda i:
            (
                f"Q{results[i]['Question No.']}: "
                f"{results[i]['Question'][:100]}"
            ),
        key="selected_question"
    )

    result = results[
        selected_index
    ]

    st.subheader(
        f"Question {result['Question No.']}"
    )

    st.write(
        result["Question"]
    )

    if result["Options"]:

        st.write(
            "**Detected answer choices:**"
        )

        for option in result["Options"]:

            st.write(
                f"- {option}"
            )

    # --------------------------------------------------------
    # INDIVIDUAL SCORE CARDS
    # --------------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "CLO",
            f"{result['CLO Alignment %']}%"
        )

    with c2:

        st.metric(
            "PLO",
            f"{result['PLO Alignment %']}%"
        )

    with c3:

        st.metric(
            "Bloom",
            f"{result['Bloom Alignment %']}%"
        )

    with c4:

        st.metric(
            "Overall",
            f"{result['Overall Quality %']}%"
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Clarity",
            f"{result['Clarity %']}%"
        )

    with c2:

        st.metric(
            "Specificity",
            f"{result['Specificity %']}%"
        )

    with c3:

        st.metric(
            "Measurability",
            f"{result['Measurability %']}%"
        )

    with c4:

        st.metric(
            "MCQ Quality",
            f"{result['MCQ Quality %']}%"
        )

    st.write(
        f"**Quality classification:** "
        f"{quality_label(result['Overall Quality %'])}"
    )

    # ========================================================
    # FEEDBACK
    # ========================================================

    st.subheader(
        "💡 Detailed Evaluation"
    )

    st.write(
        "**Clarity:** "
        + result["Clarity Feedback"]
    )

    st.write(
        "**Specificity:** "
        + result["Specificity Feedback"]
    )

    st.write(
        "**Measurability:** "
        + result["Measurability Feedback"]
    )

    st.write(
        "**Relevance:** "
        + result["Relevance Feedback"]
    )

    st.write(
        "**MCQ structure:** "
        + result["MCQ Feedback"]
    )

    # ========================================================
    # TARGET CHECK
    # ========================================================

    target_met = (
        result["CLO Alignment %"] >= 85
        and result["PLO Alignment %"] >= 85
        and result["Bloom Alignment %"] >= 85
        and result["Clarity %"] >= 85
        and result["Specificity %"] >= 85
        and result["Measurability %"] >= 85
    )

    if target_met:

        st.success(
            "This question meets the defined quality and "
            "alignment thresholds and represents a strong "
            "candidate for full alignment with the specified "
            "assessment requirements."
        )

    else:

        st.warning(
            "This question has one or more areas that should "
            "be strengthened before final use."
        )

        # ====================================================
        # SUGGESTED QUESTIONS
        # ====================================================

        st.subheader(
            "✨ Three Improved Questions"
        )

        selected_clo_code = (
            result["Best CLO"]
        )

        selected_plo_code = (
            result["Best PLO"]
        )

        selected_clo_text = clos.get(
            selected_clo_code,
            ""
        )

        selected_plo_text = plos.get(
            selected_plo_code,
            ""
        )

        suggestions = generate_suggestions(
            selected_clo_text,
            result["Intended Bloom"]
        )

        for i, suggestion in enumerate(
            suggestions,
            1
        ):

            evaluation = evaluate_suggested_question(
                suggestion,
                selected_clo_text,
                selected_plo_text,
                result["Intended Bloom"]
            )

            st.write(
                f"### Suggested Question {i}"
            )

            st.info(
                suggestion
            )

            st.write(
                "**Predicted alignment of this suggested item:**"
            )

            s1, s2, s3, s4 = st.columns(4)

            with s1:

                st.metric(
                    "CLO",
                    f"{evaluation['CLO']}%"
                )

            with s2:

                st.metric(
                    "PLO",
                    f"{evaluation['PLO']}%"
                )

            with s3:

                st.metric(
                    "Bloom",
                    f"{evaluation['Bloom']}%"
                )

            with s4:

                st.metric(
                    "Target Alignment",
                    f"{evaluation['Target Alignment']}%"
                )

            st.caption(
                f"Detected Bloom: "
                f"{evaluation['Detected Bloom']} | "
                f"Clarity: {evaluation['Clarity']}% | "
                f"Specificity: {evaluation['Specificity']}% | "
                f"Measurability: {evaluation['Measurability']}%"
            )

            if (
                evaluation["CLO"] >= 85
                and evaluation["PLO"] >= 85
                and evaluation["Bloom"] >= 85
                and evaluation["Clarity"] >= 85
                and evaluation["Specificity"] >= 85
                and evaluation["Measurability"] >= 85
            ):

                st.success(
                    "This suggested question satisfies the "
                    "defined target thresholds across the "
                    "learning-outcome, cognitive-level, and "
                    "question-quality checks."
                )

    # ========================================================
    # WEAK QUESTIONS
    # ========================================================

    st.divider()

    st.header(
        "⚠️ Questions Requiring Revision"
    )

    weak = [
        r
        for r in results
        if r["Overall Quality %"] < 70
    ]

    if weak:

        for r in weak:

            st.write(
                f"**Q{r['Question No.']}** — "
                f"{r['Question']}"
            )

            st.caption(
                f"Overall Quality: "
                f"{r['Overall Quality %']}% | "
                f"CLO: {r['CLO Alignment %']}% | "
                f"PLO: {r['PLO Alignment %']}% | "
                f"Bloom: {r['Bloom Alignment %']}%"
            )

    else:

        st.success(
            "No questions fall below the major-revision threshold."
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "📥 Export Evaluation"
    )

    export_df = pd.DataFrame(
        results
    ).copy()

    export_df["Options"] = export_df[
        "Options"
    ].apply(
        lambda x:
        " | ".join(x)
        if isinstance(x, list)
        else str(x)
    )

    csv_data = (
        export_df
        .to_csv(index=False)
        .encode("utf-8")
    )

    st.download_button(
        "Download Complete Quiz Evaluation",
        data=csv_data,
        file_name="OBE_Quiz_Quality_Analysis.csv",
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "📌 Final Evaluation"
    )

    st.write(
        f"**Course:** {course_name}"
    )

    st.write(
        f"**Assessment:** {assessment_name}"
    )

    st.write(
        f"**Questions evaluated:** {len(results)}"
    )

    st.write(
        f"**Intended Bloom level:** {intended_bloom}"
    )

    st.write(
        f"**Overall question quality:** {overall}%"
    )

    st.write(
        f"**CLO alignment:** {clo_avg}%"
    )

    st.write(
        f"**PLO alignment:** {plo_avg}%"
    )

    st.write(
        f"**Bloom alignment:** {bloom_avg}%"
    )

    st.info(
        "The tool evaluates the assessment itself. It does not "
        "calculate student CLO/PLO attainment unless student "
        "marks are provided. Suggested questions are generated "
        "to strengthen alignment and should be reviewed by the "
        "instructor before being used in an actual assessment."
    )
