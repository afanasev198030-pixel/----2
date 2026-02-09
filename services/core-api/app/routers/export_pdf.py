"""PDF экспорт декларации в формате ДТ."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Declaration, DeclarationItem, Counterparty, User

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/declarations", tags=["export"])


@router.get("/{declaration_id}/export-pdf")
async def export_pdf(
    declaration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт декларации в PDF формат ДТ."""
    result = await db.execute(
        select(Declaration).options(selectinload(Declaration.items)).where(Declaration.id == declaration_id)
    )
    decl = result.scalar_one_or_none()
    if not decl:
        raise HTTPException(status_code=404, detail="Declaration not found")

    # Load counterparties
    sender_name = "Не указан"
    receiver_name = "Не указан"
    if decl.sender_counterparty_id:
        r = await db.execute(select(Counterparty).where(Counterparty.id == decl.sender_counterparty_id))
        s = r.scalar_one_or_none()
        if s:
            sender_name = f"{s.name} [{s.country_code or ''}] {s.address or ''}"
    if decl.receiver_counterparty_id:
        r = await db.execute(select(Counterparty).where(Counterparty.id == decl.receiver_counterparty_id))
        s = r.scalar_one_or_none()
        if s:
            receiver_name = f"{s.name} [{s.country_code or ''}] {s.address or ''}"

    items = decl.items or []
    f = lambda v: v if v else ""
    num = lambda v, d=2: f"{float(v):,.{d}f}".replace(",", " ") if v else ""

    # Build HTML
    items_html = ""
    for item in items:
        items_html += f"""
        <tr class="section-header"><td colspan="8"><b>Товар № {item.item_no or 1}</b></td></tr>
        <tr>
            <td colspan="4"><b>31</b> {f(item.description or item.commercial_name)}<br><small>{num(item.additional_unit_qty,0)} {f(item.additional_unit) or 'шт'}</small></td>
            <td colspan="4"><b>33</b> Код: <b>{f(item.hs_code)}</b><br><b>34</b> Страна: {f(item.country_origin_code)}</td>
        </tr>
        <tr>
            <td colspan="2"><b>35</b> Брутто: {num(item.gross_weight,3)} кг</td>
            <td colspan="2"><b>38</b> Нетто: {num(item.net_weight,3)} кг</td>
            <td colspan="2"><b>42</b> Цена: {num(item.unit_price,4)}</td>
            <td colspan="2"><b>45</b> Стоимость: {num(item.customs_value_rub)}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: 'Courier New', monospace; font-size: 10px; margin: 20px; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #000; padding: 3px 5px; vertical-align: top; }}
.header {{ text-align: center; font-size: 14px; font-weight: bold; background: #e3f2fd; }}
.section-header {{ background: #f0f0f0; font-weight: bold; }}
b {{ font-weight: bold; }}
.label {{ font-size: 8px; color: #666; }}
</style></head><body>
<table>
<tr><td class="header" colspan="8">ДЕКЛАРАЦИЯ НА ТОВАРЫ / GOODS DECLARATION</td></tr>
<tr><td colspan="4"><b>1</b> {f(decl.type_code)}</td><td colspan="4"><b>A</b></td></tr>
<tr><td colspan="4"><b>2</b> Отправитель<br>{sender_name}</td>
    <td colspan="2"><b>3</b> Формы: {f(decl.forms_count) or 1}<br><b>4</b> Спец: {f(decl.specifications_count)}</td>
    <td colspan="2"><b>5</b> Товаров: {f(decl.total_items_count)}<br><b>6</b> Мест: {f(decl.total_packages_count)}</td></tr>
<tr><td colspan="4"><b>8</b> Получатель<br>{receiver_name}</td>
    <td colspan="2"><b>9</b> Фин. лицо</td>
    <td colspan="2"><b>12</b> Стоимость: {num(decl.total_customs_value or (items[0].customs_value_rub if items else 0))}</td></tr>
<tr><td colspan="4"><b>14</b> Декларант</td>
    <td colspan="1"><b>15</b> {f(decl.country_dispatch_code)}</td>
    <td colspan="1"><b>16</b> {f(decl.country_origin_code)}</td>
    <td colspan="2"><b>17</b> {f(decl.country_destination_code)}</td></tr>
<tr><td colspan="3"><b>18</b> Транспорт: {f(decl.transport_at_border)}</td>
    <td colspan="1"><b>19</b></td>
    <td colspan="4"><b>20</b> Условия: {f(decl.incoterms_code)}</td></tr>
<tr><td colspan="3"><b>22</b> Валюта: {f(decl.currency_code)} Сумма: {num(decl.total_invoice_value)}</td>
    <td colspan="2"><b>23</b> Курс: {num(decl.exchange_rate,4)}</td>
    <td colspan="1"><b>24</b> {f(decl.deal_nature_code)}</td>
    <td colspan="2"><b>25</b> Трансп: {f(decl.transport_type_border)}</td></tr>
{items_html}
<tr><td colspan="4"><b>54</b> Место и дата: {f(decl.place_and_date)}</td>
    <td colspan="4">Тамож.орган: {f(decl.customs_office_code)}</td></tr>
<tr><td class="header" colspan="8">{f(decl.number_internal) or 'ЧЕРНОВИК'} — Статус: {f(decl.status)}</td></tr>
</table></body></html>"""

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        logger.info("pdf_exported", declaration_id=str(declaration_id), size=len(pdf_bytes))
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="DT_{str(declaration_id)[:8]}.pdf"'},
        )
    except Exception as e:
        logger.error("pdf_export_failed", error=str(e))
        # Fallback: return HTML
        return Response(content=html.encode(), media_type="text/html")
