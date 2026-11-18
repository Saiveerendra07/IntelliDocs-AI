import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse, Response
from backend.app.schemas.document import DocumentOut, DocumentStatus, DocumentPageOut
from backend.app.schemas.common import PaginatedResponse
from backend.app.core.deps import get_current_user
from backend.app.core.config import settings

router = APIRouter(prefix="/documents", tags=["Documents"])

# Internal store for documents and pages before DB integration
_DOCS_STORE = {}
_PAGES_STORE = {}


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # Extension and MIME check
    valid_exts = {".pdf", ".docx", ".pptx", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in valid_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(valid_exts)}"
        )

    content = await file.read()
    file_size = len(content)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_MB} MB."
        )

    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Save to user storage
    user_storage_dir = os.path.join(settings.STORAGE_DIR, "uploads", str(current_user["id"]))
    os.makedirs(user_storage_dir, exist_ok=True)
    saved_filename = f"{doc_id}{ext}"
    saved_path = os.path.join(user_storage_dir, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(content)

    doc_record = {
        "id": doc_id,
        "user_id": current_user["id"],
        "original_filename": file.filename,
        "stored_path": saved_path,
        "mime_type": file.content_type or "application/octet-stream",
        "file_size": file_size,
        "page_count": 1,
        "language": "en",
        "is_scanned": False,
        "status": "ready",
        "error_message": None,
        "processing_progress": 1.0,
        "created_at": now,
        "updated_at": now,
    }
    _DOCS_STORE[doc_id] = doc_record

    # Seed an initial page
    page_record = {
        "id": uuid.uuid4(),
        "document_id": doc_id,
        "page_number": 1,
        "text": f"Extracted content for {file.filename}.\nAcademic document ready for NLP processing.",
        "ocr_applied": False,
        "tables_json": None,
    }
    _PAGES_STORE[doc_id] = [page_record]

    return DocumentOut(**doc_record)


@router.get("", response_model=PaginatedResponse[DocumentOut])
async def list_documents(
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    user_docs = [
        d for d in _DOCS_STORE.values()
        if str(d["user_id"]) == str(current_user["id"])
    ]

    if search:
        s = search.lower()
        user_docs = [d for d in user_docs if s in d["original_filename"].lower()]

    if status:
        user_docs = [d for d in user_docs if d["status"] == status]

    user_docs.sort(key=lambda x: x["created_at"], reverse=True)
    total = len(user_docs)
    start = (page - 1) * page_size
    items = user_docs[start : start + page_size]

    return PaginatedResponse(
        items=[DocumentOut(**d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=DocumentOut)
async def get_document(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    # Strictly return 404 for other users' resources to prevent enumeration
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentOut(**doc)


@router.get("/{id}/status", response_model=DocumentStatus)
async def get_document_status(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentStatus(
        id=doc["id"],
        status=doc["status"],
        processing_progress=doc["processing_progress"],
        error_message=doc["error_message"],
    )


@router.get("/{id}/pages", response_model=List[DocumentPageOut])
async def get_document_pages(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")
    pages = _PAGES_STORE.get(id, [])
    return [DocumentPageOut(**p) for p in pages]


@router.get("/{id}/download")
async def download_original(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")
    if not os.path.exists(doc["stored_path"]):
        raise HTTPException(status_code=404, detail="Stored file missing on disk.")
    return FileResponse(
        path=doc["stored_path"],
        filename=doc["original_filename"],
        media_type=doc["mime_type"],
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    doc = _DOCS_STORE.get(id)
    if not doc or str(doc["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Document not found.")

    if os.path.exists(doc["stored_path"]):
        try:
            os.remove(doc["stored_path"])
        except OSError:
            pass

    _DOCS_STORE.pop(id, None)
    _PAGES_STORE.pop(id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
