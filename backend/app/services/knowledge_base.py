import json
import math
import re
from collections import Counter
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.models import KnowledgeDocument, DocumentChunk

class KnowledgeBaseService:

    @staticmethod
    def parse_document(filename: str, content: bytes, file_type: str) -> str:
        """
        Parses document bytes into plain text for TXT, MD, and PDF files.
        """
        file_ext = filename.lower().split(".")[-1] if "." in filename else ""
        
        if file_ext == "pdf" or file_type == "application/pdf":
            try:
                import pypdf
                import io
                reader = pypdf.PdfReader(io.BytesIO(content))
                text_parts = [page.extract_text() for page in reader.pages if page.extract_text()]
                if text_parts:
                    return "\n\n".join(text_parts)
            except Exception:
                pass
            
            # Pure Python fallback for PDF stream text extraction
            try:
                raw_str = content.decode("latin1", errors="ignore")
                # Extract text within PDF text objects (BT ... ET)
                stream_texts = re.findall(r"BT\s*(.*?)\s*ET", raw_str, re.DOTALL)
                extracted = []
                for st in stream_texts:
                    # Find string literals inside parentheses ( ... ) TJ/Tj
                    strings = re.findall(r"\((.*?)\)", st)
                    if strings:
                        extracted.append(" ".join(strings))
                if extracted:
                    return "\n".join(extracted)
            except Exception:
                pass
            
            # Generic fallback decode
            return content.decode("utf-8", errors="ignore")
            
        else:
            # Plain text, Markdown, CSV, JSON
            return content.decode("utf-8", errors="ignore")

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Splits text into overlapping chunks of approx chunk_size characters.
        """
        text = text.strip()
        if not text:
            return []
            
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            if end < text_len:
                # Try to break at nearest sentence boundary or whitespace
                break_point = max(text.rfind(". ", start, end), text.rfind("\n", start, end), text.rfind(" ", start, end))
                if break_point > start + 100:
                    end = break_point + 1
                    
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                
            start = end - overlap if end < text_len else text_len
            
        return chunks

    @classmethod
    def compute_vector(cls, text: str) -> Dict[str, float]:
        """
        Computes L2-normalized TF-IDF term frequency vector for text.
        Filters out common structural stop words to prevent false similarity matches.
        """
        stop_words = {
            "what", "is", "the", "of", "a", "an", "and", "or", "to", "in", "on", "for",
            "by", "with", "this", "that", "it", "are", "be", "as", "at", "from", "how",
            "why", "which", "where", "who", "when", "do", "does", "did", "have", "has",
            "had", "can", "could", "would", "should", "will", "shall", "me", "my", "you",
            "your", "he", "she", "it", "we", "they", "them", "their", "our", "us"
        }
        words = [w.lower().strip(".,!?;:()[]\"'#*_`~") for w in re.split(r"\s+", text)]
        # Filter out stop words, numbers, and very short words
        words = [w for w in words if len(w) > 1 and not w.isdigit() and w not in stop_words]
        
        if not words:
            return {}
            
        counts = Counter(words)
        total = len(words)
        tf = {w: count / total for w, count in counts.items()}
        
        norm = math.sqrt(sum(v * v for v in tf.values()))
        if norm > 0:
            return {w: round(v / norm, 6) for w, v in tf.items()}
        return tf

    @classmethod
    def cosine_similarity(cls, v1: Dict[str, float], v2: Dict[str, float]) -> float:
        """
        Calculates cosine similarity dot product between two L2-normalized sparse vectors.
        """
        if not v1 or not v2:
            return 0.0
        
        # Determine smaller vector to iterate over
        if len(v1) > len(v2):
            v1, v2 = v2, v1
            
        dot = sum(v1[k] * v2[k] for k in v1 if k in v2)
        return float(dot)

    @classmethod
    def ingest_document(
        cls,
        filename: str,
        content: bytes,
        file_type: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Parses, chunks, embeds, and stores document in SQLite database.
        """
        parsed_text = cls.parse_document(filename, content, file_type)
        chunks = cls.chunk_text(parsed_text)
        
        doc = KnowledgeDocument(
            filename=filename,
            file_type=file_type or "text/plain",
            file_size=len(content),
            chunk_count=len(chunks)
        )
        db.add(doc)
        db.flush()
        
        for idx, chunk_str in enumerate(chunks):
            vector = cls.compute_vector(chunk_str)
            chunk_obj = DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                text=chunk_str,
                embedding_json=json.dumps(vector),
                metadata_json=json.dumps({"filename": filename, "chunk_index": idx})
            )
            db.add(chunk_obj)
            
        db.commit()
        db.refresh(doc)
        
        return {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "chunk_count": doc.chunk_count,
            "created_at": doc.created_at.isoformat()
        }

    @classmethod
    def search_chunks(
        cls,
        query: str,
        db: Optional[Session] = None,
        top_k: int = 3,
        min_similarity: float = 0.15
    ) -> List[Dict[str, Any]]:
        """
        Searches all document chunks in database for matches against query using vector similarity.
        """
        if not db:
            return []
            
        query_vec = cls.compute_vector(query)
        if not query_vec:
            return []
            
        try:
            chunks = db.execute(select(DocumentChunk)).scalars().all()
        except Exception:
            return []
            
        results = []
        for chunk in chunks:
            try:
                chunk_vec = json.loads(chunk.embedding_json)
            except Exception:
                continue
                
            score = cls.cosine_similarity(query_vec, chunk_vec)
            if score >= min_similarity:
                meta = json.loads(chunk.metadata_json) if chunk.metadata_json else {}
                doc_name = chunk.document.filename if chunk.document else meta.get("filename", "Document")
                results.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": doc_name,
                    "chunk_index": chunk.chunk_index,
                    "similarity_score": round(score, 4),
                    "text_snippet": chunk.text
                })
                
        # Sort by similarity score descending
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    @classmethod
    def list_documents(cls, db: Session) -> List[Dict[str, Any]]:
        """
        Returns list of all ingested knowledge base documents.
        """
        docs = db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())).scalars().all()
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "file_size": d.file_size,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat()
            }
            for d in docs
        ]

    @classmethod
    def delete_document(cls, doc_id: str, db: Session) -> bool:
        """
        Deletes document and all its chunks from the database.
        """
        doc = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)).scalars().first()
        if not doc:
            return False
            
        db.delete(doc)
        db.commit()
        return True
