import streamlit as st
import pandas as pd
import re
import io
import os
from collections import Counter

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Analyzer",
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
        "define", "list", "name", "identify", "state",
        "recall", "recognize", "recognise", "mention",
        "label", "select", "match", "repeat"
    ],
    "Understand": [
        "explain", "summarize", "summarise", "interpret",
        "discuss", "classify", "describe", "outline",
        "paraphrase", "illustrate", "translate", "clarify"
    ],
    "Apply": [
        "apply", "use", "demonstrate", "solve", "calculate",
        "implement", "execute", "perform", "practice",
        "show", "compute"
    ],
    "Analyze": [
        "analyze", "analyse", "examine", "compare",
        "contrast", "differentiate", "distinguish",
        "investigate", "categorize", "categorise",
        "break down", "deconstruct", "inspect"
    ],
    "Evaluate": [
        "evaluate", "justify", "critique", "assess",
        "judge", "defend", "appraise", "recommend",
        "argue", "validate", "rate", "review"
    ],
    "Create": [
        "create", "design", "develop", "formulate",
        "produce", "compose", "plan", "propose",
        "generate", "construct", "develop", "invent"
    ]
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in",
    "on", "for", "with", "from", "by", "is", "are",
    "was", "were", "be", "as", "at", "that", "this",
    "these", "those", "it", "its", "their", "there",
    "which", "what", "when", "where", "who", "whom",
    "why", "how", "you", "your", "they", "them",
    "he", "she", "his", "her", "we", "our", "can",
    "could", "would", "should", "will", "may", "might",
    "do", "does", "did", "into", "than", "then",
    "using", "use", "given", "following", "question"
}

# ============================================================
# CONCEPT GROUPS
# ============================================================

CONCEPT_GROUPS = {
    "main idea": {
        "main", "idea", "central", "point", "message",
        "purpose", "theme", "key idea", "central idea"
    },
    "reading comprehension": {
        "reading", "comprehension", "understanding",
        "interpret", "meaning", "text", "passage",
        "paragraph", "content"
    },
    "pattern organization": {
        "pattern", "organization", "organisation",
        "structure", "cause", "effect", "compare",
        "contrast", "sequence", "chronological",
        "problem", "solution", "classification"
    },
    "paraphrasing": {
        "paraphrase", "paraphrasing", "rewrite",
        "restate", "restatement", "reword", "meaning"
    },
    "author purpose": {
        "author", "purpose", "intent", "intention",
        "reason", "inform", "persuade", "entertain"
    },
    "tone": {
        "tone", "attitude", "feeling", "mood",
        "author attitude", "writer attitude"
    },
    "writing": {
        "writing", "write", "essay", "paragraph",
        "composition", "draft", "revision", "revise"
    },
    "critical thinking": {
        "critical", "thinking", "reasoning", "argument",
        "evidence", "claim", "logic", "analysis",
        "evaluate", "judgment", "judgement"
    },
    "communication": {
        "communication", "communicate", "speaking",
        "listening", "presentation", "oral", "verbal"
    },
    "grammar": {
        "grammar", "sentence", "syntax", "verb",
        "noun", "adjective", "adverb", "tense",
        "punctuation"
    },
    "vocabulary": {
        "vocabulary", "word", "meaning", "definition",
        "synonym", "antonym", "lexical"
    },
    "research": {
        "research", "source", "citation", "evidence",
        "reference", "academic", "investigate"
    },
    "analysis": {
        "analysis", "analyze", "analyse", "examine",
        "compare", "contrast", "differentiate",
        "relationship", "evidence"
    }
}

# ============================================================
# TEXT NORMALIZATION
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

    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize(text):
    text = normalize_text(text)

    words = re.findall(r"\b[a-z]+\b", text)

    return {
        word
        for word in words
        if word not in STOP_WORDS and len(word) > 2
    }


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):
    text = normalize_text(question)

    scores = {}

    for level, verbs in BLOOM_VERBS.items():
        score = 0

        for verb in verbs:

            if " " in verb:
                if verb in text:
                    score += 3
            else:
                pattern = r"\b" + re.escape(verb) + r"(?:s|ed|ing)?\b"

                if re.search(pattern, text):
                    score += 2

        scores[level] = score

    # Special question patterns
    if "why" in text:
        scores["Analyze"] += 2

    if "how" in text:
        scores["Understand"] += 1

    if "compare and contrast" in text:
        scores["Analyze"] += 5

    if "justify" in text:
        scores["Evaluate"] += 5

    if "design" in text:
        scores["Create"] += 5

    if "create" in text:
        scores["Create"] += 5

    if "evaluate" in text:
        scores["Evaluate"] += 5

    best_level = max(scores, key=scores.get)

    if scores[best_level] == 0:
        return "Needs Review", scores

    return best_level, scores


