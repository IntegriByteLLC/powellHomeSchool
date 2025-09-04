# main.py or a small control router
from fastapi import APIRouter
from Postgres.config import config

control = APIRouter(prefix="/control", tags=["Control"])

@control.post("/reload-persona")
async def reload_persona():
    changed = await config.fetch_persona_from_powpow()
    return {
        "updated": changed,
        "version": config.persona_version,
        "provider": config.default_provider,
        "model": config.default_model,
    }


