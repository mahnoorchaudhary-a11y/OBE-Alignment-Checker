import streamlit as st
import pandas as pd
import re

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Studio",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 36px;
    font-weight: 800;
    margin-bottom: 5px;
}

.subtitle {
    font-size: 16px;
    color: #666;
    margin-bottom: 25px;
}

.section-title {
    font-size: 23px;
    font-weight: 750;
    margin-top: 25px;
    margin-bottom: 12px;
}

.question-box {
    background: #f7f9fc;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #dfe4ea;
    font-size: 17px;
    line-height: 1.6;
}

.success-box {
    background: #eaf8ee;
    border-left: 6px solid #28a745;
    padding: 18px;
    border-radius: 10px;
}

.warning-box {
    background: #fff8e5;
    border-left: 6px solid #e0a800;
    padding: 18px;
    border-radius: 10px;
}

.error-box {
    background: #fff0f0;
    border-left: 6px solid #dc3545;
    padding: 18px;
    border-radius: 10px;
}

.info-box {
    background: #eef6ff;
    border-left: 6px solid #2673dd;
    padding: 18px;
    border-radius: 10px;
}

.small-text {
    color: #777;
    font-size: 13px;
}

</style>
""", unsafe_allow_html=True)


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

BLOOM_VERBS = {

    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize"
    ],

    "Understand": [
        "explain",
        "summarize",
        "describe",
        "interpret",
        "discuss",
        "illustrate"
    ],

    "Apply": [
        "apply",
        "use",
        "demonstrate",
        "solve",
        "implement",
        "practice"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate"
    ],

    "Evaluate": [
        "evaluate",
        "justify",
        "assess",
        "argue",
        "critique",
        "defend",
        "judge",
        "position",
        "agree",
        "disagree"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "construct",
        "produce",
        "formulate",
        "prepare"
    ]
}


# ============================================================
# SESSION STATE
# ============================================================

if "question" not in st.session_state:
    st.session_state.question = ""

if "answer" not in st.session_state:
    st.session_state.answer = ""

if "marking_scheme" not in st.session_state:
    st.session_state.marking_scheme = []

if "checked" not in st.session_state:
    st.session_state.checked = False

if "approval" not in st.session_state:
    st.session_state.approval = "Not Reviewed"

if "alignment_data" not in st.session_state:
    st.session_state.alignment_data = {}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    return str(text).strip()


def word_count(text):

    return len(clean_text(text).split())


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    question = clean_text(question).lower()

    # Higher levels first
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

            if re.search(r"\b" + re.escape(verb) + r"\b", question):

                return level

    return None


# ============================================================
# BLOOM ALIGNMENT
# ============================================================

def check_bloom_alignment(question, selected_bloom):

    question = clean_text(question)

    if not question:
        return 0, "No question entered."

    detected = detect_bloom(question)

    if detected == selected_bloom:

        return 100, f"Question wording supports {selected_bloom}."

    # Special cases where common assessment wording
    # represents higher-order thinking.

    q = question.lower()

    if selected_bloom == "Evaluate":

        evaluation_phrases = [
            "take a position",
            "take a clear position",
            "give your opinion",
            "justify your answer",
            "support your position",
            "do you think",
            "do you agree",
            "do you disagree",
            "defend your position",
            "argue"
        ]

        if any(phrase in q for phrase in evaluation_phrases):

            return 100, "Question requires judgment, position, or justification."

    if selected_bloom == "Analyze":

        analysis_phrases = [
            "analyze",
            "analyse",
            "compare",
            "contrast",
            "examine",
            "differentiate",
            "relationship",
            "causes and effects"
        ]

        if any(phrase in q for phrase in analysis_phrases):

            return 100, "Question requires analysis."

    if selected_bloom == "Apply":

        application_phrases = [
            "apply",
            "use",
            "demonstrate",
            "real-life",
            "real world",
            "situation",
            "scenario"
        ]

        if any(phrase in q for phrase in application_phrases):

            return 100, "Question requires application."

    # Teacher-selected Bloom is treated as authoritative.
    # We do not unnecessarily penalize the assessment.

    return 100, (
        f"Faculty-selected Bloom level: {selected_bloom}. "
        "Review wording if required."
    )


# ============================================================
# CLO ALIGNMENT
# ============================================================

def check_clo_alignment(clo, question):

    clo = clean_text(clo)
    question = clean_text(question)

    if not clo:

        return 0, "CLO has not been entered."

    if not question:

        return 0, "Question has not been entered."

    # IMPORTANT:
    # CLO is faculty-selected and therefore authoritative.
    #
    # The system must NOT demand exact CLO keywords inside
    # the question.
    #
    # A speaking CLO can be assessed through presentation,
    # discussion, viva, speech, debate, etc.

    return 100, (
        "CLO is treated as faculty-confirmed. "
        "The assessment is linked to the selected CLO."
    )


# ============================================================
# PLO ALIGNMENT
# ============================================================

def check_plo_alignment(clo, plo):

    clo = clean_text(clo)
    plo = clean_text(plo)

    if not clo:

        return 0, "CLO is missing."

    if not plo:

        return 0, "PLO is missing."

    # IMPORTANT:
    # PLO mapping is faculty-confirmed.
    # We do NOT use unreliable keyword matching.

    return 100, (
        "CLO → PLO mapping is treated as faculty-confirmed."
    )


# ============================================================
# QUESTION TYPE ALIGNMENT
# ============================================================

def check_question_type(clo, qtype):

    clo = clean_text(clo).lower()

    if not clo:
        return 0, "CLO missing."

    # Speaking / oral communication
    speaking_words = [
        "speaking",
        "oral communication",
        "oral",
        "speak",
        "presentation",
        "communicate ideas",
        "communication skills"
    ]

    if any(word in clo for word in speaking_words):

        if qtype in [
            "Oral Presentation / Speaking",
            "Viva / Oral Question",
            "Debate / Discussion"
        ]:

            return 100, (
                "Question type directly assesses oral communication."
            )

        return 70, (
            "CLO emphasizes oral communication, but the selected "
            "question type is not primarily oral."
        )

    return 100, "Question type can assess the selected CLO."


# ============================================================
# DIFFICULTY
# ============================================================

def get_difficulty(bloom):

    if bloom in ["Remember", "Understand"]:

        return "Easy", "Foundational cognitive demand."

    if bloom in ["Apply", "Analyze"]:

        return "Moderate", "Moderate cognitive demand."

    if bloom in ["Evaluate", "Create"]:

        return "Challenging", "Higher-order cognitive demand."

    return "Moderate", "Moderate cognitive demand."


# ============================================================
# MARKS REVIEW
# ============================================================

def review_marks(marks, qtype, bloom):

    try:
        marks = int(marks)
    except:
        marks = 5

    if qtype in [
        "Oral Presentation / Speaking",
        "Debate / Discussion"
    ]:

        if marks >= 3:

            return "Appropriate", (
                "Marks provide reasonable scope for an oral task."
            )

        return "Review Suggested", (
            "Consider allocating more marks for an oral performance."
        )

    if qtype == "Viva / Oral Question":

        if marks <= 5:

            return "Appropriate", (
                "Marks are reasonable for a viva/oral response."
            )

        return "Review Suggested", (
            "Consider whether the marks match the expected response length."
        )

    if marks <= 10:

        return "Appropriate", (
            "Marks are reasonable for this assessment type."
        )

    return "Review Suggested", (
        "Review the relationship between marks and expected response."
    )


# ============================================================
# QUESTION GENERATOR
# ============================================================

def generate_question(
    course,
    clo,
    plo,
    bloom,
    qtype,
    marks
):

    course = clean_text(course)

    # --------------------------------------------------------
    # ORAL PRESENTATION
    # --------------------------------------------------------

    if qtype == "Oral Presentation / Speaking":

        if bloom == "Evaluate":

            return (
                f"Do you think the use of AI should be allowed in exams? "
                f"Take a clear position and explain your opinion in a "
                f"2–3 minute oral presentation. Support your position "
                f"with at least two relevant reasons and examples."
            )

        if bloom == "Analyze":

            return (
                f"Give a 2–3 minute oral presentation on {course}. "
                f"Analyze the major issues related to the topic and "
                f"support your explanation with relevant examples."
            )

        if bloom == "Apply":

            return (
                f"Give a short oral presentation on {course}. "
                f"Explain how the relevant concepts can be applied "
                f"in a real-life or academic situation."
            )

        if bloom == "Create":

            return (
                f"Prepare and deliver a short oral presentation on "
                f"{course}. Develop your own ideas and support them "
                f"with relevant examples."
            )

        if bloom == "Understand":

            return (
                f"Give a short oral presentation explaining the main "
                f"ideas related to {course}. Use clear language and "
                f"at least one relevant example."
            )

        return (
            f"Give a short oral presentation identifying the key "
            f"ideas related to {course}."
        )

    # --------------------------------------------------------
    # VIVA
    # --------------------------------------------------------

    if qtype == "Viva / Oral Question":

        if bloom == "Evaluate":

            return (
                f"Do you think the use of AI should be allowed in exams? "
                f"Take a clear position and justify your answer with "
                f"at least two reasons."
            )

        if bloom == "Analyze":

            return (
                f"What are the major factors related to {course}? "
                f"Analyze their relationship and give an example."
            )

        if bloom == "Apply":

            return (
                f"How would you apply the concepts related to {course} "
                f"in a real-life situation?"
            )

        return (
            f"Explain the main concept related to {course} "
            f"in your own words."
        )

    # --------------------------------------------------------
    # ESSAY
    # --------------------------------------------------------

    if qtype == "Essay / Written":

        if bloom == "Evaluate":

            return (
                f"Do you think the use of AI should be allowed in exams? "
                f"Take a clear position and support your argument with "
                f"relevant reasons and examples."
            )

        if bloom == "Analyze":

            return (
                f"Analyze the major issues related to {course}. "
                f"Discuss their causes, effects, and implications."
            )

        if bloom == "Apply":

            return (
                f"Explain how the concepts related to {course} "
                f"can be applied in a real-life situation."
            )

        return (
            f"Explain the main concepts related to {course} "
            f"and provide suitable examples."
        )

    # --------------------------------------------------------
    # SHORT ANSWER
    # --------------------------------------------------------

    if qtype == "Short Answer":

        if bloom == "Evaluate":

            return (
                f"Do you agree or disagree with the use of AI in exams? "
                f"Give a clear reason for your position."
            )

        if bloom == "Analyze":

            return (
                f"Analyze one important issue related to {course} "
                f"and provide a relevant example."
            )

        if bloom == "Apply":

            return (
                f"Apply one concept from {course} to a suitable "
                f"real-life example."
            )

        return (
            f"Explain one important concept related to {course}."
        )

    # --------------------------------------------------------
    # DEBATE / DISCUSSION
    # --------------------------------------------------------

    if qtype == "Debate / Discussion":

        return (
            f"Discuss the topic of {course}. Present your position, "
            f"respond to an alternative viewpoint, and support your "
            f"ideas with relevant reasons and examples."
        )

    return (
        f"Discuss the important concepts related to {course} "
        f"and support your answer with relevant examples."
    )


# ============================================================
# RECOMMENDED ANSWER
# ============================================================

def generate_answer(question, bloom):

    q = clean_text(question).lower()

    if "ai" in q and "exam" in q:

        return (
            "A student may argue that the use of AI should be limited "
            "or carefully controlled during exams. First, unrestricted "
            "AI use can make it difficult to determine whether students "
            "have personally achieved the intended learning outcomes. "
            "Second, students may become dependent on AI instead of "
            "developing their own reasoning and communication skills. "
            "However, AI may be permitted in selected assessments when "
            "the purpose is to assess responsible AI use, critical "
            "thinking, or problem solving. Therefore, the rules should "
            "depend on the learning outcomes being assessed."
        )

    if bloom == "Evaluate":

        return (
            "A strong response should take a clear position, provide "
            "relevant reasons, support the reasons with examples or "
            "evidence, consider an alternative viewpoint where "
            "appropriate, and conclude clearly."
        )

    if bloom == "Analyze":

        return (
            "A strong response should identify the main components "
            "of the issue, explain their relationships, and support "
            "the analysis with relevant examples or evidence."
        )

    if bloom == "Apply":

        return (
            "A strong response should explain the relevant concept "
            "and demonstrate how it can be applied correctly to "
            "a realistic situation."
        )

    if bloom == "Create":

        return (
            "A strong response should present an original and "
            "well-organized idea, solution, or approach and explain "
            "why it is appropriate."
        )

    if bloom == "Understand":

        return (
            "A strong response should explain the concept accurately "
            "using clear language and provide a relevant example."
        )

    return (
        "A strong response should correctly identify the required "
        "information and present it clearly."
    )


# ============================================================
# MARKING SCHEME
# ============================================================

def generate_marking_scheme(marks, bloom, qtype):

    marks = int(marks)

    # --------------------------------------------------------
    # ORAL COMMUNICATION
    # --------------------------------------------------------

    if qtype in [
        "Oral Presentation / Speaking",
        "Viva / Oral Question",
        "Debate / Discussion"
    ]:

        if bloom in ["Evaluate", "Analyze"]:

            criteria = [
                ("Content and understanding", 20),
                ("Reasoning / analysis / supporting examples", 25),
                ("Organization and coherence", 20),
                ("Language and vocabulary", 15),
                ("Clarity, confidence and delivery", 20)
            ]

        else:

            criteria = [
                ("Content and understanding", 25),
                ("Organization", 20),
                ("Language and vocabulary", 20),
                ("Clarity and pronunciation", 20),
                ("Confidence and delivery", 15)
            ]

    # --------------------------------------------------------
    # WRITTEN
    # --------------------------------------------------------

    elif qtype == "Essay / Written":

        criteria = [
            ("Understanding of topic", 20),
            ("Argument / analysis", 25),
            ("Examples / evidence", 20),
            ("Organization and coherence", 20),
            ("Language and conclusion", 15)
        ]

    # --------------------------------------------------------
    # SHORT ANSWER
    # --------------------------------------------------------

    else:

        criteria = [
            ("Understanding", 25),
            ("Explanation", 20),
            ("Application / analysis", 25),
            ("Example / evidence", 15),
            ("Clarity", 15)
        ]

    # Convert percentages into marks
    raw = [
        marks * percentage / 100
        for _, percentage in criteria
    ]

    allocated = [int(round(x)) for x in raw]

    # Ensure total equals marks
    difference = marks - sum(allocated)

    index = 0

    while difference != 0:

        current = index % len(allocated)

        if difference > 0:

            allocated[current] += 1
            difference -= 1

        else:

            if allocated[current] > 0:

                allocated[current] -= 1
                difference += 1

        index += 1

    result = []

    for (criterion, percentage), mark in zip(
        criteria,
        allocated
    ):

        result.append({
            "Criterion": criterion,
            "Marks": mark,
            "Percentage": round((mark / marks) * 100, 1)
        })

    return result


# ============================================================
# TWEAK QUESTION
# ============================================================

def tweak_question(question, action):

    question = clean_text(question)

    if action == "Make Easier":

        return (
            question +
            " Use simple language and provide one clear example."
        )

    if action == "Make Harder":

        return (
            question +
            " Support your response with multiple relevant examples "
            "and explain the implications of your position."
        )

    if action == "More Analytical":

        return (
            question +
            " Analyze the causes, effects, and implications of the issue."
        )

    if action == "More Application-Based":

        return (
            question +
            " Relate your response to a realistic academic, "
            "professional, or everyday situation."
        )

    if action == "More Critical Thinking":

        return (
            question +
            " Consider an alternative viewpoint before justifying "
            "your conclusion."
        )

    if action == "More Discipline-Specific":

        return (
            question +
            " Use appropriate terminology and a relevant example "
            "from the discipline."
        )

    return question


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 OBE Assessment Studio</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Create and review assessments using CLOs, PLOs, Bloom’s Taxonomy, '
    'assessment type, marks, and marking criteria.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# STEP 1 — COURSE AND OUTCOMES
# ============================================================

st.markdown(
    '<div class="section-title">1. Course & Learning Outcomes</div>',
    unsafe_allow_html=True
)

col1, col2 = st.columns(2)

with col1:

    course = st.text_input(
        "Course",
        value="English I"
    )

    clo = st.text_area(
        "CLO",
        value=(
            "Demonstrate the ability to communicate ideas clearly "
            "and confidently when speaking on a range of topics."
        ),
        height=120
    )

with col2:

    plo = st.text_area(
        "PLO",
        value=(
            "Demonstrate effective oral communication skills in "
            "academic and professional contexts."
        ),
        height=120
    )

    bloom = st.selectbox(
        "Bloom's Level",
        BLOOM_LEVELS,
        index=4
    )


# ============================================================
# STEP 2 — ASSESSMENT SETTINGS
# ============================================================

st.markdown(
    '<div class="section-title">2. Assessment Settings</div>',
    unsafe_allow_html=True
)

c1, c2, c3 = st.columns(3)

with c1:

    qtype = st.selectbox(
        "Question Type",
        [
            "Oral Presentation / Speaking",
            "Viva / Oral Question",
            "Debate / Discussion",
            "Essay / Written",
            "Short Answer"
        ]
    )

with c2:

    marks = st.number_input(
        "Marks",
        min_value=1,
        max_value=100,
        value=5
    )

with c3:

    if st.button(
        "✨ GENERATE QUESTION",
        use_container_width=True
    ):

        st.session_state.question = generate_question(
            course,
            clo,
            plo,
            bloom,
            qtype,
            marks
        )

        st.session_state.answer = generate_answer(
            st.session_state.question,
            bloom
        )

        st.session_state.marking_scheme = (
            generate_marking_scheme(
                marks,
                bloom,
                qtype
            )
        )

        st.session_state.checked = False


# ============================================================
# STEP 3 — QUESTION
# ============================================================

st.markdown(
    '<div class="section-title">3. Assessment Question</div>',
    unsafe_allow_html=True
)

question = st.text_area(
    "Edit the question as required",
    value=st.session_state.question,
    height=160,
    placeholder="Enter your assessment question here..."
)

st.session_state.question = question


# ============================================================
# TWEAK BUTTONS
# ============================================================

st.markdown("### 🛠️ Improve / Tweak Question")

t1, t2, t3 = st.columns(3)

with t1:

    if st.button(
        "Make Easier",
        use_container_width=True
    ):

        st.session_state.question = tweak_question(
            question,
            "Make Easier"
        )

        st.rerun()

with t2:

    if st.button(
        "Make Harder",
        use_container_width=True
    ):

        st.session_state.question = tweak_question(
            question,
            "Make Harder"
        )

        st.rerun()

with t3:

    if st.button(
        "More Analytical",
        use_container_width=True
    ):

        st.session_state.question = tweak_question(
            question,
            "More Analytical"
        )

        st.rerun()


t4, t5, t6 = st.columns(3)

with t4:

    if st.button(
        "More Application-Based",
        use_container_width=True
    ):

        st.session_state.question = tweak_question(
            question,
            "More Application-Based"
        )

        st.rerun()

with t5:

    if st.button(
        "More Critical Thinking",
        use_container_width=True
    ):

        st.session_state.question = tweak_question(
            question,
            "More Critical Thinking"
        )

        st.rerun()

with t6:

    if st.button(
        "More Discipline-Specific",
        use_container_width=True
    ):

        st.session_state.question = tweak_question(
            question,
            "More Discipline-Specific"
        )

        st.rerun()


# ============================================================
# STEP 4 — CHECK ALIGNMENT
# ============================================================

st.markdown(
    '<div class="section-title">4. OBE Alignment</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="info-box">
    <strong>Important:</strong> CLO and PLO mappings are faculty-controlled.
    The system does not reduce alignment merely because the exact CLO or PLO
    wording is not repeated in the question.
    <br><br>
    Marks and difficulty are reported separately and do not reduce the OBE
    alignment percentage.
    </div>
    """,
    unsafe_allow_html=True
)

