"""PDF экспорт декларации в формате ДТ (Решение КТС N 257)."""
import math
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


def _f(v) -> str:
    return str(v).upper() if v else ""


def _num(v, d: int = 2) -> str:
    if not v:
        return ""
    return f"{float(v):,.{d}f}".replace(",", " ")


def _cp_line(cp) -> str:
    if not cp:
        return "НЕ УКАЗАН"
    parts = [cp.name or ""]
    if cp.country_code:
        parts.append(cp.country_code)
    if cp.address:
        parts.append(cp.address)
    return " ".join(parts).upper()


CSS = """
@page { size: A4 portrait; margin: 8mm; }
body { font-family: 'Courier New', monospace; font-size: 10px; margin: 0; padding: 0; text-transform: uppercase; }
.sheet { page-break-after: always; border: 2px solid #000; width: 100%; box-sizing: border-box; }
.sheet:last-child { page-break-after: auto; }
table { border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #000; padding: 1px 3px; vertical-align: top; font-size: 10px; line-height: 1.2; }
.lbl { font-size: 7px; color: #555; font-weight: 700; }
.hdr { text-align: center; font-weight: 700; font-size: 12px; border-bottom: 2px solid #000; }
.thick-b { border-bottom: 2px solid #000; }
.thick-t { border-top: 2px solid #000; }
.no-border { border: none; }
.status-bar { text-align: center; background: #e8f5e9; font-size: 12px; font-weight: 700; padding: 3px; }
b { font-weight: 700; }
"""


def _item_block_html(item) -> str:
    """Renders fields 31-46 for a single item."""
    docs = ""
    if item.documents_json:
        for doc in item.documents_json:
            docs += f"{doc.get('code','')}/{doc.get('marker','')} {doc.get('number','')} {doc.get('date','')}<br>"

    return f"""
    <tr>
      <td style="width:57%" rowspan="5"><span class="lbl">31 </span>Грузовые места и описание товаров<br>
        Маркировка и количество — Номера контейнеров — Количество и отличительные особенности<br>
        {_f(item.description or item.commercial_name)}<br>
        {(str(item.package_count or '') + ' ' + _f(item.package_type)) if item.package_count else ''}
        {(_num(item.additional_unit_qty, 0) + ' ' + (_f(item.additional_unit) or 'ШТ')) if item.additional_unit_qty else ''}
      </td>
      <td style="width:15%"><span class="lbl">32 </span>Товар<br><b>№{_f(item.item_no)}</b></td>
      <td style="width:28%"><span class="lbl">33 </span>Код товара<br><b style="font-size:12px">{_f(item.hs_code)}</b></td>
    </tr>
    <tr>
      <td><span class="lbl">34 </span>Код страны происх.<br><small>a</small> <b>{_f(item.country_origin_code)}</b> <small>b</small> {_f(item.country_origin_pref_code)}</td>
      <td colspan="1">
        <table class="no-border" style="width:100%"><tr>
          <td class="no-border" style="width:60%"><span class="lbl">35 </span>Вес брутто (кг)<br><b>{_num(item.gross_weight, 3)}</b></td>
          <td class="no-border"><span class="lbl">36 </span>Преференция<br>{_f(item.preference_code)}</td>
        </tr></table>
      </td>
    </tr>
    <tr>
      <td><span class="lbl">37 </span>ПРОЦЕДУРА<br><b>{_f(item.procedure_code)}</b></td>
      <td>
        <table class="no-border" style="width:100%"><tr>
          <td class="no-border" style="width:60%"><span class="lbl">38 </span>Вес нетто (кг)<br><b>{_num(item.net_weight, 3)}</b></td>
          <td class="no-border"><span class="lbl">39 </span>Квота<br>{_f(item.quota_info)}</td>
        </tr></table>
      </td>
    </tr>
    <tr>
      <td colspan="2"><span class="lbl">40 </span>Общая декларация/Предшествующий документ<br>{_f(item.prev_doc_ref)}</td>
    </tr>
    <tr>
      <td colspan="2">
        <table class="no-border" style="width:100%"><tr>
          <td class="no-border" style="width:35%"><span class="lbl">41 </span>Доп.единицы<br>{(_num(item.additional_unit_qty, 0) + ' ' + (_f(item.additional_unit) or 'ШТ')) if item.additional_unit_qty else ''}</td>
          <td class="no-border" style="width:40%"><span class="lbl">42 </span>Цена товара<br><b>{_num(item.unit_price, 4)}</b></td>
          <td class="no-border"><span class="lbl">43 </span>Код МОС<br>{_f(item.mos_method_code)}</td>
        </tr></table>
      </td>
    </tr>
    <tr>
      <td style="width:57%"><span class="lbl">44 </span>Дополнит. информация / Представл. документы<br>{docs}</td>
      <td colspan="2">
        <span class="lbl">45 </span>Таможенная стоимость<br><b style="font-size:12px">{_num(item.customs_value_rub)}</b>
        <br><span class="lbl">46 </span>Статистическая стоимость<br><b>{_num(item.statistical_value_usd)}</b>
      </td>
    </tr>"""


