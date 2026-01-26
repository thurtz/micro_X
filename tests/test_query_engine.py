# tests/test_query_engine.py

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from modules import query_engine

@pytest.fixture
def mock_config():
    return {
        "ai_models": {
            "router": {"model": "test-model"}
        }
    }

@patch("modules.query_engine.load_config")
@patch("modules.query_engine.RAGManager")
def test_query_knowledge_base_success(mock_rag_cls, mock_load_config, mock_config):
    mock_load_config.return_value = mock_config
    mock_rag_instance = mock_rag_cls.return_value
    mock_rag_instance.vector_store = True # simulate initialized
    mock_rag_instance.query.return_value = ["Chunk 1", "Chunk 2"]
    
    result = query_engine.query_knowledge_base("test_kb", "test query")
    
    assert "Chunk 1" in result
    assert "Chunk 2" in result
    mock_rag_cls.assert_called_with(config=mock_config, name="test_kb")
    mock_rag_instance.initialize.assert_called_once()
    mock_rag_instance.query.assert_called_once_with("test query")

@patch("modules.query_engine.load_config")
@patch("modules.query_engine.RAGManager")
def test_query_knowledge_base_init_fail(mock_rag_cls, mock_load_config, mock_config):
    mock_load_config.return_value = mock_config
    mock_rag_instance = mock_rag_cls.return_value
    mock_rag_instance.vector_store = None # simulate init failure
    
    result = query_engine.query_knowledge_base("test_kb", "test query")
    
    assert "not found or failed to load" in result

@patch("modules.query_engine.load_config")
@patch("modules.query_engine.RAGManager")
def test_query_knowledge_base_no_results(mock_rag_cls, mock_load_config, mock_config):
    mock_load_config.return_value = mock_config
    mock_rag_instance = mock_rag_cls.return_value
    mock_rag_instance.vector_store = True
    mock_rag_instance.query.return_value = []
    
    result = query_engine.query_knowledge_base("test_kb", "test query")
    
    assert "No relevant information found" in result

@pytest.mark.asyncio
@patch("modules.query_engine.load_config")
@patch("modules.query_engine.RAGManager")
@patch("modules.query_engine.OllamaLLM")
async def test_query_knowledge_base_rag_success(mock_llm_cls, mock_rag_cls, mock_load_config, mock_config):
    mock_load_config.return_value = mock_config
    
    # RAG Mock
    mock_rag_instance = mock_rag_cls.return_value
    mock_rag_instance.vector_store = True
    mock_rag_instance.query.return_value = ["Context 1"]
    
    # LLM Mock
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm
    
    # Chain Mock
    # chain = prompt | llm
    # We need to mock the prompt template creation to control the chain
    with patch("modules.query_engine.ChatPromptTemplate") as mock_prompt_cls:
        mock_prompt = MagicMock()
        mock_prompt_cls.from_template.return_value = mock_prompt
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = "AI Answer"
        
        # prompt | llm -> chain
        mock_prompt.__or__.return_value = mock_chain # simplified
        # Actually in code it is: chain = prompt | llm
        # So prompt.__or__(llm) should return chain
        mock_prompt.__or__.side_effect = lambda x: mock_chain if x == mock_llm else MagicMock()

        result = await query_engine.query_knowledge_base_rag("test_kb", "question")
        
        assert result == "AI Answer"
        mock_chain.ainvoke.assert_awaited_once()
        args = mock_chain.ainvoke.await_args[0][0]
        assert args['context'] == "Context 1"
        assert args['question'] == "question"

@pytest.mark.asyncio
@patch("modules.query_engine.load_config")
@patch("modules.query_engine.RAGManager")
async def test_query_knowledge_base_rag_no_context(mock_rag_cls, mock_load_config, mock_config):
    mock_load_config.return_value = mock_config
    mock_rag_instance = mock_rag_cls.return_value
    mock_rag_instance.vector_store = True
    mock_rag_instance.query.return_value = []
    
    result = await query_engine.query_knowledge_base_rag("test_kb", "question")
    
    assert "could not find any relevant information" in result
