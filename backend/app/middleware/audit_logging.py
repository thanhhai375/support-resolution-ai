"""Audit logging middleware for security-sensitive CRM operations (CRM-60)."""
from __future__ import annotations
import logging, re
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
logger = logging.getLogger(__name__)

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Persist selected audit events without storing credentials or request bodies."""
    def __init__(self, app, session_factory: Callable | None = None):
        super().__init__(app)
        self.session_factory = session_factory

    @staticmethod
    def _event_for(request: Request):
        method = request.method.upper()
        path = request.url.path.rstrip("/") or "/"
        if path.endswith("/auth/login") and method == "POST":
            return "LOGIN", "auth", None
        if path.startswith("/api/knowledge") and method == "GET":
            return "KNOWLEDGE_VIEW", "knowledge", None
        match = re.search(r"/api/v1/copilot/([^/]+)/(approve|reject)$", path)
        if match and method == "PATCH":
            return ("TICKET_APPROVE" if match.group(2) == "approve" else "TICKET_REJECT", "ticket", match.group(1))
        match = re.search(r"/api/v1/copilot/([^/]+)/export$", path)
        if match and method == "GET":
            return "PDF_EXPORT", "ticket", match.group(1)
        return None

    async def dispatch(self, request: Request, call_next) -> Response:
        event = self._event_for(request)
        login_email = None
        if event and event[0] == "LOGIN" and hasattr(request, "json"):
            try:
                # Read only the login identifier; never persist the password/body.
                login_payload = await request.json()
                if isinstance(login_payload, dict):
                    login_email = str(login_payload.get("email") or "").strip().lower() or None
            except Exception:
                login_email = None
        response = await call_next(request)
        if event is None:
            return response
        action, resource_type, resource_id = event
        actor_email = login_email
        actor_role = None
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            try:
                from app.services import auth_service
                actor = auth_service.get_user_from_token(authorization.split(" ", 1)[1].strip())
                if actor:
                    actor_email, actor_role = actor.get("email"), actor.get("role")
            except Exception:
                logger.debug("Could not resolve audit actor", exc_info=True)
        try:
            if self.session_factory is None:
                import app.main as app_main
                session_factory = app_main.AsyncSessionLocal
            else:
                session_factory = self.session_factory
            from models import AuditLog
            async with session_factory() as db:
                db.add(AuditLog(
                    action=action, resource_type=resource_type, resource_id=resource_id,
                    actor_email=actor_email, actor_role=actor_role,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent", "")[:500] or None,
                    status_code=response.status_code,
                    details={"method": request.method, "path": request.url.path},
                ))
                await db.commit()
        except Exception:
            logger.exception("Failed to persist CRM audit event: %s", action)
        return response
