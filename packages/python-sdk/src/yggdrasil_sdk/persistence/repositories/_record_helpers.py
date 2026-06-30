from ._imports import ActorRef, Any, EntityRef, ExternalRef, ImportPolicy, NodeORM


def _actor(value: dict[str, Any] | ActorRef | None, *, default_type: str = "system", default_id: str = "kernel") -> ActorRef:
    if value is None:
        return ActorRef(type=default_type, id=default_id)
    if isinstance(value, ActorRef):
        return value
    return ActorRef.model_validate(value)


def _external_ref(value: dict[str, Any] | ExternalRef | None) -> ExternalRef | None:
    if value is None:
        return None
    if isinstance(value, ExternalRef):
        return value
    return ExternalRef.model_validate(value)


def _entity_refs(values: list[dict[str, Any] | EntityRef] | None) -> list[EntityRef]:
    if not values:
        return []
    refs: list[EntityRef] = []
    for value in values:
        if isinstance(value, EntityRef):
            refs.append(value)
            continue
        refs.append(EntityRef.model_validate(value))
    return refs


def _import_policy(value: dict[str, Any] | ImportPolicy | None) -> ImportPolicy:
    if value is None:
        return ImportPolicy()
    if isinstance(value, ImportPolicy):
        return value
    return ImportPolicy.model_validate(value)


def _score_snapshot_from_node(node: NodeORM) -> dict[str, float]:
    return {
        "importance": node.importance,
        "stability": node.stability,
        "forgetRate": node.forget_rate,
        "feedforwardScore": node.feedforward_score,
        "accessScore": node.access_score,
        "activityK": node.activity_k,
        "floatScore": node.float_score,
    }
