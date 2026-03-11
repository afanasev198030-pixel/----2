import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, delete, update
from sqlalchemy.orm import selectinload
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import (
    Declaration,
    DeclarationStatus,
    DeclarationItem,
    DeclarationLog,
    DeclarationStatusHistory,
    Company,
    Classifier,
    Document,
    User,
)
from app.models.hs_code_history import HsCodeHistory
from app.models.parse_issue import ParseIssue
from app.schemas import (
    DeclarationCreate,
    DeclarationUpdate,
    DeclarationResponse,
    DeclarationListResponse,
    PaginatedResponse,
)
from app.middleware.company_filter import get_accessible_company_ids
from app.utils.declaration_helpers import (
    merge_company_inn_kpp as _merge_company_inn_kpp,
    post_address_fallback as _post_address_fallback,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/declarations", tags=["declarations"])

PROTECTED_SPARSE_UPDATE_FIELDS = {
    "currency_code",
    "total_invoice_value",
    "exchange_rate",
    "country_dispatch_code",
    "country_origin_name",
    "country_destination_code",
    "incoterms_code",
    "delivery_place",
    "transport_type_border",
    "transport_type_inland",
    "customs_office_code",
    "goods_location",
    "total_gross_weight",
    "total_net_weight",
    "total_packages_count",
    "total_items_count",
    "forms_count",
    "total_customs_value",
    "trading_country_code",
    "sender_counterparty_id",
    "receiver_counterparty_id",
    "declarant_counterparty_id",
    "financial_counterparty_id",
    "container_info",
    "deal_nature_code",
}
def _has_meaningful_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, set, tuple)):
        return bool(value)
    return True


def _strip_suspicious_sparse_update(
    update_data: dict,
    declaration: Declaration,
) -> list[str]:
    cleared_fields: list[str] = []
    filled_fields = 0

    for field in PROTECTED_SPARSE_UPDATE_FIELDS:
        if field not in update_data:
            continue
        incoming_value = update_data.get(field)
        current_value = getattr(declaration, field, None)
        if _has_meaningful_value(incoming_value):
            filled_fields += 1
            continue
        if _has_meaningful_value(current_value):
            cleared_fields.append(field)

    if len(cleared_fields) >= 6 and filled_fields <= 2:
        for field in cleared_fields:
            update_data.pop(field, None)
        return cleared_fields

    return []


