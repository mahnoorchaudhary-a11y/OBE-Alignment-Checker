import streamlit as st
import pandas as pd
import re

# ============================================================
# PAGE CONFIG
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
    font-size: 38px;
    font-weight: 800;
    margin-bottom: 4px;
}

.subtitle {
    font-size: 17px;
    color: #666;
    margin-bottom: 28px;
}

.section-title {
    font-size: 23px;
    font-weight: 750;
    margin-top: 28px;
    margin-bottom: 12px;
}

.score-card {
    border: 1px solid #ddd;
    border-radius: 14px;
    padding: 18px;
    text-align: center;
    background: white;
}

.score-number {
    font-size: 38px;
    font-weight: 800;
}

.good-box {
    background: #eaf7ee;
    border: 1px solid #9bd2aa;
    padding: 15px;
    border-radius: 10px;
}

.review-box {
    background: #fff7df;
    border: 1px solid #e5c76b;
    padding: 15px;
    border-radius: 10px;
}

.info-box {
    background: #eef5ff;
    border: 1px solid #b7ccef;
    padding: 15px;
    border-radius: 10px;
}

.edit-box {
    background: #f7f7f7;
    border: 1px solid #ddd;
    padding: 15px;
    border-radius: 10px;
}

.small-text {
    color: #666;
    font-size: 14px;
}

