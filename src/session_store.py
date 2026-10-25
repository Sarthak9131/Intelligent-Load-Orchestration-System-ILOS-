"""Replaceable Google ADK session-service provider interface."""

from typing import Protocol

from google.adk.sessions import BaseSessionService, InMemorySessionService


class SessionServiceProvider(Protocol):
    """Factory boundary for selecting an ADK session-service implementation."""

    def create(self) -> BaseSessionService:
        """Return a fresh session service for an agent runner."""


class InMemorySessionServiceProvider:
    """Current process-local implementation of the session-service boundary."""

    def create(self) -> BaseSessionService:
        """Return an ADK in-memory session service."""
        return InMemorySessionService()


def create_session_service(
    provider: SessionServiceProvider | None = None,
) -> BaseSessionService:
    """Create a session service using the supplied or default provider."""
    selected_provider = provider or InMemorySessionServiceProvider()
    return selected_provider.create()
