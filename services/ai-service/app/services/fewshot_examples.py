"""
Few-shot examples for classify_and_extract LLM prompt.

Each example is a (user_text, assistant_json) pair derived from real
documents. Confidential data (INN, company names, addresses) is masked.

To update with new examples:
1. Upload a real document via POST /api/v1/ai/parse-debug
2. Take the OCR text fragment (25-30 lines) — header + key sections
3. Manually correct the JSON output to the expected result
4. Mask confidential data, keep the structure intact
5. Add to FEWSHOT_EXAMPLES below
"""
import json

FEWSHOT_EXAMPLES: list[dict] = [
    # ── CONTRACT (USD, bilingual, no fixed total, incoterms per shipment) ──
    {
        "doc_type": "contract",
        "user": (
            "Filename: Договор_MK-TRD-USD-2025-0040 от 23.01.2025.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "CONTRACT\n"
            "MK-TRD-USD/2025/0040 on 23.01.2025\n"
            "Moscow\n"
            "КОНТРАКТ\n"
            "MK-TRD-USD/2025/0040 от 23.01.2025\n"
            "г. Москва\n"
            "The company Global Trading Co., Limited represented\n"
            "by the director Ivan Petrov hereinafter referred to as\n"
            "SELLER, on the one hand, and «TK-Logistik» LLC, Russia,\n"
            "represented by the general director Sidorov Alexei Ivanovich,\n"
            "hereinafter referred to as the BUYER, on the other hand, have\n"
            "concluded the present Contract as follows:\n"
            "Компания Глобал Трейдинг Ко., Лимитед,\n"
            "в лице директора Ивана Петрова, действующего на\n"
            "основании устава, в дальнейшем именуемая ПРОДАВЕЦ, с\n"
            "одной стороны, и ООО «ТК-Логистик», Россия, в лице\n"
            "Генерального директора Сидоров Алексей Иванович, в\n"
            "дальнейшем именуемая ПОКУПАТЕЛЬ, с другой стороны,\n"
            "заключили настоящий Контракт о нижеследующем:\n"
            "1. SUBJECT OF THE CONTRACT\n"
            "The SELLER sells, and the BUYER purchases goods\n"
            "(equipment) for delivery to the territory of the Russian\n"
            "Federation.\n"
            "The range and cost of the goods are agreed upon by the parties in\n"
            "the invoice, which is an integral part of the contract.\n"
            "The CONTRACT is valid till 31.12.2027.\n"
            "1. ПРЕДМЕТ КОНТРАКТА.\n"
            "ПРОДАВЕЦ продает, а ПОКУПАТЕЛЬ покупает товары\n"
            "(оборудование) для поставки на территорию РФ.\n"
            "Ассортимент и стоимость товара согласовываются\n"
            "сторонами в счете являющейся неотъемлемой частью контракта.\n"
            "КОНТРАКТ действителен до 31.12.2027 г.\n"
            "2. PRICE OF GOODS AND TOTAL VALUE CONTRACT\n"
            "The currency of the Contract is the USD.\n"
            "The total value of the contract is the total value of the entire\n"
            "product delivered in accordance with commercial invoices issued\n"
            "for each individual batch of goods.\n"
            "2. ЦЕНА ТОВАРА И ОБЩАЯ СТОИМОСТЬ КОНТРАКТА\n"
            "Валютой Контракта являются доллары.\n"
            "Общая стоимость контракта составляет суммарную\n"
            "стоимость всего товара, поставленного в соответствии с\n"
            "коммерческими инвойсами.\n"
            "4. TERMS OF DELIVERY.\n"
            "The goods are delivered on the conditions specified in invoices\n"
            "each consignment of goods.\n"
            "4. УСЛОВИЯ ПОСТАВКИ\n"
            "Товар поставляется на условиях, указываемых в\n"
            "спецификациях на каждую партию товара.\n"
            "5. TERMS OF PAYMENT\n"
            "Payment shall be made in Russian rubles at the exchange rate of\n"
            "the Bank of Russia on the date of payment of the invoice.\n"
            "5. УСЛОВИЯ ПЛАТЕЖА\n"
            "Оплата производится в российских рублях по курсу Банка\n"
            "России на дату оплаты счета.\n"
            "...\n"
            "13. LEGAL ADRESSES AND BANKING DETAILS\n"
            "THE SELLER:\n"
            "Global Trading Co., Limited\n"
            "Address: Room 1005, 10/F Ho King Commercial Center,\n"
            "Fa Yuen Street, 2-16, Mong Kok, Hong Kong\n"
            "ИНН 9909801234\n"
            "BUYER:\n"
            "LLC \"TK-LOGISTIK\"\n"
            "125171, Moscow, Leningradskoe sh., 16A\n"
            "TIN/KPP 9728100494 / 774301001\n"
            "OGRN 1237700467652\n"
            "ПОКУПАТЕЛЬ:\n"
            "ООО «ТК-Логистик»\n"
            "125171, г. Москва, ш Ленинградское, д. 16А\n"
            "ИНН/КПП 9728100494 / 774301001\n"
            "ОГРН 1237700467652"
        ),
        "assistant": json.dumps({
            "doc_type": "contract",
            "doc_type_confidence": 0.98,
            "reasoning": "Bilingual document titled CONTRACT/КОНТРАКТ with contract number, SELLER/BUYER parties, currency USD, delivery terms — sale/purchase contract",
            "extracted": {
                "contract_number": "MK-TRD-USD/2025/0040",
                "contract_date": "23.01.2025",
                "currency": "USD",
                "total_amount": None,
                "incoterms": None,
                "delivery_place": None,
                "subject": "Товары (оборудование) для поставки на территорию РФ",
                "payment_terms": "Оплата производится в российских рублях по курсу Банка России на дату оплаты счета",
                "is_trilateral": False,
                "seller": {
                    "name": "Global Trading Co., Limited",
                    "address": "Room 1005, 10/F Ho King Commercial Center, Fa Yuen Street, 2-16, Mong Kok, Hong Kong",
                    "country_code": "HK",
                    "inn": "9909801234", "kpp": None, "ogrn": None
                },
                "buyer": {
                    "name": "ООО «ТК-Логистик»",
                    "address": "125171, г. Москва, ш Ленинградское, д. 16А",
                    "country_code": "RU",
                    "inn": "9728100494", "kpp": "774301001", "ogrn": "1237700467652"
                },
                "receiver": None,
                "financial_party": None
            }
        }, ensure_ascii=False),
    },
    # ── CONTRACT (RUB, bilingual, payment in different currency possible) ──
    {
        "doc_type": "contract",
        "user": (
            "Filename: Договор_MK-TRD-2025-0029 on 23.01.2025.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "CONTRACT\n"
            "№ MK-TRD/2025/0029 on 23.01.2025\n"
            "Moscow\n"
            "КОНТРАКТ\n"
            "№ MK-TRD/2025/0029 от 23.01.2025\n"
            "г. Москва\n"
            "The company Global Trading Co., Limited represented\n"
            "by the director Ivan Petrov hereinafter referred to as\n"
            "SELLER, on the one hand, and «TK-Logistik» LLC, Russia,\n"
            "represented by the general director Sidorov Alexei Ivanovich,\n"
            "hereinafter referred to as the BUYER, on the other hand, have\n"
            "concluded the present Contract as follows:\n"
            "Компания Глобал Трейдинг Ко., Лимитед,\n"
            "в лице директора Ивана Петрова, в дальнейшем именуемая ПРОДАВЕЦ, с\n"
            "одной стороны, и ООО «ТК-Логистик», Россия, в лице\n"
            "Генерального директора Сидоров Алексей Иванович, в\n"
            "дальнейшем именуемая ПОКУПАТЕЛЬ, с другой стороны,\n"
            "заключили настоящий Контракт о нижеследующем:\n"
            "1. ПРЕДМЕТ КОНТРАКТА.\n"
            "ПРОДАВЕЦ продает, а ПОКУПАТЕЛЬ покупает товары\n"
            "(оборудование) для поставки на территорию РФ.\n"
            "Ассортимент и стоимость товара согласовываются\n"
            "сторонами в спецификации являющейся неотъемлемой частью контракта.\n"
            "КОНТРАКТ действителен до 31.12.2027.\n"
            "2. ЦЕНА ТОВАРА И ОБЩАЯ СТОИМОСТЬ КОНТРАКТА\n"
            "Валютой Контракта являются рубли.\n"
            "Общая стоимость контракта составляет суммарную\n"
            "стоимость всего товара, поставленного в соответствии с\n"
            "коммерческими инвойсами.\n"
            "4. УСЛОВИЯ ПОСТАВКИ\n"
            "Товар поставляется на условиях, указываемых в\n"
            "спецификациях на каждую партию товара.\n"
            "5. УСЛОВИЯ ПЛАТЕЖА\n"
            "Платеж за поставляемый товар может производиться в\n"
            "валюте отличной от валюты контракта. Валюта инвойса,\n"
            "валюта оплаты, порядок и сроки оплаты согласуются\n"
            "Сторонами в Спецификации."
        ),
        "assistant": json.dumps({
            "doc_type": "contract",
            "doc_type_confidence": 0.98,
            "reasoning": "Bilingual КОНТРАКТ with number, parties, currency RUB. Total amount not fixed — per invoices. Incoterms per specification.",
            "extracted": {
                "contract_number": "MK-TRD/2025/0029",
                "contract_date": "23.01.2025",
                "currency": "RUB",
                "total_amount": None,
                "incoterms": None,
                "delivery_place": None,
                "subject": "Товары (оборудование) для поставки на территорию РФ",
                "payment_terms": "Платеж может производиться в валюте отличной от валюты контракта. Порядок и сроки согласуются в Спецификации.",
                "is_trilateral": False,
                "seller": {
                    "name": "Global Trading Co., Limited",
                    "address": "Room 1005, 10/F Ho King Commercial Center, Fa Yuen Street, 2-16, Mong Kok, Hong Kong",
                    "country_code": "HK",
                    "inn": "9909801234", "kpp": None, "ogrn": None
                },
                "buyer": {
                    "name": "ООО «ТК-Логистик»",
                    "address": "125171, г. Москва, ш Ленинградское, д. 16А",
                    "country_code": "RU",
                    "inn": "9728100494", "kpp": "774301001", "ogrn": "1237700467652"
                },
                "receiver": None,
                "financial_party": None
            }
        }, ensure_ascii=False),
    },
    # ── INVOICE (USD, Vision OCR concatenated table, bank details present) ──
    {
        "doc_type": "invoice",
        "user": (
            "Filename: Invoice № MK2025170631 on 2025.09.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "# Global Trading Co., Limited\n"
            "FLAT/1005 10/F Ho King Commercial Center, Fa YuenStreet, 2-16, Mong Kok, Hong Kong\n\n"
            "Поставщик / The supplier\n"
            "Global Trading Co., Limited\n"
            "Покупатель / Buyer\n"
            "FLAT/1005 10/F Ho King Commercial Center, Fa YuenStreet, 2-16, Mong\n"
            "LLC \"TK-Logistik\"\n"
            "Kok, Hong Kong\n"
            "125171, Moscow, Vaykovsky Municipal District, Leningradskoye\n"
            "Road, 16A, Building 3\n"
            "ООО «ТК-Логистик»\n"
            "125171, г. Москва, вн.тер.г. Муниципальный Округ\n"
            "Войковский, ш Ленинградское, д. 16А, стр. 3\n\n"
            "Contract/Doropov N&MK-TRD-USD/2025/0040 on 23.01.2025\n"
            "Terms of delivery/Vсловия поставки EXW Hongkong\n"
            "Payment terms/Vсловия оплаты 100% предоплата, по факту уведомления\n"
            "Продовцом о готовности груза к отгрузке\n"
            "Страна происхождения Китай\n\n"
            "Invoice № MK2025/1706/31 on 2025.09.25\n\n"
            "[TABLE_START]\n"
            "No.ItemQtyUnit Price (USD)Total (USD)1Камера RS 65-N1700643,67001 094 239,00 | Note:Total USD1 094 239,00\n"
            "[TABLE_END]\n\n"
            "1. Destination Customer Tax: on buyer side.\n"
            "2. Payment : T/T 100% Down Payment Balance before shipping.\n"
            "3. Delivery methods: Airline shipping.\n\n"
            "## Bank Information:\n"
            "BENEFICIARY BANK: PJSC \"AKIBANK\"\n"
            "INN 1650002455\n"
            "BIK 049205933\n"
            "BENEFICIARY NAME: Global Trading Co., Limited\n"
            "A/C NO: 40807810500000000013\n"
            "INN 9909709190"
        ),
        "assistant": json.dumps({
            "doc_type": "invoice",
            "doc_type_confidence": 0.97,
            "reasoning": "Document with Invoice number, item table with prices, seller/buyer, contract reference — commercial goods invoice (not transport). OCR distorted 'Договор' as 'Doropov' and '№' as 'N&' — cleaned.",
            "extracted": {
                "invoice_number": "MK2025/1706/31",
                "invoice_date": "2025.09.25",
                "currency": "USD",
                "total_amount": 1094239.00,
                "incoterms": "EXW",
                "contract_number": "MK-TRD-USD/2025/0040",
                "country_origin": "CN",
                "seller": {
                    "name": "Global Trading Co., Limited",
                    "address": "FLAT/1005 10/F Ho King Commercial Center, Fa YuenStreet, 2-16, Mong Kok, Hong Kong",
                    "country_code": "HK",
                    "tax_number": "9909709190"
                },
                "buyer": {
                    "name": "ООО «ТК-Логистик»",
                    "address": "125171, г. Москва, вн.тер.г. Муниципальный Округ Войковский, ш Ленинградское, д. 16А, стр. 3",
                    "country_code": "RU",
                    "tax_number": None
                },
                "items": [
                    {"description": "Камера RS 65-N", "quantity": 1700, "unit": "pcs", "unit_price": 643.67, "line_total": 1094239.00, "country_origin": "CN", "hs_code": None, "gross_weight": None, "net_weight": None}
                ],
                "total_gross_weight": None,
                "total_net_weight": None,
                "total_packages": None,
                "country_origin": "CN"
            }
        }, ensure_ascii=False),
    },
    # ── INVOICE (CNY, multi-column table with part numbers, FCA) ──
    {
        "doc_type": "invoice",
        "user": (
            "Filename: Invoice for RU20251121-HY34(7)- air freight.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "# 上海亚域动力工程有限公司\n"
            "F-DIESEL POWER CO., LTD.\n\n"
            "ADDRESS: BUILDING 9, NO. 365, LIANYANG ROAD, SONGJIANG DISTRICT,\n"
            "SHANGHAI, CHINA 201613\n"
            "TEL: 86-21-33506915 FAX: 86-21-33506269\n\n"
            "Invoice\n\n"
            "The SELLER - F-DIESEL POWER CO., LTD\n"
            "Legal address: 1st Floor, Building 9, No. 365, Lianyang\n"
            "Road, Songjiang District, Shanghai, China 201613\n"
            "Date: Jan. 15th, 2026\n"
            "Invoice No.: RU20251121-HY34(7)\n\n"
            "The BUYER - JSC «KAMA DIESEL»\n"
            "PRICE TERMS: FCA SHANGHAI, CNY\n"
            "Legal address: 423800, Republic of Tatarstan\n"
            "(Tatarstan), City District of Naberezhnye Chelny,\n"
            "Naberezhnye Chelny, Motornaya street, building 11A, office 216\n\n"
            "Contract No. F-253/22 dd 12.08.22\n\n"
            "[TABLE_START]\n"
            "ItemFD Part No.OE Part No.DescriptionQuantityUnitUnit Price (CNY)Amount (CNY)PO NumberTrade Mark\n"
            "12336381200313947759TAPPET,VALVE14400PCS19.85285840.00FDPO77F-DIESEL\n"
            " | TOTAL:285840.00\n"
            "[TABLE_END]\n\n"
            "ORIGIN OF GOODS: CHINA\n\n"
            "F-DIESEL CNY BANK ACCOUNT:\n"
            "Name: F-DIESEL POWER CO., LTD\n"
            "Beneficiary bank code: 767290000018\n"
            "A/C: 40807156500610000625\n"
            "Bank: VTB Bank (PJSC) Shanghai Branch\n"
            "SWIFT: VTBRCNSH"
        ),
        "assistant": json.dumps({
            "doc_type": "invoice",
            "doc_type_confidence": 0.98,
            "reasoning": "Document with Invoice No., item table with prices (TAPPET,VALVE), FCA terms, seller/buyer — commercial goods invoice despite 'air freight' in filename. Filename refers to delivery method, not document type.",
            "extracted": {
                "invoice_number": "RU20251121-HY34(7)",
                "invoice_date": "2026-01-15",
                "currency": "CNY",
                "total_amount": 285840.00,
                "incoterms": "FCA",
                "contract_number": "F-253/22",
                "country_origin": "CN",
                "seller": {
                    "name": "F-DIESEL POWER CO., LTD.",
                    "address": "BUILDING 9, NO. 365, LIANYANG ROAD, SONGJIANG DISTRICT, SHANGHAI, CHINA 201613",
                    "country_code": "CN",
                    "tax_number": None
                },
                "buyer": {
                    "name": "JSC «KAMA DIESEL»",
                    "address": "423800, Republic of Tatarstan (Tatarstan), City District of Naberezhnye Chelny, Naberezhnye Chelny, Motornaya street, building 11A, office 216",
                    "country_code": "RU",
                    "tax_number": None
                },
                "items": [
                    {"description": "TAPPET,VALVE", "quantity": 14400, "unit": "PCS", "unit_price": 19.85, "line_total": 285840.00, "country_origin": "CN", "hs_code": None, "gross_weight": None, "net_weight": None}
                ],
                "total_gross_weight": None,
                "total_net_weight": None,
                "total_packages": None,
                "country_origin": "CN"
            }
        }, ensure_ascii=False),
    },
    # ── PACKING LIST (PDF, Vision OCR, 2 items with concatenated table) ──
    {
        "doc_type": "packing_list",
        "user": (
            "Filename: 8_1843 PL.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "# ZED Group Trading Co., Limited\n"
            "FLAT/1005 10/F Ho King Commercial Center, Fa YuenStreet, 2-16, Mong Kok, Hong Kong\n\n"
            "Поставщик / The supplier\n"
            "ZED Group Trading Co., Limited\n"
            "Покупатель / Buyer\n"
            "LLC \"AG-LOGISTIK\"\n"
            "125171, Moscow, Vykovskiy Municipal District, Leningradskoye Road, 16A, Building 3\n"
            "ООО «АГ-ЛОГИСТИК»\n"
            "125171, г. Москва, вн.тер.г. Муниципальный Округ Войковский, ш Ленинградское, д. 16А, стр. 3\n\n"
            "Contract/Dotopb N°AG-ZED-USD/2025/0040 on 23.01.2025\n\n"
            "PACKING LIST for Invoice № AGZED2025/1843/8 on 2025.12.30\n\n"
            "[TABLE_START]\n"
            "ITEMMODELSETQTY (PC)CTNGW (KG)NW (KG)CBM\n"
            "РеменьBattery belt 350*25*1.8 mm-1530225,9824,381,71\n"
            "ПропеллерыGF 1050-3 glassfiber nylon (4pcs/bag)\n"
            "SUPPLIED WITH HARDWARE ELEMENTS IN THE QUANTITY REQUIRED FOR INSTALLATION.\n"
            "153016146,02132,42\n"
            "[TABLE_END]\n\n"
            "Поставщик / The supplier\n"
            "ZED Group Trading Co., Limited"
        ),
        "assistant": json.dumps({
            "doc_type": "packing_list",
            "doc_type_confidence": 0.97,
            "reasoning": "Document titled 'PACKING LIST for Invoice' with item table containing weights, quantities and CBM — packing list. OCR distorted 'Договор' as 'Dotopb' and '№' as 'N°'.",
            "extracted": {
                "total_packages": 2,
                "package_type": None,
                "total_gross_weight": None,
                "total_net_weight": None,
                "country_origin": None,
                "items": [
                    {"description": "Battery belt 350*25*1.8 mm", "quantity": 1530, "packages_count": 2, "package_type": None, "gross_weight": 25.98, "net_weight": 24.38, "country_origin": None},
                    {"description": "GF 1050-3 glassfiber nylon (4pcs/bag)", "quantity": 1530, "packages_count": 16, "package_type": None, "gross_weight": 146.02, "net_weight": 132.42, "country_origin": None},
                ]
            }
        }, ensure_ascii=False),
    },
    # ── PACKING LIST (Excel, detailed multi-item with pallets) ──
    {
        "doc_type": "packing_list",
        "user": (
            "Filename: 555-08118154 PL.xlsx\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "HK SAN GENSHIN INDUSTRY CO., LIMITED\n"
            "PACKING LIST\n"
            "УПАКОВОЧНЫЙ ЛИСТ\n"
            "1. Sender, Address/Отправитель, адрес:\n"
            "HK SAN GENSHIN INDUSTRY CO., LIMITED\n"
            "ROOM 202, NO.1, BLOCK 16 INTEGRITY ZONE I, FUTIAN STREET, YIWU CITY\n"
            "PHONE:+86 18222112831\n"
            "7.Consignee, Address/Получатель, адрес:\n"
            "LLC \"AG-LOGISTIK\"\n"
            "125171, MOSCOW, VOYKOVSKY DISTRICT, LENINGRADSKOE SH, 16A, P. 3.\n"
            "+7 987 279-95-94\n"
            "INN: 9728100494  KPP: 774301001\n\n"
            "| № Item | Goods name model | Q-ty pcs | Q-ty pack | CBM m³ | Net weight, kg | Gross weight, kg |\n"
            "| 1 | PDB FCHUB-12S | 270 | 1 | 0.0248 | 7.6 | 8 |\n"
            "| Total/итого: | | 270 | 1 | 0.0248 | 7.6 | 8 |"
        ),
        "assistant": json.dumps({
            "doc_type": "packing_list",
            "doc_type_confidence": 0.97,
            "reasoning": "Bilingual document titled 'PACKING LIST / УПАКОВОЧНЫЙ ЛИСТ' with sender/consignee, item table with weights and CBM — packing list from Excel file.",
            "extracted": {
                "total_packages": 1,
                "package_type": None,
                "total_gross_weight": 8.0,
                "total_net_weight": 7.6,
                "country_origin": None,
                "items": [
                    {"description": "PDB FCHUB-12S", "quantity": 270, "packages_count": 1, "package_type": None, "gross_weight": 8.0, "net_weight": 7.6, "country_origin": None},
                ]
            }
        }, ensure_ascii=False),
    },
    # ── TRANSPORT_DOC: AWB (air waybill, Vision OCR table format) ──
    {
        "doc_type": "transport_doc",
        "user": (
            "Filename: 876-14813945 AWB.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "[TABLE_START]\n"
            "Shipper's Name and Address\n"
            "HK SAN GENSHIN INDUSTRY CO., LIMITED\n"
            "ROOM 202, NO.1, BLOCK 16 INTEGRITY ZONE I, FUTIAN STREET, YIWU CITY, 322000\n"
            "CONTACT: LIU MING PHONE:+86 18222112831\n"
            "Not Negotiable Air Waybill Sichuan Airlines Issued by\n"
            "Consignee's Name and Address\n"
            "LLC \"AG-LOGISTIK\"\n"
            "125171, MOSCOW, VOYKOVSKY DISTRICT, LENINGRADSKOE SH, 16A,\n"
            "BLDG. VOYKOVSKY MUNICIPAL DISTRICT, LENINGRADSKOE SH, 16A P. 3.\n"
            "CONTACT: SABINA +7 987 279-95-94  INN: 9728100494 KPP: 774301001\n"
            "\"FREIGHT PREPAID\" NOTIFY PARTY: SAME AS CONSIGNEE\n"
            "Airport of Departure HONG KONG\n"
            "To SVO By First Carrier 3U\n"
            "Airport of Destination MOSCOW\n"
            "Flight/Date 3U3960/16DEC 2025\n"
            "Handling Information\n"
            "TOTAL: (9)PACKAGES ONLY.\n"
            "T/S CARGO FM CN TO SVO VIA HKG BY TRUCK **NO S.W.P.M.**\n"
            "CONSIGNEE WILL PICK UP CARGO AT SVO AIRPORT\n"
            "No of Pieces 9  Gross Weight 98.0 K Q\n"
            "CAMERA\n"
            "DIM(CMS):53X30X37(9) VOL: 0.53 CBM\n"
            "Currency HKD  Amount of Insurance NIL\n"
            "876 HKG 14813945\n"
            "[TABLE_END]"
        ),
        "assistant": json.dumps({
            "doc_type": "transport_doc",
            "doc_type_confidence": 0.99,
            "reasoning": "Document is an Air Waybill (AWB) issued by Sichuan Airlines with AWB number, shipper/consignee, flight details and cargo description — air transport document.",
            "extracted": {
                "awb_number": "876-14813945",
                "shipper_name": "HK SAN GENSHIN INDUSTRY CO., LIMITED",
                "shipper_address": "ROOM 202, NO.1, BLOCK 16 INTEGRITY ZONE I, FUTIAN STREET, YIWU CITY, 322000",
                "consignee_name": "ООО \"АГ-ЛОГИСТИК\"",
                "consignee_address": "125171, г. Москва, район Войковский, Ленинградское ш., д. 16А, стр. 3",
                "consignee_inn": "9728100494",
                "consignee_kpp": "772801001",
                "consignee_ogrn": None,
                "departure_airport": "HKG",
                "destination_airport": "SVO",
                "transport_type": 40,
                "flight_number": "3U3960",
                "vehicle_reg_number": None,
                "vessel_name": None,
                "vehicle_country_code": "CN",
                "container_numbers": [],
                "departure_country": "HK"
            }
        }, ensure_ascii=False),
    },
    # ── TRANSPORT_DOC: CMR (international road waybill, .doc format) ──
    {
        "doc_type": "transport_doc",
        "user": (
            "Filename: СМР 030126-11281.doc\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "1\n"
            "Отправитель (наименование, адрес, страна)\n"
            "Absender (Name, Anschrift, Land)\n"
            "Международная товарно-транспортная накладная\n"
            "Internationaler Frachtbrief\n"
            "F-DIESEL POWER CO., LTD\n"
            "1st Floor, Building 9, No. 365, Lianyang Road, Songjiang District, Shanghai, CHINA\n"
            "CMR    030126-11281\n\n"
            "2\n"
            "Получатель (наименование, адрес, страна)\n"
            "Empfänger (Name, Anschrift, Land)\n"
            "АО \"КАМА ДИЗЕЛЬ\"\n"
            "Россия, Татарстан, Набережные Челны, ул. Моторная 11А, офис 216, 423827\n\n"
            "3\n"
            "Место разгрузки груза\n"
            "Место / Ort: пгт. Забайкальск\n"
            "Страна / Land: Россия\n\n"
            "4\n"
            "Место и дата погрузки груза\n"
            "Место / Ort: г. Маньчжурия\n"
            "Страна / Land: Китай\n"
            "Дата / Datum: 04.01.2026 г.\n\n"
            "5\n"
            "Прилагаемые документы\n"
            "Инвойс-спецификация № 1128-1 от 03.01.2026г.\n\n"
            "7 Количество мест: 47\n"
            "8 Род упаковки: ящик\n"
            "9 Наименование груза: Наименование товаров согласно спецификации\n"
            "11 Вес брутто, кг: 14073"
        ),
        "assistant": json.dumps({
            "doc_type": "transport_doc",
            "doc_type_confidence": 0.98,
            "reasoning": "Bilingual document titled 'Международная товарно-транспортная накладная / Internationaler Frachtbrief' with CMR number, shipper/consignee, loading point — international road transport waybill (CMR).",
            "extracted": {
                "awb_number": None,
                "shipper_name": "F-DIESEL POWER CO., LTD",
                "shipper_address": "1st Floor, Building 9, No. 365, Lianyang Road, Songjiang District, Shanghai, CHINA",
                "consignee_name": "АО \"КАМА ДИЗЕЛЬ\"",
                "consignee_address": "Россия, Татарстан, Набережные Челны, ул. Моторная 11А, офис 216, 423827",
                "consignee_inn": "1650142011",
                "consignee_kpp": "165001001",
                "consignee_ogrn": None,
                "departure_airport": None,
                "destination_airport": None,
                "transport_type": 30,
                "flight_number": None,
                "vehicle_reg_number": None,
                "vessel_name": None,
                "vehicle_country_code": None,
                "container_numbers": [],
                "departure_country": "CN"
            }
        }, ensure_ascii=False),
    },
    # ── TRANSPORT_INVOICE: international freight forwarder (CNY, with MAWB ref) ──
    {
        "doc_type": "transport_invoice",
        "user": (
            "Filename: 555-08118154 Invoice.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "# Qing Dao Qi Xin Global Trans Co., Ltd\n\n"
            "QING DAO QI XIN GLOBAL TRANS CO., LTD\n"
            "ROOM306-41,3F, BUILDING 2, XINLIAN TIANDI, NO.176\n"
            "ROAD, LICHANG DISTRICT, QINGDAO, SHANDONG PROVINCE\n\n"
            "## Invoice 555-08118154\n\n"
            "TO: LLC \"AG-LOGISTIK\"\n"
            "125171, Moscow, vn.ter.g. Municipal District Voikovsky,\n"
            "and Leningradskoye, d 16A, building 3\n"
            "INN: 9728100494 KPP: 774301001\n"
            "CONTRACT: AG-QING-T25 on 30.09.2025\n\n"
            "DEPARTURE: GUANGZHOU\n"
            "DEST: SVO\n"
            "Date: 2025-11-23\n"
            "HAWB NO: NONE\n"
            "MAWB: 555-08118154\n"
            "FLIGHT NO.: SU221\n\n"
            "Description Quantity Unit Price Currency Amount\n"
            "Freight fee 1,00 4250,00 CNY 4250,00\n\n"
            "TOTAL CNY 4250,00\n\n"
            "FOUR THOUSAND TWO HUNDRED FIFTY ONLY."
        ),
        "assistant": json.dumps({
            "doc_type": "transport_invoice",
            "doc_type_confidence": 0.98,
            "reasoning": "Invoice from freight forwarder Qing Dao Qi Xin with ONLY 'Freight fee' charge, MAWB reference, flight info and route — transport invoice, NOT a commercial goods invoice.",
            "extracted": {
                "doc_number": "555-08118154",
                "doc_date": "23.11.2025",
                "freight_amount": 4250.00,
                "freight_currency": "CNY",
                "shipper_name": "QING DAO QI XIN GLOBAL TRANS CO., LTD",
                "shipper_address": "ROOM306-41,3F, BUILDING 2, XINLIAN TIANDI, NO.176 ROAD, LICHANG DISTRICT, QINGDAO, SHANDONG PROVINCE",
                "shipper_contact": "Ape TEL:17353411635",
                "consignee_name": "LLC \"AG-LOGISTIK\"",
                "consignee_address": "125171, Moscow, vn.ter.g. Municipal District Voikovsky, and Leningradskoye, d 16A, building 3",
                "consignee_inn": "9728100494",
                "contract_number": "AG-QING-T25",
                "contract_date": "30.09.2025",
                "awb_number": "555-08118154",
                "transport_type": 40,
                "route": "GUANGZHOU - SVO",
                "flight_number": "SU221",
                "bank_details": "VTB Bank(PJSC) Shanghai Branch, Acc: 40807156800610045856"
            }
        }, ensure_ascii=False),
    },
    # ── TRANSPORT_INVOICE: Russian domestic forwarder (CNY, with AWB ref, concatenated table) ──
    {
        "doc_type": "transport_invoice",
        "user": (
            "Filename: Счет_LT104601D1 (1).pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "## Счет на оплату № LT104601D1 от 21.01.2026г.\n\n"
            "Поставщик: ИНН 7729703685, КПП 165001001, ООО \"ЛТ Глобал Форвардинг\",\n"
            "423831, Республика Татарстан, г. Набережные Челны, пр-кт Чулман, д. 50, помещ. 1059\n\n"
            "Покупатель: ИНН 1650142011, КПП 165001001, АО \"КАМА ДИЗЕЛЬ\",\n"
            "423800, Россия, НАБЕРЕЖНЫЕ ЧЕЛНЫ, МОТОРНАЯ УЛ, 3Д. 11А, ОФИС 216\n\n"
            "Основание: Договор № Р-122/17 от 21.06.2017.\n\n"
            "[TABLE_START]\n"
            "№НаименованиетовараКол-воЕд.ЦенаСумма\n"
            "1Организация доставки груза по маршруту Shanghai – Москва (SVO-1), "
            "AWВ 898-80935772, инвойс RU20251121-HY34(7).155000.0055000.00\n"
            "[TABLE_END]\n\n"
            "Итого: 55000.00\n"
            "В том числе НДС: 0.00\n"
            "Всего к оплате: 55000.00\n"
            "Всего наименований 1, на сумму 55000.00 китайских юаней"
        ),
        "assistant": json.dumps({
            "doc_type": "transport_invoice",
            "doc_type_confidence": 0.97,
            "reasoning": "Russian 'Счет на оплату' from logistics company with a single line for freight delivery service (Shanghai-Moscow), AWB reference — transport invoice for freight forwarding, not a goods invoice.",
            "extracted": {
                "doc_number": "LT104601D1",
                "doc_date": "21.01.2026",
                "freight_amount": 55000.00,
                "freight_currency": "CNY",
                "shipper_name": "ООО \"ЛТ Глобал Форвардинг\"",
                "shipper_address": "423831, Республика Татарстан, г. Набережные Челны, пр-кт Чулман, д. 50, помещ. 1059",
                "shipper_contact": None,
                "consignee_name": "АО \"КАМА ДИЗЕЛЬ\"",
                "consignee_address": "423800, Россия, НАБЕРЕЖНЫЕ ЧЕЛНЫ, МОТОРНАЯ УЛ, 3Д. 11А, ОФИС 216",
                "consignee_inn": "1650142011",
                "contract_number": "Р-122/17",
                "contract_date": "21.06.2017",
                "awb_number": "898-80935772",
                "transport_type": 40,
                "route": "Shanghai - Москва (SVO-1)",
                "flight_number": None,
                "bank_details": None
            }
        }, ensure_ascii=False),
    },
    # ── SPECIFICATION: RUB order with EXW Beijing, 13 items ──
    {
        "doc_type": "specification",
        "user": (
            "Filename: 1843 AGZED specification.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "Приложение 1 к Рамочному контракту на поставку № AG-ZED/2025/0029 от 23.01.2025\n"
            "Appendix 1 to the Framework Supply Contract No. AG-ZED/2025/0029 on 23.01.2025\n\n"
            "Заказ № 1843 к Рамочному контракту на поставку № AG-ZED/2025/0029 от 23.01.2025\n"
            "Дата: 30.12.2025\n\n"
            "Статья 1. Цена и общая стоимость Заказа\n"
            "1. Общая стоимость Заказа составляет RUB 279 278 866,20\n\n"
            "Статья 3. Прочие условия\n"
            "3.1. Поставщик поставляет Покупателю Оборудование на условиях поставки "
            "EXW Beijing, согласно ИНКОТЕРМС 2010\n"
            "3.2. Стороны согласовали доставку груза авиакомпанией до аэропорта "
            "Шереметьево г. Москва\n\n"
            "[TABLE]\n"
            "No. | Item | Qty | Unit Price (RUB) | Total (RUB)\n"
            "1 | Pama Frame 10 inch | 5100 | 3723.06 | 18987606.00\n"
            "2 | FC F4 AUS | 5100 | 2978.45 | 15190095.00\n"
            "... (13 items total)\n"
            "Total RUB 279 278 866,20\n\n"
            "Поставщик: ZED Group Trading Co., Limited\n"
            "Покупатель: AG-LOGISTIC LLC"
        ),
        "assistant": json.dumps({
            "doc_type": "specification",
            "doc_type_confidence": 0.97,
            "reasoning": "Appendix to framework supply contract with order number, item table with quantities and prices, delivery terms (EXW Beijing) — specification/order, not an invoice.",
            "extracted": {
                "incoterms": "EXW",
                "delivery_place": "Beijing",
                "items_count": 13,
                "total_amount": 279278866.20,
                "currency": "RUB",
                "total_gross_weight": None,
                "total_net_weight": None
            }
        }, ensure_ascii=False),
    },
    # ── SPECIFICATION: USD order with EXW Hongkong, 16 items ──
    {
        "doc_type": "specification",
        "user": (
            "Filename: 1706 AGZED specification.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "Заказ № 1706/2025 к Рамочному контракту на поставку "
            "№ AG-ZED-USD/2025/0040 от 23.01.2025\n"
            "Дата: 25.09.2025\n\n"
            "Статья 1. Цена и общая стоимость Заказа\n"
            "1. Общая стоимость Заказа составляет 32 495 847,92 USD\n\n"
            "Статья 3. Прочие условия\n"
            "3.1. Поставщик поставляет Покупателю Оборудование на условиях "
            "поставки EXW Hongkong, согласно ИНКОТЕРМС 2010\n"
            "3.2. Стороны согласовали доставку авиакомпанией до Шереметьево, Москва\n\n"
            "[TABLE]\n"
            "No | Name | Unit | Qty | Unit price USD | Total Price USD\n"
            "1 | Мотор Motor 4320 350KV | шт | 56888 | 44.68 | 2541755.84\n"
            "2 | Stack Axisflying argus F7 | шт | 14222 | 122.35 | 1740061.70\n"
            "... (16 items total)\n"
            "Итого / Total USD 32 495 847,92\n\n"
            "Поставщик: ZED Group Trading Co., Limited\n"
            "Покупатель: AG-LOGISTIC LLC"
        ),
        "assistant": json.dumps({
            "doc_type": "specification",
            "doc_type_confidence": 0.97,
            "reasoning": "Order appendix to framework supply contract with item table, unit prices, totals in USD, and delivery terms EXW Hongkong — specification.",
            "extracted": {
                "incoterms": "EXW",
                "delivery_place": "Hongkong",
                "items_count": 16,
                "total_amount": 32495847.92,
                "currency": "USD",
                "total_gross_weight": None,
                "total_net_weight": None
            }
        }, ensure_ascii=False),
    },
    # ── INSURANCE: cargo transportation insurance policy (10-page, key data from p.1) ──
    {
        "doc_type": "insurance",
        "user": (
            "Filename: INSURANCE 112-38539561.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "CARGO TRANSPORTATION INSURANCE POLICY\n\n"
            "POLICY NO.: ANIB90024225QAA4Y53O\n\n"
            "This Policy of Insurance witnesses that China Pacific Property Insurance "
            "Company Limited (hereinafter called \"The Underwriter\") at the request of "
            "the Insured named hereunder...\n\n"
            "(Insured) LLC \"AG-LOGISTIK\"\n\n"
            "Marks & Nos: As par Invoice No, AS PER B/L\n"
            "BL: 112 3533331\n"
            "Quantity: 6 CARTONS\n"
            "Description of Goods: CONTROLLER H30\n\n"
            "Amount Insured: CNY 545,737.50\n"
            "Total Amount Insured: CHINESE YUAN FIVE HUNDRED AND FORTY FIVE THOUSAND "
            "SEVEN HUNDRED AND THIRTY SEVEN AND FIFTY CENTS ONLY\n\n"
            "Rate: AS ARRANGED\n"
            "Premium: AS ARRANGED\n"
            "Per conveyance: MU 726\n"
            "Route From: HONGKONG, CHINA\n\n"
            "Conditions: Covering Air Transportation All Risks\n\n"
            "Claim payable at: MOSCOW\n\n"
            "CHINA PACIFIC PROPERTY INSURANCE CO., LTD.\n"
            "September 11, 2025"
        ),
        "assistant": json.dumps({
            "doc_type": "insurance",
            "doc_type_confidence": 0.99,
            "reasoning": "Document titled 'CARGO TRANSPORTATION INSURANCE POLICY' with policy number, insured party, insured amount, goods description and coverage conditions — cargo insurance policy.",
            "extracted": {
                "policy_number": "ANIB90024225QAA4Y53O",
                "issue_date": "11.09.2025",
                "insured_name": "LLC \"AG-LOGISTIK\"",
                "insured_amount": 545737.50,
                "insured_currency": "CNY",
                "goods_description": "CONTROLLER H30, 6 CARTONS",
                "route": "HONGKONG, CHINA - MOSCOW",
                "transport_type": 40,
                "awb_number": None,
                "bl_number": "112 3533331",
                "insurer_name": "CHINA PACIFIC PROPERTY INSURANCE CO., LTD.",
                "conditions": "Air Transportation All Risks",
                "claim_payable_at": "MOSCOW"
            }
        }, ensure_ascii=False),
    },
    # ── CONFORMITY_DECLARATION: EAEU conformity declaration for thermal camera ──
    {
        "doc_type": "conformity_declaration",
        "user": (
            "Filename: Декларация ЕАЭС N RU Д-CN.РА11.А.8196825.docx\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "ЕВРАЗИЙСКИЙ ЭКОНОМИЧЕСКИЙ СОЮЗ\n"
            "ДЕКЛАРАЦИЯ О СООТВЕТСТВИИ\n"
            "Заявитель: ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ \"АГ-ЛОГИСТИК\", "
            "ОГРН: 1237700467652\n"
            "заявляет, что Видеоаппаратура промышленная: "
            "ТЕПЛОВИЗИОННАЯ КАМЕРА НОЧНОГО ВИДЕНИЯ, модель RS65-N.\n"
            "Изготовитель: SHENZHEN DYNAMICS TECHNOLOGY CO., LTD., Китай\n"
            "Коды ТН ВЭД ЕАЭС: 8525831900\n"
            "Партия - 1700 штук, Инвойс № AGZED2025/1706/31 от 25.09.2025, "
            "Контракт № AG-ZED-USD/2025/0040 от 23.01.2025\n"
            "Соответствует требованиям ТР ТС 020/2011\n"
            "Протокол DT-2211 выдан 17.07.2025; Схема: 2д\n"
            "Регистрационный номер: ЕАЭС N RU Д-CN.РА11.А.81968/25\n"
            "Дата регистрации: 19.12.2025"
        ),
        "assistant": json.dumps({
            "doc_type": "conformity_declaration",
            "doc_type_confidence": 0.99,
            "reasoning": "EAEU conformity declaration with registration number, applicant, product description, HS code, and technical regulation reference.",
            "extracted": {
                "declaration_number": "ЕАЭС N RU Д-CN.РА11.А.81968/25",
                "registration_date": "19.12.2025",
                "valid_until": None,
                "applicant_name": "ООО \"АГ-ЛОГИСТИК\"",
                "applicant_ogrn": "1237700467652",
                "product_name": "Видеоаппаратура промышленная: ТЕПЛОВИЗИОННАЯ КАМЕРА НОЧНОГО ВИДЕНИЯ, модель RS65-N",
                "manufacturer_name": "SHENZHEN DYNAMICS TECHNOLOGY CO., LTD.",
                "manufacturer_country": "CN",
                "hs_code": "8525831900",
                "quantity": 1700,
                "quantity_unit": "штук",
                "invoice_number": "AGZED2025/1706/31",
                "invoice_date": "25.09.2025",
                "contract_number": "AG-ZED-USD/2025/0040",
                "contract_date": "23.01.2025",
                "technical_regulation": "ТР ТС 020/2011 Электромагнитная совместимость технических средств",
                "conformity_scheme": "2д",
                "test_protocol_number": "DT-2211",
                "test_protocol_date": "17.07.2025",
                "test_lab_name": "Испытательная лаборатория SHENZHEN DYNAMICS TECHNOLOGY CO., LTD."
            }
        }, ensure_ascii=False),
    },
    # ── CONFORMITY_DECLARATION: EAEU conformity declaration for flight controller ──
    {
        "doc_type": "conformity_declaration",
        "user": (
            "Filename: Декларация ЕАЭС N RU Д-CN.РА01.А.1763526.docx\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "ЕВРАЗИЙСКИЙ ЭКОНОМИЧЕСКИЙ СОЮЗ\n"
            "ДЕКЛАРАЦИЯ О СООТВЕТСТВИИ\n"
            "Заявитель: ООО \"АГ-ЛОГИСТИК\", ОГРН: 1237700467652\n"
            "заявляет, что Контроллеры на напряжение до 50 В: "
            "программируемый контроллер - стек полетного контроллера, "
            "модель HAKRC 70AF4.\n"
            "Изготовитель: SHENZHEN HAIKE TECHNOLOGY CO., Китай\n"
            "Коды ТН ВЭД ЕАЭС: 8537109100\n"
            "Партия - 1600 штук, Инвойс № AGZED20251112/1809 от 11.12.2025, "
            "Контракт № AG-ZED/2025/0029 от 23.01.2025\n"
            "Соответствует требованиям ТР ТС 020/2011\n"
            "Протокол Н/850 выдан 07.11.2025; Схема: 2д\n"
            "Регистрационный номер: ЕАЭС N RU Д-CN.РА01.А.17635/26\n"
            "Дата регистрации: 19.01.2026"
        ),
        "assistant": json.dumps({
            "doc_type": "conformity_declaration",
            "doc_type_confidence": 0.99,
            "reasoning": "EAEU conformity declaration — contains standard registration number, applicant, manufacturer, product with HS code, and ТР ТС reference.",
            "extracted": {
                "declaration_number": "ЕАЭС N RU Д-CN.РА01.А.17635/26",
                "registration_date": "19.01.2026",
                "valid_until": None,
                "applicant_name": "ООО \"АГ-ЛОГИСТИК\"",
                "applicant_ogrn": "1237700467652",
                "product_name": "Контроллеры на напряжение до 50 В: программируемый контроллер - стек полетного контроллера, модель HAKRC 70AF4",
                "manufacturer_name": "SHENZHEN HAIKE TECHNOLOGY CO.",
                "manufacturer_country": "CN",
                "hs_code": "8537109100",
                "quantity": 1600,
                "quantity_unit": "штук",
                "invoice_number": "AGZED20251112/1809",
                "invoice_date": "11.12.2025",
                "contract_number": "AG-ZED/2025/0029",
                "contract_date": "23.01.2025",
                "technical_regulation": "ТР ТС 020/2011 Электромагнитная совместимость технических средств",
                "conformity_scheme": "2д",
                "test_protocol_number": "Н/850",
                "test_protocol_date": "07.11.2025",
                "test_lab_name": "Испытательная лаборатория SHENZHEN HAIKE TECHNOLOGY CO."
            }
        }, ensure_ascii=False),
    },
    # ── TECH_DESCRIPTION: table format (Vision OCR, concatenated columns) ──
    {
        "doc_type": "tech_description",
        "user": (
            "Filename: техоп ELRS 433mhz.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "## Общество с ограниченной ответственностью «АГ-Логистик»\n\n"
            "125171, г. Москва, вн.тер.г. Муниципальный Округ Войковский, "
            "ш Ленинградское, д. 16А, стр. 3 ИНН 9728100494 КПП 774301001 ОГРН 1237700467652\n\n"
            "## Техническое описание\n\n"
            "Исх. № 1670/2025-5 от 13.10.2025\n\n"
            "[TABLE_START]\n"
            "ОписаниеПроизводительТорговая маркаМодельАртикул\n"
            "ПРИЕМНИК ELRS 433 MHZ ПРЕДСТАВЛЯЕТ СОБОЙ МИКРОСХЕМУ КВАДРАТНОЙ ФОРМЫ "
            "В КОМПЛЕКТЕ С ВСЕНАПРАВЛЕННОЙ Т-ОБРАЗНОЙ АНТЕННОЙ. ПРЕДНАЗНАЧЕН ДЛЯ ПРИЕМА "
            "ДАННЫХ НА РАЗЛИЧНЫХ РАДИОУПРАВЛЯЕМЫХ МОДЕЛЯХ. ДИАПАЗОН ПОДДЕРЖИВАЕМЫХ "
            "ЧАСТОТ 420-450 МГЦ. ВХОДНОЕ НАПРЯЖЕНИЕ: 4.5-5.5 В."
            "Quzhou Yunduan Intelligent Technology Co., Ltd."
            "HAPPYMODELELRS 433 MHZОТСУТСТВУЕТ\n"
            "[TABLE_END]\n\n"
            "Генеральный директор Газизов А. Р."
        ),
        "assistant": json.dumps({
            "doc_type": "tech_description",
            "doc_type_confidence": 0.97,
            "reasoning": "Document titled 'Техническое описание' with product specifications, manufacturer, brand and model in a table — technical product description for customs.",
            "extracted": {
                "products": [
                    {
                        "name": "Приемник ELRS 433 MHz",
                        "purpose": "Приём данных на радиоуправляемых моделях",
                        "materials": None,
                        "specifications": "Диапазон частот 420-450 МГц. Входное напряжение: 4.5-5.5 В. Микросхема квадратной формы с всенаправленной Т-образной антенной.",
                        "application_area": "Радиоуправляемые модели",
                        "operating_conditions": None
                    }
                ]
            }
        }, ensure_ascii=False),
    },
    # ── TECH_DESCRIPTION: free text format (no table, detailed specs) ──
    {
        "doc_type": "tech_description",
        "user": (
            "Filename: ТЕХ ОПИСАНИЕ 1581-2025.pdf\n\n"
            "Determine the document type and extract data.\n\n"
            "FULL DOCUMENT TEXT:\n"
            "125171, г. Москва, вн.тер.г. Муниципальный Округ Войковский, "
            "ш Ленинградское, д. 16А, стр. 3 ИНН 9728100494 КПП 774301001 ОГРН 1237700467652\n\n"
            "Исх. №1581/2025 от 15.09.2025\n\n"
            "В таможенные органы\n\n"
            "## Техническое описание\n\n"
            "ПУЛЬТ ДИСТАНЦИОННОГО УПРАВЛЕНИЯ SKYDROID H30 ИСПОЛЬЗУЕТСЯ В РАДИОМОДЕЛИРОВАНИИ "
            "ДЛЯ УПРАВЛЕНИЯ АВИАМОДЕЛЯМИ, ГРАЖДАНСКОГО НАЗНАЧЕНИЯ, ПРЕДНАЗНАЧЕННЫМИ ДЛЯ "
            "ОБСЛЕДОВАНИЯ И МОНИТОРИНГА ПРОМЫШЛЕННЫХ, СЕЛЬСКОХОЗЯЙСТВЕННЫХ И ПРИРОДНЫХ ОБЪЕКТОВ, "
            "ПРЕДОТВРАЩЕНИЯ И ВЫЯВЛЕНИЯ ПОЖАРОВ, НАВОДНЕНИЙ И ТЕХНОГЕННЫХ АВАРИЙНЫХ СИТУАЦИЙ. "
            "ПОСТАВЛЯЕТСЯ В КОМПЛЕКТНОМ ВИДЕ В КЕЙСЕ С ЗАПАСНЫМИ ДЕТАЛЯМИ, АНТЕННАМИ, "
            "ПРОВОДКАМИ ПОДКЛЮЧЕНИЯ, БЛОКОМ ПИТАНИЯ ДЛЯ ЗАРЯДКИ ОТ СЕТИ ЭЛЕКТРИЧЕСТВА, "
            "ЛИТИЙ-ИОННЫМ АККУМУЛЯТОРОМ. РАБОЧАЯ ЧАСТОТА ПУЛЬТА: 2.4 ГГЦ, МОЩНОСТЬ ПЕРЕДАТЧИКА "
            "РЕГУЛИРУЕМАЯ, НЕ БОЛЕЕ 10 МВТ, РАБОЧЕЕ НОМИНАЛЬНОЕ НАПРЯЖЕНИЕ: 4.2 В. "
            "ЖК-ДИСПЛЕЙ ПУЛЬТА: 10.1\" С РАЗРЕШЕНИЕМ 1920X1200. "
            "НЕ ОСНАЩЕН СИСТЕМОЙ НАВИГАЦИИ GPS, ФУНКЦИИ ШИФРОВАНИЯ (КРИПТОГРАФИИ) ОТСУТСТВУЮТ\n\n"
            "ПРОИЗВОДИТЕЛЬ: QUANZHOU YUNZHUO TECHNOLOGY CO.,LTD МАРКА: SKYDROID МОДЕЛЬ: SKYDROID H30"
        ),
        "assistant": json.dumps({
            "doc_type": "tech_description",
            "doc_type_confidence": 0.98,
            "reasoning": "Document addressed 'В таможенные органы' titled 'Техническое описание' with detailed product specs, frequencies, display specs, and explicit notes about GPS/encryption absence — technical description for customs declaration.",
            "extracted": {
                "products": [
                    {
                        "name": "Пульт дистанционного управления SKYDROID H30",
                        "purpose": "Управление авиамоделями гражданского назначения для обследования и мониторинга промышленных, сельскохозяйственных и природных объектов",
                        "materials": None,
                        "specifications": "Рабочая частота: 2.4 ГГц. Мощность передатчика: регулируемая, не более 10 мВт. Напряжение: 4.2 В. ЖК-дисплей: 10.1\" 1920x1200. Не оснащен GPS, функции шифрования отсутствуют.",
                        "application_area": "Радиомоделирование, мониторинг промышленных и природных объектов, предотвращение пожаров и наводнений",
                        "operating_conditions": "Комплект: кейс, запасные детали, антенны, проводки, блок питания, литий-ионный аккумулятор"
                    }
                ]
            }
        }, ensure_ascii=False),
    },
]


def build_fewshot_messages(doc_type: str | None = None) -> list[dict]:
    """Build few-shot messages for LLM prompt.

    Args:
        doc_type: If provided, return only examples of this type (max 2).
                  If None (fallback mode), return 1 example per type (max 3 diverse).
    """
    messages = []

    if doc_type:
        matching = [ex for ex in FEWSHOT_EXAMPLES if ex["doc_type"] == doc_type]
        selected = matching[:2]
    else:
        seen_types: set[str] = set()
        selected = []
        for ex in FEWSHOT_EXAMPLES:
            if ex["doc_type"] not in seen_types and len(selected) < 3:
                selected.append(ex)
                seen_types.add(ex["doc_type"])

    for ex in selected:
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": ex["assistant"]})
    return messages