@router.get("/", response_model=PaginatedResponse)
async def list_declarations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    filter_status: Optional[str] = Query(None, alias="status"),
    type_code: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    client_id: Optional[uuid.UUID] = Query(None, description="Filter by client company ID (for brokers)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List declarations with pagination and filters."""
    # Build query
    query = select(Declaration)
    count_query = select(func.count()).select_from(Declaration)
    
    # Apply filters
    conditions = []
    
    if filter_status:
        try:
            status_enum = DeclarationStatus(filter_status)
            conditions.append(Declaration.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {filter_status}",
            )
    
    if type_code:
        conditions.append(Declaration.type_code == type_code)
    
    if date_from:
        conditions.append(Declaration.created_at >= date_from)
    
    if date_to:
        conditions.append(Declaration.created_at <= date_to)
    
    # Multi-company data isolation: filter by accessible companies
    accessible = await get_accessible_company_ids(current_user, db)
    if not accessible:
        return PaginatedResponse(
            items=[],
            total=0,
            page=page,
            per_page=per_page,
            pages=0,
        )
    conditions.append(Declaration.company_id.in_(accessible))

    # Optional filter by specific client company
    if client_id is not None:
        if client_id not in accessible:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to the specified client company",
            )
        conditions.append(Declaration.company_id == client_id)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(Declaration.created_at.desc()).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    declarations = result.scalars().all()
    
    # Calculate pages
    pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    return PaginatedResponse(
        items=[DeclarationListResponse.model_validate(d) for d in declarations],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post("/", response_model=DeclarationResponse, status_code=status.HTTP_201_CREATED)
async def create_declaration(
    data: DeclarationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new draft declaration."""
    # Validate company access
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with a company",
        )
    if data.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create declaration for different company",
        )
    
    # Create declaration
    declaration = Declaration(
        type_code=data.type_code,
        company_id=data.company_id,
        status=DeclarationStatus.DRAFT,
        created_by=current_user.id,
        number_internal=data.number_internal,
        sender_counterparty_id=data.sender_counterparty_id,
        receiver_counterparty_id=data.receiver_counterparty_id,
        financial_counterparty_id=data.financial_counterparty_id,
        declarant_counterparty_id=data.declarant_counterparty_id,
        country_dispatch_code=data.country_dispatch_code,
        special_ref_code=data.special_ref_code,
        country_origin_name=data.country_origin_name,
        country_destination_code=data.country_destination_code,
        transport_at_border=data.transport_at_border,
        container_info=data.container_info,
        incoterms_code=data.incoterms_code,
        transport_on_border=data.transport_on_border,
        currency_code=data.currency_code,
        total_invoice_value=data.total_invoice_value,
        exchange_rate=data.exchange_rate,
        deal_nature_code=data.deal_nature_code,
        deal_specifics_code=data.deal_specifics_code,
        transport_type_border=data.transport_type_border,
        transport_type_inland=data.transport_type_inland,
        loading_place=data.loading_place,
        financial_info=data.financial_info,
        total_customs_value=data.total_customs_value,
        total_gross_weight=data.total_gross_weight,
        total_net_weight=data.total_net_weight,
        total_items_count=data.total_items_count,
        total_packages_count=data.total_packages_count,
        forms_count=data.forms_count,
        specifications_count=data.specifications_count,
        customs_office_code=data.customs_office_code,
        warehouse_name=data.warehouse_name,
        place_and_date=data.place_and_date,
    )
    
    db.add(declaration)
    await db.commit()
    
    # Log action
    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=current_user.id,
        action="create",
        new_value={"status": "draft", "type_code": data.type_code},
    )
    db.add(log_entry)
    status_history_entry = DeclarationStatusHistory(
        declaration_id=declaration.id,
        status_code=DeclarationStatus.DRAFT.value,
        status_text="Декларация создана",
        source="system",
    )
    db.add(status_history_entry)

    # Audit log
    from app.services.audit import log_action
    await log_action(db, current_user.id, "create_declaration",
        resource_type="declaration", resource_id=str(declaration.id),
        details={"type_code": data.type_code}, request=request)
    await db.commit()
    
    # Re-fetch with relationships
    result = await db.execute(
        select(Declaration)
        .options(selectinload(Declaration.items))
        .where(Declaration.id == declaration.id)
    )
    declaration = result.scalar_one()
    
    logger.info(
        "declaration_created",
        declaration_id=str(declaration.id),
        user_id=str(current_user.id),
        type_code=data.type_code,
    )
    
    return DeclarationResponse.model_validate(declaration)


@router.get("/{id}", response_model=DeclarationResponse)
async def get_declaration(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single declaration with items."""
    result = await db.execute(
        select(Declaration)
        .options(selectinload(Declaration.items))
        .where(Declaration.id == id)
    )
    declaration = result.scalar_one_or_none()
    
    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found",
        )
    
    # Check company access
    if current_user.company_id and declaration.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with a company",
        )
    
    return DeclarationResponse.model_validate(declaration)


