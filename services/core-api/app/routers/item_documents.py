"""CRUD for declaration item documents (графа 44)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User, DeclarationItem, DeclarationItemDocument
from app.schemas import ItemDocumentCreate, ItemDocumentUpdate, ItemDocumentResponse

logger = structlog.get_logger()
router = APIRouter(
    prefix="/api/v1/declarations/{decl_id}/items/{item_id}/item-documents",
    tags=["item-documents"],
)


async def _get_item(decl_id: uuid.UUID, item_id: uuid.UUID, db: AsyncSession) -> DeclarationItem:
    result = await db.execute(
        select(DeclarationItem).where(
            DeclarationItem.id == item_id,
            DeclarationItem.declaration_id == decl_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Declaration item not found")
    return item


@router.get("/", response_model=list[ItemDocumentResponse])
async def list_item_documents(
    decl_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_item(decl_id, item_id, db)
    result = await db.execute(
        select(DeclarationItemDocument)
        .where(DeclarationItemDocument.declaration_item_id == item_id)
        .order_by(DeclarationItemDocument.sort_order)
    )
    return result.scalars().all()


@router.post("/", response_model=ItemDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_item_document(
    decl_id: uuid.UUID,
    item_id: uuid.UUID,
    data: ItemDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_item(decl_id, item_id, db)
    doc = DeclarationItemDocument(
        declaration_item_id=item_id,
        **data.model_dump(),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.put("/{doc_id}", response_model=ItemDocumentResponse)
async def update_item_document(
    decl_id: uuid.UUID,
    item_id: uuid.UUID,
    doc_id: uuid.UUID,
    data: ItemDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_item(decl_id, item_id, db)
    result = await db.execute(
        select(DeclarationItemDocument).where(
            DeclarationItemDocument.id == doc_id,
            DeclarationItemDocument.declaration_item_id == item_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Item document not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(doc, key, val)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item_document(
    decl_id: uuid.UUID,
    item_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_item(decl_id, item_id, db)
    result = await db.execute(
        select(DeclarationItemDocument).where(
            DeclarationItemDocument.id == doc_id,
            DeclarationItemDocument.declaration_item_id == item_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Item document not found")
    await db.delete(doc)
    await db.commit()
