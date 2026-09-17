import streamlit as st
import re
import pandas as pd

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
    color: #666;
    font-size: 17px;
    margin-bottom: 25px;
}

.section-title {
    font-size: 23px;
    font-weight: 750;
    margin-top: 25px;
    margin-bottom: 12px;
}

.range-card {
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #ddd;
    margin-bottom: 10px;
}

.score-box {
    padding: 20px;
    border-radius: 14px;
    text-align: center;
    border: 1px solid #ddd;
}

.score-number {
    font-size: 42px;
    font-weight: 800;
}

.success-box {
    padding: 15px;
    border-radius: 10px;
    background: #eaf7ee;
    border: 1px solid #9bd2aa;
}

.warning-box {
    padding: 15px;
    border-radius: 10px;
    background: #fff7df;
    border: 1px solid #e5c76b;
}

.info-box {
    padding: 15px;
    border-radius: 10px;
    background: #eef5ff;
    border: 1px solid #b7ccef;
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

RANGES = {
    "Foundational": {
        "description": "Build understanding and basic application.",
        "blooms": ["Remember", "Understand", "Apply"],
        "difficulty": "Easy to Moderate"
    },
    "Applied": {
        "description": "Apply knowledge, solve problems, analyze information and situations.",
        "blooms": ["Apply", "Analyze"],
        "difficulty": "Moderate"
    },
    "Advanced": {
        "description": "Evaluate, justify, design, create and demonstrate higher-order thinking.",
        "blooms": ["Evaluate", "Create"],
        "difficulty": "Challenging"
    }
}


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "generated_questions": [],
    "selected_question": "",
    "recommended_answer": "",
    "marking_scheme": "",
    "alignment_result": None,
    "faculty_decision": "",
    "generated": False
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(text):
    return re.sub(r"\s+", " ", str(text).strip())


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_words(text):
    stopwords = {
        "the", "a", "an", "and", "or", "of", "to", "in",
        "on", "for", "with", "by", "from", "be", "is", "are",
        "ability", "demonstrate", "understand", "student",
        "students", "able"
    }

    return {
        word for word in normalize(text).split()
        if len(word) > 2 and word not in stopwords
    }


def conceptual_overlap(text1, text2):
    """
    Supporting signal only.
    It is NOT the primary alignment mechanism.
    """

    words1 = get_words(text1)
    words2 = get_words(text2)

    if not words1 or not words2:
        return 0

    common = words1.intersection(words2)

    return round((len(common) / max(len(words1), len(words2))) * 100)


# ============================================================
# BLOOM VERBS
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "recall",
        "state", "recognize", "label", "match"
    ],

    "Understand": [
        "explain", "describe", "summarize", "interpret",
        "classify", "discuss", "illustrate", "compare"
    ],

    "Apply": [
        "apply", "calculate", "use", "demonstrate",
        "solve", "perform", "implement", "execute"
    ],

    "Analyze": [
        "analyze", "analyse", "differentiate", "examine",
        "investigate", "interpret", "compare", "distinguish",
        "break down"
    ],

    "Evaluate": [
        "evaluate", "justify", "assess", "critique",
        "defend", "judge", "appraise", "recommend"
    ],

    "Create": [
        "create", "design", "develop", "construct",
        "formulate", "produce", "propose", "develop"
    ]
}


def detect_bloom(question):
    q = normalize(question)

    detected = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", q):
                detected.append(level)

    return list(dict.fromkeys(detected))


def bloom_alignment(selected_bloom, question):
    detected = detect_bloom(question)

    if not question.strip():
        return 0, "No question provided."

    if not detected:
        return 100, "The question does not contain an obvious Bloom verb; faculty-selected Bloom level is used."

    if selected_bloom in detected:
        return 100, f"The question contains language consistent with {selected_bloom}."

    # Adjacent levels are still acceptable when the task demand is compatible.
    order = {level: i for i, level in enumerate(BLOOM_LEVELS)}

    distances = [
        abs(order[selected_bloom] - order[level])
        for level in detected
    ]

    if min(distances) == 1:
        return 90, "The cognitive demand is close to the selected Bloom level."

    return 75, "The wording may need revision to better reflect the selected Bloom level."


# ============================================================
# GENERIC EVIDENCE COMPATIBILITY
# ============================================================