@router.put("/{id}", response_model=DeclarationResponse)
async def update_declaration(
    id: uuid.UUID,
    data: DeclarationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update declaration fields. Only allowed if status is draft or checking_lvl1."""
    result = await db.execute(
        select(Declaration).where(Declaration.id == id)
    )
    declaration = result.scalar_one_or_none()
    
    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found",
        )
    
    # Check company access
    if current_user.company_id and declaration.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with a company",
        )
    
    # Check status
    if declaration.status not in (DeclarationStatus.DRAFT, DeclarationStatus.CHECKING_LVL1):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update declaration with status: {declaration.status}",
        )
    
    # Update fields, track what actually changed
    update_data = data.model_dump(exclude_unset=True)
    cleared_protected_fields = _strip_suspicious_sparse_update(update_data, declaration)
    if cleared_protected_fields:
        logger.warning(
            "suspicious_sparse_update_blocked",
            declaration_id=str(id),
            user_id=str(current_user.id),
            blocked_fields=cleared_protected_fields,
        )

    changed_fields = {}
    for field, value in update_data.items():
        old_val = getattr(declaration, field, None)
        # Compare stringified values to handle Decimal/UUID
        if str(old_val) != str(value) and not (old_val is None and value is None):
            changed_fields[field] = {"old": str(old_val) if old_val is not None else None, "new": str(value) if value is not None else None}
        setattr(declaration, field, value)

    # Auto-fill/normalize declarant INN/KPP from company.
    if current_user.company_id:
        company = await db.get(Company, current_user.company_id)
        new_inn_kpp = _merge_company_inn_kpp(company, declaration.declarant_inn_kpp)
        if new_inn_kpp and str(declaration.declarant_inn_kpp or "") != str(new_inn_kpp):
            old_val = declaration.declarant_inn_kpp
            declaration.declarant_inn_kpp = new_inn_kpp
            changed_fields["declarant_inn_kpp"] = {
                "old": str(old_val) if old_val is not None else None,
                "new": new_inn_kpp,
            }

    # Auto-fill goods location by customs post code if empty
    office_code = (declaration.customs_office_code or declaration.entry_customs_code or "")[:8] or None
    if office_code and (not declaration.goods_location or not declaration.goods_location.strip()):
        post_result = await db.execute(
            select(Classifier).where(
                Classifier.classifier_type == "customs_post",
                Classifier.code == office_code,
                Classifier.is_active == True,
            )
        )
        post = post_result.scalar_one_or_none()
        if post and post.meta and post.meta.get("address"):
            old_val = declaration.goods_location
            declaration.goods_location = post.meta["address"]
            if str(old_val) != str(declaration.goods_location):
                changed_fields["goods_location"] = {
                    "old": str(old_val) if old_val is not None else None,
                    "new": str(declaration.goods_location),
                }
            logger.info("goods_location_autofilled", declaration_id=str(id), code=office_code)
        else:
            fallback_addr = _post_address_fallback(office_code)
            if fallback_addr:
                old_val = declaration.goods_location
                declaration.goods_location = fallback_addr
                if str(old_val) != str(declaration.goods_location):
                    changed_fields["goods_location"] = {
                        "old": str(old_val) if old_val is not None else None,
                        "new": str(declaration.goods_location),
                    }
                logger.info("goods_location_fallback_autofilled", declaration_id=str(id), code=office_code)
            else:
                logger.warning("goods_location_post_not_found", declaration_id=str(id), code=office_code)
    
    declaration.updated_at = datetime.utcnow()
    
    # Only log if something actually changed
    if changed_fields:
        import json
        log_entry = DeclarationLog(
            declaration_id=declaration.id,
            user_id=current_user.id,
            action="update",
            old_value={k: v["old"] for k, v in changed_fields.items()},
            new_value={k: v["new"] for k, v in changed_fields.items()},
        )
        db.add(log_entry)

        from app.services.audit import log_action
        await log_action(db, current_user.id, "update_declaration",
            resource_type="declaration", resource_id=str(id),
            details={"changed": list(changed_fields.keys())}, request=request)
    await db.commit()
    
    # Re-fetch with relationships
    result = await db.execute(
        select(Declaration)
        .options(selectinload(Declaration.items))
        .where(Declaration.id == id)
    )
    declaration = result.scalar_one()
    
    logger.info(
        "declaration_updated",
        declaration_id=str(declaration.id),
        user_id=str(current_user.id),
    )
    
    return DeclarationResponse.model_validate(declaration)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_declaration(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete declaration. Only allowed if status is draft."""
    result = await db.execute(
        select(Declaration).where(Declaration.id == id)
    )
    declaration = result.scalar_one_or_none()
    
    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found",
        )
    
    # Check company access
    if current_user.company_id and declaration.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with a company",
        )
    
    # Check status
    if declaration.status != DeclarationStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete declaration with status: {declaration.status}",
        )

    item_ids_result = await db.execute(
        select(DeclarationItem.id).where(DeclarationItem.declaration_id == id)
    )
    item_ids = list(item_ids_result.scalars().all())

    doc_filters = [Document.declaration_id == id]
    if item_ids:
        doc_filters.append(Document.item_id.in_(item_ids))
    docs_deleted = await db.execute(
        delete(Document).where(or_(*doc_filters))
    )
    parse_issues_deleted = await db.execute(
        delete(ParseIssue).where(ParseIssue.declaration_id == id)
    )

    hs_history_filter = HsCodeHistory.declaration_id == id
    if item_ids:
        hs_history_filter = or_(hs_history_filter, HsCodeHistory.item_id.in_(item_ids))
    hs_history_updated = await db.execute(
        update(HsCodeHistory)
        .where(hs_history_filter)
        .values(declaration_id=None, item_id=None)
    )

    await db.delete(declaration)
    await db.commit()
    
    logger.info(
        "declaration_deleted",
        declaration_id=str(id),
        user_id=str(current_user.id),
        docs_deleted=docs_deleted.rowcount or 0,
        parse_issues_deleted=parse_issues_deleted.rowcount or 0,
        hs_history_updated=hs_history_updated.rowcount or 0,
    )


