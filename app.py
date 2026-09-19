def normalize_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def meaningful_words(text):
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]+", str(text).lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def concept_overlap(question, outcome):
    q_words = set(meaningful_words(question))
    o_words = set(meaningful_words(outcome))

    if not q_words or not o_words:
        return 0.0

    overlap = len(q_words & o_words)
    return overlap / max(1, len(o_words))


def extract_clo_concepts(clo):
    """
    Extract meaningful concepts from the actual CLO.
    Removes common instructional verbs so the revision can
    focus on what the CLO actually requires.
    """
    words = meaningful_words(clo)

    action_verbs = {
        "define", "describe", "explain", "identify", "list",
        "discuss", "compare", "contrast", "analyze", "analyse",
        "evaluate", "assess", "apply", "demonstrate", "calculate",
        "interpret", "develop", "design", "create", "justify",
        "differentiate", "classify", "summarize", "summarise",
        "solve", "construct", "examine", "critique"
    }

    concepts = [w for w in words if w not in action_verbs]

    return concepts


def extract_clo_action(clo):
    """
    Detect the main cognitive action required by the CLO.
    """
    text = str(clo).lower()

    ordered_actions = [
        ("create", ["create", "design", "develop", "construct", "formulate"]),
        ("evaluate", ["evaluate", "assess", "critique", "judge"]),
        ("analyze", ["analyze", "analyse", "examine", "differentiate"]),
        ("apply", ["apply", "demonstrate", "use", "solve", "calculate"]),
        ("understand", ["explain", "describe", "summarize", "summarise"]),
        ("remember", ["define", "identify", "list", "state", "name"]),
    ]

    for level, verbs in ordered_actions:
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", text):
                return level, verb

    return "understand", "explain"


def preserve_numbers(original, revised):
    """
    Prevent the revision engine from changing numerical information.
    """
    original_numbers = re.findall(
        r"\b\d+(?:\.\d+)?\b",
        str(original)
    )

    revised_numbers = re.findall(
        r"\b\d+(?:\.\d+)?\b",
        str(revised)
    )

    return original_numbers == revised_numbers


def preserve_mcq_options(original, revised):
    """
    Ensure MCQ options are not accidentally modified.
    """
    option_lines = re.findall(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+.+$",
        str(original)
    )

    if not option_lines:
        return True

    for option in option_lines:
        option_text = re.sub(
            r"^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s*",
            "",
            option
        ).strip()

        if option_text and option_text.lower() not in revised.lower():
            return False

    return True


def preserve_question_type(original, revised):
    """
    The revision must remain the same type of assessment question.
    """
    q_type = detect_question_type(original)

    revised_lower = revised.lower()

    if q_type == "MCQ":
        return bool(
            re.search(r"\b[A-D][\.\)]\b", revised, re.I)
            or re.search(r"(?m)^\s*[A-D][\.\)]", revised)
        )

    if q_type == "True/False":
        return (
            "true" in revised_lower
            and "false" in revised_lower
        )

    if q_type == "Fill in the Blank":
        return "_" in revised or "blank" in revised_lower

    return True


def build_clo_revision(question, clo, q_type):
    """
    Build a revision directly from the actual CLO.
    This is the primary fix for the CLO-not-attained problem.
    """

    question = normalize_text(question)
    clo = normalize_text(clo)

    if not clo:
        return question

    action_level, action = extract_clo_action(clo)
    concepts = extract_clo_concepts(clo)

    # ---------------------------------------------------------
    # MCQ
    # ---------------------------------------------------------
    if q_type == "MCQ":
        stem = re.split(
            r"(?im)^\s*(?:A|B|C|D)[\.\)]\s+",
            question
        )[0].strip()

        if not stem:
            stem = question

        if action_level == "evaluate":
            new_stem = (
                "Which option best evaluates "
                + stem.rstrip("?. ")
                + "?"
            )
        elif action_level == "analyze":
            new_stem = (
                "Which option best analyzes "
                + stem.rstrip("?. ")
                + "?"
            )
        elif action_level == "apply":
            new_stem = (
                "Which option best applies the concept in "
                + stem.rstrip("?. ")
                + "?"
            )
        else:
            new_stem = (
                action.capitalize()
                + " "
                + stem.rstrip("?. ")
                + "."
            )

        # Keep all original options.
        options = re.findall(
            r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)]).*$",
            question
        )

        if options:
            return new_stem + "\n" + "\n".join(options)

        return new_stem

    # ---------------------------------------------------------
    # TRUE / FALSE
    # ---------------------------------------------------------
    if q_type == "True/False":
        body = re.sub(
            r"(?i)\b(true|false)\b\s*$",
            "",
            question
        ).strip()

        body = body.rstrip(".?")

        # Keep the statement itself but make it explicit.
        revised = (
            "Determine whether the following statement is correct: "
            + body
            + ". (True/False)"
        )

        return revised

    # ---------------------------------------------------------
    # FILL IN THE BLANK
    # ---------------------------------------------------------
    if q_type == "Fill in the Blank":
        if "_" in question:
            return question

        return (
            question.rstrip(".? ")
            + ": __________"
        )

    # ---------------------------------------------------------
    # NUMERICAL / CALCULATION
    # ---------------------------------------------------------
    if q_type in ["Numerical", "Calculation"]:
        if re.search(
            r"(?i)\b(show|calculate|determine|solve)\b",
            question
        ) and re.search(
            r"(?i)\b(step|working|unit)\b",
            question
        ):
            return question

        return (
            question.rstrip(".? ")
            + ". Show the calculation steps and give the final answer "
              "with the appropriate unit."
        )

    # ---------------------------------------------------------
    # CASE STUDY
    # ---------------------------------------------------------
    if q_type == "Case Study":
        body = question.rstrip(".? ")

        if action_level == "analyze":
            return (
                body
                + ". Analyze the case using the concepts identified "
                  "in the course learning outcome and support your "
                  "answer with evidence from the case."
            )

        if action_level == "evaluate":
            return (
                body
                + ". Evaluate the situation using the concepts "
                  "identified in the course learning outcome and "
                  "support your judgment with evidence from the case."
            )

        if action_level == "apply":
            return (
                body
                + ". Apply the relevant concept from the course "
                  "learning outcome to the case and explain your answer."
            )

        return (
            body
            + ". Explain your answer using the concepts identified "
              "in the course learning outcome."
        )

    # ---------------------------------------------------------
    # ESSAY / LONG ANSWER
    # ---------------------------------------------------------
    if q_type in ["Essay", "Long Answer"]:
        if action_level == "evaluate":
            return (
                "Evaluate "
                + question.rstrip("?. ")
                + " and support your evaluation with relevant reasons."
            )

        if action_level == "analyze":
            return (
                "Analyze "
                + question.rstrip("?. ")
                + " by examining the key concepts involved."
            )

        if action_level == "apply":
            return (
                "Apply the relevant concepts from the course to "
                + question.rstrip("?. ")
                + " and explain your application."
            )

        if action_level == "create":
            return (
                "Develop a response to "
                + question.rstrip("?. ")
                + " that addresses the key concepts specified "
                  "in the course learning outcome."
            )

        return (
            action.capitalize()
            + " "
            + question.rstrip("?. ")
            + " with reference to the key concepts in the course "
              "learning outcome."
        )

    # ---------------------------------------------------------
    # SHORT ANSWER / GENERAL QUESTION
    # ---------------------------------------------------------
    if action_level == "evaluate":
        return (
            "Evaluate "
            + question.rstrip("?. ")
            + " and give reasons to support your evaluation."
        )

    if action_level == "analyze":
        return (
            "Analyze "
            + question.rstrip("?. ")
            + " by identifying the key factors involved."
        )

    if action_level == "apply":
        return (
            "Apply the relevant concept to "
            + question.rstrip("?. ")
            + " and explain your answer."
        )

    if action_level == "create":
        return (
            "Develop a response to "
            + question.rstrip("?. ")
            + " using the relevant concepts from the course."
        )

    # Direct CLO-driven revision.
    #
    # This is deliberately NOT a generic
    # "relate your answer to the CLO" sentence.
    #
    # It uses the actual CLO wording.
    return (
        clo[0].upper()
        + clo[1:].rstrip(".? ")
        + "."
    )