</style>
""", unsafe_allow_html=True)


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

RANGES = {
    "Foundational": {
        "description": "Knowledge, understanding and basic application.",
        "blooms": ["Remember", "Understand", "Apply"],
        "difficulty": "Easy–Moderate"
    },
    "Applied": {
        "description": "Application, analysis and problem-solving.",
        "blooms": ["Apply", "Analyze"],
        "difficulty": "Moderate"
    },
    "Advanced": {
        "description": "Evaluation, creation, design and higher-order thinking.",
        "blooms": ["Evaluate", "Create"],
        "difficulty": "Challenging"
    }
}

QUESTION_TYPES = [
    "Short Answer",
    "Essay / Written",
    "MCQ",
    "Problem Solving",
    "Case Study",
    "Practical / Laboratory",
    "Project / Task",
    "Oral Presentation",
    "Viva",
    "Debate / Discussion",
    "Demonstration",
    "Simulation",
    "Design Task",
    "Programming Task",
    "Other"
]

EVIDENCE_TYPES = [
    "Written Response",
    "Calculation / Numerical Work",
    "Analysis / Interpretation",
    "Oral Performance",
    "Practical Performance",
    "Product / Design",
    "Code / Program",
    "Project / Portfolio",
    "Presentation",
    "Demonstration",
    "Case Analysis",
    "Other"
]


# ============================================================
# BLOOM VERBS
# ============================================================

BLOOM_VERBS = {

    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "recall",
        "state",
        "recognize",
        "label",
        "mention"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss",
        "illustrate",
        "compare"
    ],

    "Apply": [
        "apply",
        "calculate",
        "use",
        "demonstrate",
        "solve",
        "perform",
        "implement",
        "execute"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "examine",
        "differentiate",
        "investigate",
        "compare",
        "distinguish",
        "break down",
        "identify relationships"
    ],

    "Evaluate": [
        "evaluate",
        "justify",
        "assess",
        "critique",
        "defend",
        "judge",
        "appraise",
        "recommend",
        "argue"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "construct",
        "formulate",
        "produce",
        "propose",
        "generate"
    ]
}


# ============================================================
# EVIDENCE CLUES
# ============================================================

EVIDENCE_CLUES = {

    "Written Response": [
        "write",
        "written",
        "essay",
        "paragraph",
        "response",
        "answer",
        "explain",
        "discuss"
    ],

    "Calculation / Numerical Work": [
        "calculate",
        "compute",
        "determine",
        "solve",
        "equation",
        "formula",
        "value",
        "numerical"
    ],

    "Analysis / Interpretation": [
        "analyze",
        "analyse",
        "interpret",
        "examine",
        "compare",
        "differentiate",
        "data",
        "results",
        "relationship"
    ],

    "Oral Performance": [
        "speak",
        "oral",
        "present",
        "presentation",
        "verbally",
        "discuss",
        "communicate",
        "respond"
    ],

    "Practical Performance": [
        "perform",
        "conduct",
        "carry out",
        "demonstrate",
        "experiment",
        "procedure",
        "practical",
        "execute"
    ],

    "Product / Design": [
        "design",
        "create",
        "develop",
        "construct",
        "prototype",
        "model",
        "product"
    ],

    "Code / Program": [
        "code",
        "program",
        "implement",
        "algorithm",
        "function",
        "software",
        "application"
    ],

    "Project / Portfolio": [
        "project",
        "portfolio",
        "document",
        "develop",
        "submit",
        "collect"
    ],

    "Presentation": [
        "present",
        "presentation",
        "slides",
        "deliver",
        "explain"
    ],

    "Demonstration": [
        "demonstrate",
        "show",
        "perform",
        "display"
    ],

    "Case Analysis": [
        "case",
        "scenario",
        "situation",
        "analyze",
        "analyse",
        "recommend",
        "interpret"
    ]
}


# ============================================================
# QUESTION TYPE → EVIDENCE
# ============================================================

QUESTION_EVIDENCE_MAP = {

    "Short Answer": [
        "Written Response",
        "Analysis / Interpretation"
    ],

    "Essay / Written": [
        "Written Response",
        "Analysis / Interpretation"
    ],

    "MCQ": [
        "Written Response"
    ],

    "Problem Solving": [
        "Calculation / Numerical Work",
        "Analysis / Interpretation",
        "Written Response"
    ],

    "Case Study": [
        "Case Analysis",
        "Analysis / Interpretation",
        "Written Response"
    ],

    "Practical / Laboratory": [
        "Practical Performance",
        "Calculation / Numerical Work",
        "Analysis / Interpretation"
    ],

    "Project / Task": [
        "Project / Portfolio",
        "Product / Design",
        "Demonstration"
    ],

    "Oral Presentation": [
        "Oral Performance",
        "Presentation"
    ],

    "Viva": [
        "Oral Performance"
    ],

    "Debate / Discussion": [
        "Oral Performance",
        "Presentation"
    ],

    "Demonstration": [
        "Demonstration",
        "Practical Performance"
    ],

    "Simulation": [
        "Practical Performance",
        "Demonstration"
    ],

    "Design Task": [
        "Product / Design",
        "Project / Portfolio"
    ],

    "Programming Task": [
        "Code / Program"
    ],

    "Other": [
        "Other"
    ]
}


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "question": "",
    "suggested_question": "",
    "review": None,
    "decision": "",
    "answer": "",
    "scheme": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words(text):

    stopwords = {
        "the", "a", "an", "and", "or", "of", "to",
        "in", "on", "for", "with", "by", "from",
        "be", "is", "are", "was", "were",
        "this", "that", "these", "those",
        "student", "students",
        "ability", "demonstrate"
    }

    return {
        word
        for word in normalize(text).split()
        if len(word) > 2 and word not in stopwords
    }


def overlap(text1, text2):

    w1 = words(text1)
    w2 = words(text2)

    if not w1 or not w2:
        return 0

    common = w1.intersection(w2)

    return round(
        len(common) / max(len(w1), len(w2)) * 100
    )


def contains_any(text, terms):

    text = normalize(text)

    return any(
        re.search(r"\b" + re.escape(term) + r"\b", text)
        for term in terms
    )


# ============================================================
# DETECT BLOOM
# ============================================================

def detect_bloom(question):

    q = normalize(question)

    found = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                q
            ):
                found.append(level)

    return list(dict.fromkeys(found))


# ============================================================
# FIND CLO ACTION
# ============================================================

def clo_actions(clo):

    result = []

    q = normalize(clo)

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                q
            ):
                result.append((verb, level))

    return result


# ============================================================
# QUESTION TYPE CHECK
# ============================================================

def check_question_type(question_type, evidence):

    allowed = QUESTION_EVIDENCE_MAP.get(
        question_type,
        ["Other"]
    )

    if evidence in allowed:
        return 100, "The selected question type can directly produce the selected evidence."

    if evidence == "Other":
        return 100, "Faculty selected Other; no restrictive compatibility rule applied."

    return 75, (
        f"{question_type} normally produces different evidence. "
        f"Consider changing the evidence type or assessment method."
    )


# ============================================================
# EVIDENCE CHECK
# ============================================================

def check_evidence(question, evidence):

    if evidence == "Other":
        return 100, "Other evidence selected; faculty can review the evidence manually."

    clues = EVIDENCE_CLUES.get(evidence, [])

    if contains_any(question, clues):
        return 100, (
            f"The wording provides observable evidence through "
            f"{evidence.lower()}."
        )

    return 70, (
        f"The question does not clearly state how students will produce "
        f"{evidence.lower()}."
    )


# ============================================================
# BLOOM CHECK
# ============================================================

def check_bloom(question, selected_bloom):

    detected = detect_bloom(question)

    if selected_bloom in detected:
        return 100, (
            f"The question contains action language consistent with "
            f"{selected_bloom}."
        )

    if not detected:
        return 80, (
            "The question does not contain a clear Bloom action verb. "
            "Consider adding an observable action."
        )

    order = {
        level: i
        for i, level in enumerate(BLOOM_LEVELS)
    }

    distance = min(
        abs(
            order[selected_bloom] -
            order[level]
        )
        for level in detected
    )

    if distance == 1:
        return 90, (
            f"The question uses a nearby cognitive level "
            f"({', '.join(detected)})."
        )

    return 70, (
        f"The question appears to use {', '.join(detected)} "
        f"rather than the selected {selected_bloom} level."
    )


# ============================================================
# QUESTION ↔ CLO CHECK
# ============================================================

def check_clo(clo, question, evidence):

    if not clo.strip():
        return 0, "CLO is missing."

    actions = clo_actions(clo)

    evidence_score, _ = check_evidence(
        question,
        evidence
    )

    semantic_overlap = overlap(
        clo,
        question
    )

    # Strong evidence can compensate for different vocabulary.
    if evidence_score == 100:

        if semantic_overlap >= 5:
            return 100, (
                "The question addresses the CLO and requires evidence "
                "through the selected assessment performance."
            )

        return 95, (
            "The question provides appropriate evidence, but its "
            "connection to the CLO could be made more explicit."
        )

    if semantic_overlap >= 15:
        return 90, (
            "The question is conceptually related to the CLO, "
            "but the required evidence could be clearer."
        )

    return 75, (
        "The question does not yet provide sufficiently explicit "
        "evidence of the CLO."
    )


# ============================================================
# CLO ↔ PLO CHECK
# ============================================================

def check_clo_plo(clo, plo):

    if not plo.strip():
        return 100, (
            "No PLO was entered. CLO alignment can still be reviewed."
        )

    similarity = overlap(
        clo,
        plo
    )

    if similarity >= 10:
        return 100, (
            "The CLO and PLO show a clear conceptual relationship."
        )

    if similarity >= 5:
        return 90, (
            "The CLO appears related to the selected PLO, "
            "although the wording differs."
        )

    return 85, (
        "The CLO–PLO relationship should be confirmed by the faculty."
    )


# ============================================================
# PLO ↔ QUESTION CHECK
# ============================================================

def check_plo_question(
    clo,
    plo,
    question,
    evidence
):

    if not plo.strip():
        return 100, (
            "No PLO entered; PLO-level review is not required."
        )

    clo_plo_score, _ = check_clo_plo(
        clo,
        plo
    )

    clo_question_score, _ = check_clo(
        clo,
        question,
        evidence
    )

    # If the CLO is clearly linked to the PLO and the question
    # measures the CLO, the assessment can be considered fully aligned.
    if (
        clo_plo_score >= 90
        and clo_question_score >= 95
    ):
        return 100, (
            "The assessment follows a coherent CLO → PLO → "
            "assessment evidence pathway."
        )

    if clo_plo_score >= 85:
        return 90, (
            "The assessment is reasonably connected to the PLO "
            "through the CLO."
        )

    return 80, (
        "The relationship between the PLO and assessment evidence "
        "should be reviewed."
    )


# ============================================================
# SUGGEST EDIT
# ============================================================

def suggest_edit(
    question,
    clo,
    plo,
    bloom,
    question_type,
    evidence,
    subject,
    topic
):

    suggestions = []
    revised = question.strip()

    # --------------------------------------------------------
    # BLOOM EDIT
    # --------------------------------------------------------

    bloom_score, _ = check_bloom(
        question,
        bloom
    )

    if bloom_score < 100:

        bloom_phrases = {

            "Remember":
                "Identify and state",

            "Understand":
                "Explain and describe",

            "Apply":
                "Apply the relevant concepts to",

            "Analyze":
                "Analyze the relevant information and",

            "Evaluate":
                "Evaluate the situation and justify",

            "Create":
                "Design or develop a suitable solution for"
        }

        phrase = bloom_phrases[bloom]

        suggestions.append({
            "area": "Bloom's Level",
            "issue": (
                f"The question does not clearly demonstrate "
                f"the selected {bloom} level."
            ),
            "edit": (
                f"Consider beginning the task with "
                f"'{phrase}' to make the expected cognitive action observable."
            )
        })

        # Avoid blindly replacing the entire question.
        revised = (
            f"{phrase} the following {topic} task. "
            f"{question[0].lower() + question[1:]}"
            if question
            else question
        )

    # --------------------------------------------------------
    # EVIDENCE EDIT
    # --------------------------------------------------------

    evidence_score, _ = check_evidence(
        question,
        evidence
    )

    if evidence_score < 100:

        evidence_phrases = {

            "Written Response":
                "Provide a written response explaining your reasoning.",

            "Calculation / Numerical Work":
                "Show all relevant calculations and explain the final result.",

            "Analysis / Interpretation":
                "Analyze the relevant information and interpret the result.",

            "Oral Performance":
                "Present your response orally and communicate your ideas clearly.",

            "Practical Performance":
                "Perform the required procedure and demonstrate the relevant skills.",

            "Product / Design":
                "Develop a suitable product or design and explain your major decisions.",

            "Code / Program":
                "Implement the solution as a working program and explain the main approach.",

            "Project / Portfolio":
                "Provide documented evidence of your project work and explain the outcome.",

            "Presentation":
                "Present your response clearly and support it with relevant evidence.",

            "Demonstration":
                "Demonstrate the required process or skill.",

            "Case Analysis":
                "Analyze the case and justify your conclusion."
        }

        if evidence in evidence_phrases:

            suggestions.append({
                "area": "Evidence",
                "issue": (
                    f"The question does not clearly require "
                    f"{evidence.lower()}."
                ),
                "edit": evidence_phrases[evidence]
            })

            if revised == question.strip():
                revised = (
                    question.rstrip(".") +
                    ". " +
                    evidence_phrases[evidence]
                )

            else:
                revised += (
                    " " +
                    evidence_phrases[evidence]
                )

    # --------------------------------------------------------
    # CLO EDIT
    # --------------------------------------------------------

    clo_score, _ = check_clo(
        clo,
        question,
        evidence
    )

    if clo_score < 95:

        suggestions.append({
            "area": "CLO Alignment",
            "issue": (
                "The question could provide clearer evidence "
                "of the competency stated in the CLO."
            ),
            "edit": (
                "Add an observable task requirement that requires "
                "the student to demonstrate the specific competency "
                "described in the CLO."
            )
        })

    # --------------------------------------------------------
    # QUESTION TYPE
    # --------------------------------------------------------

    type_score, _ = check_question_type(
        question_type,
        evidence
    )

    if type_score < 100:

        suggestions.append({
            "area": "Question Type / Evidence",
            "issue": (
                f"{question_type} may not directly produce "
                f"{evidence.lower()}."
            ),
            "edit": (
                "Either change the evidence type to match the assessment "
                "method or revise the assessment task so the selected "
                "evidence is actually produced."
            )
        })

    # --------------------------------------------------------
    # FINAL SUGGESTION
    # --------------------------------------------------------

    if not suggestions:

        return [], question

    # Clean repeated spaces.
    revised = re.sub(
        r"\s+",
        " ",
        revised
    ).strip()

    return suggestions, revised


# ============================================================
# FULL REVIEW
# ============================================================

def review_question(
    subject,
    topic,
    clo,
    plo,
    bloom,
    question_type,
    evidence,
    question
):

    clo_score, clo_reason = check_clo(
        clo,
        question,
        evidence
    )

    clo_plo_score, clo_plo_reason = check_clo_plo(
        clo,
        plo
    )

    plo_score, plo_reason = check_plo_question(
        clo,
        plo,
        question,
        evidence
    )

    bloom_score, bloom_reason = check_bloom(
        question,
        bloom
    )

    evidence_score, evidence_reason = check_evidence(
        question,
        evidence
    )

    type_score, type_reason = check_question_type(
        question_type,
        evidence
    )

    # ========================================================
    # 100% RULE
    # ========================================================
    #
    # Marks and difficulty are NOT part of this score.
    #
    # A question can reach 100% if:
    #
    # CLO evidence       >= 95
    # CLO-PLO pathway    >= 90
    # PLO evidence       >= 95
    # Bloom              >= 90
    # Evidence           >= 90
    # Question type      >= 90
    #
    # This avoids punishing properly aligned questions merely
    # because their wording differs from the CLO/PLO.
    # ========================================================

    if (
        clo_score >= 95
        and clo_plo_score >= 90
        and plo_score >= 95
        and bloom_score >= 90
        and evidence_score >= 90
        and type_score >= 90
    ):
        overall = 100

    else:

        overall = round(
            (
                clo_score * 0.30
                + clo_plo_score * 0.15
                + plo_score * 0.20
                + bloom_score * 0.15
                + evidence_score * 0.10
                + type_score * 0.10
            )
        )

    suggestions, revised = suggest_edit(
        question,
        clo,
        plo,
        bloom,
        question_type,
        evidence,
        subject,
        topic
    )

    return {
        "overall": overall,

        "clo": clo_score,
        "clo_reason": clo_reason,

        "clo_plo": clo_plo_score,
        "clo_plo_reason": clo_plo_reason,

        "plo": plo_score,
        "plo_reason": plo_reason,

        "bloom": bloom_score,
        "bloom_reason": bloom_reason,

        "evidence": evidence_score,
        "evidence_reason": evidence_reason,

        "type": type_score,
        "type_reason": type_reason,

        "suggestions": suggestions,
        "suggested_question": revised
    }


# ============================================================
# DIFFICULTY
# ============================================================

def difficulty(bloom):

    if bloom in ["Remember", "Understand"]:
        return "Easy"

    if bloom in ["Apply", "Analyze"]:
        return "Moderate"

    return "Challenging"


# ============================================================
# MARKING SCHEME
# ============================================================

def create_marking_scheme(marks, bloom):

    if bloom in ["Remember", "Understand"]:

        criteria = [
            ("Accuracy of knowledge", 30),
            ("Understanding", 30),
            ("Relevance", 20),
            ("Clarity and completeness", 20)
        ]

    elif bloom == "Apply":

        criteria = [
            ("Correct application", 30),
            ("Method / procedure", 25),
            ("Accuracy", 25),
            ("Explanation", 20)
        ]

    elif bloom == "Analyze":

        criteria = [
            ("Identification of relevant factors", 20),
            ("Analysis and reasoning", 30),
            ("Use of evidence / concepts", 25),
            ("Interpretation / conclusion", 25)
        ]

    elif bloom == "Evaluate":

        criteria = [
            ("Use of appropriate criteria", 20),
            ("Evaluation", 30),
            ("Evidence and justification", 30),
            ("Conclusion / recommendation", 20)
        ]

    else:

        criteria = [
            ("Quality of solution / design", 30),
            ("Application of concepts", 25),
            ("Justification", 25),
            ("Clarity and completeness", 20)
        ]

    rows = []

    for criterion, percentage in criteria:

        rows.append({
            "Criterion": criterion,
            "Marks": round(
                marks * percentage / 100,
                2
            ),
            "Allocation": f"{percentage}%"
        })

    return pd.DataFrame(rows)


# ============================================================
# EXPECTED ANSWER
# ============================================================

def expected_answer(
    question,
    bloom,
    evidence
):

    return (
        f"The expected response should directly address the assessment task "
        f"and demonstrate the competency identified in the CLO.\n\n"
        f"The student should provide accurate, relevant and sufficiently "
        f"supported evidence through {evidence.lower()}.\n\n"
        f"The response should demonstrate the selected Bloom level: "
        f"{bloom}."
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 OBE Assessment Studio</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Review your own assessment questions, identify alignment gaps, '
    'and decide which suggested edits to accept.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# 1. CONTEXT
# ============================================================

st.markdown(
    '<div class="section-title">1. Course & Topic</div>',
    unsafe_allow_html=True
)

col1, col2 = st.columns(2)

with col1:

    subject = st.text_input(
        "Subject / Discipline",
        placeholder="e.g., Chemistry, Computer Science, Business, Biology, English"
    )

with col2:

    topic = st.text_input(
        "Topic",
        placeholder="e.g., Acid–Base Titration"
    )


# ============================================================
# 2. CLO / PLO
# ============================================================

st.markdown(
    '<div class="section-title">2. Learning Outcomes</div>',
    unsafe_allow_html=True
)

clo = st.text_area(
    "Course Learning Outcome (CLO)",
    placeholder=(
        "Enter the CLO that this question is intended to assess."
    )
)

plo = st.text_area(
    "Program Learning Outcome (PLO)",
    placeholder=(
        "Enter the PLO linked with this CLO."
    )
)


# ============================================================
# 3. RANGE
# ============================================================

st.markdown(
    '<div class="section-title">3. Assessment Range</div>',
    unsafe_allow_html=True
)

range_cols = st.columns(3)

for i, (name, details) in enumerate(RANGES.items()):

    with range_cols[i]:

        st.markdown(
            f"""
            <div class="info-box">
            <h4>{name}</h4>
            <div>{details["description"]}</div>
            <br>
            <b>Bloom:</b> {", ".join(details["blooms"])}<br>
            <b>Typical difficulty:</b> {details["difficulty"]}
            </div>
            """,
            unsafe_allow_html=True
        )

assessment_range = st.radio(
    "Select range",
    list(RANGES.keys()),
    horizontal=True
)


# ============================================================
# 4. ASSESSMENT DESIGN
# ============================================================

st.markdown(
    '<div class="section-title">4. Assessment Design</div>',
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

with col1:

    bloom = st.selectbox(
        "Bloom's Level",
        RANGES[assessment_range]["blooms"]
    )

with col2:

    question_type = st.selectbox(
        "Question Type",
        QUESTION_TYPES
    )

with col3:

    evidence = st.selectbox(
        "Evidence Produced",
        EVIDENCE_TYPES
    )

marks = st.number_input(
    "Marks",
    min_value=1,
    max_value=100,
    value=10
)


# ============================================================
# 5. FACULTY QUESTION
# ============================================================

st.markdown(
    '<div class="section-title">5. Enter Your Question</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="info-box">
    <b>Faculty Control:</b>
    Enter your own assessment question. The tool will review it,
    but it will never silently replace or modify your question.
    </div>
    """,
    unsafe_allow_html=True
)

