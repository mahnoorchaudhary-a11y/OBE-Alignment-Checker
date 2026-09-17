import io
import re
import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


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
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "label",
        "select",
        "match"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "discuss",
        "classify",
        "illustrate",
        "compare",
        "paraphrase"
    ],

    "Apply": [
        "apply",
        "use",
        "demonstrate",
        "solve",
        "calculate",
        "implement",
        "execute",
        "practice",
        "construct"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "compare",
        "contrast",
        "examine",
        "investigate",
        "categorize",
        "distinguish",
        "infer"
    ],

    "Evaluate": [
        "evaluate",
        "assess",
        "judge",
        "justify",
        "critique",
        "defend",
        "argue",
        "recommend",
        "validate",
        "appraise"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "formulate",
        "produce",
        "construct",
        "generate",
        "plan",
        "propose",
        "compose"
    ]
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "by",
    "from",
    "at",
    "as",
    "is",
    "are",
    "be",
    "been",
    "being",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "their",
    "they",
    "them",
    "student",
    "students",
    "learner",
    "learners",
    "will",
    "should",
    "can",
    "may",
    "able",
    "ability",
    "course",
    "learning",
    "learn",
    "knowledge",
    "skills",
    "skill"
}


# ============================================================
# CONCEPT GROUPS
# ============================================================

