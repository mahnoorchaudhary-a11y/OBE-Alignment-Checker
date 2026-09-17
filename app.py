import streamlit as st
import pandas as pd
import re

# ============================================================
# OBE ASSESSMENT STUDIO
# Discipline-Neutral CLO/PLO Alignment Checker
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Studio",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# STYLE
# ============================================================

st.markdown("""
<style>
.main-title {
    font-size: 38px;
    font-weight: 800;
    margin-bottom: 4px;
}

.subtitle {
    color: #666;
    font-size: 17px;
    margin-bottom: 25px;
}

.section-title {
    font-size: 23px;
    font-weight: 700;
    margin-top: 28px;
    margin-bottom: 12px;
}

.score-card {
    padding: 22px;
    border-radius: 14px;
    text-align: center;
    border: 1px solid #ddd;
    margin-bottom: 15px;
}

.score-number {
    font-size: 44px;
    font-weight: 800;
}

.good {
    background: #eaf7ee;
    border-left: 6px solid #2e8b57;
}

.medium {
    background: #fff8e6;
    border-left: 6px solid #e0a000;
}

.low {
    background: #fdecec;
    border-left: 6px solid #d9534f;
}

.info-box {
    padding: 15px;
    border-radius: 10px;
    background: #f3f7fc;
    border-left: 5px solid #3182ce;
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

ASSESSMENT_EVIDENCE = [
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
# SESSION STATE
# ============================================================

if "question" not in st.session_state:
    st.session_state.question = ""

if "answer" not in st.session_state:
    st.session_state.answer = ""

if "checked" not in st.session_state:
    st.session_state.checked = False

if "results" not in st.session_state:
    st.session_state.results = None

if "decision" not in st.session_state:
    st.session_state.decision = ""


# ============================================================
# BASIC TEXT FUNCTIONS
# ============================================================

def normalize(text):
    if text is None:
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


def words(text):
    return set(
        re.findall(
            r"\b[a-z]{4,}\b",
            normalize(text)
        )
    )


def overlap_score(text1, text2):

    a = words(text1)
    b = words(text2)

    if not a or not b:
        return 0

    common = a.intersection(b)

    return min(
        100,
        round((len(common) / max(len(a), 1)) * 100)
    )


# ============================================================
# ACTION VERB DETECTION
# ============================================================

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
        "select"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss",
        "illustrate",
        "paraphrase"
    ],

    "Apply": [
        "apply",
        "calculate",
        "solve",
        "use",
        "demonstrate",
        "implement",
        "perform",
        "execute",
        "compute"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "categorize",
        "distinguish",
        "deconstruct",
        "break down"
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
        "appraise",
        "evaluate",
        "take a position",
        "support your conclusion"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "construct",
        "formulate",
        "produce",
        "propose",
        "generate",
        "build",
        "develop a solution",
        "design a solution"
    ]
}


def detect_bloom(question):

    q = normalize(question)

    detected = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if verb in q:
                detected.append(level)
                break

    if not detected:
        return "Not clearly detected"

    # Highest detected cognitive level
    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    return max(
        detected,
        key=lambda x: order[x]
    )


# ============================================================
# BLOOM ALIGNMENT
# ============================================================

def check_bloom(selected, question):

    if not question:
        return 0, "Question is missing."

    detected = detect_bloom(question)

    if detected == selected:

        return 100, (
            f"The question contains evidence consistent "
            f"with the selected {selected} level."
        )

    if detected == "Not clearly detected":

        return 65, (
            f"The selected Bloom level is {selected}, but "
            f"the question does not contain a clearly "
            f"identifiable cognitive action."
        )

    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    selected_value = order[selected]
    detected_value = order[detected]

    difference = abs(
        selected_value - detected_value
    )

    if difference == 1:

        return 75, (
            f"The question appears to operate around "
            f"{detected}, while {selected} was selected."
        )

    return 45, (
        f"The question appears to require {detected}, "
        f"which differs substantially from the selected "
        f"{selected} level."
    )


# ============================================================
# GENERIC CLO ALIGNMENT
# ============================================================

def check_clo_alignment(
    clo,
    question,
    question_type,
    evidence_type
):

    if not clo or not question:
        return 0, "CLO or question is missing."

    clo_words = words(clo)
    question_words = words(question)

    common = clo_words.intersection(
        question_words
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # We DO NOT give 100 merely because a CLO was selected.
    # --------------------------------------------------------

    semantic_overlap = overlap_score(
        clo,
        question
    )

    # --------------------------------------------------------
    # Evidence/action compatibility
    # --------------------------------------------------------

    clo_text = normalize(clo)
    q_text = normalize(question)
    evidence = normalize(evidence_type)
    qtype = normalize(question_type)

    evidence_score = 50

    # Generic evidence matching
    evidence_terms = {
        "oral performance": [
            "oral",
            "speak",
            "speaking",
            "presentation",
            "communicate",
            "present"
        ],

        "practical performance": [
            "perform",
            "demonstrate",
            "experiment",
            "operate",
            "conduct",
            "execute"
        ],

        "calculation numerical work": [
            "calculate",
            "solve",
            "compute",
            "determine",
            "numerical"
        ],

        "analysis interpretation": [
            "analyze",
            "analyse",
            "interpret",
            "compare",
            "evaluate",
            "examine"
        ],

        "product design": [
            "design",
            "develop",
            "create",
            "construct",
            "build",
            "produce"
        ],

        "code program": [
            "code",
            "program",
            "implement",
            "develop",
            "algorithm"
        ],

        "written response": [
            "write",
            "explain",
            "describe",
            "discuss",
            "essay",
            "response"
        ],

        "project portfolio": [
            "project",
            "develop",
            "produce",
            "portfolio",
            "create"
        ]
    }

    matched_evidence = False

    for evidence_name, terms in evidence_terms.items():

        if evidence_name in evidence:

            if any(
                term in q_text
                for term in terms
            ):
                matched_evidence = True

    if matched_evidence:
        evidence_score = 100

    # --------------------------------------------------------
    # Question type clues
    # --------------------------------------------------------

    type_score = 60

    type_mapping = {

        "oral presentation": [
            "present",
            "presentation",
            "speak",
            "explain"
        ],

        "viva": [
            "explain",
            "answer",
            "justify",
            "defend"
        ],

        "problem solving": [
            "solve",
            "calculate",
            "determine",
            "apply"
        ],

        "practical laboratory": [
            "perform",
            "conduct",
            "experiment",
            "demonstrate"
        ],

        "programming task": [
            "code",
            "program",
            "implement",
            "algorithm"
        ],

        "design task": [
            "design",
            "develop",
            "construct",
            "create"
        ],

        "case study": [
            "analyze",
            "analyse",
            "recommend",
            "evaluate",
            "interpret"
        ],

        "essay written": [
            "write",
            "explain",
            "analyze",
            "evaluate",
            "discuss"
        ]
    }

    for type_name, terms in type_mapping.items():

        if type_name in qtype:

            if any(
                term in q_text
                for term in terms
            ):
                type_score = 100

    # --------------------------------------------------------
    # Final CLO evidence score
    # --------------------------------------------------------

    if semantic_overlap >= 50:
        overlap_component = 100

    elif semantic_overlap >= 25:
        overlap_component = 80

    elif semantic_overlap >= 10:
        overlap_component = 65

    else:
        overlap_component = 35

    final_score = round(
        (
            overlap_component * 0.40
            + evidence_score * 0.35
            + type_score * 0.25
        )
    )

    # Do not allow keyword overlap alone to make score perfect
    if final_score >= 95 and evidence_score < 100:
        final_score = 90

    if final_score >= 90:

        message = (
            "The assessment provides strong evidence that "
            "students are being asked to demonstrate the "
            "selected CLO."
        )

    elif final_score >= 75:

        message = (
            "The assessment provides reasonable evidence "
            "of the CLO, but the required student action "
            "could be made clearer."
        )

    elif final_score >= 50:

        message = (
            "The assessment provides partial evidence of "
            "the CLO. Review what the student is actually "
            "required to demonstrate."
        )

    else:

        message = (
            "The question does not clearly provide evidence "
            "of the selected CLO."
        )

    return final_score, message


# ============================================================
# GENERIC PLO ALIGNMENT
# ============================================================

def check_plo_alignment(
    clo,
    plo,
    question,
    question_type,
    evidence_type
):

    if not plo or not question:
        return 0, "PLO or question is missing."

    # First determine whether CLO and PLO are conceptually related
    clo_plo_overlap = overlap_score(
        clo,
        plo
    )

    # Determine whether question provides evidence of PLO
    plo_question_overlap = overlap_score(
        plo,
        question
    )

    # Evidence type compatibility
    evidence = normalize(evidence_type)
    q_text = normalize(question)

    evidence_match = 50

    generic_evidence_terms = {

        "oral performance": [
            "oral",
            "speak",
            "presentation",
            "communicate"
        ],

        "written response": [
            "write",
            "written",
            "explain",
            "describe"
        ],

        "calculation numerical work": [
            "calculate",
            "solve",
            "compute",
            "determine"
        ],

        "analysis interpretation": [
            "analyze",
            "analyse",
            "interpret",
            "compare",
            "evaluate"
        ],

        "practical performance": [
            "perform",
            "demonstrate",
            "conduct",
            "experiment"
        ],

        "product design": [
            "design",
            "create",
            "develop",
            "construct"
        ],

        "code program": [
            "code",
            "program",
            "algorithm",
            "implement"
        ]
    }

    for evidence_name, terms in generic_evidence_terms.items():

        if evidence_name in evidence:

            if any(
                term in q_text
                for term in terms
            ):
                evidence_match = 100

    # Mapping strength
    if clo_plo_overlap >= 40:
        mapping_score = 100

    elif clo_plo_overlap >= 20:
        mapping_score = 85

    elif clo_plo_overlap >= 5:
        mapping_score = 70

    else:
        mapping_score = 50

    # Question evidence
    if plo_question_overlap >= 30:
        question_score = 100

    elif plo_question_overlap >= 15:
        question_score = 85

    elif plo_question_overlap >= 5:
        question_score = 70

    else:
        question_score = 45

    final_score = round(
        mapping_score * 0.35
        + question_score * 0.35
        + evidence_match * 0.30
    )

    if final_score >= 90:

        message = (
            "The assessment provides strong evidence toward "
            "the selected PLO through the CLO and assessment task."
        )

    elif final_score >= 75:

        message = (
            "The assessment provides reasonable evidence "
            "toward the selected PLO."
        )

    elif final_score >= 50:

        message = (
            "The assessment provides partial evidence toward "
            "the PLO. Review the CLO-PLO relationship and "
            "the evidence produced by the task."
        )

    else:

        message = (
            "The question does not clearly provide evidence "
            "for the selected PLO."
        )

    return final_score, message


# ============================================================
# QUESTION TYPE ALIGNMENT
# ============================================================

def check_question_type(
    question,
    question_type,
    evidence_type
):

    if not question:
        return 0, "Question is missing."

    q = normalize(question)
    qtype = normalize(question_type)
    evidence = normalize(evidence_type)

    # --------------------------------------------------------
    # Generic compatibility matrix
    # --------------------------------------------------------

    compatibility = {

        "oral presentation": [
            "oral performance",
            "presentation"
        ],

        "viva": [
            "oral performance"
        ],

        "debate discussion": [
            "oral performance",
            "presentation"
        ],

        "practical laboratory": [
            "practical performance"
        ],

        "demonstration": [
            "practical performance",
            "presentation"
        ],

        "programming task": [
            "code program"
        ],

        "design task": [
            "product design"
        ],

        "problem solving": [
            "calculation numerical work",
            "analysis interpretation"
        ],

        "case study": [
            "case analysis",
            "analysis interpretation"
        ],

        "essay written": [
            "written response",
            "analysis interpretation"
        ],

        "short answer": [
            "written response"
        ],

        "project task": [
            "project portfolio",
            "product design"
        ]
    }

    if qtype in compatibility:

        valid_evidence = compatibility[qtype]

        if any(
            item in evidence
            for item in valid_evidence
        ):

            return 100, (
                "The selected assessment type is consistent "
                "with the evidence students are expected to produce."
            )

    return 70, (
        "The assessment type is usable, but review whether "
        "it produces the evidence required by the CLO."
    )


# ============================================================
# OVERALL OBE ALIGNMENT
# ============================================================

def calculate_obe_alignment(
    clo_score,
    plo_score,
    bloom_score,
    type_score
):

    # IMPORTANT:
    # Marks and difficulty are NOT included.
    #
    # The score measures only evidence of alignment.

    score = round(
        (
            clo_score
            + plo_score
            + bloom_score
            + type_score
        ) / 4,
        1
    )

    return score


# ============================================================
# DIFFICULTY
# ============================================================

def calculate_difficulty(bloom):

    if bloom == "Remember":
        return "Easy"

    if bloom == "Understand":
        return "Easy"

    if bloom == "Apply":
        return "Moderate"

    if bloom == "Analyze":
        return "Moderate"

    if bloom == "Evaluate":
        return "Challenging"

    if bloom == "Create":
        return "Challenging"

    return "Moderate"


# ============================================================
# MARKS REVIEW
# ============================================================

def review_marks(
    marks,
    bloom,
    question_type
):

    if marks <= 0:
        return "Marks must be greater than zero."

    if question_type == "MCQ":

        if marks > 2:
            return (
                "Consider whether this number of marks is "
                "appropriate for a single MCQ."
            )

    if bloom in ["Evaluate", "Create"] and marks < 4:

        return (
            "This higher-order task may need sufficient marks "
            "to generate meaningful evidence."
        )

    return (
        "Marks appear reasonable. Marks are advisory and "
        "do not reduce the OBE alignment score."
    )


# ============================================================
# GENERIC QUESTION GENERATOR
# ============================================================

def generate_question(
    subject,
    topic,
    clo,
    plo,
    bloom,
    question_type,
    marks
):

    topic = topic.strip() or "the selected topic"

    if bloom == "Remember":

        action = "identify and state"

    elif bloom == "Understand":

        action = "explain"

    elif bloom == "Apply":

        action = "apply the relevant principles of"

    elif bloom == "Analyze":

        action = "analyze"

    elif bloom == "Evaluate":

        action = "evaluate"

    else:

        action = "design or develop"

    # --------------------------------------------------------
    # Generic question templates
    # --------------------------------------------------------

    if question_type == "MCQ":

        return (
            f"Which of the following statements about "
            f"{topic} is correct?"
        )

    if question_type == "Short Answer":

        return (
            f"{action.capitalize()} {topic} and provide "
            f"appropriate evidence or an example to support "
            f"your response."
        )

    if question_type == "Essay / Written":

        return (
            f"{action.capitalize()} {topic}. Develop a clear "
            f"and well-supported response using relevant "
            f"concepts, evidence, examples, or reasoning."
        )

    if question_type == "Problem Solving":

        return (
            f"Apply the relevant concepts related to {topic} "
            f"to solve the given problem. Show your working "
            f"and explain the reasoning behind your answer."
        )

    if question_type == "Case Study":

        return (
            f"Analyze the following case related to {topic}. "
            f"Identify the key issue, apply relevant concepts, "
            f"and provide a justified conclusion or recommendation."
        )

    if question_type == "Practical / Laboratory":

        return (
            f"Perform the required practical task related to "
            f"{topic}. Demonstrate the appropriate procedure, "
            f"record relevant observations, and explain the result."
        )

    if question_type == "Project / Task":

        return (
            f"Develop a project or task related to {topic}. "
            f"Explain your approach, demonstrate its application, "
            f"and present the resulting product or outcome."
        )

    if question_type == "Oral Presentation":

        return (
            f"Deliver a {marks}-mark oral presentation on {topic}. "
            f"Explain the key issue clearly, support your ideas "
            f"with relevant evidence or examples, and respond "
            f"appropriately to questions."
        )

    if question_type == "Viva":

        return (
            f"Explain {topic} orally and justify your response "
            f"using relevant concepts, evidence, or reasoning."
        )

    if question_type == "Debate / Discussion":

        return (
            f"Discuss or debate the issue of {topic}. Present "
            f"a clear position, support it with relevant "
            f"evidence, and respond to alternative viewpoints."
        )

    if question_type == "Demonstration":

        return (
            f"Demonstrate the appropriate method or procedure "
            f"related to {topic} and explain the key decisions "
            f"made during the demonstration."
        )

    if question_type == "Simulation":

        return (
            f"Complete the simulation related to {topic}. "
            f"Apply the relevant knowledge or skills and "
            f"explain your decisions and outcome."
        )

    if question_type == "Design Task":

        return (
            f"Design a solution, product, model, or process "
            f"related to {topic}. Explain the design decisions "
            f"and justify how the proposed solution addresses "
            f"the identified requirements."
        )

    if question_type == "Programming Task":

        return (
            f"Develop a program or computational solution "
            f"related to {topic}. Implement the solution and "
            f"explain the main design decisions."
        )

    return (
        f"{action.capitalize()} {topic} and justify your "
        f"response using relevant evidence or examples."
    )


# ============================================================
# GENERIC ANSWER
# ============================================================

def generate_answer(
    question,
    bloom,
    question_type
):

    if question_type == "MCQ":

        return (
            "Recommended Answer:\n\n"
            "Select the option that correctly represents "
            "the concept being assessed. The final answer "
            "should be verified by the subject expert."
        )

    if bloom == "Remember":

        return (
            "Recommended Answer:\n\n"
            "The student should accurately identify or state "
            "the required information."
        )

    if bloom == "Understand":

        return (
            "Recommended Answer:\n\n"
            "The student should explain the concept accurately "
            "in their own words and provide a relevant example "
            "where appropriate."
        )

    if bloom == "Apply":

        return (
            "Recommended Answer:\n\n"
            "The student should select the appropriate concept "
            "or method, apply it correctly, show the relevant "
            "steps, and reach an appropriate result."
        )

    if bloom == "Analyze":

        return (
            "Recommended Answer:\n\n"
            "The student should identify relevant components, "
            "relationships, patterns, causes, differences, "
            "or implications and support the analysis with "
            "appropriate evidence."
        )

    if bloom == "Evaluate":

        return (
            "Recommended Answer:\n\n"
            "The student should make a justified judgment, "
            "support the position with relevant evidence, "
            "consider appropriate alternatives where required, "
            "and reach a logical conclusion."
        )

    return (
        "Recommended Answer:\n\n"
        "The student should develop an appropriate solution, "
        "product, design, proposal, or response and justify "
        "the decisions made."
    )


# ============================================================
# MARKING SCHEME
# ============================================================

def generate_marking_scheme(
    marks,
    bloom,
    question_type
):

    if bloom == "Remember":

        criteria = [
            ("Accuracy of required information", 60),
            ("Completeness", 25),
            ("Clarity", 15)
        ]

    elif bloom == "Understand":

        criteria = [
            ("Conceptual understanding", 35),
            ("Explanation", 30),
            ("Relevant example/evidence", 20),
            ("Clarity", 15)
        ]

    elif bloom == "Apply":

        criteria = [
            ("Selection of appropriate method", 20),
            ("Application", 30),
            ("Working/reasoning", 25),
            ("Accuracy of result", 15),
            ("Clarity", 10)
        ]

    elif bloom == "Analyze":

        criteria = [
            ("Identification of relevant components", 20),
            ("Analysis and reasoning", 30),
            ("Evidence/examples", 20),
            ("Interpretation", 20),
            ("Clarity", 10)
        ]

    elif bloom == "Evaluate":

        criteria = [
            ("Understanding of issue", 20),
            ("Quality of evaluation", 25),
            ("Evidence/reasoning", 25),
            ("Justification", 20),
            ("Clarity/conclusion", 10)
        ]

    else:

        criteria = [
            ("Understanding of requirements", 15),
            ("Quality of design/solution", 25),
            ("Application/implementation", 25),
            ("Justification", 20),
            ("Originality/quality of outcome", 15)
        ]

    rows = []

    for criterion, percentage in criteria:

        allocated = round(
            marks * percentage / 100,
            2
        )

        rows.append({
            "Criterion": criterion,
            "Marks": allocated,
            "Allocation": f"{percentage}%"
        })

    return pd.DataFrame(rows)


# ============================================================
# QUESTION TWEAKS
# ============================================================

def tweak_question(
    question,
    option
):

    if not question:
        return question

    if option == "Make Easier":

        return (
            question
            + "\n\nUse clear instructions and limit the task "
              "to the essential concepts."
        )

    if option == "Make Harder":

        return (
            question
            + "\n\nRequire additional evidence, reasoning, "
              "application, or justification."
        )

    if option == "More Analytical":

        return (
            question
            + "\n\nAnalyze the relationships, causes, "
              "patterns, differences, or implications involved."
        )

    if option == "More Application-Based":

        return (
            question
            + "\n\nApply the relevant concept or method to "
              "a realistic situation."
        )

    if option == "More Critical Thinking":

        return (
            question
            + "\n\nEvaluate the available evidence and "
              "justify the conclusion."
        )

    if option == "More Discipline-Specific":

        return (
            question
            + "\n\nUse appropriate discipline-specific "
              "terminology, concepts, methods, and evidence."
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
    'A discipline-neutral tool for designing and checking '
    'CLO, PLO, Bloom and assessment alignment.'
    '</div>',
    unsafe_allow_html=True
)

# ============================================================
# 1. COURSE
# ============================================================

st.markdown(
    '<div class="section-title">1. Course & Assessment Context</div>',
    unsafe_allow_html=True
)

c1, c2, c3 = st.columns(3)

with c1:

    subject = st.text_input(
        "Discipline / Subject",
        placeholder="e.g., Chemistry, Computer Science, English, Physics"
    )

with c2:

    course = st.text_input(
        "Course",
        placeholder="e.g., Organic Chemistry"
    )

with c3:

    topic = st.text_input(
        "Topic",
        placeholder="e.g., Acid-Base Titration"
    )

# ============================================================
# 2. CLO
# ============================================================

st.markdown(
    '<div class="section-title">2. Course Learning Outcome (CLO)</div>',
    unsafe_allow_html=True
)

clo = st.text_area(
    "Enter the CLO",
    placeholder=(
        "What should students be able to demonstrate "
        "after completing the course?"
    ),
    height=120
)

# ============================================================
# 3. PLO
# ============================================================

st.markdown(
    '<div class="section-title">3. Program Learning Outcome (PLO)</div>',
    unsafe_allow_html=True
)

plo = st.text_area(
    "Enter the PLO",
    placeholder=(
        "What broader graduate competency does this CLO "
        "contribute toward?"
    ),
    height=120
)

# ============================================================
# 4. ASSESSMENT DESIGN
# ============================================================

st.markdown(
    '<div class="section-title">4. Assessment Design</div>',
    unsafe_allow_html=True
)

c1, c2, c3, c4 = st.columns(4)

with c1:

    bloom = st.selectbox(
        "Bloom's Level",
        BLOOM_LEVELS,
        index=2
    )

with c2:

    question_type = st.selectbox(
        "Question / Assessment Type",
        QUESTION_TYPES
    )

with c3:

    evidence_type = st.selectbox(
        "Evidence Produced",
        ASSESSMENT_EVIDENCE
    )

with c4:

    marks = st.number_input(
        "Marks",
        min_value=1,
        max_value=100,
        value=10
    )

# ============================================================
# 5. GENERATE QUESTION
# ============================================================

st.markdown(
    '<div class="section-title">5. Assessment Question</div>',
    unsafe_allow_html=True
)

if st.button(
    "✨ GENERATE QUESTION",
    use_container_width=True
):

    if not clo:

        st.error("Please enter the CLO first.")

    elif not plo:

        st.error("Please enter the PLO first.")

    else:

        st.session_state.question = generate_question(
            subject,
            topic,
            clo,
            plo,
            bloom,
            question_type,
            marks
        )

        st.session_state.answer = generate_answer(
            st.session_state.question,
            bloom,
            question_type
        )

        st.session_state.checked = False
        st.session_state.results = None
        st.session_state.decision = ""

# ============================================================
# QUESTION EDITOR
# ============================================================

question = st.text_area(
    "Edit the question — faculty has full control",
    value=st.session_state.question,
    height=180
)

st.session_state.question = question

# ============================================================
# TWEAK BUTTONS
# ============================================================

st.markdown("**Quick Tweaks**")

t1, t2, t3, t4, t5, t6 = st.columns(6)

options = [
    ("Make Easier", t1),
    ("Make Harder", t2),
    ("More Analytical", t3),
    ("More Application-Based", t4),
    ("More Critical Thinking", t5),
    ("More Discipline-Specific", t6)
]

for label, col in options:

    with col:

        if st.button(
            label,
            key="btn_" + label,
            use_container_width=True
        ):

            st.session_state.question = tweak_question(
                st.session_state.question,
                label
            )

            st.rerun()

# ============================================================
# 6. ALIGNMENT CHECK
# ============================================================

st.markdown(
    '<div class="section-title">6. OBE Alignment Check</div>',
    unsafe_allow_html=True
)

if st.button(
    "🔍 CHECK OBE ALIGNMENT",
    use_container_width=True
):

    if not clo:

        st.error("Please enter the CLO.")

    elif not plo:

        st.error("Please enter the PLO.")

    elif not question:

        st.error("Please enter the assessment question.")

    else:

        clo_score, clo_msg = check_clo_alignment(
            clo,
            question,
            question_type,
            evidence_type
        )

        plo_score, plo_msg = check_plo_alignment(
            clo,
            plo,
            question,
            question_type,
            evidence_type
        )

        bloom_score, bloom_msg = check_bloom(
            bloom,
            question
        )

        type_score, type_msg = check_question_type(
            question,
            question_type,
            evidence_type
        )

        overall = calculate_obe_alignment(
            clo_score,
            plo_score,
            bloom_score,
            type_score
        )

        difficulty = calculate_difficulty(
            bloom
        )

        marks_msg = review_marks(
            marks,
            bloom,
            question_type
        )

        st.session_state.results = {

            "CLO": clo_score,
            "PLO": plo_score,
            "Bloom": bloom_score,
            "Question Type": type_score,

            "Overall": overall,

            "Difficulty": difficulty,

            "CLO Message": clo_msg,
            "PLO Message": plo_msg,
            "Bloom Message": bloom_msg,
            "Type Message": type_msg,

            "Marks Message": marks_msg
        }

        st.session_state.checked = True

# ============================================================
# 7. RESULTS
# ============================================================

if st.session_state.checked:

    result = st.session_state.results

    overall = result["Overall"]

    st.markdown(
        '<div class="section-title">7. OBE Alignment Result</div>',
        unsafe_allow_html=True
    )

    if overall >= 90:

        css = "good"
        label = "STRONG ALIGNMENT"

    elif overall >= 75:

        css = "medium"
        label = "PARTIAL ALIGNMENT"

    else:

        css = "low"
        label = "NEEDS REVIEW"

    st.markdown(
        f"""
        <div class="score-card {css}">
            <div class="score-number">{overall}%</div>
            <strong>{label}</strong>
        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # COMPONENTS
    # --------------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "CLO Evidence",
            f"{result['CLO']}%"
        )

    with c2:
        st.metric(
            "PLO Evidence",
            f"{result['PLO']}%"
        )

    with c3:
        st.metric(
            "Bloom",
            f"{result['Bloom']}%"
        )

    with c4:
        st.metric(
            "Assessment Type",
            f"{result['Question Type']}%"
        )

    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">Alignment Explanation</div>',
        unsafe_allow_html=True
    )

    st.info(
        f"**CLO — {result['CLO']}%:** "
        f"{result['CLO Message']}"
    )

    st.info(
        f"**PLO — {result['PLO']}%:** "
        f"{result['PLO Message']}"
    )

    st.info(
        f"**Bloom — {result['Bloom']}%:** "
        f"{result['Bloom Message']}"
    )

    st.info(
        f"**Assessment Type — {result['Question Type']}%:** "
        f"{result['Type Message']}"
    )

    # --------------------------------------------------------
    # DIFFICULTY
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">Difficulty</div>',
        unsafe_allow_html=True
    )

    if result["Difficulty"] == "Easy":

        st.success(
            "🟢 Easy"
        )

    elif result["Difficulty"] == "Moderate":

        st.info(
            "🟡 Moderate"
        )

    else:

        st.warning(
            "🟠 Challenging"
        )

    st.caption(
        "Difficulty is separate from OBE alignment and "
        "does not lower the alignment score."
    )

    # --------------------------------------------------------
    # MARKS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">Marks Review</div>',
        unsafe_allow_html=True
    )

    st.info(
        f"**{marks} marks:** {result['Marks Message']}"
    )