# ============================================================
# BLOOM ALIGNMENT
# ============================================================

def bloom_alignment(intended, detected):

    if detected == "Needs Review":
        return 40

    if intended not in BLOOM_RANK:
        return 0

    if detected not in BLOOM_RANK:
        return 40

    difference = abs(
        BLOOM_RANK[intended] -
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
# CONCEPT EXPANSION
# ============================================================

def expand_concepts(text):

    text_normalized = normalize_text(text)

    concepts = set(tokenize(text))

    for concept_name, related_words in CONCEPT_GROUPS.items():

        concept_tokens = set()

        for item in related_words:
            concept_tokens.update(tokenize(item))

        if (
            concept_name in text_normalized
            or len(concepts.intersection(concept_tokens)) > 0
        ):
            concepts.update(concept_tokens)

    return concepts


# ============================================================
# OUTCOME SIMILARITY
# ============================================================

def outcome_similarity(question, outcome):

    if not question or not outcome:
        return 0, []

    question_text = normalize_text(question)
    outcome_text = normalize_text(outcome)

    q_words = expand_concepts(question_text)
    o_words = expand_concepts(outcome_text)

    if not q_words or not o_words:
        return 0, []

    intersection = q_words.intersection(o_words)

    direct_q = tokenize(question_text)
    direct_o = tokenize(outcome_text)

    direct_overlap = direct_q.intersection(direct_o)

    # Dice similarity
    dice = (
        (2 * len(intersection)) /
        (len(q_words) + len(o_words))
    )

    score = dice * 100

    # Direct word overlap bonus
    if direct_overlap:
        score += min(20, len(direct_overlap) * 6)

    # Phrase matching
    outcome_phrases = [
        phrase.strip()
        for phrase in re.split(r"[,;:]", outcome_text)
        if len(phrase.strip()) > 4
    ]

    for phrase in outcome_phrases:
        if phrase in question_text:
            score += 15

    score = min(100, score)

    evidence = sorted(
        list(intersection),
        key=lambda x: (-len(x), x)
    )

    return round(score, 1), evidence[:8]


# ============================================================
# ALIGNMENT LABEL
# ============================================================

def alignment_label(score):

    if score >= 70:
        return "Strong Alignment"

    if score >= 50:
        return "Good Alignment"

    if score >= 30:
        return "Partial Alignment"

    if score > 0:
        return "Weak Alignment"

    return "Needs Review"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    if not text:
        return []

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    questions = []

    # Pattern:
    # 1. Question
    # Q1. Question
    # Q1: Question
    # 1) Question
    pattern = re.compile(
        r"(?:^|\n)\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s*"
        r"(.*?)(?="
        r"\n\s*(?:Q(?:uestion)?\s*)?\d{1,3}\s*[\.\):\-]"
        r"|\Z)",
        re.IGNORECASE | re.DOTALL
    )

    matches = pattern.findall(text)

    for number, question in matches:

        clean = re.sub(
            r"\s+",
            " ",
            question
        ).strip()

        clean = re.sub(
            r"\s*\n\s*",
            " ",
            clean
        )

        if len(clean) >= 8:
            questions.append(
                {
                    "number": int(number),
                    "text": clean
                }
            )

    # Fallback: split by lines if numbered pattern failed
    if not questions:

        lines = text.split("\n")

        for i, line in enumerate(lines):

            clean = line.strip()

            if len(clean) < 10:
                continue

            if clean.endswith("?"):

                questions.append(
                    {
                        "number": i + 1,
                        "text": clean
                    }
                )

    return questions


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_text_from_file(uploaded_file):

    filename = uploaded_file.name.lower()
    data = uploaded_file.read()

    # TXT
    if filename.endswith(".txt"):

        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return str(data)

    # DOCX
    if filename.endswith(".docx"):

        try:
            from docx import Document

            document = Document(
                io.BytesIO(data)
            )

            paragraphs = [
                p.text
                for p in document.paragraphs
                if p.text.strip()
            ]

            return "\n".join(paragraphs)

        except Exception as e:

            st.error(
                f"Could not read DOCX file: {e}"
            )

            return ""

    # PDF
    if filename.endswith(".pdf"):

        # First attempt: pypdf
        try:

            from pypdf import PdfReader

            reader = PdfReader(
                io.BytesIO(data)
            )

            pages = []

            for page in reader.pages:

                page_text = page.extract_text()

                if page_text:
                    pages.append(page_text)

            text = "\n".join(pages)

            if text.strip():
                return text

        except Exception:
            pass

        # OCR fallback
        try:

            import pytesseract
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(data)

            pages = []

            for image in images:

                page_text = pytesseract.image_to_string(
                    image
                )

                pages.append(page_text)

            return "\n".join(pages)

        except Exception as e:

            st.error(
                "Could not read PDF. "
                "Install pypdf for text PDFs or "
                "pytesseract + pdf2image for scanned PDFs.\n\n"
                f"Error: {e}"
            )

            return ""

    # Excel
    if filename.endswith(".xlsx") or filename.endswith(".xls"):

        try:

            excel_file = pd.ExcelFile(
                io.BytesIO(data)
            )

            all_text = []

            for sheet in excel_file.sheet_names:

                df = pd.read_excel(
                    excel_file,
                    sheet_name=sheet
                )

                all_text.append(
                    f"Sheet: {sheet}"
                )

                all_text.append(
                    df.to_string(index=False)
                )

            return "\n".join(all_text)

        except Exception as e:

            st.error(
                f"Could not read Excel file: {e}"
            )

            return ""

    st.error(
        "Unsupported file type."
    )

    return ""


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None


# ============================================================
# TITLE
# ============================================================

st.title("🎓 OBE Quiz Analyzer")

st.caption(
    "Upload a quiz and evaluate its alignment with the "
    "Course Learning Outcomes (CLOs), Program Learning Outcomes (PLOs), "
    "and Bloom's Taxonomy."
)

st.divider()


# ============================================================
# STEP 1 — BASIC INFORMATION
# ============================================================

st.header("1️⃣ Assessment Information")

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
# STEP 2 — CLO INPUT
# ============================================================

st.header("2️⃣ Enter Course Learning Outcomes (CLOs)")

st.info(
    "Enter the CLOs that this quiz is designed to assess. "
    "Add as many CLOs as required."
)

num_clos = st.number_input(
    "Number of CLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

clos = []

for i in range(int(num_clos)):

    col1, col2 = st.columns([1, 5])

    with col1:

        clo_code = st.text_input(
            f"CLO {i+1} Code",
            value=f"CLO{i+1}",
            key=f"clo_code_{i}"
        )

    with col2:

        clo_text = st.text_input(
            f"CLO {i+1} Description",
            placeholder="e.g., Analyze patterns of organization in written texts.",
            key=f"clo_text_{i}"
        )

    if clo_text.strip():

        clos.append(
            {
                "code": clo_code.strip() or f"CLO{i+1}",
                "text": clo_text.strip()
            }
        )


# ============================================================
# STEP 3 — PLO INPUT
# ============================================================

st.header("3️⃣ Enter Program Learning Outcomes (PLOs)")

st.info(
    "Enter the PLOs against which the CLOs and assessment are mapped."
)

num_plos = st.number_input(
    "Number of PLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

plos = []

for i in range(int(num_plos)):

    col1, col2 = st.columns([1, 5])

    with col1:

        plo_code = st.text_input(
            f"PLO {i+1} Code",
            value=f"PLO{i+1}",
            key=f"plo_code_{i}"
        )

    with col2:

        plo_text = st.text_input(
            f"PLO {i+1} Description",
            placeholder="e.g., Demonstrate effective communication skills.",
            key=f"plo_text_{i}"
        )

    if plo_text.strip():

        plos.append(
            {
                "code": plo_code.strip() or f"PLO{i+1}",
                "text": plo_text.strip()
            }
        )


# ============================================================
# STEP 4 — BLOOM LEVEL
# ============================================================

st.header("4️⃣ Select Intended Bloom's Level")

intended_bloom = st.selectbox(
    "What Bloom's Taxonomy level is intended for this quiz?",
    BLOOM_LEVELS
)

st.write(
    f"**Selected cognitive level:** {intended_bloom}"
)

bloom_description = {
    "Remember": "Recall facts, terms, definitions, or basic information.",
    "Understand": "Explain, summarize, interpret, or describe concepts.",
    "Apply": "Use knowledge to solve or perform a task.",
    "Analyze": "Break information into parts and examine relationships.",
    "Evaluate": "Judge, justify, critique, or defend a position.",
    "Create": "Design, formulate, construct, or produce something new."
}

st.caption(
    bloom_description[intended_bloom]
)


# ============================================================
# STEP 5 — QUIZ UPLOAD
# ============================================================

st.header("5️⃣ Upload Quiz")

uploaded_file = st.file_uploader(
    "Upload the quiz file",
    type=[
        "pdf",
        "docx",
        "txt",
        "xlsx",
        "xls"
    ],
    help="Supported formats: PDF, DOCX, TXT, XLSX and XLS."
)


# ============================================================
# ANALYSIS BUTTON
# ============================================================

st.divider()

analyze_button = st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
)


# ============================================================
# VALIDATION
# ============================================================

if analyze_button:

    errors = []

    if not course_name.strip():
        errors.append(
            "Please enter the course name."
        )

    if not assessment_name.strip():
        errors.append(
            "Please enter the assessment name."
        )

    if not clos:
        errors.append(
            "Please enter at least one CLO."
        )

    if not plos:
        errors.append(
            "Please enter at least one PLO."
        )

    if uploaded_file is None:
        errors.append(
            "Please upload a quiz file."
        )

    if errors:

        for error in errors:
            st.error(error)

        st.stop()

    # --------------------------------------------------------
    # READ FILE
    # --------------------------------------------------------

    with st.spinner(
        "Reading and analyzing the uploaded quiz..."
    ):

        quiz_text = extract_text_from_file(
            uploaded_file
        )

    if not quiz_text.strip():

        st.error(
            "No readable text was found in the uploaded file."
        )

        st.stop()

    # --------------------------------------------------------
    # EXTRACT QUESTIONS
    # --------------------------------------------------------

    questions = extract_questions(
        quiz_text
    )

    if not questions:

        st.error(
            "No questions could be detected. "
            "Please make sure the quiz contains numbered questions "
            "such as 1., 2., 3. or Q1., Q2., Q3."
        )

        st.stop()

    # --------------------------------------------------------
    # ANALYZE QUESTIONS
    # --------------------------------------------------------

    results = []

    for question in questions:

        question_text = question["text"]

        # Bloom
        detected_bloom, bloom_scores = detect_bloom(
            question_text
        )

        bloom_score = bloom_alignment(
            intended_bloom,
            detected_bloom
        )

        # CLO matching
        clo_scores = []

        for clo in clos:

            score, evidence = outcome_similarity(
                question_text,
                clo["text"]
            )

            clo_scores.append(
                {
                    "code": clo["code"],
                    "text": clo["text"],
                    "score": score,
                    "evidence": evidence
                }
            )

        clo_scores = sorted(
            clo_scores,
            key=lambda x: x["score"],
            reverse=True
        )

        best_clo = clo_scores[0]

        # PLO matching
        plo_scores = []

        for plo in plos:

            score, evidence = outcome_similarity(
                question_text,
                plo["text"]
            )

            plo_scores.append(
                {
                    "code": plo["code"],
                    "text": plo["text"],
                    "score": score,
                    "evidence": evidence
                }
            )

        plo_scores = sorted(
            plo_scores,
            key=lambda x: x["score"],
            reverse=True
        )

        best_plo = plo_scores[0]

        # ----------------------------------------------------
        # FEEDBACK
        # ----------------------------------------------------

        feedback = []

        if bloom_score >= 100:

            feedback.append(
                "Bloom level matches the intended cognitive level."
            )

        elif bloom_score >= 65:

            feedback.append(
                f"Bloom level is close to the intended "
                f"{intended_bloom} level."
            )

        else:

            feedback.append(
                f"Revise the question so that its cognitive demand "
                f"clearly targets {intended_bloom}."
            )

        if best_clo["score"] >= 70:

            feedback.append(
                f"Strong alignment with {best_clo['code']}."
            )

        elif best_clo["score"] >= 50:

            feedback.append(
                f"Good but improvable alignment with {best_clo['code']}."
            )

        else:

            feedback.append(
                f"Consider revising the question to more directly "
                f"measure {best_clo['code']}."
            )

        if best_plo["score"] >= 70:

            feedback.append(
                f"Strong alignment with {best_plo['code']}."
            )

        elif best_plo["score"] >= 50:

            feedback.append(
                f"Good but improvable alignment with {best_plo['code']}."
            )

        else:

            feedback.append(
                f"Review the relationship between this question "
                f"and {best_plo['code']}."
            )

        results.append(
            {
                "Question No.": question["number"],
                "Question": question_text,
                "Intended Bloom": intended_bloom,
                "Detected Bloom": detected_bloom,
                "Bloom Alignment %": bloom_score,
                "Best CLO": best_clo["code"],
                "CLO Alignment %": best_clo["score"],
                "Best PLO": best_plo["code"],
                "PLO Alignment %": best_plo["score"],
                "Feedback": " ".join(feedback)
            }
        )

    results_df = pd.DataFrame(results)

    st.session_state.analysis_results = results_df
    st.session_state.uploaded_filename = uploaded_file.name


# ============================================================
# DISPLAY ANALYSIS
# ============================================================

if st.session_state.analysis_results is not None:

    results_df = st.session_state.analysis_results

    st.divider()

    st.header(
        "📊 Quiz Alignment Results"
    )

    st.info(
        "These percentages represent **quiz-level alignment** "
        "with the entered CLOs, PLOs and intended Bloom level. "
        "They are not student attainment percentages. "
        "Actual student attainment requires student marks."
    )

    # ========================================================
    # OVERALL NUMBERS
    # ========================================================

    average_clo = results_df[
        "CLO Alignment %"
    ].mean()

    average_plo = results_df[
        "PLO Alignment %"
    ].mean()

    average_bloom = results_df[
        "Bloom Alignment %"
    ].mean()

    overall_alignment = (
        average_clo * 0.35 +
        average_plo * 0.25 +
        average_bloom * 0.40
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Questions Analyzed",
            len(results_df)
        )

    with col2:

        st.metric(
            "CLO Alignment",
            f"{average_clo:.1f}%"
        )

    with col3:

        st.metric(
            "PLO Alignment",
            f"{average_plo:.1f}%"
        )

    with col4:

        st.metric(
            "Bloom Alignment",
            f"{average_bloom:.1f}%"
        )

    st.metric(
        "Overall Quiz Alignment",
        f"{overall_alignment:.1f}%"
    )

    st.divider()

    # ========================================================
    # CLO ANALYSIS
    # ========================================================

    st.subheader(
        "🎯 CLO Alignment"
    )

    clo_summary = []

    for clo in clos:

        mapped = results_df[
            results_df["Best CLO"] == clo["code"]
        ]

        if len(mapped) > 0:

            avg_score = mapped[
                "CLO Alignment %"
            ].mean()

            question_count = len(mapped)

        else:

            avg_score = 0
            question_count = 0

        coverage = (
            question_count /
            len(results_df)
        ) * 100

        clo_summary.append(
            {
                "CLO": clo["code"],
                "Description": clo["text"],
                "Questions Mapped": question_count,
                "Average Alignment %": round(
                    avg_score,
                    1
                ),
                "Question Coverage %": round(
                    coverage,
                    1
                ),
                "Status": alignment_label(
                    avg_score
                )
            }
        )

    clo_summary_df = pd.DataFrame(
        clo_summary
    )

    c1, c2 = st.columns([1.2, 1])

    with c1:

        st.dataframe(
            clo_summary_df,
            use_container_width=True,
            hide_index=True
        )

    with c2:

        chart_df = clo_summary_df[
            ["CLO", "Average Alignment %"]
        ].set_index("CLO")

        st.bar_chart(
            chart_df,
            use_container_width=True
        )

    st.write("### CLO Alignment Levels")

    for _, row in clo_summary_df.iterrows():

        st.write(
            f"**{row['CLO']} — "
            f"{row['Average Alignment %']:.1f}%**"
        )

        st.progress(
            min(
                1.0,
                max(
                    0.0,
                    row["Average Alignment %"] / 100
                )
            )
        )

    # ========================================================
    # PLO ANALYSIS
    # ========================================================

    st.divider()

    st.subheader(
        "🎯 PLO Alignment"
    )

    plo_summary = []

    for plo in plos:

        mapped = results_df[
            results_df["Best PLO"] == plo["code"]
        ]

        if len(mapped) > 0:

            avg_score = mapped[
                "PLO Alignment %"
            ].mean()

            question_count = len(mapped)

        else:

            avg_score = 0
            question_count = 0

        coverage = (
            question_count /
            len(results_df)
        ) * 100

        plo_summary.append(
            {
                "PLO": plo["code"],
                "Description": plo["text"],
                "Questions Mapped": question_count,
                "Average Alignment %": round(
                    avg_score,
                    1
                ),
                "Question Coverage %": round(
                    coverage,
                    1
                ),
                "Status": alignment_label(
                    avg_score
                )
            }
        )

    plo_summary_df = pd.DataFrame(
        plo_summary
    )

    c1, c2 = st.columns([1.2, 1])

    with c1:

        st.dataframe(
            plo_summary_df,
            use_container_width=True,
            hide_index=True
        )

    with c2:

        chart_df = plo_summary_df[
            ["PLO", "Average Alignment %"]
        ].set_index("PLO")

        st.bar_chart(
            chart_df,
            use_container_width=True
        )

    st.write("### PLO Alignment Levels")

    for _, row in plo_summary_df.iterrows():

        st.write(
            f"**{row['PLO']} — "
            f"{row['Average Alignment %']:.1f}%**"
        )

        st.progress(
            min(
                1.0,
                max(
                    0.0,
                    row["Average Alignment %"] / 100
                )
            )
        )

    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.divider()

    st.subheader(
        "🧠 Bloom's Taxonomy Analysis"
    )

    bloom_distribution = (
        results_df[
            "Detected Bloom"
        ]
        .value_counts()
        .reindex(
            BLOOM_LEVELS,
            fill_value=0
        )
    )

    bloom_chart_df = pd.DataFrame(
        {
            "Questions": bloom_distribution
        }
    )

    c1, c2 = st.columns([1, 1])

    with c1:

        st.bar_chart(
            bloom_chart_df,
            use_container_width=True
        )

    with c2:

        bloom_table = []

        for level in BLOOM_LEVELS:

            level_questions = results_df[
                results_df[
                    "Detected Bloom"
                ] == level
            ]

            count = len(level_questions)

            percentage = (
                count /
                len(results_df)
            ) * 100

            alignment = (
                level_questions[
                    "Bloom Alignment %"
                ].mean()
                if count > 0
                else 0
            )

            bloom_table.append(
                {
                    "Bloom Level": level,
                    "Questions": count,
                    "Distribution %": round(
                        percentage,
                        1
                    ),
                    "Alignment %": round(
                        alignment,
                        1
                    )
                }
            )

        bloom_table_df = pd.DataFrame(
            bloom_table
        )

        st.dataframe(
            bloom_table_df,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # BLOOM PROGRESS
    # ========================================================

    st.write(
        "### Bloom-Level Distribution"
    )

    for level in BLOOM_LEVELS:

        count = int(
            bloom_distribution.get(
                level,
                0
            )
        )

        percentage = (
            count /
            len(results_df)
        ) * 100

        st.write(
            f"**{level}: {count} question(s) "
            f"— {percentage:.1f}%**"
        )

        st.progress(
            min(
                1.0,
                percentage / 100
            )
        )

    # ========================================================
    # ALIGNMENT SUMMARY
    # ========================================================

    st.divider()

    st.subheader(
        "📈 Alignment Summary"
    )

    summary_data = pd.DataFrame(
        {
            "Area": [
                "CLO Alignment",
                "PLO Alignment",
                "Bloom Alignment",
                "Overall Quiz Alignment"
            ],
            "Percentage": [
                round(
                    average_clo,
                    1
                ),
                round(
                    average_plo,
                    1
                ),
                round(
                    average_bloom,
                    1
                ),
                round(
                    overall_alignment,
                    1
                )
            ]
        }
    )

    st.dataframe(
        summary_data,
        use_container_width=True,
        hide_index=True
    )

    st.bar_chart(
        summary_data.set_index(
            "Area"
        ),
        use_container_width=True
    )

    # ========================================================
    # QUESTION-BY-QUESTION RESULTS
    # ========================================================

    st.divider()

    st.subheader(
        "📝 Question-by-Question Analysis"
    )

    display_columns = [
        "Question No.",
        "Question",
        "Intended Bloom",
        "Detected Bloom",
        "Bloom Alignment %",
        "Best CLO",
        "CLO Alignment %",
        "Best PLO",
        "PLO Alignment %",
        "Feedback"
    ]

    st.dataframe(
        results_df[
            display_columns
        ],
        use_container_width=True,
        hide_index=True,
        height=500
    )

    # ========================================================
    # DETAILED QUESTIONS
    # ========================================================

    st.divider()

    st.subheader(
        "🔎 Detailed Question Review"
    )

    for _, row in results_df.iterrows():

        question_no = row[
            "Question No."
        ]

        with st.expander(
            f"Question {question_no}: "
            f"{row['Question'][:100]}"
        ):

            st.write(
                f"**Question:** "
                f"{row['Question']}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "Bloom Alignment",
                    f"{row['Bloom Alignment %']:.1f}%"
                )

                st.write(
                    f"Intended: **{row['Intended Bloom']}**"
                )

                st.write(
                    f"Detected: **{row['Detected Bloom']}**"
                )

            with c2:

                st.metric(
                    "CLO Alignment",
                    f"{row['CLO Alignment %']:.1f}%"
                )

                st.write(
                    f"Best CLO: **{row['Best CLO']}**"
                )

            with c3:

                st.metric(
                    "PLO Alignment",
                    f"{row['PLO Alignment %']:.1f}%"
                )

                st.write(
                    f"Best PLO: **{row['Best PLO']}**"
                )

            st.write(
                f"**Feedback:** {row['Feedback']}"
            )

    # ========================================================
    # OVERALL INTERPRETATION
    # ========================================================

    st.divider()

    st.subheader(
        "💡 Overall Interpretation"
    )

    if overall_alignment >= 80:

        st.success(
            f"The quiz shows strong overall OBE alignment "
            f"with an overall score of {overall_alignment:.1f}%."
        )

    elif overall_alignment >= 60:

        st.warning(
            f"The quiz shows moderate OBE alignment "
            f"with an overall score of {overall_alignment:.1f}%. "
            f"Some questions may require refinement."
        )

    else:

        st.error(
            f"The quiz requires substantial alignment review. "
            f"The overall alignment score is "
            f"{overall_alignment:.1f}%."
        )

    # ========================================================
    # DOWNLOAD RESULTS
    # ========================================================

    st.divider()

    st.subheader(
        "📥 Download Analysis"
    )

    csv_data = results_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download Question Analysis (CSV)",
        data=csv_data,
        file_name=(
            f"{assessment_name.replace(' ', '_')}"
            f"_OBE_Analysis.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.subheader(
        "📌 Final Quiz Summary"
    )

    final_col1, final_col2, final_col3, final_col4 = st.columns(4)

    with final_col1:

        st.metric(
            "CLO",
            f"{average_clo:.1f}%"
        )

    with final_col2:

        st.metric(
            "PLO",
            f"{average_plo:.1f}%"
        )

    with final_col3:

        st.metric(
            "Bloom",
            f"{average_bloom:.1f}%"
        )

    with final_col4:

        st.metric(
            "Overall",
            f"{overall_alignment:.1f}%"
        )

    st.caption(
        f"Analyzed file: {st.session_state.uploaded_filename}"
    )
