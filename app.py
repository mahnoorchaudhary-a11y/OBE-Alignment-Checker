import streamlit as st
import pandas as pd
import re
import io

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Analyzer",
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
        "list",
        "name",
        "identify",
        "state",
        "recall",
        "recognize",
        "recognise",
        "mention",
        "label",
        "select",
        "match",
        "repeat"
    ],

    "Understand": [
        "explain",
        "summarize",
        "summarise",
        "interpret",
        "discuss",
        "classify",
        "describe",
        "outline",
        "paraphrase",
        "illustrate",
        "translate",
        "clarify"
    ],

    "Apply": [
        "apply",
        "use",
        "demonstrate",
        "solve",
        "calculate",
        "implement",
        "execute",
        "perform",
        "practice",
        "show",
        "compute"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "examine",
        "compare",
        "contrast",
        "differentiate",
        "distinguish",
        "investigate",
        "categorize",
        "categorise",
        "break down",
        "deconstruct",
        "inspect"
    ],

    "Evaluate": [
        "evaluate",
        "justify",
        "critique",
        "assess",
        "judge",
        "defend",
        "appraise",
        "recommend",
        "argue",
        "validate",
        "rate",
        "review"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "formulate",
        "produce",
        "compose",
        "plan",
        "propose",
        "generate",
        "construct",
        "invent"
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
    "from",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "as",
    "at",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "their",
    "there",
    "which",
    "what",
    "when",
    "where",
    "who",
    "whom",
    "why",
    "how",
    "you",
    "your",
    "they",
    "them",
    "he",
    "she",
    "his",
    "her",
    "we",
    "our",
    "can",
    "could",
    "would",
    "should",
    "will",
    "may",
    "might",
    "do",
    "does",
    "did",
    "into",
    "than",
    "then",
    "using",
    "use",
    "given",
    "following",
    "question"
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
        "message",
        "purpose",
        "theme",
        "key"
    },

    "reading": {
        "reading",
        "comprehension",
        "understanding",
        "interpret",
        "meaning",
        "text",
        "passage",
        "paragraph",
        "content"
    },

    "organization": {
        "pattern",
        "organization",
        "organisation",
        "structure",
        "cause",
        "effect",
        "compare",
        "contrast",
        "sequence",
        "chronological",
        "problem",
        "solution",
        "classification"
    },

    "paraphrasing": {
        "paraphrase",
        "paraphrasing",
        "rewrite",
        "restate",
        "restatement",
        "reword"
    },

    "author purpose": {
        "author",
        "purpose",
        "intent",
        "intention",
        "reason",
        "inform",
        "persuade",
        "entertain"
    },

    "tone": {
        "tone",
        "attitude",
        "feeling",
        "mood",
        "writer"
    },

    "writing": {
        "writing",
        "write",
        "essay",
        "paragraph",
        "composition",
        "draft",
        "revision",
        "revise"
    },

    "critical thinking": {
        "critical",
        "thinking",
        "reasoning",
        "argument",
        "evidence",
        "claim",
        "logic",
        "analysis",
        "evaluate",
        "judgment",
        "judgement"
    },

    "communication": {
        "communication",
        "communicate",
        "speaking",
        "listening",
        "presentation",
        "oral",
        "verbal"
    },

    "grammar": {
        "grammar",
        "sentence",
        "syntax",
        "verb",
        "noun",
        "adjective",
        "adverb",
        "tense",
        "punctuation"
    },

    "vocabulary": {
        "vocabulary",
        "word",
        "meaning",
        "definition",
        "synonym",
        "antonym",
        "lexical"
    },

    "research": {
        "research",
        "source",
        "citation",
        "evidence",
        "reference",
        "academic",
        "investigate"
    },

    "analysis": {
        "analysis",
        "analyze",
        "analyse",
        "examine",
        "compare",
        "contrast",
        "differentiate",
        "relationship",
        "evidence"
    }
}

