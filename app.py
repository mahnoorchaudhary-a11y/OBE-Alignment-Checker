# ============================================================
# IMPROVED CONCEPT / OUTCOME MATCHING
# ============================================================

from difflib import SequenceMatcher


# Related academic / OBE concepts.
# These allow the system to recognize related wording rather
# than requiring the exact same words.
CONCEPT_GROUPS = {

    "analysis": {
        "analyze", "analyse", "analysis", "examining",
        "examine", "investigate", "investigation",
        "compare", "comparison", "contrast",
        "differentiate", "distinguish", "relationship",
        "relationships", "pattern", "patterns",
        "cause", "effect", "structure", "breakdown"
    },

    "evaluation": {
        "evaluate", "evaluation", "assess", "assessment",
        "judge", "judgment", "critique", "critical",
        "justify", "justification", "defend",
        "evidence", "validity", "argument",
        "recommend", "recommendation"
    },

    "understanding": {
        "understand", "understanding", "explain",
        "explanation", "describe", "description",
        "summarize", "summary", "interpret",
        "interpretation", "discuss", "discussion",
        "meaning", "illustrate"
    },

    "application": {
        "apply", "application", "use", "using",
        "demonstrate", "demonstration", "solve",
        "solution", "calculate", "calculation",
        "implement", "implementation", "perform"
    },

    "communication": {
        "communication", "communicate", "write",
        "writing", "written", "speak", "speaking",
        "presentation", "present", "express",
        "expression", "language", "audience",
        "message", "discussion", "oral", "verbal"
    },

    "reading": {
        "read", "reading", "passage", "text",
        "main", "idea", "meaning", "purpose",
        "tone", "author", "organization",
        "organization", "organizational",
        "comprehension", "interpret"
    },

    "writing": {
        "write", "writing", "written", "essay",
        "paragraph", "compose", "composition",
        "draft", "revise", "revision",
        "organize", "organization", "thesis",
        "sentence", "academic", "argument"
    },

    "problem_solving": {
        "problem", "problems", "solve", "solution",
        "apply", "strategy", "method", "decision",
        "design", "develop", "development",
        "implement", "formulate"
    },

    "knowledge": {
        "knowledge", "know", "identify", "recognize",
        "recall", "define", "definition", "list",
        "state", "name", "describe", "concept"
    },

    "research": {
        "research", "researcher", "investigate",
        "investigation", "evidence", "source",
        "sources", "data", "information",
        "analyze", "evaluate", "findings"
    }
}


def word_variants(word):

    word = normalize_word(word)

    variants = {word}

    # Basic morphological variants
    if word.endswith("ies") and len(word) > 4:
        variants.add(word[:-3] + "y")

    if word.endswith("s") and len(word) > 4:
        variants.add(word[:-1])

    if word.endswith("tion"):
        variants.add(word[:-4])

    if word.endswith("ment"):
        variants.add(word[:-4])

    return variants


def expanded_concepts(text):

    base_words = set(
        normalized_words(text)
    )

    concepts = set(base_words)

    # Add related terms when a concept is present.
    for group_name, terms in CONCEPT_GROUPS.items():

        normalized_terms = {
            normalize_word(x)
            for x in terms
        }

        if base_words.intersection(
            normalized_terms
        ):

            concepts.add(group_name)

            concepts.update(
                normalized_terms
            )

    return concepts


def fuzzy_word_match(word1, word2):

    word1 = normalize_word(word1)
    word2 = normalize_word(word2)

    if not word1 or not word2:
        return 0.0

    if word1 == word2:
        return 1.0

    # One word contains the other.
    if (
        len(word1) >= 5
        and len(word2) >= 5
        and (
            word1 in word2
            or word2 in word1
        )
    ):
        return 0.90

    return SequenceMatcher(
        None,
        word1,
        word2
    ).ratio()


def direct_word_similarity(question, outcome):

    q_words = set(
        normalized_words(question)
    )

    o_words = set(
        normalized_words(outcome)
    )

    if not q_words or not o_words:
        return 0.0, []

    matched = set()

    # Exact or fuzzy matching
    for qw in q_words:

        for ow in o_words:

            similarity = fuzzy_word_match(
                qw,
                ow
            )

            if similarity >= 0.82:

                matched.add(qw)
                break

    score = (
        len(matched)
        /
        max(1, min(len(q_words), len(o_words)))
    ) * 100

    return min(
        100.0,
        score
    ), sorted(matched)


def concept_similarity(question, outcome):

    q_concepts = expanded_concepts(
        question
    )

    o_concepts = expanded_concepts(
        outcome
    )

    if not q_concepts or not o_concepts:
        return 0.0, []

    overlap = q_concepts.intersection(
        o_concepts
    )

    if not overlap:
        return 0.0, []

    score = (
        len(overlap)
        /
        max(
            1,
            min(
                len(q_concepts),
                len(o_concepts)
            )
        )
    ) * 100

    return min(
        100.0,
        score
    ), sorted(overlap)


def outcome_similarity(question, outcome):

    """
    Improved CLO/PLO alignment detector.

    Combines:
    1. Direct wording similarity
    2. Fuzzy word similarity
    3. Related academic concepts
    4. Important Bloom/task concepts

    This is a screening tool, not a substitute for faculty review.
    """

    question = clean_text(question)
    outcome = clean_text(outcome)

    if not question or not outcome:
        return 0.0, []

    direct_score, direct_terms = direct_word_similarity(
        question,
        outcome
    )

    concept_score, concept_terms = concept_similarity(
        question,
        outcome
    )

    # Weighted combination
    #
    # Direct wording = 45%
    # Concept similarity = 55%
    #
    # Concept similarity is slightly more important because
    # CLO/PLO and questions often use different wording.
    score = (
        direct_score * 0.45
        +
        concept_score * 0.55
    )

    # Strong bonus where the same important concept occurs.
    important_groups = {
        "analysis",
        "evaluation",
        "understanding",
        "application",
        "communication",
        "reading",
        "writing",
        "problem_solving",
        "research"
    }

    shared_groups = (
        set(concept_terms)
        &
        important_groups
    )

    if shared_groups:
        score += min(
            15,
            len(shared_groups) * 7
        )

    score = min(
        100.0,
        round(score, 1)
    )

    evidence = []

    evidence.extend(
        direct_terms
    )

    evidence.extend(
        concept_terms
    )

    evidence = list(
        dict.fromkeys(
            evidence
        )
    )

    return score, evidence


def classify_alignment(score):

    if score >= 70:
        return "Strong Alignment"

    if score >= 50:
        return "Good Alignment"

    if score >= 30:
        return "Partial Alignment"

    if score >= 15:
        return "Weak Alignment"

    return "Needs Review"
