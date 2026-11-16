from fastapi import APIRouter, Body, Depends, Response, status

from src.dependencies import get_evaluation_service, get_verified_user
from src.models.auth import AuthenticatedUser
from src.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    LlmSessionCreateRequest,
    LlmSessionResponse,
)
from src.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post(
    "/sessions",
    response_model=LlmSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open an LLM grading session",
    responses={
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        503: {"description": "No LLM API key is configured"},
    },
)
def create_llm_session(
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: EvaluationService = Depends(get_evaluation_service),
    payload: LlmSessionCreateRequest = Body(default_factory=LlmSessionCreateRequest),
) -> LlmSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    api_key = payload.api_key.get_secret_value() if payload.api_key is not None else None
    return LlmSessionResponse(session_id=service.create_session(user.uid, api_key))


@router.post(
    "/sessions/{session_id}/evaluations",
    response_model=EvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Grade an open flashcard answer",
    responses={
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        404: {"description": "Unknown or expired LLM session"},
        422: {"description": "Invalid grading request"},
        502: {"description": "LLM provider failed"},
        504: {"description": "LLM evaluation timed out"},
    },
)
async def evaluate_answer(
    session_id: str,
    payload: EvaluationRequest,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationResult:
    response.headers["Cache-Control"] = "no-store"
    return await service.evaluate(user.uid, session_id, payload)