# ============================================================
# TEXT FUNCTIONS
# ============================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text).lower()

    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("’", "'")
    text = text.replace("“", '"')
    text = text.replace("”", '"')

    text = re.sub(
        r"[^a-z0-9\s-]",
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

    text = normalize_text(text)

    words = re.findall(
        r"\b[a-z]+\b",
        text
    )

    return {
        word
        for word in words
        if word not in STOP_WORDS
        and len(word) > 2
    }


def expand_concepts(text):

    normalized = normalize_text(text)

    concepts = set(
        tokenize(normalized)
    )

    for concept_name, related_words in CONCEPT_GROUPS.items():

        related_tokens = set()

        for item in related_words:

            related_tokens.update(
                tokenize(item)
            )

        if (
            concept_name in normalized
            or concepts.intersection(
                related_tokens
            )
        ):

            concepts.update(
                related_tokens
            )

    return concepts


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    text = normalize_text(question)

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if " " in verb:

                if verb in text:
                    scores[level] += 4

            else:

                pattern = (
                    r"\b"
                    + re.escape(verb)
                    + r"(?:s|ed|ing)?\b"
                )

                if re.search(
                    pattern,
                    text
                ):

                    scores[level] += 3

    # Question structures
    if "why" in text:
        scores["Analyze"] += 3

    if "how" in text:
        scores["Understand"] += 1

    if "compare and contrast" in text:
        scores["Analyze"] += 6

    if "justify" in text:
        scores["Evaluate"] += 6

    if "design" in text:
        scores["Create"] += 6

    if "evaluate" in text:
        scores["Evaluate"] += 6

    if "create" in text:
        scores["Create"] += 6

    best_level = max(
        scores,
        key=scores.get
    )

    if scores[best_level] == 0:

        return (
            "Needs Review",
            scores
        )

    return (
        best_level,
        scores
    )


# ============================================================
# BLOOM ALIGNMENT
# ============================================================

def bloom_alignment(
    intended,
    detected
):

    if detected == "Needs Review":
        return 40

    if (
        intended not in BLOOM_RANK
        or detected not in BLOOM_RANK
    ):
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
# CLO/PLO MATCHING
# ============================================================

def outcome_similarity(
    question,
    outcome
):

    if not question or not outcome:
        return 0, []

    q_text = normalize_text(
        question
    )

    o_text = normalize_text(
        outcome
    )

    q_words = expand_concepts(
        q_text
    )

    o_words = expand_concepts(
        o_text
    )

    if not q_words or not o_words:
        return 0, []

    intersection = (
        q_words.intersection(
            o_words
        )
    )

    direct_q = tokenize(
        q_text
    )

    direct_o = tokenize(
        o_text
    )

    direct_overlap = (
        direct_q.intersection(
            direct_o
        )
    )

    # Dice coefficient
    dice = (
        2 * len(intersection)
    ) / (
        len(q_words)
        +
        len(o_words)
    )

    score = dice * 100

    # Direct overlap bonus
    if direct_overlap:

        score += min(
            25,
            len(direct_overlap) * 7
        )

    # Important phrase matching
    outcome_phrases = re.findall(
        r"\b[a-z]+(?:\s+[a-z]+){1,4}\b",
        o_text
    )

    for phrase in outcome_phrases:

        if (
            len(phrase) > 8
            and phrase in q_text
        ):

            score += 15

    score = min(
        100,
        score
    )

    evidence = sorted(
        intersection,
        key=lambda x: (
            -len(x),
            x
        )
    )

    return (
        round(score, 1),
        evidence[:10]
    )


# ============================================================
# ALIGNMENT LABEL
# ============================================================

def alignment_label(score):

    if score >= 70:
        return "Strong"

    if score >= 50:
        return "Good"

    if score >= 30:
        return "Partial"

    if score > 0:
        return "Weak"

    return "Needs Review"


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

    text = text.replace(
        "\r",
        "\n"
    )

    questions = []

    pattern = re.compile(
        r"(?:^|\n)"
        r"\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]"
        r"\s*"
        r"(.*?)"
        r"(?="
        r"\n\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"\d{1,3}"
        r"\s*[\.\):\-]"
        r"|\Z)",
        re.IGNORECASE |
        re.DOTALL
    )

    matches = pattern.findall(
        text
    )

    for number, question in matches:

        clean = re.sub(
            r"\s+",
            " ",
            question
        ).strip()

        if len(clean) >= 8:

            questions.append(
                {
                    "number": int(number),
                    "text": clean
                }
            )

    # Fallback
    if not questions:

        for i, line in enumerate(
            text.split("\n")
        ):

            clean = line.strip()

            if (
                len(clean) >= 10
                and clean.endswith("?")
            ):

                questions.append(
                    {
                        "number": i + 1,
                        "text": clean
                    }
                )

    return questions


# ============================================================
# FILE READER
# ============================================================

def extract_text_from_file(
    uploaded_file
):

    filename = uploaded_file.name.lower()

    data = uploaded_file.read()

    # TXT
    if filename.endswith(".txt"):

        return data.decode(
            "utf-8",
            errors="ignore"
        )

    # DOCX
    if filename.endswith(".docx"):

        try:

            from docx import Document

            document = Document(
                io.BytesIO(data)
            )

            paragraphs = []

            for paragraph in document.paragraphs:

                if paragraph.text.strip():

                    paragraphs.append(
                        paragraph.text
                    )

            return "\n".join(
                paragraphs
            )

        except Exception as e:

            st.error(
                f"Could not read DOCX: {e}"
            )

            return ""

    # PDF
    if filename.endswith(".pdf"):

        try:

            from pypdf import PdfReader

            reader = PdfReader(
                io.BytesIO(data)
            )

            pages = []

            for page in reader.pages:

                text = page.extract_text()

                if text:
                    pages.append(text)

            extracted = "\n".join(
                pages
            )

            if extracted.strip():

                return extracted

        except Exception:
            pass

        # OCR fallback
        try:

            import pytesseract
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(
                data
            )

            pages = []

            for image in images:

                pages.append(
                    pytesseract.image_to_string(
                        image
                    )
                )

            return "\n".join(
                pages
            )

        except Exception as e:

            st.error(
                "Could not read PDF.\n\n"
                f"Error: {e}\n\n"
                "For normal PDFs install pypdf. "
                "For scanned PDFs install "
                "pytesseract and pdf2image."
            )

            return ""

    # EXCEL
    if (
        filename.endswith(".xlsx")
        or filename.endswith(".xls")
    ):

        try:

            excel = pd.ExcelFile(
                io.BytesIO(data)
            )

            all_text = []

            for sheet in excel.sheet_names:

                df = pd.read_excel(
                    excel,
                    sheet_name=sheet
                )

                all_text.append(
                    f"Sheet: {sheet}"
                )

                all_text.append(
                    df.to_string(
                        index=False
                    )
                )

            return "\n".join(
                all_text
            )

        except Exception as e:

            st.error(
                f"Could not read Excel: {e}"
            )

            return ""

    return ""


# ============================================================
# PAGE TITLE
# ============================================================

st.title(
    "🎓 OBE Quiz Analyzer"
)

st.write(
    "Enter your CLOs, PLOs and intended Bloom level, "
    "upload a quiz, and receive numerical, graphical "
    "and actionable OBE alignment feedback."
)

st.divider()


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header(
    "1️⃣ Assessment Information"
)

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course Name",
        placeholder="e.g., English I"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="e.g., Quiz 1"
    )


