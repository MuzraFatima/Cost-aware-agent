from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from backend.app.db.session import get_db
from backend.app.services.knowledge_base import KnowledgeBaseService

router = APIRouter()

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Query string to search in vector index")
    top_k: Optional[int] = Field(3, ge=1, le=10, description="Max number of chunks to return")
    min_similarity: Optional[float] = Field(0.15, ge=0.0, le=1.0, description="Minimum similarity threshold")

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Uploads a document (PDF, TXT, MD), parses content, extracts chunks,
    generates vector embeddings, and stores in SQLite knowledge base.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename missing")
        
    file_ext = file.filename.lower().split(".")[-1] if "." in file.filename else ""
    allowed_exts = {"txt", "md", "pdf", "json", "csv"}
    if file_ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '.{file_ext}'. Allowed: {sorted(allowed_exts)}"
        )
        
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
            
        doc_info = KnowledgeBaseService.ingest_document(
            filename=file.filename,
            content=content,
            file_type=file.content_type or "text/plain",
            db=db
        )
        
        return {
            "status": "success",
            "message": f"Successfully ingested '{file.filename}' into knowledge base.",
            "document": doc_info
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest document: {str(e)}"
        )

@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    """
    Returns list of all documents currently indexed in the knowledge base.
    """
    try:
        docs = KnowledgeBaseService.list_documents(db)
        return {
            "status": "success",
            "total_documents": len(docs),
            "documents": docs
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """
    Deletes document and all associated chunks from the knowledge base.
    """
    success = KnowledgeBaseService.delete_document(doc_id, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found"
        )
    return {
        "status": "success",
        "message": f"Document '{doc_id}' successfully removed from knowledge base."
    }

@router.post("/search")
def search_vector_index(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Performs direct vector similarity search on knowledge base chunks.
    """
    results = KnowledgeBaseService.search_chunks(
        query=request.query,
        db=db,
        top_k=request.top_k or 3,
        min_similarity=request.min_similarity or 0.15
    )
    return {
        "status": "success",
        "query": request.query,
        "matches_count": len(results),
        "results": results
    }
