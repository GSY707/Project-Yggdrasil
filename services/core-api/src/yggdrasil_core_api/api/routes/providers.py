from fastapi import APIRouter, Body, HTTPException, status

from yggdrasil_sdk.provider_config import (
    PROVIDER_ENV_GROUPS,
    delete_provider_key,
    provider_configuration_status,
    save_provider_key,
)


router = APIRouter()


@router.get("")
def get_provider_settings() -> dict[str, object]:
    return {
        "providers": [
            {"id": str(item["id"]), "label": str(item["label"])}
            for item in PROVIDER_ENV_GROUPS
            if item["id"] != "generic"
        ],
        "status": provider_configuration_status(),
    }


@router.post("/{provider_id}")
def set_provider_key(provider_id: str, payload: dict[str, object] = Body(...)) -> dict[str, object]:
    try:
        status_payload = save_provider_key(provider_id, str(payload.get("apiKey") or ""))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown LLM provider.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"status": status_payload}


@router.delete("/{provider_id}")
def remove_provider_key(provider_id: str) -> dict[str, object]:
    try:
        status_payload = delete_provider_key(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown LLM provider.") from exc
    return {"status": status_payload}
