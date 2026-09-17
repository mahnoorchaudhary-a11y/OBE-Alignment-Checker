import streamlit as st
import pandas as pd
import re
import io

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Alignment Checker",
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
        "apply", "use", "demonstrate", "solve",
        "calculate", "implement", "execute", "perform",
        "practice", "show", "compute"
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
        "generate", "construct", "invent"
    ]
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in",
    "on", "for", "with", "by", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those",
    "from", "as", "at", "it", "its", "into", "about",
    "which", "what", "how", "why", "when", "where",
    "who", "whom", "can", "could", "should", "would",
    "will", "may", "might", "do", "does", "did"
}

CONCEPT_GROUPS = {
    "main idea": {
        "main", "idea", "central", "point", "theme",
        "message", "purpose"
    },
    "reading": {
        "read", "reading", "comprehension", "understand",
        "understanding", "passage", "text"
    },
    "organization": {
        "organization", "organisation", "pattern",
        "structure", "sequence", "cause", "effect",
        "compare", "contrast", "problem", "solution"
    },
    "paraphrasing": {
        "paraphrase", "paraphrasing", "rewrite",
        "restatement", "restating"
    },
    "author purpose": {
        "author", "purpose", "intent", "intention",
        "inform", "persuade", "entertain"
    },
    "tone": {
        "tone", "attitude", "feeling", "mood"
    },
    "writing": {
        "write", "writing", "essay", "paragraph",
        "sentence", "composition"
    },
    "critical thinking": {
        "critical", "thinking", "reason", "reasoning",
        "evidence", "argument", "claim"
    },
    "communication": {
        "communication", "communicate", "language",
        "speaking", "listening", "presentation"
    },
    "grammar": {
        "grammar", "grammatical", "verb", "noun",
        "sentence", "syntax"
    },
    "vocabulary": {
        "vocabulary", "word", "meaning", "definition",
        "lexical"
    },
    "research": {
        "research", "source", "citation", "reference",
        "evidence", "data"
    },
    "analysis": {
        "analyze", "analyse", "analysis", "examine",
        "evaluate", "critique", "compare"
    }
}

# ============================================================
# TEXT UTILITIES
# ============================================================

def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    text = normalize_text(text)
    return {
        word for word in text.split()
        if word not in STOP_WORDS and len(word) > 2
    }


def expanded_concepts(text):
    words = tokenize(text)

    concepts = set(words)

    for group_words in CONCEPT_GROUPS.values():
        if words.intersection(group_words):
            concepts.update(group_words)

    return concepts


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    q = normalize_text(question)

    scores = {}

    for level, verbs in BLOOM_VERBS.items():

        score = 0

        for verb in verbs:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                q
            ):
                score += 1

        scores[level] = score

    if "why" in q:
        scores["Analyze"] += 1

    if "how" in q:
        scores["Understand"] += 1

    if "compare and contrast" in q:
        scores["Analyze"] += 3

    if "justify" in q:
        scores["Evaluate"] += 3

    if "design" in q:
        scores["Create"] += 3

    if "create" in q:
        scores["Create"] += 3

    best_level = max(
        scores,
        key=scores.get
    )

    if scores[best_level] == 0:
        return "Needs Review"

    return best_level


def bloom_alignment(intended, detected):

    if detected == "Needs Review":
        return 40

    distance = abs(
        BLOOM_RANK[intended]
        - BLOOM_RANK[detected]
    )

    if distance == 0:
        return 100

    if distance == 1:
        return 65

    if distance == 2:
        return 45

    return 25


# ============================================================
# CLO / PLO SIMILARITY
# ============================================================

def outcome_similarity(question, outcome):

    q_words = expanded_concepts(question)
    o_words = expanded_concepts(outcome)

    if not q_words or not o_words:
        return 0, []

    intersection = q_words.intersection(o_words)

    dice = (
        2 * len(intersection)
        / (len(q_words) + len(o_words))
    )

    score = dice * 100

    q_norm = normalize_text(question)
    o_norm = normalize_text(outcome)

    phrase_bonus = 0

    outcome_words = list(o_words)

    for i in range(len(outcome_words) - 1):

        phrase = (
            outcome_words[i]
            + " "
            + outcome_words[i + 1]
        )

        if phrase in q_norm:
            phrase_bonus += 5

    score += phrase_bonus

    score = min(score, 100)

    evidence = sorted(
        list(intersection)
    )[:10]

    return score, evidence


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
# FILE EXTRACTION
# ============================================================

