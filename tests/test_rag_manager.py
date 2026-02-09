# tests/test_rag_manager.py

import pytest
import os
from unittest.mock import MagicMock, patch, mock_open
from modules.rag_manager import RAGManager

@pytest.fixture
def mock_config():
    return {
        "intent_classification": {
            "embedding_model": "test-embed-model"
        }
    }

@pytest.fixture
def rag_manager(mock_config):
    with patch('modules.rag_manager.OllamaEmbeddings'), \
         patch('modules.rag_manager.Chroma'):
        manager = RAGManager(mock_config, name="test_kb")
        manager.initialize()
        return manager

def test_rag_manager_init_paths(mock_config):
    manager = RAGManager(mock_config, name="test_kb")
    assert manager.name == "test_kb"
    assert "knowledge_bases/test_kb" in manager._db_path
    assert "knowledge_bases/test_kb/cache" in manager._cache_path

def test_rag_manager_initialize(mocker, mock_config):
    mock_embeddings = mocker.patch('modules.rag_manager.OllamaEmbeddings')
    mock_chroma = mocker.patch('modules.rag_manager.Chroma')
    mock_makedirs = mocker.patch('os.makedirs')
    
    manager = RAGManager(mock_config, name="test_kb")
    manager.initialize()
    
    mock_embeddings.assert_called_once_with(model="test-embed-model")
    mock_chroma.assert_called_once()
    assert manager.vector_store is not None
    mock_makedirs.assert_called_with(manager._cache_path, exist_ok=True)

def test_add_file_unsupported_extension(rag_manager):
    with patch.object(rag_manager.vector_store, 'add_documents') as mock_add:
        rag_manager.add_file("test.exe")
        mock_add.assert_not_called()

@pytest.mark.parametrize("ext, loader_name", [
    (".txt", "TextLoader"),
    (".pdf", "PyPDFLoader"),
    (".html", "BSHTMLLoader"),
])
def test_add_file_supported_extensions(rag_manager, ext, loader_name):
    file_path = f"test{ext}"
    mock_loader = MagicMock()
    mock_doc = MagicMock()
    mock_loader.load.return_value = [mock_doc]
    
    with patch(f"modules.rag_manager.{loader_name}", return_value=mock_loader), \
         patch.object(rag_manager.text_splitter, 'split_documents', return_value=[mock_doc]) as mock_split, \
         patch.object(rag_manager.vector_store, 'add_documents') as mock_add:
        
        rag_manager.add_file(file_path)
        
        mock_loader.load.assert_called_once()
        mock_split.assert_called_once_with([mock_doc])
        mock_add.assert_called_once_with([mock_doc])

def test_add_directory(rag_manager):
    with patch('os.walk') as mock_walk, \
         patch.object(rag_manager, 'add_file') as mock_add_file:
        
        mock_walk.return_value = [
            ('/root', ('subdir',), ('file1.md', 'file2.txt')),
        ]
        
        rag_manager.add_directory("/root")
        
        assert mock_add_file.call_count == 2
        mock_add_file.assert_any_call('/root/file1.md')
        mock_add_file.assert_any_call('/root/file2.txt')

def test_add_url_success(rag_manager):
    mock_head = MagicMock()
    mock_head.headers = {'Content-Type': 'text/html'}
    mock_head.raise_for_status = MagicMock()
    
    mock_get = MagicMock()
    mock_get.text = "<html><body>Hello World</body></html>"
    mock_get.raise_for_status = MagicMock()
    
    with patch('requests.head', return_value=mock_head), \
         patch('requests.get', return_value=mock_get), \
         patch.object(rag_manager.vector_store, 'add_texts') as mock_add:
        
        rag_manager.add_url("http://example.com")
        
        mock_add.assert_called_once()
        args, kwargs = mock_add.call_args
        assert "Hello World" in kwargs['texts'][0]

def test_query_success(rag_manager):
    mock_doc = MagicMock()
    mock_doc.page_content = "Relevant content"
    rag_manager.vector_store.similarity_search.return_value = [mock_doc]
    
    results = rag_manager.query("some query")
    
    assert results == ["Relevant content"]
    rag_manager.vector_store.similarity_search.assert_called_once_with("some query", k=5)

def test_rag_manager_initialize_missing_config():
    # Test initialization without embedding model
    manager = RAGManager({}, name="test_kb")
    manager.initialize()
    assert manager.embeddings is None
    assert manager.vector_store is None

def test_rag_manager_initialize_exception(mocker, mock_config):
    # Test initialization exception (e.g., Chroma init fail)
    mocker.patch('modules.rag_manager.OllamaEmbeddings')
    mocker.patch('modules.rag_manager.Chroma', side_effect=Exception("DB Error"))
    manager = RAGManager(mock_config, name="test_kb")
    manager.initialize()
    assert manager.vector_store is None

def test_add_file_exception(rag_manager):
    with patch("modules.rag_manager.TextLoader", side_effect=Exception("Load Error")):
        # Should catch exception and log error, not crash
        rag_manager.add_file("test.txt")

def test_add_directory_exception(rag_manager):
    with patch("os.walk", side_effect=Exception("Walk Error")):
        rag_manager.add_directory("/root")

def test_add_url_recursion_and_filtering(rag_manager, mocker):
    # Mock requests
    mock_response_html = MagicMock()
    mock_response_html.headers = {'Content-Type': 'text/html'}
    mock_response_html.text = '<html><a href="/page2">Link</a></html>'
    mock_response_html.raise_for_status = MagicMock()

    mock_response_page2 = MagicMock()
    mock_response_page2.headers = {'Content-Type': 'text/html'}
    mock_response_page2.text = '<html>Content Page 2</html>'
    
    mock_response_image = MagicMock()
    mock_response_image.headers = {'Content-Type': 'image/png'}

    def side_effect_head(url, **kwargs):
        if "image" in url: return mock_response_image
        return mock_response_html # Default to HTML for HEAD check

    def side_effect_get(url, **kwargs):
        if url.endswith("/page2"): return mock_response_page2
        return mock_response_html

    mocker.patch('requests.head', side_effect=side_effect_head)
    mocker.patch('requests.get', side_effect=side_effect_get)
    
    mock_add_texts = mocker.patch.object(rag_manager.vector_store, 'add_texts')

    # Add URL with recursion depth 2
    rag_manager.add_url("http://example.com", recursive=True, depth=2)

    # Should have processed example.com and example.com/page2
    assert mock_add_texts.call_count >= 2
    
    # Check that image was skipped (if we had one in the list, but our mock logic is simple)
    # Let's test the filtering explicitly
    mock_add_texts.reset_mock()
    rag_manager.add_url("http://example.com/image.png")
    mock_add_texts.assert_not_called()

def test_query_exception(rag_manager):
    rag_manager.vector_store.similarity_search.side_effect = Exception("Search Fail")
    results = rag_manager.query("query")
    assert results == []
