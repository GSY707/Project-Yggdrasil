from fastapi import APIRouter

from yggdrasil_sdk.spec_catalog import list_spec_documents


router = APIRouter()


@router.get("")
def list_specs() -> dict[str, object]:
    documents = list_spec_documents()
    counts: dict[str, int] = {}
    for document in documents:
        counts[document.category] = counts.get(document.category, 0) + 1

    return {
        "counts": counts,
        "documents": [document.model_dump(by_alias=True) for document in documents],
    }