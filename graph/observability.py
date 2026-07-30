import os
import uuid

import structlog

from config import get_settings

logger = structlog.get_logger()
_langfuse_client = None

def safe_uuid(id_str: str) -> str:
    """Convert an arbitrary string to a valid UUID string (generates a deterministic UUID if not a valid hex UUID)."""
    try:
        uuid.UUID(id_str)
        return id_str
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str))

def get_langfuse_client():
    global _langfuse_client
    if _langfuse_client is None:
        settings = get_settings()
        pub_key = os.getenv("LANGFUSE_PUBLIC_KEY") or getattr(settings, "langfuse_public_key", None)
        sec_key = os.getenv("LANGFUSE_SECRET_KEY") or getattr(settings, "langfuse_secret_key", None)
        host = os.getenv("LANGFUSE_HOST") or getattr(settings, "langfuse_host", "http://localhost:4000")
        
        # Check if keys are set and not placeholder values
        if pub_key and sec_key and "placeholder" not in pub_key and "placeholder" not in sec_key:
            try:
                from langfuse import Langfuse
                _langfuse_client = Langfuse(
                    public_key=pub_key,
                    secret_key=sec_key,
                    host=host
                )
                logger.info("observability.langfuse_client_connected", host=host)
            except Exception as e:
                logger.warning("observability.langfuse_client_init_failed", error=str(e))
    return _langfuse_client

def get_callbacks(trace_id: str, session_id: str | None = None) -> list:
    callbacks = []
    settings = get_settings()
    pub_key = os.getenv("LANGFUSE_PUBLIC_KEY") or getattr(settings, "langfuse_public_key", None)
    sec_key = os.getenv("LANGFUSE_SECRET_KEY") or getattr(settings, "langfuse_secret_key", None)
    host = os.getenv("LANGFUSE_HOST") or getattr(settings, "langfuse_host", "http://localhost:4000")
    
    # Check if keys are set and not placeholder values
    if pub_key and sec_key and "placeholder" not in pub_key and "placeholder" not in sec_key:
        try:
            from langfuse.langchain import CallbackHandler
            handler = CallbackHandler(
                public_key=pub_key,
                secret_key=sec_key,
                host=host,
            )
            callbacks.append(handler)
            logger.info("observability.langfuse_callbacks_registered", trace_id=trace_id)
        except Exception as e:
            logger.warning("observability.langfuse_callback_init_failed", error=str(e))
    return callbacks

def log_validation_score(trace_id: str, accuracy: float, completion: float, compliance: float, overall: float, passed: bool, retry_count: int):
    client = get_langfuse_client()
    if client:
        try:
            # Normalize trace ID
            valid_trace_id = safe_uuid(trace_id)
            client.create_score(name="factual_accuracy", value=accuracy, trace_id=valid_trace_id)
            client.create_score(name="task_completion", value=completion, trace_id=valid_trace_id)
            client.create_score(name="format_compliance", value=compliance, trace_id=valid_trace_id)
            client.create_score(name="overall_quality", value=overall, trace_id=valid_trace_id)
            client.create_score(name="passed", value=int(passed), trace_id=valid_trace_id)
            client.create_score(name="retry_count", value=retry_count, trace_id=valid_trace_id)
            client.flush()
            logger.info("observability.logged_validation_scores", trace_id=valid_trace_id, overall=overall)
        except Exception as e:
            logger.warning("observability.log_validation_scores_failed", trace_id=trace_id, error=str(e))

def log_hitl_event(trace_id: str, event_type: str, feedback: str | None = None, approved: bool | None = None):
    client = get_langfuse_client()
    if client:
        try:
            # Normalize trace ID
            valid_trace_id = safe_uuid(trace_id)
            comment = f"Feedback: {feedback}" if feedback else None
            val = int(approved) if approved is not None else 0
            client.create_score(
                name=f"hitl_{event_type}",
                value=val,
                trace_id=valid_trace_id,
                comment=comment
            )
            client.flush()
            logger.info("observability.logged_hitl_event", trace_id=valid_trace_id, event_type=event_type)
        except Exception as e:
            logger.warning("observability.log_hitl_event_failed", trace_id=trace_id, error=str(e))