def _build_dt1(decl, items, sender, receiver, declarant, financial) -> str:
    """Build HTML for ДТ1 main sheet."""
    first_item = items[0] if items else None
    total_forms = 1 + math.ceil(max(0, len(items) - 1) / 3)
    total_customs_value = _num(decl.total_customs_value)

    item_html = _item_block_html(first_item) if first_item else ""

    return f"""<div class="sheet"><table>
    <!-- HEADER -->
    <tr class="thick-b">
      <td style="width:57%" class="hdr" colspan="2">ДЕКЛАРАЦИЯ НА ТОВАРЫ</td>
      <td style="width:28%"><span class="lbl">1 </span><b>{_f(decl.type_code)}</b></td>
      <td style="width:15%;text-align:center"><span class="lbl">А</span></td>
    </tr>
    <!-- 2 / 3-4 / 5-7 -->
    <tr>
      <td colspan="2" rowspan="2" style="min-height:40px"><span class="lbl">2 </span>Отправитель/Экспортер<br><b>{_cp_line(sender)}</b></td>
      <td><span class="lbl">3 </span>Формы<br><b>{_f(decl.forms_count) or total_forms}</b><br><span class="lbl">4 </span>Отгр.спец.<br>{_f(decl.specifications_count)}</td>
      <td><span class="lbl">5 </span>Всего т-ов<br><b>{_f(decl.total_items_count) or len(items)}</b><br><span class="lbl">6 </span>Всего мест<br><b>{_f(decl.total_packages_count)}</b><br><span class="lbl">7 </span>Справ.номер<br>{_f(decl.special_ref_code)}</td>
    </tr>
    <tr></tr>
    <!-- 8 / 9 -->
    <tr>
      <td colspan="2" style="min-height:40px"><span class="lbl">8 </span>Получатель<br><b>{_cp_line(receiver)}</b></td>
      <td><span class="lbl">9 </span>Лицо, ответственное за финансовое урегулирование<br>{_cp_line(financial) if financial else ''}</td>
      <td></td>
    </tr>
    <!-- 10 / 11 / 12 / 13 -->
    <tr>
      <td><span class="lbl">10 </span>Страна перв.назн./посл.отпр.<br>{_f(decl.country_first_destination_code)}</td>
      <td><span class="lbl">11 </span>Торг.страна<br><b>{_f(decl.trading_country_code)}</b></td>
      <td><span class="lbl">12 </span>Общая таможенная стоимость<br><b>{total_customs_value}</b></td>
      <td><span class="lbl">13</span></td>
    </tr>
    <!-- 14 / 15 / 15a-b / 17a-b -->
    <tr>
      <td colspan="2"><span class="lbl">14 </span>Декларант<br><b>{_cp_line(declarant or receiver)}</b><br>{_f(decl.declarant_inn_kpp)} {_f(decl.declarant_ogrn)} {_f(decl.declarant_phone)}</td>
      <td><span class="lbl">15 </span>Страна отправления<br><b>{_f(decl.country_dispatch_code)}</b><br><span class="lbl">15a </span>{_f(decl.country_dispatch_code)} <span class="lbl">b</span></td>
      <td><span class="lbl">17 </span>Код страны назнач.<br><span class="lbl">a </span>{_f(decl.country_destination_code)} <span class="lbl">b</span></td>
    </tr>
    <!-- 16 / 17 -->
    <tr>
      <td colspan="2"></td>
      <td><span class="lbl">16 </span>Страна происхождения<br><b>{_f(decl.country_origin_name)}</b></td>
      <td><span class="lbl">17 </span>Страна назначения<br><b>{_f(decl.country_destination_code)}</b></td>
    </tr>
    <!-- 18 / 19 / 20 -->
    <tr>
      <td colspan="2"><span class="lbl">18 </span>Идент. и страна регистрации трансп. средства<br><b>{_f(decl.transport_at_border)}</b></td>
      <td><span class="lbl">19 </span>Конт.<br><b>{_f(decl.container_info) or '0'}</b></td>
      <td><span class="lbl">20 </span>Условия поставки<br><b>{_f(decl.incoterms_code)} {_f(decl.delivery_place)}</b></td>
    </tr>
    <!-- 21 / 22 / 23 / 24 -->
    <tr>
      <td colspan="2"><span class="lbl">21 </span>Идент. активного транспортного средства на границе<br><b>{_f(decl.transport_on_border_id)}</b></td>
      <td><span class="lbl">22 </span>Валюта и общая сумма по счету<br><b>{_f(decl.currency_code)} {_num(decl.total_invoice_value)}</b><br><span class="lbl">23 </span>Курс валюты<br><b>{_num(decl.exchange_rate, 4)}</b></td>
      <td><span class="lbl">24 </span>Характер сделки<br><b>{_f(decl.deal_nature_code)}{('/' + decl.deal_specifics_code) if decl.deal_specifics_code else ''}</b></td>
    </tr>
    <!-- 25 / 26 / 27 / 28 -->
    <tr>
      <td><span class="lbl">25 </span>Вид транспорта на границе<br><b>{_f(decl.transport_type_border)}</b></td>
      <td><span class="lbl">26 </span>Вид транспорта внутри страны<br><b>{_f(decl.transport_type_inland)}</b></td>
      <td><span class="lbl">27 </span>Место погрузки/разгрузки<br>{_f(decl.loading_place)}</td>
      <td><span class="lbl">28 </span>Финансовые и банковские сведения<br>{_f(decl.financial_info)}</td>
    </tr>
    <!-- 29 / 30 -->
    <tr>
      <td><span class="lbl">29 </span>Орган въезда/выезда<br><b>{_f(decl.entry_customs_code)}</b></td>
      <td colspan="3"><span class="lbl">30 </span>Местонахождение товаров<br>{_f(decl.goods_location)}</td>
    </tr>
    <!-- ITEM BLOCK 31-46 -->
    {item_html}
    <!-- 47 / 48 / 49 / B -->
    <tr class="thick-t">
      <td colspan="2" rowspan="3" style="min-height:60px">
        <span class="lbl">47 </span>Исчисление платежей<br>
        <table style="width:100%;font-size:9px"><tr><th>Вид</th><th>Основа</th><th>Ставка</th><th>Сумма</th><th>СП</th></tr>
        <tr><td>1010</td><td>{total_customs_value}</td><td>—</td><td></td><td>ИУ</td></tr>
        <tr><td>2010</td><td>{total_customs_value}</td><td></td><td></td><td>ИУ</td></tr>
        <tr><td>5010</td><td></td><td></td><td></td><td>ИУ</td></tr>
        <tr style="font-weight:700"><td colspan="3">Всего:</td><td></td><td></td></tr>
        </table>
      </td>
      <td colspan="2"><span class="lbl">48 </span>Отсрочка платежей<br>{_f(decl.payment_deferral)}</td>
    </tr>
    <tr>
      <td colspan="2"><span class="lbl">49 </span>Реквизиты склада<br>{_f(decl.warehouse_requisites)}</td>
    </tr>
    <tr>
      <td colspan="2"><span class="lbl">В </span>ПОДРОБНОСТИ ПОДСЧЕТА</td>
    </tr>
    <!-- C -->
    <tr><td colspan="4" style="text-align:center"><span class="lbl">С</span></td></tr>
    <!-- 51 / 52 / 53 -->
    <tr>
      <td><span class="lbl">51 </span>Предполагаемые таможенные органы (и страна) транзита<br>{_f(decl.transit_offices)}</td>
      <td><span class="lbl">52 </span>Гарантия недействительна для<br>{_f(decl.guarantee_info)}</td>
      <td colspan="2"><span class="lbl">53 </span>Таможенный орган назначения (и страна)<br><b>{_f(decl.destination_office_code)}</b></td>
    </tr>
    <!-- D / 54 -->
    <tr>
      <td colspan="2"><span class="lbl">D</span><br>Результат:<br>Наложенные пломбы:<br>Номер:<br>Срок доставки (дата):<br>Подпись:</td>
      <td colspan="2"><span class="lbl">54 </span>Место и дата<br><b>{_f(decl.place_and_date)}</b><br><br>Подпись и печать декларанта</td>
    </tr>
    <!-- Status bar -->
    <tr><td colspan="4" class="status-bar">{_f(decl.number_internal) or 'ЧЕРНОВИК'} — Статус: {_f(decl.status)}</td></tr>
    </table></div>"""


