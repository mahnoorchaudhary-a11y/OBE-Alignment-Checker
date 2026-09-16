import streamlit as st
import re

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="OBE Assessment Studio",
    page_icon="🎯",
    layout="wide"
)

# =========================================================
# STYLING
# =========================================================
st.markdown("""
<style>
.main-title {
    font-size: 38px;
    font-weight: 800;
    margin-bottom: 5px;
}

.subtitle {
    color: #666;
    font-size: 17px;
    margin-bottom: 25px;
}

.card {
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #ddd;
    background-color: #fafafa;
    margin-bottom: 15px;
}

.question-card {
    padding: 22px;
    border-radius: 12px;
    border: 1px solid #d9e2ec;
    background-color: #f8fbff;
    margin: 15px 0;
}

.answer-card {
    padding: 22px;
    border-radius: 12px;
    border: 1px solid #d5e8d4;
    background-color: #f7fff7;
    margin: 15px 0;
}

.score {
    font-size: 42px;
    font-weight: 800;
}

.big-number {
    font-size: 30px;
    font-weight: 700;
}

.small-note {
    color: #666;
    font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.markdown(
    '<div class="main-title">🎯 OBE Assessment Studio</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Generate, tweak, answer, and check assessment questions for '
    'CLO, PLO, Bloom\'s Taxonomy, marks, and assessment alignment.'
    '</div>',
    unsafe_allow_html=True
)

# =========================================================
# BLOOM VERBS
# =========================================================
BLOOM_VERBS = {
    "Remember": [
        "define", "list", "name", "identify", "recall",
        "state", "mention"
    ],
    "Understand": [
        "explain", "summarize", "interpret", "classify",
        "discuss", "illustrate"
    ],
    "Apply": [
        "apply", "calculate", "demonstrate", "use",
        "solve", "implement", "execute"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine",
        "investigate", "compare", "contrast", "deconstruct"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "judge", "defend", "argue", "recommend"
    ],
    "Create": [
        "create", "design", "develop", "construct",
        "formulate", "propose", "produce", "generate"
    ]
}

# =========================================================
# SESSION STATE
# =========================================================
if "question" not in st.session_state:
    st.session_state.question = ""

if "recommended_answer" not in st.session_state:
    st.session_state.recommended_answer = ""

if "marking_scheme" not in st.session_state:
    st.session_state.marking_scheme = []

if "approval_status" not in st.session_state:
    st.session_state.approval_status = ""

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def clean_text(text):
    return re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())


def get_words(text):
    return set(clean_text(text).split())


def detect_bloom(question):
    words = get_words(question)

    matches = {}

    for level, verbs in BLOOM_VERBS.items():
        found = [verb for verb in verbs if verb in words]

        if found:
            matches[level] = found

    return matches


def bloom_alignment(question, selected_bloom):

    detected = detect_bloom(question)

    if selected_bloom in detected:

        return (
            100,
            f"Clear {selected_bloom.lower()}-level action verb detected: "
            f"{', '.join(detected[selected_bloom])}."
        )

    if detected:

        detected_levels = list(detected.keys())

        return (
            45,
            f"The question uses verbs associated with "
            f"{', '.join(detected_levels)}, rather than clearly targeting "
            f"{selected_bloom}."
        )

    return (
        30,
        f"No clear {selected_bloom.lower()}-level action verb was detected."
    )


def clo_alignment(question, clo):

    question_words = get_words(question)
    clo_words = get_words(clo)

    stopwords = {
        "the", "a", "an", "of", "to", "and", "in", "on",
        "for", "with", "students", "student", "will", "be",
        "able", "should", "can", "by", "from", "this",
        "that", "their", "its"
    }

    q = question_words - stopwords
    c = clo_words - stopwords

    if not c:

        return (
            50,
            "The CLO needs more information for alignment checking."
        )

    overlap = q.intersection(c)

    ratio = len(overlap) / len(c)

    if ratio >= 0.5:

        return (
            100,
            "The question strongly reflects concepts in the CLO."
        )

    elif ratio >= 0.25:

        return (
            70,
            "The question has partial conceptual overlap with the CLO."
        )

    else:

        return (
            40,
            "The question may not directly measure the stated CLO."
        )


def question_length_score(question, marks):

    words = len(question.split())

    if marks <= 2:

        if words <= 35:
            return 100, "Question length is appropriate for short marks."

        return 70, "Consider shortening the question."

    if marks <= 5:

        if 8 <= words <= 60:
            return 100, "Question length is reasonable for the marks."

        return 75, "Review the question length against the marks."

    if words >= 15:

        return (
            100,
            "Question provides sufficient scope for the allocated marks."
        )

    return (
        70,
        "Consider providing more scope for a higher-mark question."
    )


def difficulty_score(question, bloom):

    if bloom in {"Analyze", "Evaluate", "Create"}:

        return (
            100,
            "The selected Bloom level supports higher-order thinking."
        )

    if bloom in {"Apply", "Understand"}:

        return (
            85,
            "The selected Bloom level supports moderate cognitive demand."
        )

    return (
        75,
        "Remember-level questions generally involve lower cognitive demand."
    )


def calculate_overall(scores):

    if not scores:
        return 0

    return round(sum(scores) / len(scores))


def rating(score):

    if score >= 85:
        return "🟢 Strong Alignment"

    elif score >= 65:
        return "🟡 Moderate Alignment"

    return "🔴 Needs Improvement"


# =========================================================
# RECOMMENDED ANSWER GENERATOR
# =========================================================
def generate_recommended_answer(question, clo, bloom, marks):

    q = question.lower()

    # -----------------------------------------------
    # ECONOMICS / INFLATION EXAMPLE
    # -----------------------------------------------
    if "inflation" in q and "purchasing power" in q:

        answer = (
            "Inflation refers to a sustained increase in the general "
            "price level of goods and services. As prices increase, "
            "the purchasing power of money decreases. Therefore, a "
            "household with the same income can purchase fewer goods "
            "and services than before. For example, if food, fuel, and "
            "utility prices rise while household income remains unchanged, "
            "the household may have to reduce its consumption or change "
            "its spending priorities."
        )

        return answer

    # -----------------------------------------------
    # GENERAL ANALYZE QUESTION
    # -----------------------------------------------
    if bloom == "Analyze":

        return (
            "A strong answer should identify the main concept presented "
            "in the question, explain its important components, and "
            "analyze the relationships between those components. The "
            "response should use relevant evidence or examples and "
            "connect the analysis directly to the stated CLO."
        )

    # -----------------------------------------------
    # EVALUATE
    # -----------------------------------------------
    if bloom == "Evaluate":

        return (
            "A strong answer should clearly state a position, provide "
            "relevant evidence, consider important factors or alternatives, "
            "and justify the conclusion using appropriate reasoning."
        )

    # -----------------------------------------------
    # CREATE
    # -----------------------------------------------
    if bloom == "Create":

        return (
            "A strong answer should propose an original and relevant "
            "solution, framework, design, or strategy. The response "
            "should explain the main elements and justify why the "
            "proposed solution addresses the stated problem."
        )

    # -----------------------------------------------
    # APPLY
    # -----------------------------------------------
    if bloom == "Apply":

        return (
            "A strong answer should correctly apply the relevant concept, "
            "principle, formula, or procedure to the given situation. "
            "The response should show the appropriate steps and provide "
            "a clear conclusion."
        )

    # -----------------------------------------------
    # UNDERSTAND
    # -----------------------------------------------
    if bloom == "Understand":

        return (
            "A strong answer should explain the central concept clearly "
            "in the student's own words and include an appropriate "
            "example where relevant."
        )

    # -----------------------------------------------
    # REMEMBER
    # -----------------------------------------------
    return (
        "A strong answer should accurately identify or state the required "
        "concept, term, definition, fact, or principle."
    )


# =========================================================
# MARKING SCHEME GENERATOR
# =========================================================
def generate_marking_scheme(question, answer, marks, bloom):

    marks = int(marks)

    if marks == 1:

        return [
            {
                "criterion": "Correct identification / key point",
                "marks": 1,
                "percentage": 100
            }
        ]

    if marks == 2:

        return [
            {
                "criterion": "Correct concept or key point",
                "marks": 1,
                "percentage": 50
            },
            {
                "criterion": "Relevant explanation",
                "marks": 1,
                "percentage": 50
            }
        ]

    if marks == 3:

        return [
            {
                "criterion": "Correct understanding of the concept",
                "marks": 1,
                "percentage": 33.3
            },
            {
                "criterion": "Relevant explanation / analysis",
                "marks": 1,
                "percentage": 33.3
            },
            {
                "criterion": "Relevant example or evidence",
                "marks": 1,
                "percentage": 33.4
            }
        ]

    if marks == 4:

        return [
            {
                "criterion": "Correct concept",
                "marks": 1,
                "percentage": 25
            },
            {
                "criterion": "Explanation",
                "marks": 1,
                "percentage": 25
            },
            {
                "criterion": "Analysis / application",
                "marks": 1,
                "percentage": 25
            },
            {
                "criterion": "Example / evidence / conclusion",
                "marks": 1,
                "percentage": 25
            }
        ]

    # -----------------------------------------------
    # 5+ MARK QUESTIONS
    # -----------------------------------------------
    base = marks // 5
    remainder = marks % 5

    allocations = [
        base,
        base,
        base,
        base,
        base
    ]

    for i in range(remainder):
        allocations[i] += 1

    criteria = [
        "Understanding of the core concept",
        "Relevant explanation",
        "Application / analysis",
        "Evidence or example",
        "Conclusion / justification"
    ]

    scheme = []

    for criterion, mark_value in zip(criteria, allocations):

        if mark_value > 0:

            percentage = round(
                (mark_value / marks) * 100,
                1
            )

            scheme.append(
                {
                    "criterion": criterion,
                    "marks": mark_value,
                    "percentage": percentage
                }
            )

    return scheme


# =========================================================
# ANSWER-CLO ALIGNMENT
# =========================================================
def answer_clo_alignment(answer, clo):

    answer_words = get_words(answer)
    clo_words = get_words(clo)

    stopwords = {
        "the", "a", "an", "of", "to", "and", "in", "on",
        "for", "with", "students", "student", "will", "be",
        "able", "should", "can", "by", "from", "this",
        "that", "their", "its"
    }

    a = answer_words - stopwords
    c = clo_words - stopwords

    if not c:
        return 50

    overlap = a.intersection(c)

    ratio = len(overlap) / len(c)

    if ratio >= 0.5:
        return 100

    if ratio >= 0.25:
        return 70

    return 40


# =========================================================
# QUESTION TWEAK
# =========================================================
def tweak_question(
    question,
    request,
    bloom,
    marks,
    question_type,
    clo
):

    q = question.strip()

    request = request.lower()

    if not q:
        return ""

    if "easier" in request:

        return (
            "Explain the main concept related to the following CLO: "
            + clo
        )

    if "harder" in request:

        return (
            "Analyze the issue presented in the following question "
            "and support your response with relevant evidence: "
            + q
        )

    if "analytical" in request:

        return (
            "Analyze the following issue, identify its major factors, "
            "and explain the relationships among them: "
            + q
        )

    if "application" in request:

        return (
            "Apply the relevant concepts to the following real-world "
            "situation and explain your response: "
            + q
        )

    if "critical" in request:

        return (
            "Critically examine the issue presented below. "
            "Provide evidence and justify your response: "
            + q
        )

    if "discipline" in request:

        return (
            "Using concepts relevant to "
            + question_type
            + ", analyze the following issue in relation to the CLO: "
            + q
        )

    if "regenerate" in request:

        verb = BLOOM_VERBS[bloom][0].capitalize()

        return (
            f"{verb} the following concept in relation to the CLO: "
            f"{clo}"
        )

    for level in BLOOM_VERBS:

        if level.lower() in request:

            verb = BLOOM_VERBS[level][0].capitalize()

            if level == "Remember":
                return (
                    f"{verb} the key concepts related to the following "
                    f"topic: {q}"
                )

            if level == "Understand":
                return (
                    f"{verb} the main ideas presented in the following "
                    f"question: {q}"
                )

            if level == "Apply":
                return (
                    f"{verb} the relevant concepts to solve the following "
                    f"problem: {q}"
                )

            if level == "Analyze":
                return (
                    f"{verb} the following issue and explain the "
                    f"relationships among its key components: {q}"
                )

            if level == "Evaluate":
                return (
                    f"{verb} the following issue and justify your response "
                    f"using relevant evidence: {q}"
                )

            if level == "Create":
                return (
                    f"{verb} a solution or framework that addresses "
                    f"the following issue: {q}"
                )

    return q


# =========================================================
# INPUT SECTION
# =========================================================
st.subheader("📝 Assessment Details")

col1, col2 = st.columns(2)

with col1:

    course = st.text_input(
        "📚 Course",
        placeholder="e.g., Introduction to Economics"
    )

    clo = st.text_area(
        "🎯 Course Learning Outcome (CLO)",
        placeholder=(
            "e.g., Analyze the causes and effects of inflation."
        ),
        height=100
    )

    plo = st.text_input(
        "🔗 Program Learning Outcome (PLO)",
        placeholder="e.g., PLO 2 – Problem Analysis"
    )

with col2:

    bloom = st.selectbox(
        "🧠 Target Bloom's Level",
        list(BLOOM_VERBS.keys())
    )

    marks = st.number_input(
        "📝 Marks",
        min_value=1,
        max_value=100,
        value=5
    )

    question_type = st.selectbox(
        "📋 Question Type",
        [
            "Short Answer",
            "MCQ",
            "Problem Solving",
            "Case Study",
            "Essay",
            "Scenario-Based",
            "Numerical",
            "Other"
        ]
    )

question = st.text_area(
    "🤖 Assessment Question",
    value=st.session_state.question,
    placeholder="Paste or type the assessment question here...",
    height=140
)

st.session_state.question = question

# =========================================================
# CHECK BUTTON
# =========================================================
check = st.button(
    "🔍 CHECK OBE ALIGNMENT",
    type="primary",
    use_container_width=True
)

# =========================================================
# RESULTS
# =========================================================
if check:

    if not clo.strip():

        st.error("Please enter the CLO.")
        st.stop()

    if not question.strip():

        st.error("Please enter an assessment question.")
        st.stop()

    # -----------------------------------------------------
    # ALIGNMENT SCORES
    # -----------------------------------------------------
    clo_score, clo_message = clo_alignment(
        question,
        clo
    )

    bloom_score, bloom_message = bloom_alignment(
        question,
        bloom
    )

    marks_score, marks_message = question_length_score(
        question,
        marks
    )

    difficulty_score_value, difficulty_message = difficulty_score(
        question,
        bloom
    )

    plo_confirmed = bool(plo.strip())

    overall = calculate_overall(
        [
            clo_score,
            bloom_score,
            marks_score,
            difficulty_score_value
        ]
    )

    # -----------------------------------------------------
    # REPORT
    # -----------------------------------------------------
    st.divider()

    st.subheader("📊 OBE Alignment Report")

    result_col1, result_col2 = st.columns([1, 2])

    with result_col1:

        st.markdown(
            f"""
            <div class="card" style="text-align:center;">
                <div class="score">{overall}%</div>
                <b>{rating(overall)}</b>
            </div>
            """,
            unsafe_allow_html=True
        )

    with result_col2:

        if overall >= 85:

            st.success(
                "The automated checks indicate strong alignment. "
                "Faculty review remains the final validation step."
            )

        elif overall >= 65:

            st.warning(
                "The question shows partial alignment. "
                "Review the highlighted areas."
            )

        else:

            st.error(
                "The question requires revision based on the "
                "automated checks."
            )

    # -----------------------------------------------------
    # ALIGNMENT CHECKS
    # -----------------------------------------------------
    st.subheader("🔎 Alignment Checks")

    c1, c2 = st.columns(2)

    with c1:

        st.markdown("### 🎯 CLO Alignment")

        if clo_score >= 85:

            st.success(
                f"✅ {clo_score}% — {clo_message}"
            )

        elif clo_score >= 65:

            st.warning(
                f"⚠️ {clo_score}% — {clo_message}"
            )

        else:

            st.error(
                f"❌ {clo_score}% — {clo_message}"
            )

        st.markdown("### 🔗 PLO Mapping")

        if plo_confirmed:

            st.info(
                f"🔗 **Mapped PLO:** {plo}\n\n"
                "PLO mapping is recorded as faculty-confirmed. "
                "The tool does not automatically claim that the mapping "
                "is academically correct."
            )

        else:

            st.error(
                "❌ No PLO selected."
            )

    with c2:

        st.markdown("### 🧠 Bloom's Alignment")

        if bloom_score >= 85:

            st.success(
                f"✅ {bloom_score}% — {bloom_message}"
            )

        elif bloom_score >= 65:

            st.warning(
                f"⚠️ {bloom_score}% — {bloom_message}"
            )

        else:

            st.error(
                f"❌ {bloom_score}% — {bloom_message}"
            )

        st.markdown("### ⚖️ Marks & Scope")

        if marks_score >= 85:

            st.success(
                f"✅ {marks_score}% — {marks_message}"
            )

        else:

            st.warning(
                f"⚠️ {marks_score}% — {marks_message}"
            )

    # -----------------------------------------------------
    # DIFFICULTY
    # -----------------------------------------------------
    st.markdown("### 📈 Cognitive Difficulty")

    if difficulty_score_value >= 85:

        st.success(
            f"✅ {difficulty_score_value}% — "
            f"{difficulty_message}"
        )

    else:

        st.warning(
            f"⚠️ {difficulty_score_value}% — "
            f"{difficulty_message}"
        )

    # =====================================================
    # RECOMMENDED ANSWER
    # =====================================================
    st.divider()

    st.subheader("📝 Recommended Answer")

    recommended_answer = generate_recommended_answer(
        question,
        clo,
        bloom,
        marks
    )

    st.session_state.recommended_answer = recommended_answer

    st.markdown(
        f"""
        <div class="answer-card">
        <b>Suggested Model Answer</b>
        <br><br>
        {recommended_answer}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.caption(
        "This is a suggested model answer. The faculty member "
        "should review it for disciplinary accuracy."
    )

    # =====================================================
    # MARKING SCHEME
    # =====================================================
    st.subheader("📊 Recommended Marking Scheme")

    marking_scheme = generate_marking_scheme(
        question,
        recommended_answer,
        marks,
        bloom
    )

    st.session_state.marking_scheme = marking_scheme

    total_marks = 0
    total_percentage = 0

    for item in marking_scheme:

        total_marks += item["marks"]
        total_percentage += item["percentage"]

    for item in marking_scheme:

        col_a, col_b, col_c = st.columns([5, 1, 2])

        with col_a:
            st.write(
                f"**{item['criterion']}**"
            )

        with col_b:
            st.write(
                f"**{item['marks']}**"
            )

        with col_c:
            st.write(
                f"**{item['percentage']}%**"
            )

    st.divider()

    total_col1, total_col2 = st.columns(2)

    with total_col1:

        st.markdown(
            f"""
            **Total Marks:** {total_marks}/{int(marks)}
            """
        )

    with total_col2:

        st.markdown(
            f"""
            **Total Allocation:** {round(total_percentage, 1)}%
            """
        )

    if round(total_percentage, 1) == 100.0:

        st.success(
            "✅ Marking scheme is completely allocated: 100%"
        )

    # =====================================================
    # ANSWER-CLO ALIGNMENT
    # =====================================================
    st.subheader("🎯 Recommended Answer–CLO Alignment")

    answer_score = answer_clo_alignment(
        recommended_answer,
        clo
    )

    if answer_score >= 85:

        st.success(
            f"✅ Recommended answer alignment: {answer_score}%"
        )

    elif answer_score >= 65:

        st.warning(
            f"⚠️ Recommended answer alignment: {answer_score}%"
        )

    else:

        st.error(
            f"❌ Recommended answer alignment: {answer_score}%"
        )

    # =====================================================
    # SUMMARY
    # =====================================================
    st.divider()

    st.subheader("📋 Assessment Summary")

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

    with summary_col1:

        st.metric(
            "CLO Alignment",
            f"{clo_score}%"
        )

    with summary_col2:

        st.metric(
            "Bloom Alignment",
            f"{bloom_score}%"
        )

    with summary_col3:

        st.metric(
            "Answer–CLO",
            f"{answer_score}%"
        )

    with summary_col4:

        st.metric(
            "Overall",
            f"{overall}%"
        )

    # =====================================================
    # IMPROVEMENTS
    # =====================================================
    st.divider()

    st.subheader("💡 Recommended Improvements")

    suggestions = []

    if clo_score < 85:

        suggestions.append(
            "🎯 Make the question directly measure the concepts "
            "and action required by the CLO."
        )

    if bloom_score < 85:

        verbs = BLOOM_VERBS[bloom][:4]

        suggestions.append(
            f"🧠 Use a clearer **{bloom}** action verb such as: "
            f"{', '.join(verbs)}."
        )

    if not plo_confirmed:

        suggestions.append(
            "🔗 Map the CLO to an appropriate PLO."
        )

    if marks_score < 85:

        suggestions.append(
            "⚖️ Review whether the question provides sufficient "
            "scope for the allocated marks."
        )

    if not suggestions:

        st.success(
            "✨ No major automated alignment issues detected."
        )

    else:

        for suggestion in suggestions:

            st.write(suggestion)

    # =====================================================
    # TWEAK SECTION
    # =====================================================
    st.divider()

    st.subheader("✏️ Tweak This Question")

    st.write(
        "Modify the question and then run the alignment check again."
    )

    tweak1, tweak2, tweak3 = st.columns(3)

    with tweak1:

        if st.button(
            "😊 Make Easier",
            use_container_width=True
        ):

            new_question = tweak_question(
                question,
                "make easier",
                bloom,
                marks,
                question_type,
                clo
            )

            st.session_state.question = new_question

            st.rerun()

        if st.button(
            "🔥 Make Harder",
            use_container_width=True
        ):

            new_question = tweak_question(
                question,
                "make harder",
                bloom,
                marks,
                question_type,
                clo
            )

            st.session_state.question = new_question

            st.rerun()

    with tweak2:

        if st.button(
            "🧠 More Analytical",
            use_container_width=True
        ):

            new_question = tweak_question(
                question,
                "make more analytical",
                bloom,
                marks,
                question_type,
                clo
            )

            st.session_state.question = new_question

            st.rerun()

        if st.button(
            "💡 Application-Based",
            use_container_width=True
        ):

            new_question = tweak_question(
                question,
                "make more application-based",
                bloom,
                marks,
                question_type,
                clo
            )

            st.session_state.question = new_question

            st.rerun()

    with tweak3:

        if st.button(
            "🔎 Critical Thinking",
            use_container_width=True
        ):

            new_question = tweak_question(
                question,
                "make more critical-thinking based",
                bloom,
                marks,
                question_type,
                clo
            )

            st.session_state.question = new_question

            st.rerun()

        if st.button(
            "🔄 Regenerate",
            use_container_width=True
        ):

            new_question = tweak_question(
                question,
                "regenerate",
                bloom,
                marks,
                question_type,
                clo
            )

            st.session_state.question = new_question

            st.rerun()

    # =====================================================
    # CHANGE BLOOM
    # =====================================================
    st.markdown("### 🧠 Change Bloom's Level")

    new_bloom = st.selectbox(
        "Choose another Bloom's level",
        list(BLOOM_VERBS.keys()),
        key="new_bloom"
    )

    if st.button(
        "Apply New Bloom Level",
        use_container_width=True
    ):

        new_question = tweak_question(
            question,
            f"change to {new_bloom}",
            new_bloom,
            marks,
            question_type,
            clo
        )

        st.session_state.question = new_question

        st.rerun()

    # =====================================================
    # FINAL FACULTY DECISION
    # =====================================================
    st.divider()

    st.subheader("👩‍🏫 Faculty Decision")

    st.caption(
        "The tool provides automated assistance. "
        "The faculty member makes the final academic decision."
    )

    approve_col1, approve_col2 = st.columns(2)

    with approve_col1:

        if st.button(
            "✅ APPROVE AS OBE ALIGNED",
            use_container_width=True
        ):

            st.session_state.approval_status = "Approved"

            st.success(
                "Assessment marked as approved by the faculty reviewer."
            )

    with approve_col2:

        if st.button(
            "🔄 NEEDS REVISION",
            use_container_width=True
        ):

            st.session_state.approval_status = "Needs Revision"

            st.warning(
                "Assessment marked for revision."
            )

# =========================================================
# FOOTER
# =========================================================
st.divider()

st.caption(
    "🎓 OBE Assessment Studio | AI-assisted assessment review "
    "with faculty-controlled final validation."
)