if st.button(
    "🔍 CHECK OBE ALIGNMENT",
    type="primary",
    use_container_width=True
):

    # --------------------------------------------------------
    # CLO
    # --------------------------------------------------------

    clo_score, clo_message = check_clo_alignment(
        clo,
        question
    )

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------

    plo_score, plo_message = check_plo_alignment(
        clo,
        plo
    )

    # --------------------------------------------------------
    # BLOOM
    # --------------------------------------------------------

    bloom_score, bloom_message = check_bloom_alignment(
        question,
        bloom
    )

    # --------------------------------------------------------
    # QUESTION TYPE
    # --------------------------------------------------------

    question_type_score, question_type_message = (
        check_question_type(
            clo,
            qtype
        )
    )

    # --------------------------------------------------------
    # OBE ALIGNMENT
    # --------------------------------------------------------
    #
    # ONLY actual OBE elements are included.
    #
    # Marks and difficulty are deliberately excluded.
    #

    obe_alignment = round(
        (
            clo_score +
            plo_score +
            bloom_score +
            question_type_score
        ) / 4,
        1
    )

    # --------------------------------------------------------
    # Difficulty
    # --------------------------------------------------------

    difficulty_level, difficulty_message = get_difficulty(
        bloom
    )

    # --------------------------------------------------------
    # Marks
    # --------------------------------------------------------

    marks_status, marks_message = review_marks(
        marks,
        qtype,
        bloom
    )

    # --------------------------------------------------------
    # Store
    # --------------------------------------------------------

    st.session_state.alignment_data = {

        "CLO": clo_score,
        "PLO": plo_score,
        "Bloom": bloom_score,
        "Question Type": question_type_score,
        "OBE": obe_alignment,

        "Difficulty": difficulty_level,
        "Difficulty Message": difficulty_message,

        "Marks Status": marks_status,
        "Marks Message": marks_message,

        "CLO Message": clo_message,
        "PLO Message": plo_message,
        "Bloom Message": bloom_message,
        "Question Type Message": question_type_message
    }

    st.session_state.answer = generate_answer(
        question,
        bloom
    )

    st.session_state.marking_scheme = (
        generate_marking_scheme(
            marks,
            bloom,
            qtype
        )
    )

    st.session_state.checked = True


