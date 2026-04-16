from __future__ import annotations

from yggdrasil_sdk.support import utc_now


PIPELINE_BY_KIND = {
    "document": {
        "stages": ["normalize", "extract-structure", "segment-text", "summarize", "embed"],
        "requiredAdapters": ["docling"],
        "derivedRoles": ["derived", "preview"],
        "summaryStrategy": "section-aware",
    },
    "image": {
        "stages": ["normalize", "ocr", "caption", "segment-regions", "embed"],
        "requiredAdapters": ["paddleocr", "vision-captioner"],
        "derivedRoles": ["thumbnail", "preview", "derived"],
        "summaryStrategy": "visual-scene",
    },
    "audio": {
        "stages": ["normalize", "transcribe", "segment-transcript", "summarize", "embed"],
        "requiredAdapters": ["faster-whisper"],
        "derivedRoles": ["transcript", "derived"],
        "summaryStrategy": "speaker-aware",
    },
    "video": {
        "stages": ["normalize", "extract-keyframes", "transcribe-audio", "segment-scenes", "summarize", "embed"],
        "requiredAdapters": ["ffmpeg", "faster-whisper", "vision-captioner"],
        "derivedRoles": ["preview", "transcript", "thumbnail", "derived"],
        "summaryStrategy": "scene-aware",
    },
}


def _normalize_kind(asset_kind: str) -> str:
    normalized = asset_kind.lower().strip()
    if normalized in {"pdf", "doc", "docx", "markdown", "text"}:
        return "document"
    if normalized in {"png", "jpg", "jpeg", "webp", "image"}:
        return "image"
    if normalized in {"mp3", "wav", "audio"}:
        return "audio"
    if normalized in {"mp4", "mov", "mkv", "video"}:
        return "video"
    return "document"


def plan_asset_processing(asset_kind: str) -> dict[str, object]:
    normalized_kind = _normalize_kind(asset_kind)
    blueprint = PIPELINE_BY_KIND[normalized_kind]
    return {
        "assetKind": normalized_kind,
        "inputKind": asset_kind,
        "status": "planned",
        "pipeline": [
            {"stage": stage, "mode": "deterministic" if stage in {"normalize", "extract-keyframes"} else "semantic"}
            for stage in blueprint["stages"]
        ],
        "requiredAdapters": blueprint["requiredAdapters"],
        "derivedRoles": blueprint["derivedRoles"],
        "summaryStrategy": blueprint["summaryStrategy"],
        "storagePlan": {
            "original": f"assets/{normalized_kind}/original",
            "derived": f"assets/{normalized_kind}/derived",
            "preview": f"assets/{normalized_kind}/preview",
        },
        "embeddingTargets": ["asset", "asset-segment"],
        "plannedAt": utc_now().isoformat(),
    }