# ============================================================
# 2. CLOs
# ============================================================

st.header(
    "2️⃣ Enter CLOs"
)

num_clos = st.number_input(
    "Number of CLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

clos = []

for i in range(
    int(num_clos)
):

    col1, col2 = st.columns(
        [1, 5]
    )

    with col1:

        code = st.text_input(
            f"CLO {i + 1}",
            value=f"CLO{i + 1}",
            key=f"clo_code_{i}"
        )

    with col2:

        description = st.text_input(
            f"CLO {i + 1} Description",
            placeholder=(
                "e.g., Analyze patterns of organization "
                "in written texts."
            ),
            key=f"clo_description_{i}"
        )

    if description.strip():

        clos.append(
            {
                "code": code.strip(),
                "text": description.strip()
            }
        )


# ============================================================
# 3. PLOs
# ============================================================

st.header(
    "3️⃣ Enter PLOs"
)

num_plos = st.number_input(
    "Number of PLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

plos = []

for i in range(
    int(num_plos)
):

    col1, col2 = st.columns(
        [1, 5]
    )

    with col1:

        code = st.text_input(
            f"PLO {i + 1}",
            value=f"PLO{i + 1}",
            key=f"plo_code_{i}"
        )

    with col2:

        description = st.text_input(
            f"PLO {i + 1} Description",
            placeholder=(
                "e.g., Demonstrate effective "
                "communication skills."
            ),
            key=f"plo_description_{i}"
        )

    if description.strip():

        plos.append(
            {
                "code": code.strip(),
                "text": description.strip()
            }
        )


# ============================================================
# 4. BLOOM
# ============================================================

st.header(
    "4️⃣ Intended Bloom's Level"
)

intended_bloom = st.selectbox(
    "Select the intended cognitive level",
    BLOOM_LEVELS
)

st.info(
    f"Selected Bloom level: **{intended_bloom}**"
)


# ============================================================
# 5. UPLOAD
# ============================================================

st.header(
    "5️⃣ Upload Quiz"
)

uploaded_file = st.file_uploader(
    "Upload Quiz",
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

st.divider()

analyze = st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
)


# ============================================================
# ANALYSIS
# ============================================================

if analyze:

    errors = []

    if not course_name.strip():

        errors.append(
            "Enter the course name."
        )

    if not assessment_name.strip():

        errors.append(
            "Enter the assessment name."
        )

    if not clos:

        errors.append(
            "Enter at least one CLO."
        )

    if not plos:

        errors.append(
            "Enter at least one PLO."
        )

    if uploaded_file is None:

        errors.append(
            "Upload a quiz file."
        )

    if errors:

        for error in errors:
            st.error(error)

        st.stop()

    with st.spinner(
        "Reading and analyzing the quiz..."
    ):

        quiz_text = extract_text_from_file(
            uploaded_file
        )

    if not quiz_text.strip():

        st.error(
            "No readable text was found in the quiz."
        )

        st.stop()

    questions = extract_questions(
        quiz_text
    )

    if not questions:

        st.error(
            "No numbered questions were detected. "
            "Use formats such as 1., 2., 3. or Q1., Q2., Q3."
        )

        st.stop()

    results = []

    for question in questions:

        q_text = question["text"]

        # ----------------------------------------------------
        # BLOOM
        # ----------------------------------------------------

        detected_bloom, bloom_scores = detect_bloom(
            q_text
        )

        bloom_score = bloom_alignment(
            intended_bloom,
            detected_bloom
        )

        # ----------------------------------------------------
        # CLO
        # ----------------------------------------------------

        clo_matches = []

        for clo in clos:

            score, evidence = outcome_similarity(
                q_text,
                clo["text"]
            )

            clo_matches.append(
                {
                    "code": clo["code"],
                    "score": score,
                    "evidence": evidence
                }
            )

        clo_matches.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        best_clo = clo_matches[0]

        # ----------------------------------------------------
        # PLO
        # ----------------------------------------------------

        plo_matches = []

        for plo in plos:

            score, evidence = outcome_similarity(
                q_text,
                plo["text"]
            )

            plo_matches.append(
                {
                    "code": plo["code"],
                    "score": score,
                    "evidence": evidence
                }
            )

        plo_matches.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        best_plo = plo_matches[0]

        # ----------------------------------------------------
        # QUESTION FEEDBACK
        # ----------------------------------------------------

        feedback = []

        if bloom_score == 100:

            feedback.append(
                "Bloom level matches the intended level."
            )

        elif bloom_score == 65:

            feedback.append(
                f"The detected Bloom level is close to "
                f"the intended {intended_bloom} level."
            )

        else:

            feedback.append(
                f"Revise the question so its cognitive "
                f"demand clearly targets {intended_bloom}."
            )

        if best_clo["score"] >= 70:

            feedback.append(
                f"Strong alignment with {best_clo['code']}."
            )

        elif best_clo["score"] >= 50:

            feedback.append(
                f"Improve the direct connection with "
                f"{best_clo['code']}."
            )

        else:

            feedback.append(
                f"Revise the question to directly measure "
                f"{best_clo['code']}."
            )

        if best_plo["score"] >= 70:

            feedback.append(
                f"Strong alignment with {best_plo['code']}."
            )

        elif best_plo["score"] >= 50:

            feedback.append(
                f"Strengthen the connection with "
                f"{best_plo['code']}."
            )

        else:

            feedback.append(
                f"Review the relationship between this question "
                f"and {best_plo['code']}."
            )

        combined = (
            best_clo["score"] * 0.35
            +
            best_plo["score"] * 0.25
            +
            bloom_score * 0.40
        )

        results.append(
            {
                "Question No.": question["number"],
                "Question": q_text,
                "Intended Bloom": intended_bloom,
                "Detected Bloom": detected_bloom,
                "Bloom Alignment %": bloom_score,
                "Best CLO": best_clo["code"],
                "CLO Alignment %": best_clo["score"],
                "Best PLO": best_plo["code"],
                "PLO Alignment %": best_plo["score"],
                "Combined Alignment %": round(
                    combined,
                    1
                ),
                "Feedback": " ".join(
                    feedback
                )
            }
        )

    results_df = pd.DataFrame(
        results
    )

    st.session_state["results"] = results_df


# ============================================================
# SHOW RESULTS
# ============================================================

if "results" in st.session_state:

    results_df = st.session_state["results"]

    st.divider()

    st.header(
        "📊 OBE Alignment Results"
    )

    st.info(
        "This analysis measures the alignment of the uploaded "
        "quiz questions with the entered CLOs, PLOs and intended "
        "Bloom level. It does not represent actual student "
        "attainment until student marks are available."
    )

    # ========================================================
    # MAIN NUMBERS
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

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "CLO Alignment",
            f"{avg_clo:.1f}%"
        )

    with col2:

        st.metric(
            "PLO Alignment",
            f"{avg_plo:.1f}%"
        )

    with col3:

        st.metric(
            "Bloom Alignment",
            f"{avg_bloom:.1f}%"
        )

    with col4:

        st.metric(
            "Overall Alignment",
            f"{overall:.1f}%"
        )

    # ========================================================
    # OVERALL GRAPH
    # ========================================================

    st.subheader(
        "📈 Overall Alignment Graph"
    )

    overall_df = pd.DataFrame(
        {
            "Area": [
                "CLO",
                "PLO",
                "Bloom",
                "Overall"
            ],
            "Alignment %": [
                round(avg_clo, 1),
                round(avg_plo, 1),
                round(avg_bloom, 1),
                round(overall, 1)
            ]
        }
    )

    st.bar_chart(
        overall_df.set_index(
            "Area"
        )
    )

    # ========================================================
    # CLO RESULTS
    # ========================================================

    st.divider()

    st.subheader(
        "🎯 CLO Alignment Analysis"
    )

    clo_rows = []

    for clo in clos:

        mapped = results_df[
            results_df["Best CLO"]
            == clo["code"]
        ]

        count = len(mapped)

        if count:

            score = mapped[
                "CLO Alignment %"
            ].mean()

        else:

            score = 0

        coverage = (
            count /
            len(results_df)
        ) * 100

        clo_rows.append(
            {
                "CLO": clo["code"],
                "Questions": count,
                "Alignment %": round(
                    score,
                    1
                ),
                "Coverage %": round(
                    coverage,
                    1
                ),
                "Status": alignment_label(
                    score
                )
            }
        )

    clo_df = pd.DataFrame(
        clo_rows
    )

    c1, c2 = st.columns(
        [1.3, 1]
    )

    with c1:

        st.dataframe(
            clo_df,
            use_container_width=True,
            hide_index=True
        )

    with c2:

        st.bar_chart(
            clo_df.set_index(
                "CLO"
            )[["Alignment %"]]
        )

    # ========================================================
    # PLO RESULTS
    # ========================================================

    st.divider()

    st.subheader(
        "🎯 PLO Alignment Analysis"
    )

    plo_rows = []

    for plo in plos:

        mapped = results_df[
            results_df["Best PLO"]
            == plo["code"]
        ]

        count = len(mapped)

        if count:

            score = mapped[
                "PLO Alignment %"
            ].mean()

        else:

            score = 0

        coverage = (
            count /
            len(results_df)
        ) * 100

        plo_rows.append(
            {
                "PLO": plo["code"],
                "Questions": count,
                "Alignment %": round(
                    score,
                    1
                ),
                "Coverage %": round(
                    coverage,
                    1
                ),
                "Status": alignment_label(
                    score
                )
            }
        )

    plo_df = pd.DataFrame(
        plo_rows
    )

    c1, c2 = st.columns(
        [1.3, 1]
    )

    with c1:

        st.dataframe(
            plo_df,
            use_container_width=True,
            hide_index=True
        )

    with c2:

        st.bar_chart(
            plo_df.set_index(
                "PLO"
            )[["Alignment %"]]
        )

    # ========================================================
    # BLOOM RESULTS
    # ========================================================

    st.divider()

    st.subheader(
        "🧠 Bloom's Taxonomy Analysis"
    )

    bloom_counts = (
        results_df[
            "Detected Bloom"
        ]
        .value_counts()
        .reindex(
            BLOOM_LEVELS,
            fill_value=0
        )
    )

    bloom_df = pd.DataFrame(
        {
            "Questions": bloom_counts
        }
    )

    c1, c2 = st.columns(
        [1, 1]
    )

    with c1:

        st.bar_chart(
            bloom_df
        )

    with c2:

        bloom_rows = []

        for level in BLOOM_LEVELS:

            count = int(
                bloom_counts[level]
            )

            percentage = (
                count /
                len(results_df)
            ) * 100

            bloom_rows.append(
                {
                    "Bloom Level": level,
                    "Questions": count,
                    "Distribution %": round(
                        percentage,
                        1
                    )
                }
            )

        bloom_summary = pd.DataFrame(
            bloom_rows
        )

        st.dataframe(
            bloom_summary,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # AUTOMATIC IMPROVEMENT SUGGESTIONS
    # ========================================================

    st.divider()

    st.header(
        "💡 Tool Suggestions to Improve Alignment"
    )

    st.write(
        "The following recommendations are automatically "
        "generated from the alignment results."
    )

    suggestions = []

    # --------------------------------------------------------
    # CLO SUGGESTIONS
    # --------------------------------------------------------

    for _, row in clo_df.iterrows():

        if row["Questions"] == 0:

            suggestions.append(
                f"🎯 **{row['CLO']} is not adequately assessed.** "
                f"No question has been mapped to this CLO. "
                f"Add or revise at least one question so that it "
                f"directly measures the knowledge or skill stated "
                f"in {row['CLO']}."
            )

        elif row["Alignment %"] < 50:

            suggestions.append(
                f"🎯 **Improve {row['CLO']} alignment "
                f"({row['Alignment %']:.1f}%).** "
                f"Revise the wording and task of the questions "
                f"mapped to this CLO so they directly measure "
                f"the CLO rather than only mentioning related content."
            )

        elif row["Coverage %"] < 20:

            suggestions.append(
                f"🎯 **Increase {row['CLO']} coverage.** "
                f"Although its alignment is reasonable, only "
                f"{row['Coverage %']:.1f}% of the quiz questions "
                f"currently contribute to this CLO."
            )

    # --------------------------------------------------------
    # PLO SUGGESTIONS
    # --------------------------------------------------------

    for _, row in plo_df.iterrows():

        if row["Questions"] == 0:

            suggestions.append(
                f"🎯 **{row['PLO']} has no direct assessment evidence.** "
                f"Review the CLO-to-PLO relationship and include "
                f"questions that provide evidence for this PLO."
            )

        elif row["Alignment %"] < 50:

            suggestions.append(
                f"🎯 **Improve {row['PLO']} alignment "
                f"({row['Alignment %']:.1f}%).** "
                f"Strengthen the connection between the assessed "
                f"CLO and the ability described by this PLO."
            )

        elif row["Coverage %"] < 20:

            suggestions.append(
                f"🎯 **Increase {row['PLO']} assessment coverage.** "
                f"Only {row['Coverage %']:.1f}% of questions currently "
                f"contribute evidence toward this PLO."
            )

    # --------------------------------------------------------
    # BLOOM SUGGESTIONS
    # --------------------------------------------------------

    mismatched_bloom = results_df[
        results_df[
            "Bloom Alignment %"
        ] < 65
    ]

    if len(mismatched_bloom) > 0:

        detected = (
            results_df[
                "Detected Bloom"
            ]
            .value_counts()
        )

        most_common = detected.index[0]

        suggestions.append(
            f"🧠 **Improve Bloom alignment.** "
            f"{len(mismatched_bloom)} of "
            f"{len(results_df)} questions do not strongly match "
            f"the intended **{intended_bloom}** level. "
            f"The most frequently detected level is "
            f"**{most_common}**. Revise the action verbs and "
            f"cognitive tasks to better target {intended_bloom}."
        )

    else:

        suggestions.append(
            f"🧠 **Bloom alignment is strong.** "
            f"The questions generally target the intended "
            f"**{intended_bloom}** cognitive level."
        )

    # --------------------------------------------------------
    # WEAK QUESTIONS
    # --------------------------------------------------------

    weakest = results_df.sort_values(
        "Combined Alignment %"
    ).head(3)

    weak_numbers = [
        str(int(number))
        for number in weakest[
            "Question No."
        ]
    ]

    if weak_numbers:

        suggestions.append(
            "📝 **Priority revision:** "
            f"Questions {', '.join(weak_numbers)} have the "
            f"lowest combined alignment. Review these questions "
            f"first because improving them is likely to strengthen "
            f"the overall quiz alignment."
        )

    # --------------------------------------------------------
    # OVERALL SUGGESTION
    # --------------------------------------------------------

    if overall < 50:

        suggestions.append(
            f"🔴 **Overall improvement needed.** "
            f"The quiz has an overall alignment of "
            f"**{overall:.1f}%**. Revise the lowest-scoring "
            f"questions first and ensure that every question "
            f"has a clear CLO, PLO contribution and appropriate "
            f"Bloom cognitive demand."
        )

    elif overall < 70:

        suggestions.append(
            f"🟠 **Moderate alignment.** "
            f"The quiz has an overall alignment of "
            f"**{overall:.1f}%**. Focus on questions with weak "
            f"CLO/PLO alignment and Bloom mismatches."
        )

    else:

        suggestions.append(
            f"🟢 **Good overall alignment.** "
            f"The quiz has an overall alignment of "
            f"**{overall:.1f}%**. Minor refinement can focus on "
            f"individual CLO/PLO coverage and precise Bloom-level "
            f"question wording."
        )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    for suggestion in suggestions:

        st.info(
            suggestion
        )

    # ========================================================
    # QUESTION-SPECIFIC SUGGESTIONS
    # ========================================================

    st.divider()

    st.header(
        "🛠️ Question-Specific Revision Suggestions"
    )

    for _, row in weakest.iterrows():

        question_no = int(
            row["Question No."]
        )

        with st.expander(
            f"Question {question_no}"
        ):

            st.write(
                f"**Question:** {row['Question']}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "CLO",
                    f"{row['CLO Alignment %']:.1f}%"
                )

            with c2:

                st.metric(
                    "PLO",
                    f"{row['PLO Alignment %']:.1f}%"
                )

            with c3:

                st.metric(
                    "Bloom",
                    f"{row['Bloom Alignment %']:.1f}%"
                )

            st.write(
                f"**Detected Bloom:** "
                f"{row['Detected Bloom']}"
            )

            st.write(
                f"**Intended Bloom:** "
                f"{row['Intended Bloom']}"
            )

            st.write(
                f"**Best CLO:** "
                f"{row['Best CLO']}"
            )

            st.write(
                f"**Best PLO:** "
                f"{row['Best PLO']}"
            )

            # Bloom suggestion
            if row["Bloom Alignment %"] < 65:

                st.warning(
                    f"🧠 **Bloom revision:** Change the question "
                    f"so that it requires students to perform the "
                    f"thinking associated with "
                    f"**{row['Intended Bloom']}** rather than "
                    f"**{row['Detected Bloom']}**."
                )

            # CLO suggestion
            if row["CLO Alignment %"] < 50:

                st.warning(
                    f"🎯 **CLO revision:** The question has only "
                    f"{row['CLO Alignment %']:.1f}% alignment with "
                    f"**{row['Best CLO']}**. Make the question "
                    f"directly assess the knowledge or skill "
                    f"described in this CLO."
                )

            # PLO suggestion
            if row["PLO Alignment %"] < 50:

                st.warning(
                    f"🎯 **PLO revision:** The question has only "
                    f"{row['PLO Alignment %']:.1f}% alignment with "
                    f"**{row['Best PLO']}**. Check whether the "
                    f"question provides clear evidence of the "
                    f"ability represented by this PLO."
                )

            if (
                row["CLO Alignment %"] >= 70
                and row["PLO Alignment %"] >= 70
                and row["Bloom Alignment %"] == 100
            ):

                st.success(
                    "✅ This question is strongly aligned "
                    "with the CLO, PLO and intended Bloom level."
                )

            st.write(
                f"**Tool feedback:** "
                f"{row['Feedback']}"
            )

    # ========================================================
    # COMPLETE RESULTS
    # ========================================================

    st.divider()

    st.header(
        "📋 Complete Question Analysis"
    )

    st.dataframe(
        results_df,
        use_container_width=True,
        hide_index=True,
        height=500
    )

    # ========================================================
    # DOWNLOAD
    # ========================================================

    st.divider()

    st.header(
        "📥 Download Results"
    )

    csv = results_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download OBE Analysis CSV",
        data=csv,
        file_name=(
            f"{assessment_name.replace(' ', '_')}"
            "_OBE_Analysis.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )
