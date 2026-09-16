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

.score {
    font-size: 42px;
    font-weight: 800;
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
    'Generate, tweak, and check assessment questions for CLO, PLO, '
    "Bloom's Taxonomy, marks, and difficulty alignment."
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

if "generated_question" not in st.session_state:
    st.session_state.generated_question = ""

if "tweak_request" not in st.session_state:
    st.session_state.tweak_request = ""

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
        return 50, "The CLO needs more information."

    overlap = q.intersection(c)
    ratio = len(overlap) / len(c)

    if ratio >= 0.5:
        return 100, "The question strongly reflects concepts in the CLO."

    if ratio >= 0.25:
        return 70, "The question has partial conceptual overlap with the CLO."

    return 40, "The question may not directly measure the stated CLO."


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
        return 100, "Question provides sufficient scope for the marks."

    return 70, "Consider providing more scope for a higher-mark question."


def difficulty_score(question, bloom):
    high_level = {"Analyze", "Evaluate", "Create"}

    if bloom in high_level:
        return 100, "Selected Bloom level supports higher-order thinking."

    if bloom in {"Apply", "Understand"}:
        return 85, "Selected Bloom level supports moderate cognitive demand."

    return 75, "Remember-level questions generally involve lower cognitive demand."


def calculate_overall(scores):
    return round(sum(scores) / len(scores))


def rating(score):
    if score >= 85:
        return "🟢 Strong Alignment"

    if score >= 65:
        return "🟡 Moderate Alignment"

    return "🔴 Needs Improvement"


# =========================================================
# QUESTION TWEAK FUNCTION
# =========================================================
def tweak_question(question, request, bloom, marks, question_type, clo):
    """
    Rule-based question tweaking.
    This works without an API key.
    """

    q = question.strip()

    if not q:
        return ""

    request = request.lower()

    # -----------------------------
    # MAKE EASIER
    # -----------------------------
    if "easier" in request:
        if bloom == "Remember":
            return "Define the key concept related to the following CLO: " + clo

        if bloom == "Understand":
            return "Explain the main concept related to: " + clo

        return "Explain the main concept related to the following CLO: " + clo

    # -----------------------------
    # MAKE HARDER
    # -----------------------------
    if "harder" in request:
        return (
            "Analyze the issue presented in the following question and "
            "support your response with relevant evidence: " + q
        )

    # -----------------------------
    # MORE ANALYTICAL
    # -----------------------------
    if "analytical" in request:
        return (
            "Analyze the following issue, identify its major factors, "
            "and explain the relationship between them: " + q
        )

    # -----------------------------
    # APPLICATION BASED
    # -----------------------------
    if "application" in request:
        return (
            "Apply the relevant concepts to the following real-world "
            "situation and explain your response: " + q
        )

    # -----------------------------
    # CRITICAL THINKING
    # -----------------------------
    if "critical" in request:
        return (
            "Critically examine the issue presented below. "
            "Provide evidence and justify your response: " + q
        )

    # -----------------------------
    # DISCIPLINE SPECIFIC
    # -----------------------------
    if "discipline" in request:
        return (
            "Using concepts from " + question_type +
            ", analyze the following issue in relation to the CLO: " + q
        )

    # -----------------------------
    # BLOOM CHANGE
    # -----------------------------
    for level in BLOOM_VERBS:

        if level.lower() in request:

            verbs = BLOOM_VERBS[level]

            verb = verbs[0].capitalize()

            if level == "Remember":
                return f"{verb} the key concepts related to the following topic: {q}"

            if level == "Understand":
                return f"{verb} the main ideas presented in the following question: {q}"

            if level == "Apply":
                return f"{verb} the relevant concepts to solve the following problem: {q}"

            if level == "Analyze":
                return f"{verb} the following issue and explain the relationships among its key components: {q}"

            if level == "Evaluate":
                return f"{verb} the following issue and justify your response using relevant evidence: {q}"

            if level == "Create":
                return f"{verb} a solution or framework that addresses the following issue: {q}"

    # -----------------------------
    # REGENERATE
    # -----------------------------
    if "regenerate" in request:
        return (
            f"{BLOOM_VERBS[bloom][0].capitalize()} the following concept "
            f"in relation to the CLO: {clo}"
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
        placeholder="e.g., Analyze the causes and effects of inflation.",
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

    # -----------------------------
    # SCORES
    # -----------------------------
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

    # PLO mapping is faculty-confirmed,
    # not automatically verified.
    plo_confirmed = bool(plo.strip())

    if plo_confirmed:
        plo_message = (
            f"CLO is mapped to {plo}. "
            "Faculty confirmation is required for final validation."
        )
        plo_display_score = 100
    else:
        plo_message = "No PLO has been selected."
        plo_display_score = 0

    overall = calculate_overall([
        clo_score,
        bloom_score,
        marks_score,
        difficulty_score_value
    ])

    # =====================================================
    # REPORT
    # =====================================================
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
                "The question requires revision based on the automated checks."
            )

    # =====================================================
    # ALIGNMENT CHECKS
    # =====================================================
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
                "Faculty confirmation required for final PLO validation."
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

    # =====================================================
    # DIFFICULTY
    # =====================================================
    st.markdown("### 📈 Cognitive Difficulty")

    if difficulty_score_value >= 85:
        st.success(
            f"✅ {difficulty_score_value}% — {difficulty_message}"
        )
    else:
        st.warning(
            f"⚠️ {difficulty_score_value}% — {difficulty_message}"
        )

    # =====================================================
    # IMPROVEMENTS
    # =====================================================
    st.divider()

    st.subheader("💡 Recommended Improvements")

    suggestions = []

    if clo_score < 85:
        suggestions.append(
            "🎯 Make the question directly measure the concepts and action "
            "required by the CLO."
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
            "⚖️ Review whether the question provides sufficient scope "
            "for the allocated marks."
        )

    if not suggestions:

        st.success(
            "✨ No major automated alignment issues detected. "
            "The faculty member should make the final academic judgment."
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
        "Change one aspect of the question and then run the alignment "
        "check again."
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

            st.success("Question revised to make it easier.")
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

            st.success("Question revised to increase difficulty.")
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

            st.success("Question made more analytical.")
            st.rerun()

        if st.button(
            "💡 More Application-Based",
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

            st.success("Question made more application-based.")
            st.rerun()

    with tweak3:

        if st.button(
            "🔎 More Critical Thinking",
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

            st.success("Question revised for critical thinking.")
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

            st.success("Question regenerated.")
            st.rerun()

    # =====================================================
    # CHANGE BLOOM
    # =====================================================
    st.markdown("### 🧠 Change Bloom's Level")

    new_bloom = st.selectbox(
        "Choose a different Bloom's level",
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

        st.success(
            f"Question revised toward {new_bloom}."
        )

        st.rerun()

    # =====================================================
    # FINAL FACULTY DECISION
    # =====================================================
    st.divider()

    st.subheader("👩‍🏫 Faculty Decision")

    st.caption(
        "The tool provides automated assistance. The faculty member "
        "makes the final academic decision."
    )

    approve_col1, approve_col2 = st.columns(2)

    with approve_col1:

        if st.button(
            "✅ APPROVE",
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
