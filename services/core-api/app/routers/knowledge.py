"""
API для базы знаний: статьи по классификации и чек-листы.
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from datetime import datetime
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.knowledge import KnowledgeArticle, Checklist

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# --- Schemas ---

class ArticleCreate(BaseModel):
    title: str
    content: str = ""
    category: str = "general"
    tags: list[str] = []
    hs_codes: list[str] = []
    is_published: bool = False

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    hs_codes: Optional[list[str]] = None
    is_published: Optional[bool] = None

class ArticleResponse(BaseModel):
    id: UUID
    title: str
    content: str
    category: str
    tags: list
    hs_codes: list
    is_published: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class ChecklistCreate(BaseModel):
    name: str
    description: str = ""
    declaration_type: str = "IM40"
    items: list[dict] = []
    is_active: bool = True

class ChecklistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    declaration_type: Optional[str] = None
    items: Optional[list[dict]] = None
    is_active: Optional[bool] = None

class ChecklistResponse(BaseModel):
    id: UUID
    name: str
    description: str
    declaration_type: str
    items: list
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Articles CRUD ---

@router.get("/articles", response_model=list[ArticleResponse])
async def list_articles(
    q: str = "",
    category: str = "",
    published_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeArticle).order_by(KnowledgeArticle.updated_at.desc())
    if q:
        query = query.where(or_(
            KnowledgeArticle.title.ilike(f"%{q}%"),
            KnowledgeArticle.content.ilike(f"%{q}%"),
        ))
    if category:
        query = query.where(KnowledgeArticle.category == category)
    if published_only:
        query = query.where(KnowledgeArticle.is_published == True)
    result = await db.execute(query.limit(100))
    return result.scalars().all()


@router.post("/articles", response_model=ArticleResponse, status_code=201)
async def create_article(
    data: ArticleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    article = KnowledgeArticle(
        title=data.title, content=data.content, category=data.category,
        tags=data.tags, hs_codes=data.hs_codes, is_published=data.is_published,
        created_by=current_user.id,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    logger.info("knowledge_article_created", id=str(article.id), title=data.title[:50])
    return article


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeArticle).where(KnowledgeArticle.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    return article


@router.put("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: UUID,
    data: ArticleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeArticle).where(KnowledgeArticle.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(article, field, value)
    article.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(article)
    return article


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeArticle).where(KnowledgeArticle.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    await db.delete(article)
    await db.commit()
    return {"status": "deleted"}


# --- Checklists CRUD ---

@router.get("/checklists", response_model=list[ChecklistResponse])
async def list_checklists(
    declaration_type: str = "",
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Checklist).order_by(Checklist.name)
    if declaration_type:
        query = query.where(Checklist.declaration_type == declaration_type)
    if active_only:
        query = query.where(Checklist.is_active == True)
    result = await db.execute(query.limit(50))
    return result.scalars().all()


@router.post("/checklists", response_model=ChecklistResponse, status_code=201)
async def create_checklist(
    data: ChecklistCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = Checklist(
        name=data.name, description=data.description,
        declaration_type=data.declaration_type, items=data.items,
        is_active=data.is_active, created_by=current_user.id,
    )
    db.add(cl)
    await db.commit()
    await db.refresh(cl)
    return cl


@router.put("/checklists/{checklist_id}", response_model=ChecklistResponse)
async def update_checklist(
    checklist_id: UUID,
    data: ChecklistUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Checklist).where(Checklist.id == checklist_id))
    cl = result.scalar_one_or_none()
    if not cl:
        raise HTTPException(404, "Checklist not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cl, field, value)
    cl.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(cl)
    return cl


@router.delete("/checklists/{checklist_id}")
async def delete_checklist(
    checklist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Checklist).where(Checklist.id == checklist_id))
    cl = result.scalar_one_or_none()
    if not cl:
        raise HTTPException(404, "Checklist not found")
    await db.delete(cl)
    await db.commit()
    return {"status": "deleted"}