# ============================================================
# 8. RECOMMENDED ANSWER
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">8. Recommended Answer</div>',
        unsafe_allow_html=True
    )

    answer = st.text_area(
        "Faculty can edit the answer",
        value=st.session_state.answer,
        height=220
    )

    st.session_state.answer = answer

# ============================================================
# 9. MARKING SCHEME
# ============================================================

if st.session_state.question:

    st.markdown(
        '<div class="section-title">9. Recommended Marking Scheme</div>',
        unsafe_allow_html=True
    )

    marking_scheme = generate_marking_scheme(
        marks,
        bloom,
        question_type
    )

    st.dataframe(
        marking_scheme,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Allocation percentages show how the marks are "
        "distributed among criteria."
    )

    st.success(
        f"Total: {marking_scheme['Marks'].sum():.2f} / {marks}"
    )

# ============================================================
# 10. FACULTY DECISION
# ============================================================

if st.session_state.checked:

    st.markdown(
        '<div class="section-title">10. Faculty Decision</div>',
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)

    with c1:

        if st.button(
            "✅ APPROVE ASSESSMENT",
            use_container_width=True
        ):

            st.session_state.decision = "Approved"

    with c2:

        if st.button(
            "🔄 NEEDS REVISION",
            use_container_width=True
        ):

            st.session_state.decision = "Needs Revision"

    if st.session_state.decision == "Approved":

        st.success(
            "Assessment approved by faculty."
        )

    elif st.session_state.decision == "Needs Revision":

        st.warning(
            "Assessment requires revision."
        )

