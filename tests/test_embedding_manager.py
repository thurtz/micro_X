import pytest
import numpy as np
import json
from unittest.mock import MagicMock, patch, mock_open

from modules.embedding_manager import EmbeddingManager

# Sample embedding vector for mocking
SAMPLE_EMBEDDING = [0.1] * 1024

# Mock intents data that would be in the JSON file
MOCK_INTENTS = {
    "show_help": ["help", "show commands"],
    "exit_shell": ["exit", "quit"]
}

@pytest.fixture
def mock_config():
    """Fixture to create a mock config dictionary."""
    return {
        'intent_classification': {
            'embedding_model': 'test-embed-model',
            'intents_file_path': 'config/intents.json'
        }
    }

@pytest.fixture
def mock_ollama_client():
    """Fixture to create a mock Ollama client."""
    mock_client = MagicMock()
    mock_client.embeddings.return_value = {'embedding': SAMPLE_EMBEDDING}
    return mock_client

@pytest.fixture
def embedding_manager(mock_config, mock_ollama_client):
    """Fixture to create an EmbeddingManager with a mocked client and config."""
    # Mock the file system read for intents.json
    m = mock_open(read_data=json.dumps(MOCK_INTENTS))
    with patch('builtins.open', m):
        with patch('modules.embedding_manager.ollama.Client', return_value=mock_ollama_client):
            manager = EmbeddingManager(config=mock_config)
            manager.initialize()
            return manager

def test_initialization_success(embedding_manager, mock_ollama_client, mock_config):
    """
    Tests if the EmbeddingManager initializes correctly, loads intents, and generates embeddings.
    """
    assert embedding_manager.client is not None
    assert embedding_manager.embedding_model == mock_config['intent_classification']['embedding_model']
    assert len(embedding_manager.intents) == len(MOCK_INTENTS)
    assert len(embedding_manager.intent_embeddings) == len(MOCK_INTENTS)
    assert mock_ollama_client.embeddings.call_count > 0
    assert np.allclose(embedding_manager.intent_embeddings['exit_shell'], SAMPLE_EMBEDDING)

def test_initialization_no_intents_file(mock_config):
    """
    Tests that initialization fails gracefully if the intents file is not found.
    """
    with patch('builtins.open', side_effect=FileNotFoundError):
        manager = EmbeddingManager(config=mock_config)
        manager.initialize()
        assert not manager.intents
        assert not manager.intent_embeddings

def test_initialization_failure(mock_config):
    """
    Tests that the manager handles an exception during Ollama client initialization.
    """
    m = mock_open(read_data=json.dumps(MOCK_INTENTS))
    with patch('builtins.open', m):
        with patch('modules.embedding_manager.ollama.Client', side_effect=Exception("Connection failed")):
            manager = EmbeddingManager(config=mock_config)
            manager.initialize()
            assert manager.client is None
            assert len(manager.intent_embeddings) == 0

def test_classify_intent_success(embedding_manager):
    """
    Tests successful intent classification with a high similarity score.
    """
    user_input = "I want to quit now"
    input_embedding = np.array(SAMPLE_EMBEDDING) * 0.98  # Slightly different
    embedding_manager.client.embeddings.return_value = {'embedding': input_embedding.tolist()}

    intent, score = embedding_manager.classify_intent(user_input)

    assert intent in MOCK_INTENTS
    assert score > 0.95

def test_classify_intent_no_client(mock_config):
    """
    Tests that classification returns (None, 0.0) if the client is not available.
    """
    manager = EmbeddingManager(config=mock_config)
    manager.client = None # Ensure client is None
    intent, score = manager.classify_intent("any input")
    assert intent is None
    assert score == 0.0

def test_classify_intent_low_similarity(embedding_manager):
    """
    Test classification where similarity is low.
    """
    # Create an orthogonal vector (dot product 0)
    input_embedding = [0.0] * 1024
    # Just to be safe, make it slightly different
    input_embedding[0] = 100.0 # High magnitude, orthogonal to small values? 
    # If sample is [0.1, ...], dot([0.1,...], [100, 0...]) -> 10.0
    # Norms: sqrt(10.24) ~ 3.2 vs 100. 
    # Cosine = 10 / (3.2 * 100) = 0.03
    
    embedding_manager.client.embeddings.return_value = {'embedding': input_embedding}
    
    intent, score = embedding_manager.classify_intent("completely unrelated")
    # Score should be very low
    assert score < 0.1

def test_classify_intent_exception(embedding_manager):
    """Test exception handling during classification."""
    embedding_manager.client.embeddings.side_effect = Exception("API Error")
    intent, score = embedding_manager.classify_intent("trigger error")
    assert intent is None
    assert score == 0.0