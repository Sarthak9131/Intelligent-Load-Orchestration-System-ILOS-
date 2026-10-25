"""Tests for the swappable ADK session-service provider."""

from google.adk.sessions import BaseSessionService, InMemorySessionService

from src.session_store import (
    InMemorySessionServiceProvider,
    SessionServiceProvider,
    create_session_service,
)


def test_default_provider_returns_in_memory_sessions():
    service = create_session_service()

    assert isinstance(service, InMemorySessionService)
    assert isinstance(service, BaseSessionService)


def test_custom_provider_can_be_injected():
    provider: SessionServiceProvider = InMemorySessionServiceProvider()

    assert isinstance(create_session_service(provider), InMemorySessionService)
