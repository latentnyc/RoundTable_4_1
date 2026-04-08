import pytest
import datetime
import json
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.services.chat_service import ChatService

@pytest.fixture
def mock_db_session():
    mock_session = AsyncMock()
    return mock_session

@pytest.mark.asyncio
async def test_save_message_with_db():
    mock_db = AsyncMock()
    
    result = await ChatService.save_message(
        campaign_id="test_camp",
        sender_id="player1",
        sender_name="John",
        content="Hello world",
        db=mock_db
    )
    
    assert "id" in result
    assert "timestamp" in result
    mock_db.execute.assert_called_once()
    
@pytest.mark.asyncio
async def test_save_message_without_db():
    with patch('app.services.chat_service.AsyncSessionLocal') as mock_session_maker:
        mock_session = AsyncMock()
        # Mock the context manager behavior
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        result = await ChatService.save_message(
            campaign_id="test_camp",
            sender_id="player1",
            sender_name="John",
            content="Hello world"
        )
        
        assert "id" in result
        assert "timestamp" in result
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_get_chat_history_with_db():
    mock_db = AsyncMock()
    
    # Mock return rows
    mock_result = AsyncMock()
    mock_rows = [
        {"content": "System started", "sender_id": "system", "sender_name": "System"},
        {"content": "Hello players", "sender_id": "dm", "sender_name": "DM"},
        {"content": "Hi DM", "sender_id": "player1", "sender_name": "Alice"}
    ]
    class MockResult:
        def mappings(self):
            class Mappings:
                def all(self):
                    return mock_rows
            return Mappings()
            
    mock_db.execute.return_value = MockResult()
    
    messages = await ChatService.get_chat_history("test_camp", limit=3, db=mock_db)
    
    assert len(messages) == 3
    # Rows are reversed in get_chat_history
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Alice: Hi DM"
    
    assert isinstance(messages[1], AIMessage)
    assert messages[1].content == "Hello players"
    
    assert isinstance(messages[2], SystemMessage)
    assert messages[2].content == "System started"

@pytest.mark.asyncio
async def test_get_latest_memory():
    with patch('app.services.chat_service.AsyncSessionLocal') as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        class MockResult:
            def mappings(self):
                class Mappings:
                    def fetchone(self):
                        return {"summary_text": "The party entered the cave", "created_at": "2023-01-01"}
                return Mappings()
        mock_session.execute.return_value = MockResult()
        
        summary, created_at = await ChatService.get_latest_memory("test_camp")
        
        assert summary == "The party entered the cave"
        assert created_at == "2023-01-01"
