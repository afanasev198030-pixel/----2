import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Container, Box, Button, CircularProgress, Typography } from '@mui/material';
import { Print as PrintIcon, Edit as EditIcon, ArrowBack, PictureAsPdf } from '@mui/icons-material';
import client from '../api/client';
import { calculatePayments, PaymentResult } from '../api/calc';

const DeclarationViewPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [decl, setDecl] = useState<any>(null);
  const [items, setItems] = useState<any[]>([]);
  const [sender, setSender] = useState<any>(null);
  const [receiver, setReceiver] = useState<any>(null);
  const [payments, setPayments] = useState<PaymentResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [declResp, itemsResp] = await Promise.all([
          client.get(`/declarations/${id}`),
          client.get(`/declarations/${id}/items/`),
        ]);
        const d = declResp.data;
        const its = Array.isArray(itemsResp.data) ? itemsResp.data : itemsResp.data?.items || [];
        setDecl(d);
        setItems(its);

        // Load counterparty names
        if (d.sender_counterparty_id) {
          try { const r = await client.get(`/counterparties/${d.sender_counterparty_id}`); setSender(r.data); } catch {}
        }
        if (d.receiver_counterparty_id) {
          try { const r = await client.get(`/counterparties/${d.receiver_counterparty_id}`); setReceiver(r.data); } catch {}
        }

        // Calculate payments
        if (its.length > 0) {
          try {
            const payItems = its.map((i: any) => ({
              item_no: i.item_no, hs_code: i.hs_code || '',
              unit_price: i.unit_price ? Number(i.unit_price) : 0,
              quantity: i.additional_unit_qty ? Number(i.additional_unit_qty) : 1,
              customs_value_rub: i.customs_value_rub ? Number(i.customs_value_rub) : 0,
            }));
            const p = await calculatePayments(payItems, d.currency_code || 'USD', d.exchange_rate ? Number(d.exchange_rate) : undefined);
            setPayments(p);
          } catch (e) { console.error('Payment calc error:', e); }
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    };
    if (id) load();
  }, [id]);

  if (loading) return <Container sx={{ py: 4, textAlign: 'center' }}><CircularProgress /></Container>;
  if (!decl) return <Container sx={{ py: 4 }}><Typography>Не найдена</Typography></Container>;

  const f = (v: any) => v || '';
  const num = (v: any, d = 2) => v ? Number(v).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }) : '';
  const item = items[0] || {};
  const totals = payments?.totals;

  return (
    <Container maxWidth="lg" sx={{ py: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }} className="no-print">
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/declarations')}>Назад</Button>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" startIcon={<EditIcon />} onClick={() => navigate(`/declarations/${id}/edit`)}>Редактировать</Button>
          <Button variant="outlined" startIcon={<PictureAsPdf />} onClick={async () => {
            try {
              const resp = await client.get(`/declarations/${id}/export-pdf`, { responseType: 'blob' });
              const url = window.URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }));
              const a = document.createElement('a'); a.href = url; a.download = `DT_${(id || '').slice(0,8)}.pdf`; a.click();
            } catch (e) { console.error(e); }
          }}>PDF</Button>
          <Button variant="contained" startIcon={<PrintIcon />} onClick={() => window.print()}>Печать</Button>
        </Box>
      </Box>

      <Box className="dt-form" sx={{ fontFamily: '"Courier New", monospace', fontSize: 11, border: '2px solid #000', bgcolor: '#fff' }}>
        <Box sx={{ display: 'flex', borderBottom: '2px solid #000' }}>
          <Cell w="70%" h={24} bold center border="right">ДЕКЛАРАЦИЯ НА ТОВАРЫ</Cell>
          <Cell w="30%" h={24} center><small>GOODS DECLARATION</small></Cell>
        </Box>

        <Row>
          <Cell w="50%" label="1" border="right"><b>{f(decl.type_code)}</b></Cell>
          <Cell w="50%" label="A" />
        </Row>

        <Row>
          <Cell w="50%" label="2" h={50} border="right">
            <b>Отправитель/Экспортер</b><br/>
            {sender ? (<>{sender.name}<br/><small>{sender.country_code} {sender.address || ''}</small></>) : 'Не указан'}
          </Cell>
          <Cell w="25%" border="right"><Lbl>3</Lbl> Формы: {f(decl.forms_count) || '1'}<br/><Lbl>4</Lbl> Отгр.спец: {f(decl.specifications_count)}</Cell>
          <Cell w="25%"><Lbl>5</Lbl> Всего т-ов: <b>{f(decl.total_items_count)}</b><br/><Lbl>6</Lbl> Всего мест: <b>{f(decl.total_packages_count)}</b><br/><Lbl>7</Lbl> Справ.номер</Cell>
        </Row>

        <Row>
          <Cell w="50%" label="8" h={50} border="right">
            <b>Получатель</b><br/>
            {receiver ? (<>{receiver.name}<br/><small>{receiver.country_code} {receiver.address || ''}</small></>) : 'Не указан'}
          </Cell>
          <Cell w="25%" label="9" border="right">Лицо, отв. за фин. урегулирование</Cell>
          <Cell w="25%"><Lbl>12</Lbl> Общая тамож. стоимость<br/><b>{num(totals?.total_customs_value || item.customs_value_rub)}</b></Cell>
        </Row>

        <Row>
          <Cell w="35%" label="14" h={40} border="right">
            <b>Декларант</b><br/>
            {receiver ? receiver.name : ''}<br/>
            <small>{f(decl.declarant_inn_kpp)} {f(decl.declarant_phone)}</small>
          </Cell>
          <Cell w="15%" border="right"><Lbl>15</Lbl> Страна отпр.<br/><b>{f(decl.country_dispatch_code)}</b></Cell>
          <Cell w="10%" border="right"><Lbl>11</Lbl> Торг.стр.<br/><b>{f(decl.trading_country_code)}</b></Cell>
          <Cell w="15%" border="right"><Lbl>16</Lbl> Происхожд.<br/><b>{f(decl.country_origin_code)}</b></Cell>
          <Cell w="10%" border="right"><Lbl>17</Lbl> Назнач.<br/><b>{f(decl.country_destination_code)}</b></Cell>
          <Cell w="15%"><Lbl>12</Lbl> Общ.тамож.ст.<br/><b>{num(totals?.total_customs_value || item.customs_value_rub)}</b></Cell>
        </Row>

        <Row>
          <Cell w="35%" label="18" border="right">Идент. трансп.средства<br/>{f(decl.transport_at_border)}</Cell>
          <Cell w="10%" label="19" border="right">{f(decl.container_info) || '0'}</Cell>
          <Cell w="25%" label="20">Условия: <b>{f(decl.incoterms_code)} {f(decl.delivery_place)}</b></Cell>
          <Cell w="30%" label="21">Трансп. на границе:<br/><b>{f(decl.transport_on_border_id)}</b></Cell>
        </Row>

        <Row>
          <Cell w="30%" label="22" border="right">Валюта: <b>{f(decl.currency_code)}</b> Сумма: <b>{num(decl.total_invoice_value)}</b></Cell>
          <Cell w="15%" label="23" border="right">Курс: {payments ? num(payments.exchange_rate, 4) : num(decl.exchange_rate, 4)}</Cell>
          <Cell w="15%" label="24" border="right">Хар.сделки: <b>{f(decl.deal_nature_code)}</b></Cell>
          <Cell w="15%" label="25" border="right">Трансп: <b>{f(decl.transport_type_border)}</b></Cell>
          <Cell w="25%"><Lbl>29</Lbl> Орган въезда: <b>{f(decl.entry_customs_code)}</b></Cell>
        </Row>

        {decl.goods_location && <Row>
          <Cell w="100%" label="30">Местонахождение товаров: {decl.goods_location}</Cell>
        </Row>}

        {/* Items */}
        {items.map((itm: any, idx: number) => {
          const pi = payments?.items?.[idx];
          return (
            <Box key={itm.id || idx}>
              <Box sx={{ borderTop: '2px solid #000', bgcolor: '#f0f0f0', px: 1, py: 0.3 }}><b>Товар № {itm.item_no || idx + 1}</b></Box>
              <Row>
                <Cell w="70%" label="31" h={60} border="right">
                  <b>Грузовые места и описание товаров</b><br/>{f(itm.description || itm.commercial_name)}<br/>
                  <small>{itm.additional_unit_qty ? `${itm.additional_unit_qty} / ${itm.additional_unit || 'ШТ'}` : ''}</small>
                </Cell>
                <Cell w="30%"><Lbl>32</Lbl> Товар №{itm.item_no}<br/><Lbl>33</Lbl> Код товара: <b style={{ fontSize: 14 }}>{f(itm.hs_code)}</b><br/><Lbl>34</Lbl> Код страны: <b>{f(itm.country_origin_code)}</b></Cell>
              </Row>
              <Row>
                <Cell w="25%" label="35" border="right">Вес брутто: <b>{num(itm.gross_weight, 3)}</b> кг</Cell>
                <Cell w="25%" label="36" border="right">Преференция: {f(itm.preference_code)}</Cell>
                <Cell w="25%" label="37" border="right">Процедура: {f(itm.procedure_code)}</Cell>
                <Cell w="25%" label="38">Вес нетто: <b>{num(itm.net_weight, 3)}</b> кг</Cell>
              </Row>
              <Row>
                <Cell w="25%" label="41" border="right">Доп.ед: {itm.additional_unit_qty ? `${num(itm.additional_unit_qty, 0)} ${itm.additional_unit || 'ШТ'}` : ''}</Cell>
                <Cell w="25%" label="42" border="right">Цена: <b>{num(itm.unit_price, 4)}</b></Cell>
                <Cell w="25%" label="43" border="right">Код МОС: {f(itm.mos_method_code)}</Cell>
                <Cell w="25%" label="45">Тамож.стоимость:<br/><b style={{ fontSize: 13 }}>{num(pi?.customs_value_rub || itm.customs_value_rub)}</b></Cell>
              </Row>
            </Box>
          );
        })}

        {/* Payments - from calc-service */}
        <Box sx={{ borderTop: '2px solid #000' }}>
          <Row>
            <Cell w="100%" label="47" h={80}>
              <b>Исчисление платежей</b><br/>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr>
                    <th style={thStyle}>Вид</th>
                    <th style={{...thStyle, textAlign: 'right'}}>Основа начисления</th>
                    <th style={{...thStyle, textAlign: 'center'}}>Ставка</th>
                    <th style={{...thStyle, textAlign: 'right'}}>Сумма</th>
                    <th style={thStyle}>СП</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td style={tdStyle}>1010 — Сборы</td>
                    <td style={{...tdStyle, textAlign: 'right'}}>{num(totals?.total_customs_value)}</td>
                    <td style={{...tdStyle, textAlign: 'center'}}>—</td>
                    <td style={{...tdStyle, textAlign: 'right'}}>{num(totals?.customs_fee)}</td>
                    <td style={tdStyle}>ИУ</td>
                  </tr>
                  <tr>
                    <td style={tdStyle}>2010 — Пошлина</td>
                    <td style={{...tdStyle, textAlign: 'right'}}>{num(totals?.total_customs_value)}</td>
                    <td style={{...tdStyle, textAlign: 'center'}}>{payments?.items?.[0]?.duty?.rate || 0}%</td>
                    <td style={{...tdStyle, textAlign: 'right'}}>{num(totals?.total_duty)}</td>
                    <td style={tdStyle}>ИУ</td>
                  </tr>
                  <tr>
                    <td style={tdStyle}>5010 — НДС</td>
                    <td style={{...tdStyle, textAlign: 'right'}}>{num(payments?.items?.[0]?.vat?.base)}</td>
                    <td style={{...tdStyle, textAlign: 'center'}}>{payments?.items?.[0]?.vat?.rate || 20}%</td>
                    <td style={{...tdStyle, textAlign: 'right'}}>{num(totals?.total_vat)}</td>
                    <td style={tdStyle}>ИУ</td>
                  </tr>
                  <tr style={{ fontWeight: 700, borderTop: '2px solid #000' }}>
                    <td style={tdStyle} colSpan={3}>ИТОГО</td>
                    <td style={{...tdStyle, textAlign: 'right'}}>{num(totals?.grand_total)}</td>
                    <td style={tdStyle}>РУБ</td>
                  </tr>
                </tbody>
              </table>
            </Cell>
          </Row>
        </Box>

        {/* Footer */}
        <Row>
          <Cell w="50%" label="54" h={36} border="right"><b>Место и дата</b><br/>{f(decl.place_and_date)}</Cell>
          <Cell w="50%"><b>Таможенный орган:</b> {f(decl.customs_office_code)}<br/><b>СВХ:</b> {f(decl.warehouse_name)}</Cell>
        </Row>

        <Box sx={{ borderTop: '2px solid #000', p: 1, textAlign: 'center', bgcolor: '#e8f5e9' }}>
          <b style={{ fontSize: 14 }}>{decl.number_internal || 'ЧЕРНОВИК'}</b>
          <span style={{ marginLeft: 20 }}>Статус: {decl.status}</span>
        </Box>
      </Box>

      <style>{`
        @media print { .no-print { display: none !important; } body { margin: 0; padding: 0; } }
      `}</style>
    </Container>
  );
};

const thStyle: React.CSSProperties = { border: '1px solid #999', padding: 2, textAlign: 'left' };
const tdStyle: React.CSSProperties = { border: '1px solid #999', padding: 2 };
const Row = ({ children }: { children: React.ReactNode }) => (<Box sx={{ display: 'flex', borderBottom: '1px solid #000', minHeight: 24 }}>{children}</Box>);
const Cell = ({ w, h, label, border, bold, center, children }: { w: string; h?: number; label?: string; border?: string; bold?: boolean; center?: boolean; children?: React.ReactNode }) => (
  <Box sx={{ width: w, minHeight: h || 24, p: '2px 4px', position: 'relative', borderRight: border === 'right' ? '1px solid #000' : 'none', fontWeight: bold ? 700 : 400, textAlign: center ? 'center' : 'left', fontSize: 11, lineHeight: 1.3, overflow: 'hidden' }}>
    {label && <Lbl>{label}</Lbl>}{children}
  </Box>
);
const Lbl = ({ children }: { children: React.ReactNode }) => (<span style={{ fontSize: 9, color: '#666', fontWeight: 700 }}>{children} </span>);

export default DeclarationViewPage;
