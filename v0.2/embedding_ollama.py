"""
embedding_ollama.py — 使用 Ollama API 进行语义嵌入
"""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

class OllamaEmbedder:
    """使用 Ollama API 进行语义嵌入"""
    
    def __init__(self, model: str = "bge-m3", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
    
    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> list[list[float]]:
        """生成文本嵌入"""
        results = []
        
        for text in texts:
            try:
                data = json.dumps({
                    "model": self.model,
                    "prompt": text,
                    "options": {"temperature": 0}
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    f"{self.base_url}/api/embeddings",
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.load(resp)
                    embedding = result.get("embedding", [])
                
                if normalize_embeddings and embedding:
                    norm = sum(x**2 for x in embedding) ** 0.5
                    if norm > 0:
                        embedding = [x / norm for x in embedding]
                
                results.append(embedding)
                
            except Exception as e:
                logger.warning(f"嵌入生成失败: {e}")
                return []
        
        return results