# ============================================================
# 11. SUMMARY
# ============================================================

if st.session_state.checked:

    result = st.session_state.results

    st.markdown(
        '<div class="section-title">11. Assessment Summary</div>',
        unsafe_allow_html=True
    )

    summary = pd.DataFrame(
        [
            ["Subject", subject],
            ["Course", course],
            ["Topic", topic],
            ["CLO", clo],
            ["PLO", plo],
            ["Bloom Level", bloom],
            ["Question Type", question_type],
            ["Evidence Produced", evidence_type],
            ["Marks", marks],
            ["Difficulty", result["Difficulty"]],
            ["CLO Alignment", f"{result['CLO']}%"],
            ["PLO Alignment", f"{result['PLO']}%"],
            ["Bloom Alignment", f"{result['Bloom']}%"],
            [
                "Assessment Type Alignment",
                f"{result['Question Type']}%"
            ],
            [
                "Overall OBE Alignment",
                f"{result['Overall']}%"
            ],
            [
                "Faculty Decision",
                st.session_state.decision or "Pending"
            ]
        ],
        columns=["Item", "Value"]
    )

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )

# ============================================================
# TEST EXAMPLES
# ============================================================

with st.expander("🧪 Test the checker with different disciplines"):

    st.markdown("""
### Chemistry

**CLO:**  
Perform acid-base titration and analyze experimental results.

**PLO:**  
Apply scientific knowledge and analytical skills to solve problems.

**Bloom:** Analyze

**Type:** Problem Solving

**Evidence:** Calculation / Numerical Work

**Question:**  
A 25 mL HCl sample requires 20 mL of 0.1 M NaOH for neutralization. Calculate the concentration of HCl and explain your calculation.

---

### Computer Science

**CLO:**  
Design algorithms to solve computational problems.

**PLO:**  
Apply computing knowledge to develop effective solutions.

**Bloom:** Create

**Type:** Programming Task

**Evidence:** Code / Program

**Question:**  
Develop an algorithm to find the shortest path in a weighted graph and explain the design decisions.

---

### Business

**CLO:**  
Analyze financial information to support business decisions.

**PLO:**  
Apply analytical skills to solve business problems.

**Bloom:** Analyze

**Type:** Case Study

**Evidence:** Analysis / Interpretation

**Question:**  
Analyze the company's financial information and recommend an appropriate business strategy based on the evidence.

---

### English

**CLO:**  
Communicate ideas clearly and confidently in oral contexts.

**PLO:**  
Demonstrate effective communication skills.

**Bloom:** Evaluate

**Type:** Oral Presentation

**Evidence:** Oral Performance

**Question:**  
Deliver a three-minute presentation taking a position on the use of AI in education and justify your position with relevant evidence.
""")

# ============================================================
# PRINCIPLE
# ============================================================

with st.expander("📌 How this OBE checker works"):

    st.markdown("""
### The tool does NOT assume:

> Selected CLO = 100%

or

> Selected PLO = 100%

Instead, it asks:

**1. CLO**  
What should the student demonstrate?

↓

**2. PLO**  
What broader competency does the CLO contribute toward?

↓

**3. Question**  
What is the student actually being asked to do?

↓

**4. Evidence**  
What evidence will the student produce?

↓

**5. Bloom**  
What level of thinking is required?

↓

**6. Assessment Type**  
Is the assessment method capable of producing the required evidence?

### Overall OBE Alignment

The score considers:

- CLO evidence
- PLO evidence
- Bloom alignment
- Assessment type/evidence compatibility

### Not included in OBE alignment

**Marks and difficulty are NOT used to reduce the OBE alignment percentage.**

They are displayed separately because:

> A difficult question can still be well aligned.

and

> An easy question can still be well aligned.

The final assessment decision always remains with the faculty member.
""")

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "🎓 OBE Assessment Studio | Discipline-Neutral | "
    "Faculty-Controlled Assessment Design"
)
