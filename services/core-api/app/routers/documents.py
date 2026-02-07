import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Document, DocumentType, User
from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    declaration_id: Optional[uuid.UUID] = None,
    item_id: Optional[uuid.UUID] = None,
    doc_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents with filters."""
    query = select(Document)
    conditions = []
    
    if declaration_id:
        conditions.append(Document.declaration_id == declaration_id)
    
    if item_id:
        conditions.append(Document.item_id == item_id)
    
    if doc_type:
        try:
            doc_type_enum = DocumentType(doc_type)
            conditions.append(Document.doc_type == doc_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid doc_type: {doc_type}",
            )
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(Document.created_at.desc())
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return [DocumentResponse.model_validate(doc) for doc in documents]


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create document metadata record."""
    # Validate doc_type
    try:
        doc_type_enum = DocumentType(data.doc_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid doc_type: {data.doc_type}",
        )
    
    document = Document(
        declaration_id=data.declaration_id,
        item_id=data.item_id,
        doc_type=doc_type_enum,
        file_key=data.file_key,
        original_filename=data.original_filename,
        mime_type=data.mime_type,
        file_size=data.file_size,
        issued_at=data.issued_at,
        issuer=data.issuer,
        doc_number=data.doc_number,
        linked_fields=data.linked_fields,
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    logger.info(
        "document_created",
        document_id=str(document.id),
        doc_type=data.doc_type,
        declaration_id=str(data.declaration_id) if data.declaration_id else None,
        user_id=str(current_user.id),
    )
    
    return DocumentResponse.model_validate(document)


@router.get("/{id}", response_model=DocumentResponse)
async def get_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get document by id."""
    result = await db.execute(select(Document).where(Document.id == id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return DocumentResponse.model_validate(document)


@router.put("/{id}", response_model=DocumentResponse)
async def update_document(
    id: uuid.UUID,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update document metadata."""
    result = await db.execute(select(Document).where(Document.id == id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    
    if "doc_type" in update_data:
        try:
            update_data["doc_type"] = DocumentType(update_data["doc_type"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid doc_type: {update_data['doc_type']}",
            )
    
    for field, value in update_data.items():
        setattr(document, field, value)
    
    await db.commit()
    await db.refresh(document)
    
    logger.info(
        "document_updated",
        document_id=str(id),
        user_id=str(current_user.id),
    )
    
    return DocumentResponse.model_validate(document)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete document."""
    result = await db.execute(select(Document).where(Document.id == id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    await db.delete(document)
    await db.commit()
    
    logger.info(
        "document_deleted",
        document_id=str(id),
        user_id=str(current_user.id),
    )