@router.post("/{id}/duplicate", response_model=DeclarationResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_declaration(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Duplicate a declaration as a new draft."""
    result = await db.execute(
        select(Declaration)
        .options(selectinload(Declaration.items))
        .where(Declaration.id == id)
    )
    original = result.scalar_one_or_none()
    
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found",
        )
    
    # Check company access
    if current_user.company_id and original.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with a company",
        )
    
    # Create new declaration (copy all fields except id, status, timestamps)
    new_declaration = Declaration(
        type_code=original.type_code,
        company_id=original.company_id,
        status=DeclarationStatus.DRAFT,
        created_by=current_user.id,
        number_internal=original.number_internal,
        sender_counterparty_id=original.sender_counterparty_id,
        receiver_counterparty_id=original.receiver_counterparty_id,
        financial_counterparty_id=original.financial_counterparty_id,
        declarant_counterparty_id=original.declarant_counterparty_id,
        country_dispatch_code=original.country_dispatch_code,
        special_ref_code=original.special_ref_code,
        country_origin_name=original.country_origin_name,
        country_destination_code=original.country_destination_code,
        transport_at_border=original.transport_at_border,
        container_info=original.container_info,
        incoterms_code=original.incoterms_code,
        transport_on_border=original.transport_on_border,
        currency_code=original.currency_code,
        total_invoice_value=original.total_invoice_value,
        exchange_rate=original.exchange_rate,
        deal_nature_code=original.deal_nature_code,
        deal_specifics_code=original.deal_specifics_code,
        transport_type_border=original.transport_type_border,
        transport_type_inland=original.transport_type_inland,
        loading_place=original.loading_place,
        financial_info=original.financial_info,
        total_customs_value=original.total_customs_value,
        total_gross_weight=original.total_gross_weight,
        total_net_weight=original.total_net_weight,
        total_items_count=original.total_items_count,
        total_packages_count=original.total_packages_count,
        forms_count=original.forms_count,
        specifications_count=original.specifications_count,
        customs_office_code=original.customs_office_code,
        warehouse_name=original.warehouse_name,
        place_and_date=original.place_and_date,
        payment_deferral=original.payment_deferral,
        warehouse_requisites=original.warehouse_requisites,
        transit_offices=original.transit_offices,
        destination_office_code=original.destination_office_code,
        spot_required=original.spot_required,
        spot_status=original.spot_status,
        spot_qr_file_key=original.spot_qr_file_key,
        spot_amount=original.spot_amount,
        invoice_number=original.invoice_number,
        invoice_date=original.invoice_date,
        contract_number=original.contract_number,
        contract_date=original.contract_date,
    )
    
    db.add(new_declaration)
    await db.flush()  # Flush to get the ID
    
    # Copy items
    for item in original.items:
        new_item = DeclarationItem(
            declaration_id=new_declaration.id,
            item_no=item.item_no,
            description=item.description,
            package_count=item.package_count,
            package_type=item.package_type,
            commercial_name=item.commercial_name,
            hs_code=item.hs_code,
            country_origin_code=item.country_origin_code,
            country_origin_pref_code=item.country_origin_pref_code,
            gross_weight=item.gross_weight,
            preference_code=item.preference_code,
            procedure_code=item.procedure_code,
            net_weight=item.net_weight,
            quota_info=item.quota_info,
            prev_doc_ref=item.prev_doc_ref,
            additional_unit=item.additional_unit,
            additional_unit_qty=item.additional_unit_qty,
            unit_price=item.unit_price,
            mos_method_code=item.mos_method_code,
            customs_value_rub=item.customs_value_rub,
            statistical_value_usd=item.statistical_value_usd,
            documents_json=item.documents_json,
            hs_code_letters=item.hs_code_letters,
            hs_code_extra=item.hs_code_extra,
        )
        db.add(new_item)
    
    await db.commit()
    await db.refresh(new_declaration)
    
    # Log action
    log_entry = DeclarationLog(
        declaration_id=new_declaration.id,
        user_id=current_user.id,
        action="duplicate",
        new_value={"duplicated_from": str(id)},
    )
    db.add(log_entry)
    await db.commit()
    
    logger.info(
        "declaration_duplicated",
        original_id=str(id),
        new_id=str(new_declaration.id),
        user_id=str(current_user.id),
    )
    
    return DeclarationResponse.model_validate(new_declaration)


@router.get("/{id}/logs")
async def get_declaration_logs(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get declaration change logs."""
    result = await db.execute(
        select(DeclarationLog)
        .where(DeclarationLog.declaration_id == id)
        .order_by(DeclarationLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "user_id": str(log.user_id) if log.user_id else None,
        }
        for log in logs
    ]


@router.get("/{id}/status-history")
async def get_declaration_status_history(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get declaration status history for status timeline."""
    declaration_result = await db.execute(
        select(Declaration).where(Declaration.id == id)
    )
    declaration = declaration_result.scalar_one_or_none()

    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found",
        )

    if current_user.company_id and declaration.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with a company",
        )

    result = await db.execute(
        select(DeclarationStatusHistory)
        .where(DeclarationStatusHistory.declaration_id == id)
        .order_by(DeclarationStatusHistory.created_at.asc())
    )
    history = result.scalars().all()

    logger.info(
        "declaration_status_history_requested",
        declaration_id=str(id),
        user_id=str(current_user.id),
        history_count=len(history),
    )

    return [
        {
            "id": str(entry.id),
            "status_code": entry.status_code,
            "status_text": entry.status_text,
            "source": entry.source,
            "customs_post_code": entry.customs_post_code,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in history
    ]