def extract_text_from_upload(uploaded_file):

    filename = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

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

            paragraphs = [
                p.text
                for p in document.paragraphs
                if p.text.strip()
            ]

            return "\n".join(paragraphs)

        except Exception as e:

            raise Exception(
                f"Could not read DOCX file: {e}"
            )

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

            extracted = "\n".join(pages)

            if extracted.strip():
                return extracted

        except Exception:
            pass

        # OCR fallback
        try:

            from pdf2image import convert_from_bytes
            import pytesseract

            images = convert_from_bytes(data)

            pages = []

            for image in images:

                text = pytesseract.image_to_string(
                    image
                )

                if text.strip():
                    pages.append(text)

            extracted = "\n".join(pages)

            if extracted.strip():
                return extracted

        except Exception as e:

            raise Exception(
                "Could not read PDF. "
                "Install pypdf or OCR dependencies. "
                f"Details: {e}"
            )

        raise Exception(
            "The PDF contains no readable text."
        )

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
                    sheet_name=sheet,
                    header=None
                )

                for row in df.values:

                    row_text = " ".join(
                        [
                            str(x)
                            for x in row
                            if pd.notna(x)
                        ]
                    )

                    if row_text.strip():
                        all_text.append(row_text)

            return "\n".join(all_text)

        except Exception as e:

            raise Exception(
                f"Could not read Excel file: {e}"
            )

    raise Exception(
        "Unsupported file type."
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    questions = []

    # First attempt:
    # numbered questions
    pattern = re.compile(
        r"^(?:q(?:uestion)?\s*)?(\d+)\s*[\.\)\:\-]\s*(.+)$",
        re.IGNORECASE
    )

    current_question = None
    current_number = None

    for line in lines:

        match = pattern.match(line)

        if match:

            if current_question:

                questions.append(
                    (
                        current_number,
                        current_question.strip()
                    )
                )

            current_number = int(
                match.group(1)
            )

            current_question = match.group(2)

        else:

            if current_question:

                current_question += " " + line

    if current_question:

        questions.append(
            (
                current_number,
                current_question.strip()
            )
        )

    # Second attempt:
    # lines ending with ?
    if len(questions) == 0:

        for i, line in enumerate(lines):

            if "?" in line:

                parts = line.split("?")

                for part in parts:

                    if part.strip():

                        questions.append(
                            (
                                len(questions) + 1,
                                part.strip() + "?"
                            )
                        )

    # Third attempt:
    # fallback to paragraphs
    if len(questions) == 0:

        for line in lines:

            if len(line.split()) >= 5:

                questions.append(
                    (
                        len(questions) + 1,
                        line
                    )
                )

    return questions


# ============================================================
# QUESTION ANALYSIS
# ============================================================

def analyze_questions(
    questions,
    clos,
    plos,
    intended_bloom
):

    rows = []

    for number, question in questions:

        # CLO matching
        clo_scores = []

        for clo in clos:

            score, evidence = outcome_similarity(
                question,
                clo["text"]
            )

            clo_scores.append(
                {
                    "code": clo["code"],
                    "score": score,
                    "evidence": evidence
                }
            )

        best_clo = max(
            clo_scores,
            key=lambda x: x["score"]
        )

        # PLO matching
        plo_scores = []

        for plo in plos:

            score, evidence = outcome_similarity(
                question,
                plo["text"]
            )

            plo_scores.append(
                {
                    "code": plo["code"],
                    "score": score,
                    "evidence": evidence
                }
            )

        best_plo = max(
            plo_scores,
            key=lambda x: x["score"]
        )

        # Bloom
        detected_bloom = detect_bloom(
            question
        )

        bloom_score = bloom_alignment(
            intended_bloom,
            detected_bloom
        )

        combined = (
            best_clo["score"] * 0.35
            + best_plo["score"] * 0.25
            + bloom_score * 0.40
        )

        rows.append(
            {
                "Question No.": number,
                "Question": question,
                "Best CLO": best_clo["code"],
                "CLO Alignment %": round(
                    best_clo["score"],
                    1
                ),
                "CLO Evidence": ", ".join(
                    best_clo["evidence"]
                ),
                "Best PLO": best_plo["code"],
                "PLO Alignment %": round(
                    best_plo["score"],
                    1
                ),
                "PLO Evidence": ", ".join(
                    best_plo["evidence"]
                ),
                "Intended Bloom": intended_bloom,
                "Detected Bloom": detected_bloom,
                "Bloom Alignment %": bloom_score,
                "Combined Alignment %": round(
                    combined,
                    1
                )
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# APPLICATION TITLE
# ============================================================

st.title("🎓 OBE Quiz Alignment Checker")

st.write(
    "Enter your course outcomes and assessment information, "
    "upload a quiz, and check how well each question aligns "
    "with the selected CLOs, PLOs, and intended Bloom's level."
)

st.info(
    "This tool evaluates **quiz-level alignment**. "
    "It does not calculate actual student attainment unless "
    "student marks are provided separately."
)

# ============================================================
# STEP 1: ASSESSMENT INFORMATION
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
# STEP 2: CLOs
# ============================================================

st.header("2️⃣ Enter CLOs")

num_clos = st.number_input(
    "Number of CLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

clos = []

for i in range(int(num_clos)):

    col1, col2 = st.columns([1, 4])

    with col1:

        code = st.text_input(
            f"CLO {i + 1} Code",
            value=f"CLO{i + 1}",
            key=f"clo_code_{i}"
        )

    with col2:

        description = st.text_input(
            f"CLO {i + 1} Description",
            key=f"clo_description_{i}",
            placeholder="Enter the CLO statement"
        )

    if description.strip():

        clos.append(
            {
                "code": code.strip(),
                "text": description.strip()
            }
        )

# ============================================================
# STEP 3: PLOs
# ============================================================

st.header("3️⃣ Enter PLOs")

num_plos = st.number_input(
    "Number of PLOs",
    min_value=1,
    max_value=20,
    value=3,
    step=1
)

plos = []

for i in range(int(num_plos)):

    col1, col2 = st.columns([1, 4])

    with col1:

        code = st.text_input(
            f"PLO {i + 1} Code",
            value=f"PLO{i + 1}",
            key=f"plo_code_{i}"
        )

    with col2:

        description = st.text_input(
            f"PLO {i + 1} Description",
            key=f"plo_description_{i}",
            placeholder="Enter the PLO statement"
        )

    if description.strip():

        plos.append(
            {
                "code": code.strip(),
                "text": description.strip()
            }
        )

# ============================================================
# STEP 4: BLOOM
# ============================================================

st.header("4️⃣ Intended Bloom's Level")

intended_bloom = st.selectbox(
    "Select the cognitive level intended for this quiz",
    BLOOM_LEVELS
)

st.write(
    f"**Selected level:** {intended_bloom}"
)

# ============================================================
# STEP 5: UPLOAD QUIZ
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
    ]
)

# ============================================================
# ANALYZE BUTTON
# ============================================================

st.divider()

analyze_button = st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
)

# ============================================================
# ANALYSIS
# ============================================================

if analyze_button:

    # Validation
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

    if len(clos) == 0:

        st.error(
            "Please enter at least one CLO description."
        )
        st.stop()

    if len(plos) == 0:

        st.error(
            "Please enter at least one PLO description."
        )
        st.stop()

    if uploaded_file is None:

        st.error(
            "Please upload a quiz file."
        )
        st.stop()

    # Extract file
    try:

        with st.spinner(
            "Reading and analyzing the quiz..."
        ):

            extracted_text = extract_text_from_upload(
                uploaded_file
            )

    except Exception as e:

        st.error(str(e))
        st.stop()

    if not extracted_text.strip():

        st.error(
            "No readable text was found in the uploaded file."
        )
        st.stop()

    # Extract questions
    questions = extract_questions(
        extracted_text
    )

    if len(questions) == 0:

        st.error(
            "No questions could be detected. "
            "Please use numbered questions such as "
            "1., 2., 3. or questions ending with '?'."
        )
        st.stop()

    # Analyze
    results_df = analyze_questions(
        questions,
        clos,
        plos,
        intended_bloom
    )

    # ========================================================
    # RESULTS
    # ========================================================

    st.divider()

    st.header("📊 Quiz Alignment Results")

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
        + avg_plo * 0.25
        + avg_bloom * 0.40
    )

    # ========================================================
    # SUMMARY METRICS
    # ========================================================

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Overall Alignment",
            f"{overall:.1f}%"
        )

    with c2:
        st.metric(
            "CLO Alignment",
            f"{avg_clo:.1f}%"
        )

    with c3:
        st.metric(
            "PLO Alignment",
            f"{avg_plo:.1f}%"
        )

    with c4:
        st.metric(
            "Bloom Alignment",
            f"{avg_bloom:.1f}%"
        )

    st.info(
        "The percentages above indicate how well the uploaded "
        "quiz aligns with the outcomes and intended Bloom level. "
        "They are not student attainment percentages."
    )

    # ========================================================
    # OVERALL GRAPH
    # ========================================================

    st.subheader(
        "📈 Overall Alignment Graph"
    )

    overall_chart = pd.DataFrame(
        {
            "Alignment Area": [
                "CLO",
                "PLO",
                "Bloom",
                "Overall"
            ],
            "Percentage": [
                avg_clo,
                avg_plo,
                avg_bloom,
                overall
            ]
        }
    )

    st.bar_chart(
        overall_chart.set_index(
            "Alignment Area"
        ),
        use_container_width=True
    )

    # ========================================================
    # CLO-BY-CLO ANALYSIS
    # ========================================================

    st.divider()

    st.header("🎯 CLO-by-CLO Analysis")

    st.write(
        "Select one CLO at a time to see its questions, "
        "numerical alignment, graph, and improvement suggestions."
    )

    clo_options = [
        clo["code"]
        for clo in clos
    ]

    selected_clo_code = st.selectbox(
        "Select CLO to analyze",
        clo_options,
        key="selected_clo"
    )

    selected_clo = next(
        (
            clo
            for clo in clos
            if clo["code"] == selected_clo_code
        ),
        None
    )

    clo_questions = results_df[
        results_df["Best CLO"] == selected_clo_code
    ].copy()

    if len(clo_questions) > 0:

        clo_alignment = clo_questions[
            "CLO Alignment %"
        ].mean()

        clo_coverage = (
            len(clo_questions)
            / len(results_df)
        ) * 100

    else:

        clo_alignment = 0
        clo_coverage = 0

    st.subheader(
        selected_clo_code
    )

    st.info(
        f"**CLO Description:** "
        f"{selected_clo['text']}"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "CLO Alignment",
            f"{clo_alignment:.1f}%"
        )

    with c2:

        st.metric(
            "Questions Mapped",
            len(clo_questions)
        )

    with c3:

        st.metric(
            "Quiz Coverage",
            f"{clo_coverage:.1f}%"
        )

    if clo_alignment >= 70:

        st.success(
            f"{selected_clo_code} has strong quiz alignment "
            f"({clo_alignment:.1f}%)."
        )

    elif clo_alignment >= 50:

        st.warning(
            f"{selected_clo_code} has moderate alignment "
            f"({clo_alignment:.1f}%). "
            "Some questions may need refinement."
        )

    else:

        st.error(
            f"{selected_clo_code} has weak alignment "
            f"({clo_alignment:.1f}%). "
            "Revision is recommended."
        )

    # ========================================================
    # CLO GRAPH
    # ========================================================

    st.subheader(
        "📊 Selected CLO Alignment Graph"
    )

    if len(clo_questions) > 0:

        graph_data = clo_questions[
            [
                "Question No.",
                "CLO Alignment %"
            ]
        ].copy()

        graph_data["Question"] = (
            "Q"
            + graph_data[
                "Question No."
            ].astype(str)
        )

        graph_data = graph_data[
            [
                "Question",
                "CLO Alignment %"
            ]
        ].set_index("Question")

        st.bar_chart(
            graph_data,
            use_container_width=True
        )

    else:

        st.warning(
            "No question is currently mapped to this CLO."
        )

    # ========================================================
    # QUESTIONS FOR SELECTED CLO
    # ========================================================

    st.subheader(
        f"📝 Questions Assessing {selected_clo_code}"
    )

    if len(clo_questions) > 0:

        question_display = clo_questions[
            [
                "Question No.",
                "Question",
                "Intended Bloom",
                "Detected Bloom",
                "Bloom Alignment %",
                "CLO Alignment %",
                "Best PLO",
                "PLO Alignment %"
            ]
        ]

        st.dataframe(
            question_display,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            f"No question has been mapped to "
            f"{selected_clo_code}. Add or revise a question "
            "that directly assesses this CLO."
        )

    # ========================================================
    # CLO SUGGESTIONS
    # ========================================================

    st.subheader(
        f"💡 Suggestions for Improving {selected_clo_code}"
    )

    clo_suggestions = []

    if len(clo_questions) == 0:

        clo_suggestions.append(
            f"Add at least one question that directly assesses "
            f"the knowledge or skill described in "
            f"{selected_clo_code}."
        )

    else:

        if clo_alignment < 50:

            clo_suggestions.append(
                f"The current alignment is only "
                f"{clo_alignment:.1f}%. Rewrite the questions "
                f"so their content and required student action "
                f"directly reflect the CLO."
            )

        elif clo_alignment < 70:

            clo_suggestions.append(
                f"The alignment is {clo_alignment:.1f}%. "
                f"Strengthen the wording of the questions so "
                f"the relationship with {selected_clo_code} "
                "is more explicit."
            )

        else:

            clo_suggestions.append(
                f"The alignment is strong at "
                f"{clo_alignment:.1f}%. Maintain the direct "
                f"connection between the questions and "
                f"{selected_clo_code}."
            )

        if clo_coverage < 20:

            clo_suggestions.append(
                f"Only {clo_coverage:.1f}% of the quiz questions "
                "currently contribute to this CLO. Consider "
                "increasing assessment coverage if this CLO "
                "is an important course outcome."
            )

        weak_bloom_questions = clo_questions[
            clo_questions[
                "Bloom Alignment %"
            ] < 65
        ]

        if len(weak_bloom_questions) > 0:

            question_numbers = ", ".join(
                [
                    f"Q{int(q)}"
                    for q in weak_bloom_questions[
                        "Question No."
                    ]
                ]
            )

            clo_suggestions.append(
                f"Questions {question_numbers} do not strongly "
                f"match the intended Bloom level of "
                f"{intended_bloom}. Revise their cognitive "
                "demand and action verbs."
            )

        weak_clo_questions = clo_questions[
            clo_questions[
                "CLO Alignment %"
            ] < 50
        ]

        if len(weak_clo_questions) > 0:

            numbers = ", ".join(
                [
                    f"Q{int(q)}"
                    for q in weak_clo_questions[
                        "Question No."
                    ]
                ]
            )

            clo_suggestions.append(
                f"Priority revision: {numbers} have CLO "
                "alignment below 50%. Review these questions first."
            )

    for suggestion in clo_suggestions:

        st.info(
            "💡 " + suggestion
        )

    # ========================================================
    # DETAILED CLO QUESTION REVIEW
    # ========================================================

    if len(clo_questions) > 0:

        st.subheader(
            "🔎 Detailed CLO Question Review"
        )

        for _, row in clo_questions.iterrows():

            with st.expander(
                f"Question {int(row['Question No.'])}"
            ):

                st.write(
                    f"**Question:** "
                    f"{row['Question']}"
                )

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "CLO Alignment",
                        f"{row['CLO Alignment %']:.1f}%"
                    )

                with c2:

                    st.metric(
                        "Bloom Alignment",
                        f"{row['Bloom Alignment %']:.1f}%"
                    )

                with c3:

                    st.metric(
                        "PLO Alignment",
                        f"{row['PLO Alignment %']:.1f}%"
                    )

                st.write(
                    f"**Intended Bloom:** "
                    f"{row['Intended Bloom']}"
                )

                st.write(
                    f"**Detected Bloom:** "
                    f"{row['Detected Bloom']}"
                )

                st.write(
                    f"**Mapped PLO:** "
                    f"{row['Best PLO']}"
                )

                if row["CLO Alignment %"] < 50:

                    st.warning(
                        f"Revise this question to make its "
                        f"connection with {selected_clo_code} "
                        "more explicit."
                    )

                if row["Bloom Alignment %"] < 65:

                    st.warning(
                        f"Revise the cognitive demand so the "
                        f"question better targets "
                        f"{intended_bloom}."
                    )

                if row["PLO Alignment %"] < 50:

                    st.warning(
                        f"Review whether this question provides "
                        f"clear evidence for {row['Best PLO']}."
                    )

                if (
                    row["CLO Alignment %"] >= 70
                    and row["Bloom Alignment %"] >= 100
                ):

                    st.success(
                        "This question provides strong alignment "
                        "with the selected CLO and intended "
                        "Bloom level."
                    )

    # ========================================================
    # PLO-BY-PLO ANALYSIS
    # ========================================================

    st.divider()

    st.header("🎯 PLO-by-PLO Analysis")

    st.write(
        "Select one PLO at a time to review its numerical "
        "alignment, questions, graph, and improvement suggestions."
    )

    plo_options = [
        plo["code"]
        for plo in plos
    ]

    selected_plo_code = st.selectbox(
        "Select PLO to analyze",
        plo_options,
        key="selected_plo"
    )

    selected_plo = next(
        (
            plo
            for plo in plos
            if plo["code"] == selected_plo_code
        ),
        None
    )

    plo_questions = results_df[
        results_df["Best PLO"] == selected_plo_code
    ].copy()

    if len(plo_questions) > 0:

        plo_alignment = plo_questions[
            "PLO Alignment %"
        ].mean()

        plo_coverage = (
            len(plo_questions)
            / len(results_df)
        ) * 100

    else:

        plo_alignment = 0
        plo_coverage = 0

    st.subheader(
        selected_plo_code
    )

    st.info(
        f"**PLO Description:** "
        f"{selected_plo['text']}"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "PLO Alignment",
            f"{plo_alignment:.1f}%"
        )

    with c2:

        st.metric(
            "Questions Mapped",
            len(plo_questions)
        )

    with c3:

        st.metric(
            "Quiz Coverage",
            f"{plo_coverage:.1f}%"
        )

    # PLO graph
    st.subheader(
        "📊 Selected PLO Alignment Graph"
    )

    if len(plo_questions) > 0:

        plo_graph = plo_questions[
            [
                "Question No.",
                "PLO Alignment %"
            ]
        ].copy()

        plo_graph["Question"] = (
            "Q"
            + plo_graph[
                "Question No."
            ].astype(str)
        )

        plo_graph = plo_graph[
            [
                "Question",
                "PLO Alignment %"
            ]
        ].set_index("Question")

        st.bar_chart(
            plo_graph,
            use_container_width=True
        )

    else:

        st.warning(
            "No question is currently mapped to this PLO."
        )

    # PLO questions
    st.subheader(
        f"📝 Questions Assessing {selected_plo_code}"
    )

    if len(plo_questions) > 0:

        st.dataframe(
            plo_questions[
                [
                    "Question No.",
                    "Question",
                    "Best CLO",
                    "CLO Alignment %",
                    "Intended Bloom",
                    "Detected Bloom",
                    "Bloom Alignment %",
                    "PLO Alignment %"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            f"No question has been mapped to "
            f"{selected_plo_code}."
        )

    # PLO suggestions
    st.subheader(
        f"💡 Suggestions for Improving {selected_plo_code}"
    )

    plo_suggestions = []

    if len(plo_questions) == 0:

        plo_suggestions.append(
            f"Add or revise questions so that they provide "
            f"clear evidence for {selected_plo_code}."
        )

    else:

        if plo_alignment < 50:

            plo_suggestions.append(
                f"The current PLO alignment is "
                f"{plo_alignment:.1f}%. Strengthen the relationship "
                "between the question content and the PLO."
            )

        elif plo_alignment < 70:

            plo_suggestions.append(
                f"The PLO alignment is {plo_alignment:.1f}%. "
                "Clarify the expected student performance "
                "so the PLO is assessed more directly."
            )

        else:

            plo_suggestions.append(
                f"The PLO alignment is strong at "
                f"{plo_alignment:.1f}%. Maintain the current "
                "connection between the assessment and PLO."
            )

        if plo_coverage < 20:

            plo_suggestions.append(
                f"Only {plo_coverage:.1f}% of the quiz questions "
                "contribute to this PLO. Consider increasing "
                "coverage if the PLO is intended to be assessed."
            )

    for suggestion in plo_suggestions:

        st.info(
            "💡 " + suggestion
        )

    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.divider()

    st.header("🧠 Bloom's Taxonomy Analysis")

    bloom_summary = (
        results_df[
            "Detected Bloom"
        ]
        .value_counts()
        .reset_index()
    )

    bloom_summary.columns = [
        "Bloom Level",
        "Questions"
    ]

    st.dataframe(
        bloom_summary,
        use_container_width=True,
        hide_index=True
    )

    bloom_chart = (
        results_df[
            "Detected Bloom"
        ]
        .value_counts()
        .reindex(
            BLOOM_LEVELS,
            fill_value=0
        )
    )

    st.bar_chart(
        bloom_chart,
        use_container_width=True
    )

    mismatched_bloom = results_df[
        results_df[
            "Bloom Alignment %"
        ] < 65
    ]

    if len(mismatched_bloom) > 0:

        st.warning(
            f"{len(mismatched_bloom)} question(s) do not "
            f"strongly match the intended Bloom level "
            f"of {intended_bloom}."
        )

    else:

        st.success(
            f"All detected questions show strong alignment "
            f"with the intended Bloom level of "
            f"{intended_bloom}."
        )

    # ========================================================
    # QUESTION-LEVEL ANALYSIS
    # ========================================================

    st.divider()

    st.header("📝 Complete Question Analysis")

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
            "Combined Alignment %"
        ]
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # AUTOMATIC SUGGESTIONS
    # ========================================================

    st.divider()

    st.header(
        "💡 Automatic Suggestions to Improve Alignment"
    )

    suggestions = []

    # Overall
    if overall < 50:

        suggestions.append(
            "The overall quiz alignment is below 50%. "
            "Several questions should be revised to establish "
            "clearer relationships with the CLOs, PLOs, and "
            "intended Bloom level."
        )

    elif overall < 70:

        suggestions.append(
            "The quiz shows moderate alignment. "
            "Review the weaker questions and revise their "
            "content, cognitive demand, or outcome connection."
        )

    else:

        suggestions.append(
            "The quiz demonstrates generally strong alignment. "
            "Focus on refining the weaker questions rather than "
            "redesigning the entire assessment."
        )

    # Weak questions
    weakest = results_df.sort_values(
        "Combined Alignment %"
    ).head(3)

    for _, row in weakest.iterrows():

        q = int(row["Question No."])

        if row["CLO Alignment %"] < 50:

            suggestions.append(
                f"Q{q}: strengthen its connection with "
                f"{row['Best CLO']}."
            )

        if row["PLO Alignment %"] < 50:

            suggestions.append(
                f"Q{q}: make the evidence for "
                f"{row['Best PLO']} clearer."
            )

        if row["Bloom Alignment %"] < 65:

            suggestions.append(
                f"Q{q}: revise its action verb and cognitive "
                f"demand to better match {intended_bloom}."
            )

    # Uncovered CLOs
    for clo in clos:

        count = len(
            results_df[
                results_df["Best CLO"]
                == clo["code"]
            ]
        )

        if count == 0:

            suggestions.append(
                f"{clo['code']} is not currently assessed "
                "by any detected question. Add a question "
                "that directly measures this CLO."
            )

    # Uncovered PLOs
    for plo in plos:

        count = len(
            results_df[
                results_df["Best PLO"]
                == plo["code"]
            ]
        )

        if count == 0:

            suggestions.append(
                f"{plo['code']} is not currently represented "
                "by any detected question. Review whether "
                "additional assessment evidence is needed."
            )

    for suggestion in suggestions:

        st.info(
            "💡 " + suggestion
        )

    # ========================================================
    # DOWNLOAD RESULTS
    # ========================================================

    st.divider()

    st.header("📥 Download Analysis")

    csv_data = results_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download Question Analysis CSV",
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

    st.header("✅ Analysis Complete")

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
        f"**Intended Bloom level:** "
        f"{intended_bloom}"
    )

    st.write(
        f"**Overall quiz alignment:** "
        f"{overall:.1f}%"
    )