CONCEPT_GROUPS = {

    "main idea": {
        "main",
        "idea",
        "central",
        "point",
        "theme",
        "message",
        "topic",
        "purpose",
        "focus"
    },

    "reading": {
        "read",
        "reading",
        "comprehension",
        "interpret",
        "meaning",
        "understand",
        "text",
        "passage"
    },

    "organization": {
        "organization",
        "organisation",
        "pattern",
        "structure",
        "sequence",
        "cause",
        "effect",
        "comparison",
        "contrast",
        "process",
        "classification",
        "chronological"
    },

    "paraphrasing": {
        "paraphrase",
        "paraphrasing",
        "restate",
        "rewrite",
        "rephrase",
        "original",
        "meaning"
    },

    "author purpose": {
        "purpose",
        "inform",
        "persuade",
        "entertain",
        "explain",
        "writer",
        "author",
        "intention"
    },

    "tone": {
        "tone",
        "attitude",
        "mood",
        "author",
        "writer",
        "language",
        "emotion",
        "feeling"
    },

    "writing": {
        "write",
        "writing",
        "essay",
        "paragraph",
        "composition",
        "draft",
        "revision",
        "revise",
        "argument"
    },

    "critical thinking": {
        "critical",
        "thinking",
        "reason",
        "reasoning",
        "evidence",
        "argument",
        "logic",
        "judgment",
        "evaluate",
        "analysis"
    },

    "communication": {
        "communication",
        "communicate",
        "presentation",
        "speaking",
        "listening",
        "audience",
        "message",
        "interaction"
    },

    "grammar": {
        "grammar",
        "sentence",
        "syntax",
        "verb",
        "noun",
        "pronoun",
        "agreement",
        "punctuation"
    },

    "vocabulary": {
        "vocabulary",
        "word",
        "meaning",
        "definition",
        "context",
        "lexical"
    },

    "research": {
        "research",
        "source",
        "citation",
        "reference",
        "academic",
        "evidence",
        "information"
    },

    "analysis": {
        "analyze",
        "analyse",
        "analysis",
        "examine",
        "compare",
        "contrast",
        "differentiate",
        "relationship"
    },

    "problem solving": {
        "problem",
        "solve",
        "solution",
        "application",
        "decision",
        "strategy"
    }
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.replace("\n", " ")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = re.sub(
        r"[^\w\s\-]",
        " ",
        text
    )

    return text.lower().strip()


def tokenize(text):

    text = normalize_text(text)

    words = re.findall(
        r"[a-zA-Z0-9]+",
        text
    )

    return {
        word
        for word in words
        if len(word) > 2
        and word not in STOP_WORDS
    }


# ============================================================
# CONCEPT EXPANSION
# ============================================================

def expanded_concepts(text):

    words = tokenize(text)

    expanded = set(words)

    for concept_words in CONCEPT_GROUPS.values():

        if words.intersection(concept_words):
            expanded.update(concept_words)

    return expanded


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    text = normalize_text(question)

    detected = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            pattern = r"\b" + re.escape(verb) + r"\b"

            if re.search(pattern, text):

                detected.append(
                    (level, verb)
                )

    if detected:

        detected.sort(
            key=lambda item: BLOOM_RANK[item[0]],
            reverse=True
        )

        level, verb = detected[0]

        return {
            "level": level,
            "verb": verb,
            "confidence": "High"
        }

    return {
        "level": "Needs Review",
        "verb": "",
        "confidence": "Low"
    }


# ============================================================
# BLOOM ALIGNMENT
# ============================================================

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
        return 65

    if difference == 2:
        return 45

    return 25


# ============================================================
# OUTCOME SIMILARITY
# ============================================================

def outcome_similarity(
    question,
    outcome
):

    q_words = expanded_concepts(
        question
    )

    o_words = expanded_concepts(
        outcome
    )

    if not q_words or not o_words:
        return 0

    intersection = q_words.intersection(
        o_words
    )

    union = q_words.union(
        o_words
    )

    jaccard = (
        len(intersection)
        /
        max(len(union), 1)
    )

    outcome_coverage = (
        len(intersection)
        /
        max(len(o_words), 1)
    )

    question_coverage = (
        len(intersection)
        /
        max(len(q_words), 1)
    )

    question_text = normalize_text(
        question
    )

    outcome_text = normalize_text(
        outcome
    )

    phrase_bonus = 0

    phrases = re.split(
        r"[,;:.]",
        outcome_text
    )

    for phrase in phrases:

        phrase = phrase.strip()

        if (
            len(phrase.split()) >= 2
            and phrase in question_text
        ):
            phrase_bonus += 0.08

    score = (
        jaccard * 0.35
        +
        outcome_coverage * 0.45
        +
        question_coverage * 0.20
        +
        min(phrase_bonus, 0.20)
    )

    return round(
        min(score * 100, 100),
        1
    )


# ============================================================
# FILE READER
# ============================================================

def extract_text_from_upload(
    uploaded_file
):

    if uploaded_file is None:
        return ""

    filename = uploaded_file.name.lower()

    data = uploaded_file.getvalue()

    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    if filename.endswith(".txt"):

        try:
            return data.decode(
                "utf-8",
                errors="ignore"
            )

        except Exception:
            return ""

    # --------------------------------------------------------
    # DOCX
    # --------------------------------------------------------

    if filename.endswith(".docx"):

        try:

            from docx import Document

            document = Document(
                io.BytesIO(data)
            )

            paragraphs = []

            for paragraph in document.paragraphs:

                text = paragraph.text.strip()

                if text:
                    paragraphs.append(text)

            return "\n".join(
                paragraphs
            )

        except Exception as error:

            st.error(
                f"Could not read DOCX file: {error}"
            )

            return ""

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if filename.endswith(".pdf"):

        # First try pypdf
        try:

            from pypdf import PdfReader

            reader = PdfReader(
                io.BytesIO(data)
            )

            pages = []

            for page in reader.pages:

                try:

                    text = (
                        page.extract_text()
                        or ""
                    )

                    pages.append(text)

                except Exception:
                    continue

            extracted = "\n".join(
                pages
            ).strip()

            if extracted:
                return extracted

        except Exception:
            pass

        # OCR fallback
        try:

            from pdf2image import convert_from_bytes
            import pytesseract

            images = convert_from_bytes(
                data
            )

            pages = []

            for image in images:

                text = pytesseract.image_to_string(
                    image
                )

                if text:
                    pages.append(text)

            extracted = "\n".join(
                pages
            ).strip()

            if extracted:
                return extracted

        except Exception:
            pass

        st.error(
            "Could not read the PDF. "
            "Please install pypdf or upload the quiz "
            "as DOCX or TXT."
        )

        return ""

    # --------------------------------------------------------
    # EXCEL
    # --------------------------------------------------------

    if (
        filename.endswith(".xlsx")
        or filename.endswith(".xls")
    ):

        try:

            excel = pd.ExcelFile(
                io.BytesIO(data)
            )

            sheets = []

            for sheet in excel.sheet_names:

                df = pd.read_excel(
                    io.BytesIO(data),
                    sheet_name=sheet,
                    header=None
                )

                sheets.append(
                    df.astype(str).to_string(
                        index=False,
                        header=False
                    )
                )

            return "\n".join(
                sheets
            )

        except Exception as error:

            st.error(
                f"Could not read Excel file: {error}"
            )

            return ""

    return ""


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def clean_question(text):

    text = re.sub(
        r"^\s*(?:question\s*)?"
        r"(?:q\s*)?"
        r"\d+\s*[\.\):\-]\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


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

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    questions = []

    current = None

    numbered_pattern = re.compile(
        r"^\s*"
        r"(?:question\s*)?"
        r"(?:q\s*)?"
        r"(\d+)"
        r"\s*[\.\):\-]\s*"
        r"(.+)$",
        re.IGNORECASE
    )

    for line in lines:

        match = numbered_pattern.match(
            line
        )

        if match:

            if current:
                questions.append(
                    current.strip()
                )

            current = match.group(2).strip()

        elif current:

            current += (
                " "
                +
                line
            )

    if current:
        questions.append(
            current.strip()
        )

    questions = [
        clean_question(q)
        for q in questions
        if len(clean_question(q)) > 5
    ]

    if questions:
        return questions

    # --------------------------------------------------------
    # Question-mark fallback
    # --------------------------------------------------------

    question_lines = []

    for line in lines:

        if "?" in line and len(line) > 10:

            question_lines.append(
                clean_question(line)
            )

    if question_lines:
        return question_lines

    # --------------------------------------------------------
    # Paragraph fallback
    # --------------------------------------------------------

    paragraphs = re.split(
        r"\n\s*\n",
        text
    )

    questions = []

    for paragraph in paragraphs:

        paragraph = paragraph.strip()

        if len(paragraph) >= 15:

            questions.append(
                clean_question(
                    paragraph
                )
            )

    return questions


# ============================================================
# INTELLIGENT TOPIC EXTRACTION
# ============================================================

def extract_core_topic(
    clo_text
):

    text = normalize_text(
        clo_text
    )

    # Remove common learning-action phrases
    action_patterns = [
        r"\bbe able to\b",
        r"\bwill be able to\b",
        r"\bwill\b",
        r"\bapply\b",
        r"\banalyze\b",
        r"\banalyse\b",
        r"\bevaluate\b",
        r"\bcreate\b",
        r"\bdevelop\b",
        r"\bdesign\b",
        r"\bexplain\b",
        r"\bdescribe\b",
        r"\bidentify\b",
        r"\bdemonstrate\b",
        r"\bdiscuss\b",
        r"\bexamine\b",
        r"\binterpret\b",
        r"\bunderstand\b",
        r"\buse\b",
        r"\bapply\b",
        r"\bcritically\b",
        r"\beffectively\b",
        r"\bappropriately\b",
        r"\bcompetently\b"
    ]

    for pattern in action_patterns:

        text = re.sub(
            pattern,
            "",
            text
        )

    text = re.sub(
        r"\bstudents?\b",
        "",
        text
    )

    text = re.sub(
        r"\blearners?\b",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip(
        " ,.;:-"
    )

    # Keep reasonable length
    if len(text) > 220:

        text = text[:220]

        if " " in text:
            text = text.rsplit(
                " ",
                1
            )[0]

    return text


# ============================================================
# IDENTIFY PLO SKILL
# ============================================================

def extract_plo_skill(
    plo_text
):

    text = normalize_text(
        plo_text
    )

    skills = [
        (
            [
                "critical thinking",
                "critical analysis",
                "critical reasoning"
            ],
            "critical reasoning"
        ),

        (
            [
                "problem solving",
                "problem-solving"
            ],
            "problem-solving"
        ),

        (
            [
                "communication",
                "communicate"
            ],
            "clear communication"
        ),

        (
            [
                "research"
            ],
            "evidence from relevant sources"
        ),

        (
            [
                "teamwork",
                "team work",
                "collaboration"
            ],
            "collaborative work"
        ),

        (
            [
                "decision making",
                "decision-making"
            ],
            "reasoned decision-making"
        ),

        (
            [
                "professional"
            ],
            "professional judgment"
        ),

        (
            [
                "ethical"
            ],
            "ethical considerations"
        ),

        (
            [
                "technology",
                "technological"
            ],
            "appropriate use of technology"
        )
    ]

    for phrases, skill in skills:

        for phrase in phrases:

            if phrase in text:
                return skill

    return ""


# ============================================================
# REMOVE LABELS FROM GENERATED QUESTION
# ============================================================

def clean_generated_question(
    question
):

    question = re.sub(
        r"\bCLO\s*\d+\b",
        "",
        question,
        flags=re.IGNORECASE
    )

    question = re.sub(
        r"\bPLO\s*\d+\b",
        "",
        question,
        flags=re.IGNORECASE
    )

    question = re.sub(
        r"\bCLO\b",
        "",
        question,
        flags=re.IGNORECASE
    )

    question = re.sub(
        r"\bPLO\b",
        "",
        question,
        flags=re.IGNORECASE
    )

    question = re.sub(
        r"\s+",
        " ",
        question
    )

    return question.strip()


# ============================================================
# QUESTION GENERATOR
# ============================================================

def generate_target_question(
    clo_text,
    plo_text,
    bloom
):

    topic = extract_core_topic(
        clo_text
    )

    if not topic:
        topic = "the topic under study"

    skill = extract_plo_skill(
        plo_text
    )

    # --------------------------------------------------------
    # REMEMBER
    # --------------------------------------------------------

    if bloom == "Remember":

        question = (
            f"Define {topic} and identify its main "
            f"characteristics or components."
        )

    # --------------------------------------------------------
    # UNDERSTAND
    # --------------------------------------------------------

    elif bloom == "Understand":

        question = (
            f"Explain {topic} in your own words and "
            f"illustrate your explanation with a relevant example."
        )

    # --------------------------------------------------------
    # APPLY
    # --------------------------------------------------------

    elif bloom == "Apply":

        if skill:

            question = (
                f"Consider a realistic situation involving "
                f"{topic}. Apply the relevant principles to "
                f"the situation and explain how you would "
                f"respond using {skill}."
            )

        else:

            question = (
                f"Consider a realistic situation involving "
                f"{topic}. Apply the relevant principles to "
                f"the situation and explain the steps you "
                f"would take."
            )

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    elif bloom == "Analyze":

        if skill:

            question = (
                f"Analyze {topic} by examining its key elements, "
                f"relationships, and underlying factors. Use "
                f"relevant evidence to support your analysis "
                f"and demonstrate {skill}."
            )

        else:

            question = (
                f"Analyze {topic} by examining its key elements, "
                f"relationships, and underlying factors. Support "
                f"your analysis with relevant evidence."
            )

    # --------------------------------------------------------
    # EVALUATE
    # --------------------------------------------------------

    elif bloom == "Evaluate":

        if skill:

            question = (
                f"Evaluate {topic} in a relevant context. "
                f"Assess its strengths and limitations, "
                f"justify your judgment with appropriate "
                f"evidence, and demonstrate {skill}."
            )

        else:

            question = (
                f"Evaluate {topic} in a relevant context. "
                f"Assess its strengths and limitations and "
                f"justify your judgment with appropriate evidence."
            )

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    else:

        if skill:

            question = (
                f"Design a practical solution or response "
                f"related to {topic}. Explain your design "
                f"choices and show how your proposed approach "
                f"demonstrates {skill}."
            )

        else:

            question = (
                f"Design a practical solution or response "
                f"related to {topic}. Explain your design "
                f"choices and show how your proposed approach "
                f"addresses the requirements of the situation."
            )

    return clean_generated_question(
        question
    )


# ============================================================
# SUGGESTION GENERATOR
# ============================================================

def generate_revision_suggestion(
    question,
    clo_text,
    plo_text,
    intended_bloom,
    detected_bloom,
    clo_score,
    plo_score,
    bloom_score
):

    # --------------------------------------------------------
    # Generate replacement question
    # --------------------------------------------------------

    suggested_question = generate_target_question(
        clo_text,
        plo_text,
        intended_bloom
    )

    # --------------------------------------------------------
    # Determine whether current item is strong
    # --------------------------------------------------------

    if (
        clo_score >= 85
        and plo_score >= 85
        and bloom_score >= 85
    ):

        return (
            "This question is appropriately constructed for "
            "the intended content, broader skill, and cognitive "
            "level. It may be retained as written and provides "
            "a basis for 100% alignment with the specified "
            "assessment requirements."
        )

    # --------------------------------------------------------
    # Build specific improvement advice
    # --------------------------------------------------------

    improvements = []

    if clo_score < 60:

        improvements.append(
            "make the question more directly assess the "
            "specific content and skill described in the "
            "intended learning outcome"
        )

    elif clo_score < 85:

        improvements.append(
            "make the connection to the intended content "
            "more explicit"
        )

    if plo_score < 60:

        improvements.append(
            "require students to demonstrate the broader "
            "skill expected from the assessment"
        )

    elif plo_score < 85:

        improvements.append(
            "strengthen the broader skill demonstrated "
            "through the response"
        )

    if bloom_score < 70:

        improvements.append(
            f"raise the cognitive demand to the "
            f"{intended_bloom} level"
        )

    elif bloom_score < 85:

        improvements.append(
            f"make the expected {intended_bloom.lower()}-level "
            f"thinking more explicit"
        )

    if detected_bloom == "Needs Review":

        improvements.append(
            "use a clear action that makes the expected "
            "thinking process measurable"
        )

    if improvements:

        advice = (
            "Revise the question to "
            + "; ".join(improvements)
            + "."
        )

    else:

        advice = (
            "Refine the wording so that the expected "
            "student response is more specific and measurable."
        )

    return (
        advice
        + "\n\n"
        + "Suggested question:\n"
        + suggested_question
    )


# ============================================================
# QUESTION ANALYSIS
# ============================================================

def analyze_questions(
    questions,
    clos,
    plos,
    intended_bloom
):

    results = []

    for number, question in enumerate(
        questions,
        start=1
    ):

        # ----------------------------------------------------
        # CLO matching
        # ----------------------------------------------------

        clo_matches = []

        for code, description in clos.items():

            score = outcome_similarity(
                question,
                description
            )

            clo_matches.append({
                "code": code,
                "description": description,
                "score": score
            })

        clo_matches.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        best_clo = clo_matches[0]

        # ----------------------------------------------------
        # PLO matching
        # ----------------------------------------------------

        plo_matches = []

        for code, description in plos.items():

            score = outcome_similarity(
                question,
                description
            )

            plo_matches.append({
                "code": code,
                "description": description,
                "score": score
            })

        plo_matches.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        best_plo = plo_matches[0]

        # ----------------------------------------------------
        # Bloom detection
        # ----------------------------------------------------

        bloom_result = detect_bloom(
            question
        )

        detected_bloom = bloom_result[
            "level"
        ]

        bloom_score = bloom_alignment(
            intended_bloom,
            detected_bloom
        )

        # ----------------------------------------------------
        # Combined score
        # ----------------------------------------------------

        combined = (
            best_clo["score"] * 0.35
            +
            best_plo["score"] * 0.25
            +
            bloom_score * 0.40
        )

        combined = round(
            min(combined, 100),
            1
        )

        # ----------------------------------------------------
        # Suggestion
        # ----------------------------------------------------

        suggestion = generate_revision_suggestion(
            question=question,
            clo_text=best_clo["description"],
            plo_text=best_plo["description"],
            intended_bloom=intended_bloom,
            detected_bloom=detected_bloom,
            clo_score=best_clo["score"],
            plo_score=best_plo["score"],
            bloom_score=bloom_score
        )

        results.append({

            "Question No.": number,

            "Question": question,

            "Best CLO": best_clo["code"],

            "CLO Alignment %": best_clo["score"],

            "Best PLO": best_plo["code"],

            "PLO Alignment %": best_plo["score"],

            "Intended Bloom": intended_bloom,

            "Detected Bloom": detected_bloom,

            "Bloom Alignment %": bloom_score,

            "Combined Alignment %": combined,

            "Suggestion": suggestion
        })

    return results


# ============================================================
# CLO ANALYSIS
# ============================================================

def calculate_clo_analysis(
    results,
    clos
):

    rows = []

    for code, description in clos.items():

        relevant = [
            row
            for row in results
            if row["Best CLO"] == code
        ]

        if relevant:

            alignment = sum(
                row["CLO Alignment %"]
                for row in relevant
            ) / len(relevant)

        else:

            alignment = 0

        rows.append({

            "CLO": code,

            "Description": description,

            "Alignment %": round(
                alignment,
                1
            ),

            "Questions": len(
                relevant
            )
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# PLO ANALYSIS
# ============================================================

def calculate_plo_analysis(
    results,
    plos
):

    rows = []

    for code, description in plos.items():

        relevant = [
            row
            for row in results
            if row["Best PLO"] == code
        ]

        if relevant:

            alignment = sum(
                row["PLO Alignment %"]
                for row in relevant
            ) / len(relevant)

        else:

            alignment = 0

        rows.append({

            "PLO": code,

            "Description": description,

            "Alignment %": round(
                alignment,
                1
            ),

            "Questions": len(
                relevant
            )
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# BLOOM ANALYSIS
# ============================================================

def calculate_bloom_analysis(
    results
):

    rows = []

    for level in BLOOM_LEVELS:

        relevant = [
            row
            for row in results
            if row["Detected Bloom"] == level
        ]

        if relevant:

            alignment = sum(
                row["Bloom Alignment %"]
                for row in relevant
            ) / len(relevant)

        else:

            alignment = 0

        rows.append({

            "Bloom Level": level,

            "Questions": len(
                relevant
            ),

            "Alignment %": round(
                alignment,
                1
            )
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "analysis_clos" not in st.session_state:
    st.session_state.analysis_clos = {}

if "analysis_plos" not in st.session_state:
    st.session_state.analysis_plos = {}

if "analysis_intended_bloom" not in st.session_state:
    st.session_state.analysis_intended_bloom = "Analyze"

if "analysis_questions" not in st.session_state:
    st.session_state.analysis_questions = []


# ============================================================
# APPLICATION TITLE
# ============================================================

st.title(
    "🎓 OBE Quiz Alignment Checker"
)

st.write(
    "Check whether your quiz questions appropriately reflect "
    "the intended learning outcomes and Bloom's cognitive level."
)


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.subheader(
    "1. Assessment Information"
)

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course Name",
        placeholder="Example: English I"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="Example: Quiz 1"
    )


# ============================================================
# 2. CLO ENTRY
# ============================================================

st.subheader(
    "2. Enter CLOs"
)

st.caption(
    "Enter the learning outcomes that the quiz is intended "
    "to assess."
)

num_clos = st.number_input(
    "Number of CLOs",
    min_value=1,
    max_value=10,
    value=2,
    step=1
)

clos = {}

for i in range(
    1,
    int(num_clos) + 1
):

    col1, col2 = st.columns(
        [1, 5]
    )

    with col1:

        st.text_input(
            "Code",
            value=f"CLO{i}",
            key=f"clo_code_{i}",
            disabled=True
        )

    with col2:

        description = st.text_area(
            f"CLO {i} Description",
            key=f"clo_description_{i}",
            height=80,
            placeholder=(
                "Example: Analyze patterns of organization "
                "in academic paragraphs."
            )
        )

        if description.strip():

            clos[
                f"CLO{i}"
            ] = description.strip()


# ============================================================
# 3. PLO ENTRY
# ============================================================

st.subheader(
    "3. Enter PLOs"
)

st.caption(
    "Enter the broader learning outcomes or graduate "
    "attributes relevant to the assessment."
)

num_plos = st.number_input(
    "Number of PLOs",
    min_value=1,
    max_value=10,
    value=2,
    step=1
)

plos = {}

for i in range(
    1,
    int(num_plos) + 1
):

    col1, col2 = st.columns(
        [1, 5]
    )

    with col1:

        st.text_input(
            "Code",
            value=f"PLO{i}",
            key=f"plo_code_{i}",
            disabled=True
        )

    with col2:

        description = st.text_area(
            f"PLO {i} Description",
            key=f"plo_description_{i}",
            height=80,
            placeholder=(
                "Example: Apply analytical and critical "
                "thinking skills to academic tasks."
            )
        )

        if description.strip():

            plos[
                f"PLO{i}"
            ] = description.strip()


# ============================================================
# 4. INTENDED BLOOM LEVEL
# ============================================================

st.subheader(
    "4. Intended Bloom's Level"
)

intended_bloom = st.selectbox(
    "Select the intended cognitive level",
    BLOOM_LEVELS,
    index=3
)


# ============================================================
# 5. QUIZ UPLOAD
# ============================================================

st.subheader(
    "5. Upload Quiz"
)

uploaded_file = st.file_uploader(
    "Upload your quiz",
    type=[
        "pdf",
        "docx",
        "txt",
        "xlsx",
        "xls"
    ],
    help=(
        "For best results, use numbered questions such as "
        "1., 2., 3. or Q1., Q2., Q3."
    )
)


# ============================================================
# ANALYZE BUTTON
# ============================================================

st.divider()

analyze_clicked = st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
)


# ============================================================
# RUN ANALYSIS
# ============================================================

if analyze_clicked:

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not course_name.strip():

        st.error(
            "Please enter the course name."
        )

        st.stop()

    if not assessment_name.strip():

        st.error(
            "Please enter the assessment name."
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

    if uploaded_file is None:

        st.error(
            "Please upload the quiz."
        )

        st.stop()

    # --------------------------------------------------------
    # Read file
    # --------------------------------------------------------

    with st.spinner(
        "Reading and analyzing the quiz..."
    ):

        quiz_text = extract_text_from_upload(
            uploaded_file
        )

        if not quiz_text.strip():

            st.error(
                "No readable text was found in the uploaded file."
            )

            st.stop()

        questions = extract_questions(
            quiz_text
        )

        if not questions:

            st.error(
                "No questions could be detected. "
                "Please upload a quiz with numbered questions "
                "or clearly separated question statements."
            )

            st.stop()

        results = analyze_questions(
            questions=questions,
            clos=clos,
            plos=plos,
            intended_bloom=intended_bloom
        )

    # --------------------------------------------------------
    # Store results
    # --------------------------------------------------------

    st.session_state.analysis_results = results

    st.session_state.analysis_clos = clos

    st.session_state.analysis_plos = plos

    st.session_state.analysis_intended_bloom = (
        intended_bloom
    )

    st.session_state.analysis_questions = questions


# ============================================================
# DISPLAY RESULTS
# ============================================================

if st.session_state.analysis_results:

    results = (
        st.session_state.analysis_results
    )

    clos = (
        st.session_state.analysis_clos
    )

    plos = (
        st.session_state.analysis_plos
    )

    intended_bloom = (
        st.session_state.analysis_intended_bloom
    )

    results_df = pd.DataFrame(
        results
    )

    # ========================================================
    # CALCULATE OVERALL ALIGNMENT
    # ========================================================

    avg_clo = results_df[
        "CLO Alignment %"
    ].mean()

    avg_plo = results_df[
        "PLO Alignment %"
    ].mean()

    avg_bloom = results_df[
        "Bloom Alignment %"
    ].mean()

    overall = (
        avg_clo * 0.35
        +
        avg_plo * 0.25
        +
        avg_bloom * 0.40
    )

    overall = round(
        min(overall, 100),
        1
    )

    # ========================================================
    # RESULTS HEADER
    # ========================================================

    st.divider()

    st.header(
        "📊 Quiz Analysis"
    )

    # ========================================================
    # GRAPH AT THE TOP
    # ========================================================

    st.subheader(
        "📈 Overall Alignment"
    )

    graph_df = pd.DataFrame({

        "Dimension": [
            "Overall",
            "CLO",
            "PLO",
            "Bloom"
        ],

        "Alignment": [
            round(overall, 1),
            round(avg_clo, 1),
            round(avg_plo, 1),
            round(avg_bloom, 1)
        ]
    })

    st.bar_chart(
        graph_df.set_index(
            "Dimension"
        ),
        y="Alignment",
        use_container_width=True
    )

    # ========================================================
    # NUMERICAL SUMMARY
    # ========================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Overall Alignment",
            f"{overall:.1f}%"
        )

    with col2:

        st.metric(
            "CLO Alignment",
            f"{avg_clo:.1f}%"
        )

    with col3:

        st.metric(
            "PLO Alignment",
            f"{avg_plo:.1f}%"
        )

    with col4:

        st.metric(
            "Bloom Alignment",
            f"{avg_bloom:.1f}%"
        )

    st.caption(
        "These percentages evaluate quiz-level alignment with "
        "the entered learning outcomes and intended cognitive "
        "level. They are not student attainment percentages."
    )

    # ========================================================
    # CLO-BY-CLO ANALYSIS
    # ========================================================

    st.divider()

    st.subheader(
        "🎯 CLO-by-CLO Analysis"
    )

    selected_clo = st.selectbox(
        "Select one CLO to review",
        list(clos.keys())
    )

    selected_clo_description = clos[
        selected_clo
    ]

    selected_clo_rows = [
        row
        for row in results
        if row["Best CLO"] == selected_clo
    ]

    if selected_clo_rows:

        selected_clo_alignment = sum(
            row["CLO Alignment %"]
            for row in selected_clo_rows
        ) / len(
            selected_clo_rows
        )

    else:

        selected_clo_alignment = 0

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Alignment",
            f"{selected_clo_alignment:.1f}%"
        )

    with col2:

        st.metric(
            "Questions Mapped",
            len(selected_clo_rows)
        )

    with col3:

        st.metric(
            "Total Questions",
            len(results)
        )

    st.info(
        f"**{selected_clo}:** "
        f"{selected_clo_description}"
    )

    if selected_clo_rows:

        st.write(
            "### Questions Assessing This Outcome"
        )

        selected_clo_table = pd.DataFrame([

            {
                "Question No.": row[
                    "Question No."
                ],

                "Question": row[
                    "Question"
                ],

                "Alignment %": row[
                    "CLO Alignment %"
                ],

                "Detected Bloom": row[
                    "Detected Bloom"
                ]
            }

            for row in selected_clo_rows

        ])

        st.dataframe(
            selected_clo_table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "No question was strongly associated with "
            "this outcome."
        )

        first_plo = list(
            plos.keys()
        )[0]

        suggested_question = (
            generate_target_question(
                selected_clo_description,
                plos[first_plo],
                intended_bloom
            )
        )

        st.write(
            "### Suggested Question"
        )

        st.info(
            suggested_question
        )

    # ========================================================
    # PLO ANALYSIS
    # ========================================================

    st.divider()

    st.subheader(
        "📌 PLO Analysis"
    )

    plo_df = calculate_plo_analysis(
        results,
        plos
    )

    st.dataframe(
        plo_df,
        use_container_width=True,
        hide_index=True
    )

    plo_chart = plo_df[
        [
            "PLO",
            "Alignment %"
        ]
    ].set_index(
        "PLO"
    )

    st.bar_chart(
        plo_chart,
        y="Alignment %",
        use_container_width=True
    )

    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.divider()

    st.subheader(
        "🧠 Bloom's Level Analysis"
    )

    st.write(
        f"**Intended Bloom's Level:** "
        f"{intended_bloom}"
    )

    bloom_df = calculate_bloom_analysis(
        results
    )

    st.dataframe(
        bloom_df,
        use_container_width=True,
        hide_index=True
    )

    bloom_chart = bloom_df[
        [
            "Bloom Level",
            "Questions"
        ]
    ].set_index(
        "Bloom Level"
    )

    st.bar_chart(
        bloom_chart,
        y="Questions",
        use_container_width=True
    )

    # ========================================================
    # COMPLETE QUESTION ANALYSIS
    # ========================================================

    st.divider()

    st.subheader(
        "📝 Complete Question Analysis"
    )

    st.caption(
        "The Suggestions column provides a specific improvement "
        "and, where needed, a professionally constructed "
        "replacement question."
    )

    display_df = results_df[
        [
            "Question No.",
            "Question",
            "Best CLO",
            "CLO Alignment %",
            "Best PLO",
            "PLO Alignment %",
            "Intended Bloom",
            "Detected Bloom",
            "Bloom Alignment %",
            "Combined Alignment %",
            "Suggestion"
        ]
    ].copy()

    st.dataframe(

        display_df,

        use_container_width=True,

        hide_index=True,

        height=650,

        column_config={

            "Question No.":

                st.column_config.NumberColumn(
                    "Question No."
                ),

            "Question":

                st.column_config.TextColumn(
                    "Question",
                    width="large"
                ),

            "Best CLO":

                st.column_config.TextColumn(
                    "Best CLO"
                ),

            "CLO Alignment %":

                st.column_config.ProgressColumn(
                    "CLO Alignment %",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%"
                ),

            "Best PLO":

                st.column_config.TextColumn(
                    "Best PLO"
                ),

            "PLO Alignment %":

                st.column_config.ProgressColumn(
                    "PLO Alignment %",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%"
                ),

            "Intended Bloom":

                st.column_config.TextColumn(
                    "Intended Bloom"
                ),

            "Detected Bloom":

                st.column_config.TextColumn(
                    "Detected Bloom"
                ),

            "Bloom Alignment %":

                st.column_config.ProgressColumn(
                    "Bloom Alignment %",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%"
                ),

            "Combined Alignment %":

                st.column_config.ProgressColumn(
                    "Combined Alignment %",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%"
                ),

            "Suggestion":

                st.column_config.TextColumn(
                    "Suggestions",
                    width="large"
                )
        }
    )

    # ========================================================
    # INDIVIDUAL QUESTION REVIEW
    # ========================================================

    st.divider()

    st.subheader(
        "🔎 Individual Question Review"
    )

    question_numbers = [
        row[
            "Question No."
        ]
        for row in results
    ]

    selected_question_number = st.selectbox(
        "Select a question",
        question_numbers
    )

    selected_row = next(
        row
        for row in results
        if row[
            "Question No."
        ]
        ==
        selected_question_number
    )

    st.markdown(
        f"### Question "
        f"{selected_question_number}"
    )

    st.write(
        selected_row[
            "Question"
        ]
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "CLO Alignment",
            f"{selected_row['CLO Alignment %']:.1f}%"
        )

    with col2:

        st.metric(
            "PLO Alignment",
            f"{selected_row['PLO Alignment %']:.1f}%"
        )

    with col3:

        st.metric(
            "Detected Bloom",
            selected_row[
                "Detected Bloom"
            ]
        )

    with col4:

        st.metric(
            "Combined Alignment",
            f"{selected_row['Combined Alignment %']:.1f}%"
        )

    st.write(
        "### 💡 Suggestion"
    )

    st.info(
        selected_row[
            "Suggestion"
        ]
    )

    # ========================================================
    # WEAK QUESTIONS
    # ========================================================

    st.divider()

    st.subheader(
        "⚠️ Questions Needing Attention"
    )

    weak_questions = results_df[
        results_df[
            "Combined Alignment %"
        ] < 60
    ].copy()

    if not weak_questions.empty:

        weak_display = weak_questions[
            [
                "Question No.",
                "Question",
                "Best CLO",
                "Best PLO",
                "Detected Bloom",
                "Combined Alignment %",
                "Suggestion"
            ]
        ]

        st.dataframe(
            weak_display,
            use_container_width=True,
            hide_index=True,
            height=450
        )

    else:

        st.success(
            "No questions fell below the review threshold."
        )

    # ========================================================
    # CSV EXPORT
    # ========================================================

    st.divider()

    st.subheader(
        "⬇️ Export Analysis"
    )

    csv_data = results_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "Download Question Analysis CSV",
        data=csv_data,
        file_name=(
            "OBE_Quiz_Alignment_Analysis.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "✅ Analysis Complete"
    )

    st.write(
        f"**Course:** {course_name}"
    )

    st.write(
        f"**Assessment:** {assessment_name}"
    )

    st.write(
        f"**Questions analyzed:** "
        f"{len(results_df)}"
    )

    st.write(
        f"**Intended Bloom's Level:** "
        f"{intended_bloom}"
    )

    st.write(
        f"**Overall Alignment:** "
        f"{overall:.1f}%"
    )

    st.info(
        "Review the question-level suggestions to strengthen "
        "the connection between assessment content, intended "
        "learning outcomes, and cognitive demand."
    )

    st.success(
        "The analysis is complete. "
        "The detailed question analysis can be downloaded "
        "using the CSV button above."
    )
