
import re
import secrets
from difflib import SequenceMatcher
from config import supabase
import time

# Loaded once and reused for subsequent duplicate checks.
_semantic_model = None

SEMANTIC_DUPLICATE_THRESHOLD = 0.65


def _get_semantic_model():
    global _semantic_model

    if _semantic_model is None:
        from sentence_transformers import SentenceTransformer

        _semantic_model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

    return _semantic_model

def _semantic_similarities(problem, candidates):
    """Compare complaint meanings across English, Hindi and Marathi."""
    if not candidates:
        return []

    try:
        model = _get_semantic_model()

        embeddings = model.encode(
            [problem] + candidates,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        query_embedding = embeddings[0]
        candidate_embeddings = embeddings[1:]

        return [
            float(query_embedding @ candidate_embedding)
            for candidate_embedding in candidate_embeddings
        ]

    except Exception as error:
        print("Semantic duplicate detection unavailable:", repr(error))
        return [None] * len(candidates)

TABLE_NAME = "citizen_requests"

# Common words that add little value when comparing civic complaints.
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "being", "of", "to", "in", "on", "at", "for", "from", "by",
    "near", "with", "and", "or", "there", "this", "that", "it",
    "has", "have", "had", "very", "please", "problem", "issue"
}

# Tune this using your demo examples. Higher = fewer false positives.
DUPLICATE_THRESHOLD = 0.72


def location_prefix(location: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", (location or "")).upper()
    return (letters[:3] if len(letters) >= 3
            else (letters + "XXX")[:3])


def generate_unique_report_id(location: str, attempts: int = 30) -> str:
    """Generate an ID such as PUN482 and check that it is unused."""
    prefix = location_prefix(location)

    for _ in range(attempts):
        report_id = f"{prefix}{secrets.randbelow(1000):03d}"

        found = (
            supabase.table(TABLE_NAME)
            .select("id")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )

        if not (found.data or []):
            return report_id

    raise RuntimeError(
        "Could not generate a unique complaint ID. Please try again."
    )



def normalize_for_duplicate_check(value: str) -> str:
    """Normalize punctuation and case while preserving Hindi/Marathi."""
    text = (value or "").casefold()
    return " ".join(
        re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    )



def _meaningful_tokens(value: str) -> set:
    normalized = normalize_for_duplicate_check(value)

    return {
        token
        for token in normalized.split()
        if token not in STOP_WORDS and len(token) > 1
    }


def _text_similarity(first: str, second: str) -> float:
    """
    Compare complaint descriptions using:
    - character/phrase similarity
    - overlap between meaningful words

    Returns a score from 0.0 to 1.0.
    """
    first_normalized = normalize_for_duplicate_check(first)
    second_normalized = normalize_for_duplicate_check(second)

    if not first_normalized or not second_normalized:
        return 0.0

    if first_normalized == second_normalized:
        return 1.0

    first_tokens = _meaningful_tokens(first_normalized)
    second_tokens = _meaningful_tokens(second_normalized)

    sequence_score = SequenceMatcher(
        None, first_normalized, second_normalized
    ).ratio()

    if not first_tokens or not second_tokens:
        return sequence_score

    common_tokens = first_tokens & second_tokens

    # Overlap relative to the shorter description helps when one
    # report includes extra details about the same underlying issue.
    token_score = len(common_tokens) / min(
        len(first_tokens), len(second_tokens)
    )

    # Weighted score: phrase similarity plus meaningful-word overlap.
    return (0.45 * sequence_score) + (0.55 * token_score)


def _location_similarity(first: str, second: str) -> float:
    first_normalized = normalize_for_duplicate_check(first)
    second_normalized = normalize_for_duplicate_check(second)

    if not first_normalized or not second_normalized:
        return 0.0

    if first_normalized == second_normalized:
        return 1.0

    first_tokens = set(first_normalized.split())
    second_tokens = set(second_normalized.split())

    if not first_tokens or not second_tokens:
        return 0.0

    overlap = len(first_tokens & second_tokens) / len(
        first_tokens | second_tokens
    )

    sequence = SequenceMatcher(
        None, first_normalized, second_normalized
    ).ratio()

    return max(overlap, sequence)



def find_duplicate_report(problem: str, location: str):
    """
    Find duplicates using lexical and multilingual semantic similarity.
    Existing return fields and duplicate metadata are preserved.
    """
    start_time = time.perf_counter()

    normalized_problem = normalize_for_duplicate_check(problem)
    normalized_location = normalize_for_duplicate_check(location)

    if not normalized_problem or not normalized_location:
        return None

    fetch_start = time.perf_counter()
    response = (
        supabase.table(TABLE_NAME)
        .select("id,problem,location,status,created_at,category")
        .execute()
    )
    print(
    f"Supabase fetch: {time.perf_counter() - fetch_start:.3f}s; "
    f"reports fetched: {len(response.data or [])}"
        )


    # First filter by location to avoid comparing unrelated places.
    candidates = []

    for report in response.data or []:
        old_problem = report.get("problem") or ""
        old_location = report.get("location") or ""

        location_score = _location_similarity(location, old_location)

        if location_score < 0.75:
            continue

        lexical_score = _text_similarity(problem, old_problem)

        print(
            "DUPLICATE CANDIDATE:",
            repr(old_problem),
            "| location =", round(location_score, 3),
            "| lexical =", round(lexical_score, 3)
            )

        candidates.append({
            "report": report,
            "location_score": location_score,
            "lexical_score": lexical_score,
        })

    if not candidates:
        return None

    # Calculate multilingual semantic similarity in one batch.
    needs_semantic_check = [
        item for item in candidates
        if item["lexical_score"] < DUPLICATE_THRESHOLD
    ]

    
    semantic_start = time.perf_counter()

    semantic_scores = _semantic_similarities(
    problem,
    [
        item["report"].get("problem") or ""
        for item in needs_semantic_check
    ],
    )
    print(
    f"Semantic comparison: "
    f"{time.perf_counter() - semantic_start:.3f}s; "
    f"candidates: {len(needs_semantic_check)}"
        )


    for item, semantic_score in zip(
        needs_semantic_check, semantic_scores
    ):
        item["semantic_score"] = semantic_score

        print(
            "SEMANTIC SCORE:",
            repr(item["report"].get("problem")),
            "score =", semantic_score
            )

    best_match = None
    best_score = 0.0

    for item in candidates:
        lexical_score = item["lexical_score"]
        semantic_score = item.get("semantic_score")

        # Existing same-language matching remains unchanged.
        is_duplicate = lexical_score >= DUPLICATE_THRESHOLD
        match_score = lexical_score

        # Use semantic matching when lexical matching is insufficient.
        if (
            not is_duplicate
            and semantic_score is not None
            and semantic_score >= SEMANTIC_DUPLICATE_THRESHOLD
        ):
            is_duplicate = True
            match_score = semantic_score

        if is_duplicate and match_score > best_score:
            best_score = match_score
            best_match = item["report"].copy()

    if best_match:
        best_match["similarity_score"] = round(best_score * 100, 1)
        best_match["duplicate_reason"] = (
            "The complaint description is similar in meaning "
            "and the reported location is sufficiently similar "
            "to an existing report."
        )
        return best_match

    return None