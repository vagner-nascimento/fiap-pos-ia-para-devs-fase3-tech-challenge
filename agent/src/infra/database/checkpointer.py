"""Persistência do estado do agente usando o checkpointer do LangGraph."""
import os
from typing import Optional

from langgraph.checkpoint.mongodb import MongoDBSaver

from infra.database.mongodb import get_mongo_client

_checkpointer: Optional[MongoDBSaver] = None


def get_checkpointer() -> MongoDBSaver:
    """Retorna o MongoDBSaver singleton usado pelo grafo do agente."""
    global _checkpointer

    if _checkpointer is None:
        _checkpointer = MongoDBSaver(
            client=get_mongo_client(),
            db_name=os.getenv("DB_NAME", "fiap_pos_ia_fase3"),
            checkpoint_collection_name="agent_checkpoints",
            writes_collection_name="agent_checkpoint_writes",
        )

    return _checkpointer