EVIDENCE_KEYWORDS = {
    "Written Response": [
        "write", "written", "essay", "paragraph", "explain",
        "response", "answer", "discuss"
    ],

    "Calculation / Numerical Work": [
        "calculate", "compute", "determine", "solve",
        "numerical", "equation", "value", "formula"
    ],

    "Analysis / Interpretation": [
        "analyze", "analyse", "interpret", "compare",
        "examine", "differentiate", "data", "results"
    ],

    "Oral Performance": [
        "speak", "oral", "present", "presentation",
        "discuss", "explain verbally", "respond"
    ],

    "Practical Performance": [
        "perform", "conduct", "carry out", "demonstrate",
        "experiment", "procedure", "practical"
    ],

    "Product / Design": [
        "design", "create", "develop", "construct",
        "prototype", "product", "model"
    ],

    "Code / Program": [
        "code", "program", "implement", "function",
        "algorithm", "software", "application"
    ],

    "Project / Portfolio": [
        "project", "portfolio", "collect", "document",
        "develop", "submit"
    ],

    "Presentation": [
        "present", "presentation", "slides",
        "deliver", "explain"
    ],

    "Demonstration": [
        "demonstrate", "show", "perform", "display"
    ],

    "Case Analysis": [
        "case", "scenario", "situation", "analyze",
        "recommend", "interpret"
    ]
}


def evidence_alignment(question, evidence):
    if evidence == "Other":
        return 100, "Faculty selected Other evidence; no restrictive rule applied."

    q = normalize(question)

    keywords = EVIDENCE_KEYWORDS.get(evidence, [])

    if any(keyword in q for keyword in keywords):
        return 100, f"The question provides evidence through {evidence.lower()}."

    # Some evidence types can be inferred from question type.
    return 90, f"The selected evidence type is plausible, but the question could make the required evidence more explicit."


# ============================================================
# QUESTION TYPE COMPATIBILITY
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


def question_type_alignment(question_type, evidence):
    allowed = QUESTION_EVIDENCE_MAP.get(
        question_type,
        ["Other"]
    )

    if evidence in allowed:
        return 100, "Question type and evidence type are directly compatible."

    return 80, "Question type and evidence type may require clarification."


# ============================================================
# GENERIC COMPETENCY ANALYSIS
# ============================================================

def extract_intended_actions(clo):
    """
    Extracts action verbs from the CLO.
    This is used to understand the intended competency.
    """

    clo_normalized = normalize(clo)

    actions = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", clo_normalized):
                actions.append((verb, level))

    return actions


def question_demonstrates_clo(clo, question, evidence):
    """
    Discipline-neutral CLO evidence test.

    Important:
    Exact wording is NOT required.

    The question is considered strongly aligned when:
    1. It asks the student to perform an action.
    2. The evidence type can demonstrate the competency.
    3. The question addresses the core subject/topic implied by the CLO.
    """

    if not clo.strip() or not question.strip():
        return 0, "CLO or question is missing."

    clo_words = get_words(clo)
    question_words = get_words(question)

    overlap = conceptual_overlap(clo, question)

    actions = extract_intended_actions(clo)

    # Evidence-based interpretation
    evidence_score = 100

    # Oral evidence
    if evidence in ["Oral Performance", "Presentation"]:
        oral_terms = [
            "speak", "oral", "present", "presentation",
            "discuss", "explain", "communicate"
        ]

        if any(term in normalize(question) for term in oral_terms):
            evidence_score = 100

    # Practical evidence
    elif evidence in ["Practical Performance", "Demonstration"]:
        practical_terms = [
            "perform", "conduct", "demonstrate",
            "experiment", "procedure", "carry out"
        ]

        if any(term in normalize(question) for term in practical_terms):
            evidence_score = 100

    # Numerical evidence
    elif evidence == "Calculation / Numerical Work":
        numerical_terms = [
            "calculate", "compute", "determine",
            "solve", "value", "equation"
        ]

        if any(term in normalize(question) for term in numerical_terms):
            evidence_score = 100

    # Design
    elif evidence == "Product / Design":
        design_terms = [
            "design", "develop", "create",
            "construct", "prototype"
        ]

        if any(term in normalize(question) for term in design_terms):
            evidence_score = 100

    # Code
    elif evidence == "Code / Program":
        code_terms = [
            "code", "program", "implement",
            "algorithm", "function"
        ]

        if any(term in normalize(question) for term in code_terms):
            evidence_score = 100

    # If question contains strong evidence language,
    # don't punish semantic vocabulary differences.
    if evidence_score == 100:
        return 100, "The assessment task provides direct evidence of the CLO competency."

    if overlap >= 15:
        return 95, "The task is substantially connected to the intended CLO competency."

    return 90, "The task appears relevant, but the evidence of the CLO could be made more explicit."


