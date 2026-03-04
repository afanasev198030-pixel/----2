"""
Mapping of 29 EEC customs classifiers to internal classifier_type values.

Each entry maps an internal type name to the portal.eaeunion.org metadata:
- guid: SharePoint list GUID (stable identifier for the classifier)
- title: Official Russian name
- code_field: OData field name containing the classifier code
- name_field: OData field name containing the Russian name
- extra_fields: additional fields to store in Classifier.meta (optional)

Field names verified against production API on 2026-03-04.
"""

EEC_CLASSIFIERS: dict[str, dict] = {
    # 1. Классификатор видов таможенных процедур (графы 1, 37)
    "procedure": {
        "guid": "5cfe1e17-c568-48f0-ac53-61a2a8cc5fb6",
        "title": "Классификатор видов таможенных процедур",
        "code_field": "KindOfCustomsProcedure_Code",
        "name_field": "KindOfCustomsProcedure_Name",
    },
    # 2. Классификатор особенностей перемещения товаров (графа 37 подр. 2)
    "movement_feature": {
        "guid": "35109f0a-7ea3-4717-a329-6c1f1940340b",
        "title": "Классификатор особенностей перемещения товаров",
        "code_field": "FeatureOfGoodsRelocation_Code",
        "name_field": "FeatureOfGoodsRelocation_Name",
    },
    # 3. Классификатор видов транспорта и транспортировки товаров (графы 25, 26, 30)
    "transport_type": {
        "guid": "11aa6f3e-866d-4ccb-8653-49ec8fedb55e",
        "title": "Классификатор видов транспорта и транспортировки товаров",
        "code_field": "KindOfTransportAndTransportationGoods_Code",
        "name_field": "KindOfTransportAndTransportationGoods_Name",
    },
    # 4. Классификатор методов определения таможенной стоимости (графа 43)
    "mos_method": {
        "guid": "e201950c-219b-4680-bb15-bb3f463b9f94",
        "title": "Классификатор методов определения таможенной стоимости",
        "code_field": "MethodOfDetermineCustomsValues_Code",
        "name_field": "MethodOfDetermineCustomsValues_Name",
    },
    # 5. Классификатор результатов контроля таможенной стоимости (графа 43 подр. 2)
    "customs_value_control": {
        "guid": "34062348-fd9b-48ed-ad99-6439f01eae6f",
        "title": "Классификатор результатов контроля таможенной стоимости",
        "code_field": "CustomsValuesDecision_Code",
        "name_field": "CustomsValuesDecision_Name",
    },
    # 6. Классификатор особенностей таможенного декларирования товаров (графа 7)
    "declaration_feature": {
        "guid": "58479078-d8b1-424e-924e-464b92a532b9",
        "title": "Классификатор особенностей таможенного декларирования товаров",
        "code_field": "CustomsGoodsAvowalFeature_Code",
        "name_field": "CustomsGoodsAvowalFeature_Name",
    },
    # 7. Разделы классификатора видов документов и сведений
    "doc_type_section": {
        "guid": "d9c132c9-dc24-473a-8d12-d7209bf3406a",
        "title": "Разделы классификатора видов документов и сведений",
        "code_field": "KindOfAvowalDocumentsAndInformationSection_Code",
        "name_field": "KindOfAvowalDocumentsAndInformationSection_Name",
    },
    # 8. Классификатор видов документов и сведений (графа 44, 54)
    "doc_type": {
        "guid": "3f65795d-673f-4122-a4f4-d636e3b662b6",
        "title": "Классификатор видов документов и сведений",
        "code_field": "KindOfAvowalDocumentsAndInformation_Code",
        "name_field": "KindOfAvowalDocumentsAndInformation_Name",
    },
    # 9. Классификатор особенностей уплаты платежей (графа 47 СП)
    "payment_feature": {
        "guid": "c3a33c49-8f8a-486f-81ee-09eb98198293",
        "title": "Классификатор особенностей уплаты платежей",
        "code_field": "FeatureOfPaymentDuesToCustomAuthorities_Code",
        "name_field": "FeatureOfPaymentDuesToCustomAuthorities_Name",
    },
    # 10. Классификатор способов уплаты платежей (графа B элемент 6)
    "payment_method": {
        "guid": "63a22273-6a7a-4165-989a-e0411ad4158f",
        "title": "Классификатор способов уплаты платежей",
        "code_field": "MethodOfPaymentDuesToCustomAuthorities_Code",
        "name_field": "MethodOfPaymentDuesToCustomAuthorities_Name",
    },
    # 11. Классификатор видов груза, упаковки и упаковочных материалов (графа 31)
    "package_type": {
        "guid": "0cb45f60-0882-429b-a0c0-c0a893b9a572",
        "title": "Классификатор видов груза, упаковки и упаковочных материалов",
        "code_field": "TypeOfCargoesAndPackingMatherials_Code",
        "name_field": "TypeOfCargoesAndPackingMatherials_Name",
    },
    # 12. Классификатор условий поставки (графа 20, 31)
    "incoterms": {
        "guid": "c40f727f-8502-4023-96e8-f156c29e7db3",
        "title": "Классификатор условий поставки",
        "code_field": "ConditionOfDelivery_Code",
        "name_field": "ConditionOfDelivery_Name",
    },
    # 13. Классификатор решений, принимаемых таможенными органами (графа C)
    "customs_decision": {
        "guid": "ca5e1b77-da79-4324-82ec-9117b7f6ba1e",
        "title": "Классификатор решений, принимаемых таможенными органами",
        "code_field": "CustomAuthoritiesDecision_Code",
        "name_field": "CustomAuthoritiesDecision_Name",
    },
    # 14. Классификатор единиц измерения (графа 41, 31)
    "measurement_unit": {
        "guid": "8d74669a-2cc0-4064-9f50-507e3c8ec714",
        "title": "Классификатор единиц измерения",
        "code_field": "UnitOfMeasure_Code",
        "name_field": "UnitOfMeasure_Name",
    },
    # 15. Классификатор мер обеспечения соблюдения процедуры таможенного транзита
    "transit_measure": {
        "guid": "0384e94c-808a-47c6-b059-72c5bfa9c8bc",
        "title": "Классификатор мер обеспечения соблюдения процедуры таможенного транзита",
        "code_field": "MeasureOfEnforcementCustomsTransitProcedure_Code",
        "name_field": "MeasureOfEnforcementCustomsTransitProcedure_Name",
    },
    # 16. Классификатор способов обеспечения исполнения обязанности по уплате пошлин (графа 52)
    "guarantee_type": {
        "guid": "86cbbdee-38e3-4b05-8955-ab2fcf5f86a2",
        "title": "Классификатор способов обеспечения исполнения обязанности по уплате пошлин",
        "code_field": "MethodOfEnforcementCustomDuty_Code",
        "name_field": "MethodOfEnforcementCustomDuty_Name",
    },
    # 17. Классификатор видов перемещения товаров (таможенный транзит)
    "transit_movement": {
        "guid": "e2a50928-1b5e-4a46-9b30-ee9d451843f3",
        "title": "Классификатор видов перемещения товаров (таможенный транзит)",
        "code_field": "KindOfTransportationInCustomsTransitProcedure_Code",
        "name_field": "KindOfTransportationInCustomsTransitProcedure_Name",
    },
    # 18. Классификатор доп. характеристик при исчислении пошлин
    "additional_chars": {
        "guid": "6cc89e08-9a32-4564-846d-11e7e106701f",
        "title": "Классификатор доп. характеристик при исчислении пошлин",
        "code_field": "AdditinalDescAndParamForCustomDutyCalc_Code",
        "name_field": "AdditinalDescAndParamForCustomDutyCalc_ShortName",
    },
    # 19. Разделы классификатора льгот по уплате таможенных платежей
    "preference_section": {
        "guid": "cfc1332f-4b85-4034-b716-0ad86933a294",
        "title": "Разделы классификатора льгот по уплате таможенных платежей",
        "code_field": "CustomsPreferentialDutySection_Code",
        "name_field": "CustomsPreferentialDutySection_Name",
    },
    # 20. Классификатор льгот по уплате таможенных платежей (графа 36)
    "preference": {
        "guid": "796a4142-4433-4093-bb9d-2e0b3ef9bbbb",
        "title": "Классификатор льгот по уплате таможенных платежей",
        "code_field": "CustomsPreferentialDuty_Code",
        "name_field": "CustomsPreferentialDuty_Name",
    },
    # 21. Разделы классификатора видов налогов и сборов
    "tax_type_section": {
        "guid": "f608ad58-3845-4847-87cf-a261004279ab",
        "title": "Разделы классификатора видов налогов и сборов",
        "code_field": "KindOfDuesAndFeesToCustomAuthoritiesSection_Code",
        "name_field": "KindOfDuesAndFeesToCustomAuthoritiesSection_Name",
    },
    # 22. Классификатор видов налогов, сборов и иных платежей (графа 47, 48, B)
    "tax_type": {
        "guid": "7d3c6521-ec67-4dc5-8206-db4372ee5262",
        "title": "Классификатор видов налогов, сборов и иных платежей",
        "code_field": "KindOfDuesAndFeesToCustomAuthorities_Code",
        "name_field": "KindOfDuesAndFeesToCustomAuthorities_Name",
    },
    # 23. Классификатор стран мира (графы 2, 8, 9, 11, 14, 15, 16, 17, 18, 21, 34, 44)
    "country": {
        "guid": "e931ca71-4068-4e2b-846f-aea6f3b2fa31",
        "title": "Классификатор стран мира",
        "code_field": "Country_Code",
        "name_field": "Country_Name",
    },
    # 24. Классификатор валют (графа 22, B)
    "currency": {
        "guid": "49bfd785-0c19-4235-abd3-2d14dabf05a3",
        "title": "Классификатор валют",
        "code_field": "Currency_Code",
        "name_field": "Currency_Name",
        "extra_fields": {"literal_code": "Currency_LiteralCode"},
    },
    # 25. Разделы классификатора мест нахождения товаров
    "goods_location_section": {
        "guid": "d49fdcc8-02c6-4ac4-962d-864690ce7828",
        "title": "Разделы классификатора мест нахождения товаров",
        "code_field": "CentreOfLocationGoodsSection_Code",
        "name_field": "CentreOfLocationGoodsSection_Name",
    },
    # 26. Классификатор мест нахождения товаров (графа 30)
    "goods_location": {
        "guid": "ea505554-05af-4888-a9ad-c02106dff1d3",
        "title": "Классификатор мест нахождения товаров",
        "code_field": "CentreOfLocationGoods_Code",
        "name_field": "CentreOfLocationGoods_Name",
    },
    # 27. Классификатор типов ТС международной перевозки
    "vehicle_type": {
        "guid": "4f0df6fa-5e12-441e-af50-7a4909d5c0e3",
        "title": "Классификатор типов ТС международной перевозки",
        "code_field": "TypeVehicle_Code",
        "name_field": "TypeVehicle_Name",
    },
    # 28. Классификатор марок дорожных ТС
    "vehicle_brand": {
        "guid": "ccd32a86-2de5-41c0-9759-01be44e90db5",
        "title": "Классификатор марок дорожных ТС",
        "code_field": "MakeOfCar_Code",
        "name_field": "MakeOfCar_Name",
    },
    # 29. Классификатор видов специальных упрощений
    "special_simplification": {
        "guid": "e468745d-6f88-4325-9ff0-81e900700084",
        "title": "Классификатор видов специальных упрощений",
        "code_field": "EspecialSimplification_Code",
        "name_field": "EspecialSimplification_Name",
    },
}

EEC_PORTAL_BASE_URL = "https://portal.eaeunion.org/sites/odata/_api/web/lists"
EEC_PORTAL_CONTEXT_URL = "https://portal.eaeunion.org/sites/odata/_api/contextinfo"
