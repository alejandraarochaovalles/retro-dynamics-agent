from __future__ import annotations

from fastapi import APIRouter

from agents import dynamic_generator
from models import DynamicsGenerateRequest, DynamicsGenerateResponse

router = APIRouter(tags=["dynamics"])


@router.post(
    "/dynamics/generate",
    operation_id="generateDynamics",
    response_model=DynamicsGenerateResponse,
)
def generate_dynamics(payload: DynamicsGenerateRequest) -> DynamicsGenerateResponse:
    proposals, source = dynamic_generator.generate(payload.context, payload.count)
    return DynamicsGenerateResponse(proposals=proposals, source=source)