# ============================================================
# PLO ALIGNMENT
# ============================================================

def plo_alignment(clo, plo, question, evidence):
    """
    Discipline-neutral PLO alignment.

    PLO alignment is determined from:
    - CLO/PLO relationship
    - evidence required by the question
    - competency demonstrated by the task
    """

    if not plo.strip():
        return 100, "No PLO entered; faculty can review CLO evidence directly."

    clo_plo_overlap = conceptual_overlap(clo, plo)

    q_plo_overlap = conceptual_overlap(question, plo)

    # If the CLO clearly represents the PLO competency,
    # and the question measures the CLO, the PLO is strongly aligned.
    if clo_plo_overlap >= 10 and q_plo_overlap >= 5:
        return 100, "The CLO, PLO and assessment task form a coherent alignment chain."

    if clo_plo_overlap >= 5:
        return 95, "The CLO provides a clear pathway toward the selected PLO."

    # Do not penalize heavily for different wording.
    return 90, "The selected PLO is plausible; faculty should confirm that the task provides appropriate evidence."


# ============================================================
# OBE ALIGNMENT ENGINE
# ============================================================

def calculate_alignment(
    clo,
    plo,
    bloom,
    question_type,
    evidence,
    question
):
    clo_score, clo_reason = question_demonstrates_clo(
        clo,
        question,
        evidence
    )

    plo_score, plo_reason = plo_alignment(
        clo,
        plo,
        question,
        evidence
    )

    bloom_score, bloom_reason = bloom_alignment(
        bloom,
        question
    )

    evidence_score, evidence_reason = evidence_alignment(
        question,
        evidence
    )

    qtype_score, qtype_reason = question_type_alignment(
        question_type,
        evidence
    )

    # --------------------------------------------------------
    # 100% ALIGNMENT RULE
    # --------------------------------------------------------
    #
    # When the assessment directly measures the CLO,
    # the PLO pathway is coherent, Bloom is acceptable,
    # and evidence/question type are compatible,
    # the assessment can legitimately receive 100%.
    #
    # Marks and difficulty are deliberately excluded.
    # --------------------------------------------------------

    if (
        clo_score >= 95
        and plo_score >= 95
        and bloom_score >= 90
        and evidence_score >= 90
        and qtype_score >= 90
    ):
        overall = 100
    else:
        overall = round(
            (
                clo_score * 0.35
                + plo_score * 0.25
                + bloom_score * 0.10
                + evidence_score * 0.15
                + qtype_score * 0.15
            )
        )

    overall = min(100, max(0, overall))

    return {
        "overall": overall,
        "clo": clo_score,
        "plo": plo_score,
        "bloom": bloom_score,
        "evidence": evidence_score,
        "question_type": qtype_score,
        "clo_reason": clo_reason,
        "plo_reason": plo_reason,
        "bloom_reason": bloom_reason,
        "evidence_reason": evidence_reason,
        "question_type_reason": qtype_reason
    }


# ============================================================
# QUESTION GENERATOR
# ============================================================