def _build_dt2(decl, sheet_items, sheet_number, total_forms, sender, receiver) -> str:
    """Build HTML for one ДТ2 additional sheet (up to 3 items)."""
    items_html = ""
    for itm in sheet_items:
        items_html += _item_block_html(itm)

    empty_slots = 3 - len(sheet_items)
    for _ in range(empty_slots):
        items_html += """<tr><td colspan="4" style="min-height:60px;position:relative">
        <div style="position:absolute;top:50%;left:5%;right:5%;border-top:2px solid #000"></div></td></tr>"""

    return f"""<div class="sheet"><table>
    <tr class="thick-b">
      <td style="width:57%" class="hdr" colspan="2">ДОБАВОЧНЫЙ ЛИСТ К ДЕКЛАРАЦИИ НА ТОВАРЫ</td>
      <td style="width:28%"><span class="lbl">1 </span><b>{_f(decl.type_code)}</b></td>
      <td style="width:15%;text-align:center"><span class="lbl">А</span></td>
    </tr>
    <tr>
      <td><span class="lbl">2 </span>Отправитель<br><b>{(sender.name if sender else 'НЕ УКАЗАН').upper()}</b></td>
      <td><span class="lbl">8 </span>Получатель<br><b>{(receiver.name if receiver else 'НЕ УКАЗАН').upper()}</b></td>
      <td colspan="2"><span class="lbl">3 </span>Формы<br><b>{sheet_number}/{total_forms}</b></td>
    </tr>
    {items_html}
    <tr><td colspan="4" style="text-align:center"><span class="lbl">С</span></td></tr>
    </table></div>"""


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

    async def load_cp(cp_id):
        if not cp_id:
            return None
        r = await db.execute(select(Counterparty).where(Counterparty.id == cp_id))
        return r.scalar_one_or_none()

    sender = await load_cp(decl.sender_counterparty_id)
    receiver = await load_cp(decl.receiver_counterparty_id)
    declarant = await load_cp(decl.declarant_counterparty_id)
    financial = await load_cp(decl.financial_counterparty_id)

    items = sorted(decl.items or [], key=lambda x: x.item_no or 0)
    total_forms = 1 + math.ceil(max(0, len(items) - 1) / 3)

    sheets_html = _build_dt1(decl, items, sender, receiver, declarant, financial)

    for i in range(1, len(items), 3):
        sheet_items = items[i : i + 3]
        sheet_number = 1 + (i // 3) + 1
        sheets_html += _build_dt2(decl, sheet_items, sheet_number, total_forms, sender, receiver)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{CSS}</style>
</head><body>{sheets_html}</body></html>"""

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
        return Response(content=html.encode(), media_type="text/html")