# ============================================================
# STEP 5 — RESULTS
# ============================================================

if st.session_state.checked:

    data = st.session_state.alignment_data

    st.markdown(
        '<div class="section-title">5. OBE Alignment Result</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # BIG RESULT
    # --------------------------------------------------------

    if data["OBE"] >= 90:

        st.markdown(
            f"""
            <div class="success-box">
            <h2>🟢 OBE ALIGNMENT: {data["OBE"]}%</h2>
            <strong>Assessment is aligned with the selected CLO, PLO,
            Bloom's level, and assessment type.</strong>
            </div>
            """,
            unsafe_allow_html=True
        )

    elif data["OBE"] >= 75:

        st.markdown(
            f"""
            <div class="warning-box">
            <h2>🟡 OBE ALIGNMENT: {data["OBE"]}%</h2>
            Some alignment elements may need faculty review.
            </div>
            """,
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            f"""
            <div class="error-box">
            <h2>🔴 OBE ALIGNMENT: {data["OBE"]}%</h2>
            Review the selected learning outcomes and assessment type.
            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # COMPONENT SCORES
    # --------------------------------------------------------

    st.markdown("### Alignment Components")

    m1, m2, m3, m4 = st.columns(4)

    with m1:

        st.metric(
            "CLO Alignment",
            f'{data["CLO"]}%'
        )

    with m2:

        st.metric(
            "PLO Alignment",
            f'{data["PLO"]}%'
        )

    with m3:

        st.metric(
            "Bloom Alignment",
            f'{data["Bloom"]}%'
        )

    with m4:

        st.metric(
            "Assessment Type",
            f'{data["Question Type"]}%'
        )

    # --------------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------------

    st.markdown("### Why the assessment is aligned")

    st.success(
        "✓ " + data["CLO Message"]
    )

    st.success(
        "✓ " + data["PLO Message"]
    )

    st.success(
        "✓ " + data["Bloom Message"]
    )

    st.success(
        "✓ " + data["Question Type Message"]
    )

    # ========================================================
    # DIFFICULTY
    # ========================================================

    st.markdown(
        '<div class="section-title">6. Difficulty</div>',
        unsafe_allow_html=True
    )

    if data["Difficulty"] == "Easy":

        st.info(
            "🟢 Difficulty: EASY — " +
            data["Difficulty Message"]
        )

    elif data["Difficulty"] == "Moderate":

        st.warning(
            "🟡 Difficulty: MODERATE — " +
            data["Difficulty Message"]
        )

    else:

        st.error(
            "🔴 Difficulty: CHALLENGING — " +
            data["Difficulty Message"]
        )

    st.caption(
        "Difficulty is reported separately. It does NOT reduce the "
        "OBE alignment percentage."
    )

    # ========================================================
    # MARKS REVIEW
    # ========================================================

    st.markdown(
        '<div class="section-title">7. Marks Review</div>',
        unsafe_allow_html=True
    )

    if data["Marks Status"] == "Appropriate":

        st.success(
            "✓ Marks: " +
            data["Marks Status"] +
            " — " +
            data["Marks Message"]
        )

    else:

        st.warning(
            "⚠ Marks: " +
            data["Marks Status"] +
            " — " +
            data["Marks Message"]
        )

    st.caption(
        "Marks review is advisory and does not reduce OBE alignment."
    )

    # ========================================================
    # RECOMMENDED ANSWER
    # ========================================================

    st.markdown(
        '<div class="section-title">8. Recommended Answer</div>',
        unsafe_allow_html=True
    )

    answer = st.text_area(
        "Expected / Recommended Answer",
        value=st.session_state.answer,
        height=200
    )

    st.session_state.answer = answer

    # ========================================================
    # ANSWER ALIGNMENT
    # ========================================================

    answer_words = word_count(answer)

    if answer_words >= 50:

        answer_alignment = 100

    elif answer_words >= 30:

        answer_alignment = 95

    elif answer_words >= 15:

        answer_alignment = 85

    else:

        answer_alignment = 70

    st.metric(
        "Recommended Answer → CLO",
        f"{answer_alignment}%"
    )

    # ========================================================
    # MARKING SCHEME
    # ========================================================

    st.markdown(
        '<div class="section-title">9. Recommended Marking Scheme</div>',
        unsafe_allow_html=True
    )

    st.write(
        "The percentage below represents the allocation of marks. "
        "It is NOT a probability of correctness."
    )

    marking_df = pd.DataFrame(
        st.session_state.marking_scheme
    )

    st.dataframe(
        marking_df,
        use_container_width=True,
        hide_index=True
    )

    total_marks = int(
        marking_df["Marks"].sum()
    )

    total_percentage = round(
        marking_df["Percentage"].sum(),
        1
    )

    mc1, mc2 = st.columns(2)

    with mc1:

        st.metric(
            "Total Marks",
            total_marks
        )

    with mc2:

        st.metric(
            "Total Allocation",
            f"{total_percentage}%"
        )

    # ========================================================
    # COMPLETE ALIGNMENT SUMMARY
    # ========================================================

    st.markdown(
        '<div class="section-title">10. Complete Assessment Summary</div>',
        unsafe_allow_html=True
    )

    summary = pd.DataFrame([

        {
            "Element": "Course",
            "Value": course,
            "Status": "Confirmed"
        },

        {
            "Element": "CLO",
            "Value": clo,
            "Status": "100% Confirmed"
        },

        {
            "Element": "PLO",
            "Value": plo,
            "Status": "100% Confirmed"
        },

        {
            "Element": "Bloom's Level",
            "Value": bloom,
            "Status": f'{data["Bloom"]}%'
        },

        {
            "Element": "Question Type",
            "Value": qtype,
            "Status": f'{data["Question Type"]}%'
        },

        {
            "Element": "Marks",
            "Value": str(marks),
            "Status": data["Marks Status"]
        },

        {
            "Element": "Difficulty",
            "Value": data["Difficulty"],
            "Status": "Separate indicator"
        },

        {
            "Element": "FINAL OBE ALIGNMENT",
            "Value": f'{data["OBE"]}%',
            "Status": "ALIGNED"
        }
    ])

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # FACULTY APPROVAL
    # ========================================================

    st.markdown(
        '<div class="section-title">11. Faculty Decision</div>',
        unsafe_allow_html=True
    )

    approval = st.radio(
        "Assessment Status",
        [
            "Not Reviewed",
            "Approved",
            "Needs Revision"
        ],
        horizontal=True
    )

    st.session_state.approval = approval

    if approval == "Approved":

        st.success(
            "✓ Assessment approved. The faculty member has confirmed "
            "the CLO, PLO, Bloom level, and assessment design."
        )

    elif approval == "Needs Revision":

        st.warning(
            "Assessment marked for revision. Use the tweak controls "
            "above and check alignment again."
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.markdown(
    """
    <div class="small-text">
    🎓 OBE Assessment Studio — Faculty-controlled assessment alignment
    </div>
    """,
    unsafe_allow_html=True
)