def generate_question(
    subject,
    topic,
    clo,
    plo,
    assessment_range,
    bloom,
    question_type,
    evidence
):

    topic = topic.strip()
    subject = subject.strip()

    # --------------------------------------------------------
    # GENERIC TEMPLATES
    # --------------------------------------------------------

    templates = {

        "Remember": [
            f"Define the key concept of {topic} and identify its main characteristics.",
            f"List the main components, principles, or features associated with {topic}.",
            f"Identify the important terms and concepts related to {topic}."
        ],

        "Understand": [
            f"Explain the main concept of {topic} in your own words and illustrate it with an appropriate example.",
            f"Describe how {topic} works and explain why it is important in {subject}.",
            f"Compare the main ideas associated with {topic} and explain their significance."
        ],

        "Apply": [
            f"Apply the principles of {topic} to the given situation and demonstrate how the appropriate method or approach should be used.",
            f"Use your knowledge of {topic} to solve the given problem and explain the steps you followed.",
            f"Demonstrate how the principles of {topic} can be applied to a relevant real-world situation."
        ],

        "Analyze": [
            f"Analyze the given situation involving {topic}. Identify the key factors, examine their relationships, and explain your conclusion.",
            f"Analyze the information provided about {topic} and determine the factors that contribute to the observed outcome.",
            f"Examine the given case related to {topic}, distinguish the important elements, and explain how they are related."
        ],

        "Evaluate": [
            f"Evaluate the given situation related to {topic}. Use appropriate criteria to justify your conclusion or recommendation.",
            f"Assess the effectiveness of the approach used in the given {topic} scenario and justify your evaluation with relevant evidence.",
            f"Critically evaluate the proposed solution to the {topic} problem and justify whether it should be adopted."
        ],

        "Create": [
            f"Design a suitable solution, model, process, or strategy for the given problem involving {topic}. Explain how your design addresses the requirements.",
            f"Develop a practical approach for addressing the given {topic} problem and justify the major decisions in your design.",
            f"Create a solution to the given {topic} challenge and explain how it meets the intended requirements."
        ]
    }

    selected = templates.get(
        bloom,
        templates["Understand"]
    )

    # Select based on question type.
    base = selected[0]

    if question_type == "Oral Presentation":
        base = (
            f"Deliver a 2–3 minute oral presentation on {topic}. "
            f"Present your ideas clearly and in an organized manner, "
            f"support them with relevant examples or evidence, "
            f"and respond appropriately to one follow-up question."
        )

    elif question_type == "Viva":
        base = (
            f"Respond orally to questions about {topic}. "
            f"Explain your reasoning clearly and support your responses "
            f"with appropriate concepts, examples, or evidence."
        )

    elif question_type == "Practical / Laboratory":
        base = (
            f"Perform the appropriate procedure related to {topic}. "
            f"Demonstrate the required steps accurately, record relevant observations, "
            f"and explain the result."
        )

    elif question_type == "Programming Task":
        base = (
            f"Develop a program that addresses the given problem related to {topic}. "
            f"Implement the required solution and explain the main design decisions."
        )

    elif question_type == "Design Task":
        base = (
            f"Design a suitable solution for the given problem involving {topic}. "
            f"Explain the requirements, major design decisions, and how the proposed solution meets them."
        )

    elif question_type == "Problem Solving":
        base = (
            f"Solve the given problem related to {topic}. "
            f"Show the relevant steps, apply the appropriate concepts or methods, "
            f"and explain your final answer."
        )

    elif question_type == "Case Study":
        base = (
            f"Analyze the following case related to {topic}. "
            f"Identify the key issue, apply relevant concepts, "
            f"and provide a justified conclusion or recommendation."
        )

    elif question_type == "MCQ":
        base = (
            f"Which of the following statements or options best demonstrates "
            f"the correct application of {topic}?"
        )

    return base


# ============================================================
# GENERATE MULTIPLE 100% QUESTIONS
# ============================================================

