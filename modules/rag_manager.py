# modules/rag_manager.py
import logging
import os
from langchain_chroma import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    BSHTMLLoader,
    UnstructuredURLLoader,
)
from langchain_community.document_loaders.recursive_url_loader import RecursiveUrlLoader
from bs4 import BeautifulSoup as Soup
import requests
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".txt", ".md", ".py", ".json", ".rst"}

class RAGManager:
    def __init__(self, config: dict, name: str = "default"):
        self.config = config
        self.name = name
        self.vector_store = None
        self.embedding_model_name = None
        self.embeddings = None
        self.text_splitter = None

        # All paths are now relative to a name-specific directory
        base_path = os.path.join(os.getcwd(), "knowledge_bases", self.name)
        self._db_path = base_path
        self._cache_path = os.path.join(base_path, "cache")
        self._collection_name = f"microx_rag_{self.name}"

    def initialize(self):
        """Initializes the RAG manager, database, and collection."""
        logger.info("Initializing RAGManager...")
        try:
            # 1. Get embedding model from config
            self.embedding_model_name = self.config.get('intent_classification', {}).get('embedding_model')
            if not self.embedding_model_name:
                logger.error("Embedding model not specified in config. Cannot initialize RAGManager.")
                return
            self.embeddings = OllamaEmbeddings(model=self.embedding_model_name)

            # 2. Initialize Chroma vector store with LangChain wrapper
            self.vector_store = Chroma(
                collection_name=self._collection_name,
                embedding_function=self.embeddings,
                persist_directory=self._db_path,
            )

            # 3. Initialize text splitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
            )

            os.makedirs(self._cache_path, exist_ok=True)

            logger.info(f"RAGManager initialized successfully. DB path: '{self._db_path}', Collection: '{self._collection_name}'")

        except Exception as e:
            logger.error(f"Failed to initialize RAGManager: {e}", exc_info=True)

    def add_file(self, file_path: str):
        """Adds a single file to the knowledge base."""
        if not self.vector_store:
            logger.error("RAG vector store not initialized. Cannot add file.")
            return

        _, extension = os.path.splitext(file_path)
        if extension.lower() not in SUPPORTED_EXTENSIONS:
            logger.info(f"Skipping unsupported file type: {file_path}")
            return
        
        logger.info(f"Processing file: {file_path}")
        try:
            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith((".html", ".htm")):
                loader = BSHTMLLoader(file_path, bs_kwargs={'features': 'html.parser'})
            else: # Default to text loader for .txt, .md, .py, etc.
                loader = TextLoader(file_path, encoding="utf-8")
            
            documents = loader.load()
            chunks = self.text_splitter.split_documents(documents)
            
            self.vector_store.add_documents(chunks)
            logger.info(f"Successfully added {len(chunks)} chunks from {file_path} to the knowledge base.")

        except Exception as e:
            logger.error(f"Failed to add file {file_path}: {e}", exc_info=True)

    def add_directory(self, dir_path: str):
        """Recursively adds all supported files in a directory."""
        if not self.vector_store:
            logger.error("RAG vector store not initialized. Cannot add directory.")
            return

        logger.info(f"Processing directory: {dir_path}")
        # This is a simplified approach. A more robust solution would iterate
        # and use the specific loaders from add_file.
        try:
            # Find all files, then load them one by one
            for root, _, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    self.add_file(file_path) # Reuse the single file logic

            logger.info(f"Finished processing directory {dir_path}.")

        except Exception as e:
            logger.error(f"Failed to process directory {dir_path}: {e}", exc_info=True)


    def _url_to_filename(self, url: str) -> str:
        """Converts a URL to a safe filename for caching."""
        parsed_url = urlparse(url)
        # Combine netloc and path, replacing slashes
        filename = f"{parsed_url.netloc}{parsed_url.path}".replace('/', '_').replace('\\', '_')
        # Ensure it doesn't end with an underscore if it was a directory
        if filename.endswith('_'):
            filename += "index.html"
        if not os.path.splitext(filename)[1]:
            filename += ".html"
        return os.path.join(self._cache_path, filename)

    def add_url(self, url: str, recursive: bool = False, save_cache: bool = False, depth: int = 2):
        """Fetches a URL and adds its content to the knowledge base."""
        if not self.vector_store:
            logger.error("RAG vector store not initialized. Cannot add URL.")
            return

        urls_to_visit = {url}
        visited_urls = set()
        max_depth = depth if recursive else 1

        for depth in range(max_depth):
            if not urls_to_visit:
                break
            
            current_urls = list(urls_to_visit)
            urls_to_visit.clear()
            
            for current_url in current_urls:
                if current_url in visited_urls:
                    continue
                
                logger.info(f"Processing URL (Depth: {depth}): {current_url}")
                visited_urls.add(current_url)

                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
                    }

                    # First, send a HEAD request to check the content type
                    head_response = requests.head(current_url, timeout=5, allow_redirects=True, headers=headers)
                    head_response.raise_for_status()
                    content_type = head_response.headers.get('Content-Type', '')

                    if 'text/html' not in content_type:
                        logger.info(f"Skipping non-HTML URL: {current_url} (Content-Type: {content_type})")
                        continue

                    # If content type is valid, proceed with GET request
                    response = requests.get(current_url, timeout=10, headers=headers)
                    response.raise_for_status()
                    html_content = response.text

                    if save_cache:
                        cache_path = self._url_to_filename(current_url)
                        with open(cache_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        logger.info(f"Saved page to cache: {cache_path}")

                    soup = Soup(html_content, "html.parser")
                    text_content = soup.get_text(separator=' ', strip=True)

                    if text_content:
                        chunks = self.text_splitter.split_text(text_content)
                        self.vector_store.add_texts(texts=chunks, metadatas=[{'source': current_url}] * len(chunks))
                        logger.info(f"Added {len(chunks)} chunks from {current_url}.")

                    if recursive and depth < max_depth - 1:
                        for link in soup.find_all('a', href=True):
                            absolute_link = urljoin(current_url, link['href'])
                            if urlparse(absolute_link).scheme in ['http', 'https']:
                                urls_to_visit.add(absolute_link)

                except requests.RequestException as e:
                    logger.warning(f"Failed to download URL {current_url}: {e}")
                except Exception as e:
                    logger.error(f"Failed to process URL {current_url}: {e}", exc_info=True)


    def query(self, query_text: str, n_results: int = 5) -> list[str]:
        """
        Queries the knowledge base and returns the most relevant document chunks.
        """
        if not self.vector_store:
            logger.error("RAG vector store not initialized. Cannot query.")
            return []

        try:
            results = self.vector_store.similarity_search(query_text, k=n_results)
            # Extract the page content from the Document objects
            return [doc.page_content for doc in results]
        except Exception as e:
            logger.error(f"Failed to query the knowledge base: {e}", exc_info=True)
            return []

