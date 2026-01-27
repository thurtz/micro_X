# tests/test_utils_knowledge.py

import pytest
import argparse
from unittest.mock import MagicMock, patch, AsyncMock
from utils import knowledge

@pytest.fixture
def mock_rag_manager(mocker):
    # Patch the class where it is used in utils.knowledge
    mock_cls = mocker.patch("utils.knowledge.RAGManager")
    instance = mock_cls.return_value
    return instance

@pytest.fixture
def mock_load_config(mocker):
    return mocker.patch("utils.knowledge.load_config", return_value={})

@pytest.mark.asyncio
async def test_main_add_file(mock_rag_manager, mock_load_config):
    with patch("os.path.isfile", return_value=True):
        with patch("sys.argv", ["knowledge.py", "add-file", "/tmp/test.txt"]):
            await knowledge.main()
        
    mock_rag_manager.initialize.assert_called_once()
    mock_rag_manager.add_file.assert_called_with("/tmp/test.txt")

@pytest.mark.asyncio
async def test_main_add_dir(mock_rag_manager, mock_load_config):
    # Mock isdir to be true for our dummy path
    with patch("os.path.isdir", return_value=True):
        with patch("sys.argv", ["knowledge.py", "add-dir", "/tmp/docs"]):
            await knowledge.main()
            
    mock_rag_manager.add_directory.assert_called_with("/tmp/docs")

@pytest.mark.asyncio
async def test_main_add_url(mock_rag_manager, mock_load_config):
    with patch("sys.argv", ["knowledge.py", "add-url", "http://example.com", "--recursive"]):
        await knowledge.main()
        
    mock_rag_manager.add_url.assert_called_with(
        "http://example.com", recursive=True, save_cache=False, depth=2
    )

@pytest.mark.asyncio
@patch("utils.knowledge.query_knowledge_base")
@patch("builtins.print")
async def test_main_query_standard(mock_print, mock_query_func, mock_rag_manager, mock_load_config):
    mock_query_func.return_value = "Standard Answer"
    
    with patch("sys.argv", ["knowledge.py", "query", "what", "is", "x"]):
        await knowledge.main()
        
    mock_query_func.assert_called_with(kb_name='default', query="what is x")
    # Verify output
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert "Standard Answer" in calls

@pytest.mark.asyncio
@patch("utils.knowledge.query_knowledge_base_rag", new_callable=AsyncMock)
@patch("builtins.print")
async def test_main_query_rag(mock_print, mock_query_rag, mock_rag_manager, mock_load_config):
    mock_query_rag.return_value = "RAG Answer"
    
    with patch("sys.argv", ["knowledge.py", "--rag", "query", "what", "is", "x"]):
        await knowledge.main()
        
    mock_query_rag.assert_awaited_with(kb_name='default', query="what is x")
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert "RAG Answer" in calls