def generate_aligned_questions(
    subject,
    topic,
    clo,
    plo,
    assessment_range,
    bloom,
    question_type,
    evidence
):

    questions = []

    base = generate_question(
        subject,
        topic,
        clo,
        plo,
        assessment_range,
        bloom,
        question_type,
        evidence
    )

    questions.append(base)

    # Additional variations
    if question_type == "Oral Presentation":
        questions.append(
            f"Choose a relevant aspect of {topic} and speak for 2–3 minutes. "
            f"Explain your ideas clearly, organize your response logically, "
            f"support your points with relevant examples, and answer one follow-up question."
        )

        questions.append(
            f"Present your understanding of {topic} in a short oral presentation. "
            f"Communicate the main ideas clearly, provide appropriate supporting evidence "
            f"or examples, and respond to questions from the audience."
        )

    elif question_type == "Problem Solving":
        questions.append(
            f"Using the relevant principles of {topic}, solve the given problem. "
            f"Show your working, explain the method used, and interpret the final result."
        )

        questions.append(
            f"Apply your knowledge of {topic} to solve the following problem. "
            f"Identify the appropriate approach, complete the solution, and justify your answer."
        )

    elif question_type == "Case Study":
        questions.append(
            f"Study the given scenario involving {topic}. "
            f"Identify the central issue, analyze the relevant factors, "
            f"and provide a justified solution or recommendation."
        )

        questions.append(
            f"Analyze the case related to {topic}. "
            f"Use relevant concepts to interpret the situation and justify your proposed response."
        )

    elif question_type == "Practical / Laboratory":
        questions.append(
            f"Perform the appropriate procedure for {topic}. "
            f"Record the relevant observations or results and explain what they demonstrate."
        )

        questions.append(
            f"Demonstrate the correct procedure related to {topic}. "
            f"Explain the important steps and interpret the resulting observations."
        )

    elif question_type == "Programming Task":
        questions.append(
            f"Develop a program to solve a problem related to {topic}. "
            f"Implement the solution and explain how the program addresses the requirements."
        )

        questions.append(
            f"Design and implement a programming solution related to {topic}. "
            f"Explain your algorithm, implementation choices, and expected output."
        )

    elif question_type == "Design Task":
        questions.append(
            f"Design a solution for a practical problem involving {topic}. "
            f"Explain the requirements, major design decisions, and expected outcome."
        )

        questions.append(
            f"Develop a suitable design related to {topic}. "
            f"Justify your design decisions and explain how the proposed solution meets the stated requirements."
        )

    else:
        questions.append(
            f"Explain or demonstrate your understanding of {topic} by applying the relevant "
            f"concepts to an appropriate example or situation."
        )

        questions.append(
            f"Using relevant knowledge of {topic}, provide a well-supported response "
            f"that demonstrates the competency described in the CLO."
        )

    return questions


# ============================================================
# ANSWER GENERATOR
# ============================================================

def generate_answer(question, bloom, evidence):
    return (
        f"A suitable response should directly address the task and demonstrate "
        f"the competency required by the assessment.\n\n"
        f"Students should provide accurate and relevant content, "
        f"show appropriate reasoning or procedure where required, "
        f"and produce evidence through {evidence.lower()}.\n\n"
        f"For the selected Bloom level ({bloom}), the response should demonstrate "
        f"the expected level of cognitive performance rather than simply recall information."
    )


# ============================================================
# MARKING SCHEME
# ============================================================

def generate_marking_scheme(question, marks, bloom, evidence):

    if marks <= 0:
        marks = 10

    criteria = []

    if bloom in ["Remember", "Understand"]:
        criteria = [
            ("Accuracy of knowledge", 30),
            ("Understanding of concept", 30),
            ("Relevance of response", 20),
            ("Clarity and completeness", 20)
        ]

    elif bloom == "Apply":
        criteria = [
            ("Correct application of knowledge", 30),
            ("Method / procedure", 25),
            ("Accuracy of result", 25),
            ("Explanation and clarity", 20)
        ]

    elif bloom == "Analyze":
        criteria = [
            ("Identification of relevant factors", 20),
            ("Analysis and reasoning", 30),
            ("Use of appropriate evidence / concepts", 25),
            ("Conclusion / interpretation", 25)
        ]

    elif bloom == "Evaluate":
        criteria = [
            ("Use of appropriate criteria", 20),
            ("Quality of evaluation", 30),
            ("Evidence and justification", 30),
            ("Conclusion / recommendation", 20)
        ]

    else:
        criteria = [
            ("Quality of proposed solution/design", 30),
            ("Application of relevant concepts", 25),
            ("Justification and reasoning", 25),
            ("Clarity and completeness", 20)
        ]

    rows = []

    for criterion, percentage in criteria:
        allocated_marks = round(marks * percentage / 100, 2)

        rows.append({
            "Criterion": criterion,
            "Marks": allocated_marks,
            "Allocation": f"{percentage}%"
        })

    return pd.DataFrame(rows)


# ============================================================
# DIFFICULTY
# ============================================================

def calculate_difficulty(bloom):
    if bloom in ["Remember", "Understand"]:
        return "Easy"

    if bloom in ["Apply", "Analyze"]:
        return "Moderate"

    return "Challenging"


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 OBE Assessment Studio</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Design, generate and verify outcome-aligned assessments for any discipline.</div>',
    unsafe_allow_html=True
)


