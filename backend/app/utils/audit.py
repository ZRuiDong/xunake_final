from datetime import datetime
from sqlalchemy import inspect
from app.models.audit import AuditLog


def snapshot_entities(entities):
    result = []
    for entity in entities:
        values = {}
        for attribute in inspect(type(entity)).column_attrs:
            if attribute.key in ("password_hash", "token_version"):
                continue
            value = getattr(entity, attribute.key)
            values[attribute.key] = value.isoformat() if isinstance(value, datetime) else value
        result.append(values)
    return result


def audit_deletion(db, actor, action, entities, selections):
    # Written in the deletion transaction, with no FK to deleted entities.
    db.add(AuditLog(actor=str(actor), action=action, snapshot={
        "entities": snapshot_entities(entities),
        "selections": snapshot_entities(selections),
    }))
