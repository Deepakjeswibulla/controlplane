import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import EvaluateRequest, EvaluateResponse, ReviewRequest
from app.models.domain import HumanReview, Interaction
from app.policy.loader import PolicyLoadError, load_all_policies
from app.services.evaluation import evaluate_interaction
from app.services.gemini_client import get_gemini_client
from app.detectors.evidence import retrieve as retrieve_evidence
from app.services.metrics import compute_metrics
from app.services.review import submit_review
from app.services.storage import get_storage

logger = logging.getLogger("controlplane.api")
router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/interactions/evaluate", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    storage = get_storage()
    try:
        ai_output = payload.ai_output
        semantic_verification = None
        if payload.generate_with_gemini:
            client = get_gemini_client()
            ai_output = client.generate(payload.user_input, context=payload.context.model_dump())

        # Semantic verification is optional and provider-aware. In fallback mode it is local/no-network.
        client = get_gemini_client()
        if ai_output.strip() and client.enabled:
            evidence_chunks = retrieve_evidence(
                (payload.user_input + " " + ai_output).strip(),
                payload.context.use_case.value,
                top_k=3,
            )
            evidence_payload = [
                {"document_id": c.doc_id, "title": c.title, "excerpt": c.text, "similarity": c.similarity}
                for c in evidence_chunks if c.similarity > 0
            ]
            semantic_verification = client.verify_sync(ai_output, evidence_payload)

        interaction = evaluate_interaction(
            storage,
            user_input=payload.user_input,
            ai_output=ai_output,
            context=payload.context,
            semantic_verification=semantic_verification,
            tool_calls=payload.tool_calls,
            model_tier=payload.model_tier,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
            model_calls=payload.model_calls,
            retries=payload.retries,
            request_complexity=payload.request_complexity,
        )
    except PolicyLoadError as exc:
        logger.error("Policy error during evaluation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return EvaluateResponse.from_interaction(interaction)


@router.get("/interactions", response_model=list[Interaction])
def list_interactions(limit: int = 100) -> list[Interaction]:
    return get_storage().list_interactions(limit=limit)


@router.get("/interactions/{interaction_id}", response_model=Interaction)
def get_interaction(interaction_id: str) -> Interaction:
    interaction = get_storage().get_interaction(interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return interaction


@router.post("/interactions/{interaction_id}/review", response_model=HumanReview)
def review_interaction(interaction_id: str, payload: ReviewRequest) -> HumanReview:
    storage = get_storage()
    interaction = storage.get_interaction(interaction_id)
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return submit_review(storage, interaction, payload.outcome, payload.reviewer, payload.notes)


@router.get("/metrics")
def metrics() -> dict:
    return compute_metrics(get_storage())


@router.get("/policies")
def policies() -> dict:
    try:
        loaded = load_all_policies()
    except PolicyLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {use_case: policy.model_dump() for use_case, policy in loaded.items()}