def validate_clo_revision(original, revised, clo):
    """
    Validate that the revision is genuinely usable.
    """

    if not revised:
        return False

    original = normalize_text(original)
    revised = normalize_text(revised)
    clo = normalize_text(clo)

    if revised == original:
        return False

    # Never change numerical values.
    if not preserve_numbers(original, revised):
        return False

    # Never remove MCQ choices.
    if not preserve_mcq_options(original, revised):
        return False

    # Keep the same assessment format.
    if not preserve_question_type(original, revised):
        return False

    # Require meaningful topic overlap.
    original_words = set(meaningful_words(original))
    revised_words = set(meaningful_words(revised))

    if original_words:
        overlap = len(original_words & revised_words) / len(original_words)

        if overlap < 0.20:
            return False

    return True


def generate_clo_revision(question, clo):
    """
    MAIN CLO FIX.

    If CLO attainment is below the threshold, this function MUST
    return a practical revision. It does not return None merely
    because the first candidate is unsuitable.
    """

    q_type = detect_question_type(question)

    candidates = []

    # Candidate 1: direct CLO-driven revision.
    candidates.append(
        build_clo_revision(
            question,
            clo,
            q_type
        )
    )

    # Candidate 2: for general questions, explicitly use CLO concepts.
    concepts = extract_clo_concepts(clo)

    if concepts:
        q_clean = normalize_text(question).rstrip(".? ")

        candidates.append(
            q_clean
            + ". Address the key concepts required by the "
              "course learning outcome: "
            + ", ".join(concepts[:5])
            + "."
        )

    # Candidate 3: direct transformation using CLO action.
    level, action = extract_clo_action(clo)

    q_clean = normalize_text(question).rstrip(".? ")

    if action in ["explain", "describe"]:
        candidates.append(
            "Explain "
            + q_clean
            + " with reference to the key concepts stated "
              "in the course learning outcome."
        )

    elif action in ["analyze", "analyse", "examine"]:
        candidates.append(
            "Analyze "
            + q_clean
            + " by examining its key components and relationships."
        )

    elif action in ["evaluate", "assess", "critique"]:
        candidates.append(
            "Evaluate "
            + q_clean
            + " and support your evaluation with relevant reasons."
        )

    elif action in ["apply", "demonstrate", "use"]:
        candidates.append(
            "Apply the relevant concept to "
            + q_clean
            + " and explain your answer."
        )

    # Validate candidates.
    valid_candidates = []

    for candidate in candidates:
        candidate = normalize_text(candidate)

        if validate_clo_revision(
            question,
            candidate,
            clo
        ):
            valid_candidates.append(candidate)

    # Return the strongest valid candidate.
    if valid_candidates:
        return valid_candidates[0]

    # ---------------------------------------------------------
    # FINAL FALLBACK
    # ---------------------------------------------------------
    #
    # IMPORTANT:
    # We do NOT return None.
    # We do NOT show "Keep Current Question".
    #
    # The tool must always provide a practical revision when
    # CLO attainment is below threshold.
    # ---------------------------------------------------------

    q_clean = normalize_text(question).rstrip(".? ")

    fallback = (
        q_clean
        + ". Explain your answer using the concepts and skills "
          "specified in the course learning outcome."
    )

    return fallback