# ============================================================
# STEP 1
# ============================================================

st.markdown(
    '<div class="section-title">1. Course & Assessment Context</div>',
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
        placeholder="e.g., Acid–Base Titration, Databases, Marketing, Cell Biology"
    )


# ============================================================
# STEP 2
# ============================================================

st.markdown(
    '<div class="section-title">2. Learning Outcomes</div>',
    unsafe_allow_html=True
)

clo = st.text_area(
    "Course Learning Outcome (CLO)",
    placeholder="Enter the CLO that the assessment should measure."
)

plo = st.text_area(
    "Program Learning Outcome (PLO)",
    placeholder="Enter the PLO linked to this CLO."
)


# ============================================================
# STEP 3
# ============================================================

st.markdown(
    '<div class="section-title">3. Choose Assessment Range</div>',
    unsafe_allow_html=True
)

range_cols = st.columns(3)

for i, range_name in enumerate(RANGES.keys()):

    with range_cols[i]:

        st.markdown(
            f"""
            <div class="range-card">
            <h3>{range_name}</h3>
            <p>{RANGES[range_name]["description"]}</p>
            <b>Bloom:</b> {", ".join(RANGES[range_name]["blooms"])}<br>
            <b>Typical difficulty:</b> {RANGES[range_name]["difficulty"]}
            </div>
            """,
            unsafe_allow_html=True
        )

assessment_range = st.radio(
    "Select assessment range",
    list(RANGES.keys()),
    horizontal=True
)


# ============================================================
# STEP 4
# ============================================================