question = st.text_area(
    "Your Assessment Question",
    value=st.session_state.question,
    height=180,
    placeholder=(
        "Type the exact question you intend to give students."
    )
)

st.session_state.question = question


# ============================================================
# 6. CHECK BUTTON
# ============================================================

if st.button(
    "🔍 CHECK OBE ALIGNMENT",
    use_container_width=True,
    type="primary"
):

    if not subject.strip():

        st.warning(
            "Please enter the subject / discipline."
        )

    elif not topic.strip():

        st.warning(
            "Please enter the topic."
        )

    elif not clo.strip():

        st.warning(
            "Please enter the CLO."
        )

    elif not plo.strip():

        st.warning(
            "Please enter the PLO."
        )

    elif not question.strip():

        st.warning(
            "Please enter your assessment question."
        )

    else:

        st.session_state.review = review_question(
            subject,
            topic,
            clo,
            plo,
            bloom,
            question_type,
            evidence,
            question
        )

        st.session_state.decision = ""


# ============================================================
# 7. REVIEW RESULTS
# ============================================================

if st.session_state.review:

    review = st.session_state.review

    st.markdown(
        '<div class="section-title">6. OBE Alignment Review</div>',
        unsafe_allow_html=True
    )

    overall = review["overall"]

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            f"""
            <div class="score-card">
                <div>OBE ALIGNMENT</div>
                <div class="score-number">{overall}%</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:

        st.markdown(
            f"""
            <div class="score-card">
                <div>DIFFICULTY</div>
                <div class="score-number" style="font-size:28px;">
                    {difficulty(bloom)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:

        st.markdown(
            f"""
            <div class="score-card">
                <div>BLOOM</div>
                <div class="score-number" style="font-size:28px;">
                    {bloom}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("### Alignment Breakdown")

    breakdown = pd.DataFrame([
        [
            "CLO → Question",
            review["clo"],
            review["clo_reason"]
        ],
        [
            "CLO → PLO",
            review["clo_plo"],
            review["clo_plo_reason"]
        ],
        [
            "PLO → Question",
            review["plo"],
            review["plo_reason"]
        ],
        [
            "Bloom's Level",
            review["bloom"],
            review["bloom_reason"]
        ],
        [
            "Evidence",
            review["evidence"],
            review["evidence_reason"]
        ],
        [
            "Question Type",
            review["type"],
            review["type_reason"]
        ]
    ], columns=[
        "Alignment Component",
        "Score",
        "Review"
    ])

    st.dataframe(
        breakdown,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 8. RESULT MESSAGE
# ============================================================

if st.session_state.review:

    review = st.session_state.review

    if review["overall"] == 100:

        st.markdown(
            """
            <div class="good-box">
            <h3>🎯 100% OBE Alignment</h3>
            Your question provides appropriate evidence for the selected
            CLO and PLO and is consistent with the selected assessment design.
            </div>
            """,
            unsafe_allow_html=True
        )

    elif review["overall"] >= 90:

        st.markdown(
            """
            <div class="review-box">
            <h3>🟡 Strong Alignment — Minor Review</h3>
            The question is substantially aligned, but the suggested edits
            below may make the evidence more explicit.
            </div>
            """,
            unsafe_allow_html=True
        )

    elif review["overall"] >= 80:

        st.warning(
            "The question has reasonable alignment but should be reviewed before approval."
        )

    else:

        st.error(
            "The question requires revision to provide stronger evidence of the intended outcomes."
        )


# ============================================================
# 9. SUGGESTED EDITS
# ============================================================

if st.session_state.review:

    review = st.session_state.review

    st.markdown(
        '<div class="section-title">7. Suggested Edits</div>',
        unsafe_allow_html=True
    )

    suggestions = review["suggestions"]

    if not suggestions:

        st.success(
            "✓ No specific edits are required. Your question is already strongly aligned."
        )

    else:

        for i, suggestion in enumerate(suggestions):

            st.markdown(
                f"""
                <div class="edit-box">
                <h4>{suggestion["area"]}</h4>

                <b>Issue identified:</b><br>
                {suggestion["issue"]}

                <br><br>

                <b>Suggested improvement:</b><br>
                {suggestion["edit"]}
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write("")

        st.markdown("### Suggested Revised Version")

        suggested_question = st.text_area(
            "Review before accepting",
            value=review["suggested_question"],
            height=180,
            key="suggested_question_box"
        )

        st.markdown(
            """
            <div class="small-text">
            The suggested version is only a recommendation. Faculty can edit,
            partially use, or reject it.
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            if st.button(
                "✅ ACCEPT SUGGESTED EDIT",
                use_container_width=True
            ):

                st.session_state.question = suggested_question

                st.session_state.review = review_question(
                    subject,
                    topic,
                    clo,
                    plo,
                    bloom,
                    question_type,
                    evidence,
                    suggested_question
                )

                st.rerun()

        with col2:

            if st.button(
                "↩️ KEEP MY QUESTION",
                use_container_width=True
            ):

                st.info(
                    "Your original question has been retained."
                )

        with col3:

            if st.button(
                "✏️ EDIT MANUALLY",
                use_container_width=True
            ):

                st.session_state.question = suggested_question

                st.rerun()


# ============================================================
# 10. MANUAL RECHECK
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">8. Revise & Recheck</div>',
        unsafe_allow_html=True
    )

    revised_question = st.text_area(
        "Current Question",
        value=st.session_state.question,
        height=180,
        key="current_question_editor"
    )

    st.session_state.question = revised_question

    if st.button(
        "🔄 RECHECK REVISED QUESTION",
        use_container_width=True
    ):

        if revised_question.strip():

            st.session_state.review = review_question(
                subject,
                topic,
                clo,
                plo,
                bloom,
                question_type,
                evidence,
                revised_question
            )

            st.rerun()


# ============================================================
# 11. MARKS & DIFFICULTY
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">9. Marks & Difficulty</div>',
        unsafe_allow_html=True
    )

    st.info(
        "Marks and difficulty are advisory. They do not reduce the OBE alignment percentage."
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Marks",
            marks
        )

    with col2:

        st.metric(
            "Difficulty",
            difficulty(bloom)
        )


# ============================================================
# 12. ANSWER
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">10. Recommended Answer / Expected Evidence</div>',
        unsafe_allow_html=True
    )

    answer = expected_answer(
        st.session_state.question,
        bloom,
        evidence
    )

    st.session_state.answer = answer

    edited_answer = st.text_area(
        "Recommended Answer",
        value=answer,
        height=170
    )

    st.session_state.answer = edited_answer


# ============================================================
# 13. MARKING SCHEME
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">11. Recommended Marking Scheme</div>',
        unsafe_allow_html=True
    )

    scheme = create_marking_scheme(
        marks,
        bloom
    )

    st.session_state.scheme = scheme

    st.dataframe(
        scheme,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Allocation percentages show how the total marks are distributed across criteria."
    )


# ============================================================
# 14. FACULTY DECISION
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">12. Faculty Decision</div>',
        unsafe_allow_html=True
    )

    decision = st.radio(
        "Assessment status",
        [
            "Approve",
            "Needs Revision"
        ],
        horizontal=True
    )

    st.session_state.decision = decision

    if decision == "Approve":

        st.success(
            "✓ Assessment marked as approved by faculty."
        )

    else:

        st.warning(
            "Assessment marked for revision."
        )


# ============================================================
# 15. FINAL SUMMARY
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">13. Assessment Summary</div>',
        unsafe_allow_html=True
    )

    current_score = (
        st.session_state.review["overall"]
        if st.session_state.review
        else "Not checked"
    )

    summary = pd.DataFrame([
        ["Subject", subject],
        ["Topic", topic],
        ["Assessment Range", assessment_range],
        ["Bloom Level", bloom],
        ["Question Type", question_type],
        ["Evidence", evidence],
        ["Marks", marks],
        ["Difficulty", difficulty(bloom)],
        ["OBE Alignment", f"{current_score}%"],
        ["Faculty Decision", st.session_state.decision or "Not decided"]
    ], columns=[
        "Field",
        "Value"
    ])

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 16. METHODOLOGY
# ============================================================

with st.expander("ℹ️ How This Tool Reviews Alignment"):

    st.markdown("""
### The tool does not simply compare words.

It reviews the relationship between:

**CLO → PLO → Question → Evidence**

It also checks:

- Bloom's cognitive level
- Assessment method
- Evidence produced
- Assessment range
- Question wording

### Three Assessment Ranges

**Foundational**
- Remember
- Understand
- Apply

**Applied**
- Apply
- Analyze

**Advanced**
- Evaluate
- Create

### Faculty remains in control

The tool:

1. Reviews your question.
2. Identifies possible weaknesses.
3. Suggests an edit.
4. Explains why the edit is suggested.
5. Lets you accept or reject it.
6. Lets you manually edit the question.
7. Rechecks the revised question.

It never silently changes the original question.

### Important

**Marks do not determine alignment.**

**Difficulty does not determine alignment.**

A challenging question can be 100% aligned.

An easy question can also be 100% aligned.

The purpose of alignment is to determine whether the assessment provides appropriate evidence of the intended learning outcome.
""")


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "🎓 OBE Assessment Studio | Faculty-Controlled | Discipline-Neutral | Question Review & Alignment"
)
