"""Tests for BaseAgent abstract class.

Validates:
- BaseAgent cannot be instantiated directly (Requirements 2.1)
- Incomplete subclass raises TypeError (Requirements 2.2)
- Complete subclass can be instantiated and execute called (Requirements 2.3)
"""

import pytest
from app.agents.base import BaseAgent


def test_base_agent_cannot_be_instantiated():
    """BaseAgent is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseAgent()


def test_incomplete_subclass_raises_type_error():
    """A subclass that doesn't implement execute cannot be instantiated."""

    class IncompleteAgent(BaseAgent):
        pass

    with pytest.raises(TypeError):
        IncompleteAgent()


@pytest.mark.asyncio
async def test_complete_subclass_can_execute():
    """A subclass implementing execute can be instantiated and used."""

    class ConcreteAgent(BaseAgent):
        async def execute(self, payload: dict) -> dict:
            return {"result": payload.get("input", "")}

    agent = ConcreteAgent()
    result = await agent.execute({"input": "test"})
    assert result == {"result": "test"}
