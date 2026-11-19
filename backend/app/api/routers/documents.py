import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.app.schemas.document import DocumentOut, DocumentStatus, DocumentPageOut
from backend.app.schemas.common import PaginatedResponse
from backend.app.core.deps import get_current_user
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.db.models.document import Document, DocumentPage
from backend.app.documents.pipeline import DocumentPipeline
from backend.app.repositories.consistency import purge_document_cascade

router = APIRouter(prefix="/documents", tags=["Documents"])

# Cache dictionaries maintained for cross-router references and backward compatibility
_DOCS_STORE = {}
_PAGES_STORE = {}



@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_exts = {
        ".pdf", ".docx", ".doc", ".pptx", ".ppt",
        ".txt", ".md", ".markdown", ".csv",
        ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"
    }
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in valid_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(sorted(valid_exts))}"
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
    user_id = uuid.UUID(str(current_user["id"]))

    # Save to user storage
    user_storage_dir = os.path.join(settings.STORAGE_DIR, "uploads", str(user_id))
    os.makedirs(user_storage_dir, exist_ok=True)
    saved_filename = f"{doc_id}{ext}"
    saved_path = os.path.join(user_storage_dir, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(content)

    doc = Document(
        id=doc_id,
        user_id=user_id,
        original_filename=file.filename,
        stored_path=saved_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        page_count=1,
        language="en",
        is_scanned=False,
        status="uploaded",
        processing_progress=0.0,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Process document synchronously or via pipeline
    try:
        pipeline = DocumentPipeline(db)
        pipeline.process_file(
            document_id=doc.id,
            user_id=user_id,
            file_path=saved_path,
            original_filename=file.filename,
        )
        db.refresh(doc)
    except Exception as e:
        # Document status is set to failed in pipeline
        db.refresh(doc)

    # Sync cache store
    _DOCS_STORE[doc.id] = {
        "id": doc.id,
        "user_id": doc.user_id,
        "original_filename": doc.original_filename,
        "stored_path": doc.stored_path,
        "mime_type": doc.mime_type,
        "file_size": doc.file_size,
        "page_count": doc.page_count,
        "language": doc.language,
        "is_scanned": doc.is_scanned,
        "status": doc.status,
        "error_message": doc.error_message,
        "processing_progress": doc.processing_progress,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }
    pages = db.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id)).scalars().all()
    _PAGES_STORE[doc.id] = [
        {
            "id": p.id,
            "document_id": p.document_id,
            "page_number": p.page_number,
            "text": p.text,
            "ocr_applied": p.ocr_applied,
            "tables_json": p.tables_json,
        }
        for p in pages
    ]

    return DocumentOut.model_validate(doc)


@router.get("", response_model=PaginatedResponse[DocumentOut])
async def list_documents(
    search: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    stmt = select(Document).where(Document.user_id == user_id)

    if search:
        stmt = stmt.where(Document.original_filename.ilike(f"%{search}%"))

    if status_filter:
        stmt = stmt.where(Document.status == status_filter)

    stmt = stmt.order_by(desc(Document.created_at))

    all_docs = db.execute(stmt).scalars().all()
    total = len(all_docs)
    start = (page - 1) * page_size
    paged_docs = all_docs[start : start + page_size]

    return PaginatedResponse(
        items=[DocumentOut.model_validate(d) for d in paged_docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=DocumentOut)
async def get_document(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    doc = db.execute(
        select(Document).where(Document.id == id, Document.user_id == user_id)
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentOut.model_validate(doc)


@router.get("/{id}/status", response_model=DocumentStatus)
async def get_document_status(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    doc = db.execute(
        select(Document).where(Document.id == id, Document.user_id == user_id)
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    return DocumentStatus(
        id=doc.id,
        status=doc.status,
        processing_progress=doc.processing_progress,
        error_message=doc.error_message,
    )


@router.get("/{id}/pages", response_model=List[DocumentPageOut])
async def get_document_pages(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    doc = db.execute(
        select(Document).where(Document.id == id, Document.user_id == user_id)
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == id)
        .order_by(DocumentPage.page_number)
    ).scalars().all()

    return [DocumentPageOut.model_validate(p) for p in pages]


@router.get("/{id}/download")
async def download_original(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    doc = db.execute(
        select(Document).where(Document.id == id, Document.user_id == user_id)
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not os.path.exists(doc.stored_path):
        raise HTTPException(status_code=404, detail="Stored file missing on disk.")

    return FileResponse(
        path=doc.stored_path,
        filename=doc.original_filename,
        media_type=doc.mime_type,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = uuid.UUID(str(current_user["id"]))
    doc = db.execute(
        select(Document).where(Document.id == id, Document.user_id == user_id)
    ).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    purge_document_cascade(db, doc.id)
    _DOCS_STORE.pop(id, None)
    _PAGES_STORE.pop(id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