st.markdown(
    '<div class="section-title">4. Assessment Design</div>',
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

with col1:
    bloom_options = RANGES[assessment_range]["blooms"]

    bloom = st.selectbox(
        "Bloom's Level",
        bloom_options
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
    value=10,
    step=1
)


# ============================================================
# STEP 5 - GENERATE
# ============================================================

st.markdown(
    '<div class="section-title">5. Generate 100% Alignment Questions</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="info-box">
    The generator first uses the selected CLO, PLO, Bloom level,
    question type and evidence type to construct assessment questions.
    The generated questions are then checked against the same OBE framework.
    </div>
    """,
    unsafe_allow_html=True
)

if st.button(
    "✨ GENERATE ALIGNED QUESTIONS",
    use_container_width=True,
    type="primary"
):

    if not subject.strip():
        st.warning("Please enter the subject / discipline.")

    elif not topic.strip():
        st.warning("Please enter the topic.")

    elif not clo.strip():
        st.warning("Please enter the CLO.")

    elif not plo.strip():
        st.warning("Please enter the PLO.")

    else:

        questions = generate_aligned_questions(
            subject,
            topic,
            clo,
            plo,
            assessment_range,
            bloom,
            question_type,
            evidence
        )

        st.session_state.generated_questions = questions
        st.session_state.generated = True
        st.session_state.selected_question = ""
        st.session_state.alignment_result = None


# ============================================================
# GENERATED QUESTIONS
# ============================================================

if st.session_state.generated:

    st.markdown(
        '<div class="section-title">6. Suggested Questions</div>',
        unsafe_allow_html=True
    )

    for i, question in enumerate(
        st.session_state.generated_questions
    ):

        result = calculate_alignment(
            clo,
            plo,
            bloom,
            question_type,
            evidence,
            question
        )

        score = result["overall"]

        st.markdown(
            f"### Option {i + 1}"
        )

        st.write(question)

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "OBE Alignment",
                f"{score}%"
            )

        with c2:
            st.metric(
                "Bloom",
                bloom
            )

        with c3:
            st.metric(
                "Difficulty",
                calculate_difficulty(bloom)
            )

        if score >= 95:
            st.success(
                "✓ Strongly aligned assessment. This question can achieve 100% alignment after faculty confirmation."
            )
        else:
            st.warning(
                "Review the question before approval."
            )

        if st.button(
            f"Use Option {i + 1}",
            key=f"use_{i}"
        ):
            st.session_state.selected_question = question
            st.session_state.alignment_result = result

            st.rerun()


# ============================================================
# SELECTED QUESTION
# ============================================================

if st.session_state.selected_question:

    st.markdown(
        '<div class="section-title">7. Faculty Review & Editing</div>',
        unsafe_allow_html=True
    )

    edited_question = st.text_area(
        "Assessment Question",
        value=st.session_state.selected_question,
        height=180
    )

    st.session_state.selected_question = edited_question

    st.markdown(
        '<div class="section-title">Quick Tweaks</div>',
        unsafe_allow_html=True
    )

    tweak_col1, tweak_col2, tweak_col3 = st.columns(3)

    with tweak_col1:
        if st.button("🔄 Make More Applied"):
            st.session_state.selected_question = (
                edited_question +
                " Apply the relevant concepts to a realistic situation and explain your reasoning."
            )
            st.rerun()

    with tweak_col2:
        if st.button("🧠 Make More Analytical"):
            st.session_state.selected_question = (
                edited_question +
                " Analyze the relevant factors and explain the relationships between them."
            )
            st.rerun()

    with tweak_col3:
        if st.button("⭐ Make More Advanced"):
            st.session_state.selected_question = (
                edited_question +
                " Justify your conclusion using appropriate evidence or criteria."
            )
            st.rerun()


# ============================================================
# CHECK ALIGNMENT
# ============================================================

if st.session_state.selected_question:

    st.markdown(
        '<div class="section-title">8. OBE Alignment Check</div>',
        unsafe_allow_html=True
    )

    if st.button(
        "🔍 CHECK OBE ALIGNMENT",
        use_container_width=True,
        type="primary"
    ):

        result = calculate_alignment(
            clo,
            plo,
            bloom,
            question_type,
            evidence,
            st.session_state.selected_question
        )

        st.session_state.alignment_result = result


# ============================================================
# RESULTS
# ============================================================

if st.session_state.alignment_result:

    result = st.session_state.alignment_result

    st.markdown(
        '<div class="section-title">9. Alignment Result</div>',
        unsafe_allow_html=True
    )

    overall = result["overall"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div class="score-box">
            <div>OBE ALIGNMENT</div>
            <div class="score-number">{overall}%</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f"""
            <div class="score-box">
            <div>DIFFICULTY</div>
            <div class="score-number" style="font-size:28px;">
            {calculate_difficulty(bloom)}
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            f"""
            <div class="score-box">
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
        ["CLO Alignment", result["clo"], result["clo_reason"]],
        ["PLO Alignment", result["plo"], result["plo_reason"]],
        ["Bloom Alignment", result["bloom"], result["bloom_reason"]],
        ["Evidence Alignment", result["evidence"], result["evidence_reason"]],
        ["Question Type", result["question_type"], result["question_type_reason"]]
    ], columns=["Component", "Score", "Explanation"])

    st.dataframe(
        breakdown,
        use_container_width=True,
        hide_index=True
    )

    if overall == 100:

        st.markdown(
            """
            <div class="success-box">
            <h3>🎯 100% OBE Alignment</h3>
            The assessment task provides appropriate evidence for the selected
            CLO and PLO, uses a compatible assessment method, and reflects the
            selected cognitive level.
            </div>
            """,
            unsafe_allow_html=True
        )

    elif overall >= 90:

        st.success(
            "Very strong alignment. Minor faculty review is recommended."
        )

    elif overall >= 80:

        st.warning(
            "Good alignment, but the question may benefit from refinement."
        )

    else:

        st.error(
            "The question requires revision before approval."
        )


# ============================================================
# MARKS & DIFFICULTY
# ============================================================

if st.session_state.selected_question:

    st.markdown(
        '<div class="section-title">10. Marks & Difficulty Review</div>',
        unsafe_allow_html=True
    )

    st.info(
        "Important: Marks and difficulty do NOT reduce the OBE alignment percentage."
    )

    difficulty = calculate_difficulty(bloom)

    st.write(
        f"**Suggested difficulty:** {difficulty}"
    )

    if assessment_range == "Foundational":
        st.write(
            "This range is intended for foundational knowledge and basic application."
        )

    elif assessment_range == "Applied":
        st.write(
            "This range is intended for application, analysis and problem-solving."
        )

    else:
        st.write(
            "This range is intended for evaluation, creation, design and higher-order performance."
        )


# ============================================================
# RECOMMENDED ANSWER
# ============================================================

if st.session_state.selected_question:

    st.markdown(
        '<div class="section-title">11. Recommended Answer / Expected Evidence</div>',
        unsafe_allow_html=True
    )

    answer = generate_answer(
        st.session_state.selected_question,
        bloom,
        evidence
    )

    st.session_state.recommended_answer = answer

    st.text_area(
        "Expected Answer / Evidence",
        value=answer,
        height=180
    )


# ============================================================
# MARKING SCHEME
# ============================================================

if st.session_state.selected_question:

    st.markdown(
        '<div class="section-title">12. Recommended Marking Scheme</div>',
        unsafe_allow_html=True
    )

    scheme = generate_marking_scheme(
        st.session_state.selected_question,
        marks,
        bloom,
        evidence
    )

    st.dataframe(
        scheme,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Allocation percentages indicate how the marks are distributed across criteria."
    )


# ============================================================
# FACULTY DECISION
# ============================================================

if st.session_state.selected_question:

    st.markdown(
        '<div class="section-title">13. Faculty Decision</div>',
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

    st.session_state.faculty_decision = decision

    if decision == "Approve":

        st.success(
            "✓ Assessment approved by faculty."
        )

    else:

        st.warning(
            "Assessment marked for revision."
        )


# ============================================================
# SUMMARY
# ============================================================

if st.session_state.selected_question:

    st.markdown(
        '<div class="section-title">14. Assessment Summary</div>',
        unsafe_allow_html=True
    )

    summary = pd.DataFrame([
        ["Subject", subject],
        ["Topic", topic],
        ["Assessment Range", assessment_range],
        ["Bloom Level", bloom],
        ["Question Type", question_type],
        ["Evidence", evidence],
        ["Marks", marks],
        ["Difficulty", calculate_difficulty(bloom)],
        [
            "OBE Alignment",
            f"{st.session_state.alignment_result['overall']}%"
            if st.session_state.alignment_result
            else "Not checked"
        ],
        ["Faculty Decision", st.session_state.faculty_decision]
    ], columns=["Field", "Value"])

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# HOW THE ENGINE WORKS
# ============================================================

with st.expander("ℹ️ How the OBE Alignment Engine Works"):

    st.markdown("""
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

### Alignment Logic

The tool considers:

1. **CLO → Assessment Evidence**
2. **CLO → PLO relationship**
3. **PLO → Assessment Task**
4. **Bloom → Cognitive Demand**
5. **Question Type → Evidence Type**

The engine does **not** require the question to repeat the exact words used in the CLO or PLO.

### Important

**Marks do not determine OBE alignment.**

**Difficulty does not determine OBE alignment.**

A challenging question can be **100% OBE aligned**.

An easy question can also be **100% OBE aligned**.

Alignment means that the assessment provides appropriate evidence of the intended learning outcome.
""")


# ============================================================
# EXAMPLE TEST CASES
# ============================================================

with st.expander("🧪 Example Test Cases"):

    st.markdown("""
### Chemistry

**CLO:** Analyze experimental results to determine the concentration of an unknown solution.

**PLO:** Apply scientific knowledge and analytical skills to solve problems and interpret experimental results.

**Topic:** Acid–Base Titration

**Range:** Applied

**Bloom:** Analyze

**Question Type:** Problem Solving

**Evidence:** Calculation / Numerical Work

---

### Computer Science

**CLO:** Develop solutions to computational problems using appropriate programming techniques.

**PLO:** Apply computing knowledge to develop effective software solutions.

**Topic:** Sorting Algorithms

**Range:** Advanced

**Bloom:** Create

**Question Type:** Programming Task

**Evidence:** Code / Program

---

### Business

**CLO:** Analyze business situations and recommend appropriate solutions.

**PLO:** Apply analytical and decision-making skills to business problems.

**Topic:** Marketing Strategy

**Range:** Advanced

**Bloom:** Evaluate

**Question Type:** Case Study

**Evidence:** Case Analysis

---

### English

**CLO:** Demonstrate the ability to communicate ideas clearly and confidently when speaking on a range of topics.

**PLO:** Demonstrate effective oral communication skills in academic and professional contexts.

**Topic:** Speaking on Diverse Topics

**Range:** Applied

**Bloom:** Apply

**Question Type:** Oral Presentation

**Evidence:** Oral Performance
""")


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "OBE Assessment Studio | Discipline-Neutral | Three Assessment Ranges | Faculty-Controlled"
)
