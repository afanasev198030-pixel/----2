export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  role: 'client' | 'ved_specialist' | 'head' | 'accountant' | 'lawyer' | 'broker' | 'admin';
  company_id: string;
  is_active: boolean;
  created_at: string;
}

export interface Company {
  id: string;
  name: string;
  inn: string;
  kpp?: string;
  ogrn?: string;
  address?: string;
  country_code?: string;
  company_type?: string;
  broker_license?: string;
  contact_email?: string;
  contact_phone?: string;
  created_at: string;
}

export interface Counterparty {
  id: string;
  type: 'seller' | 'buyer' | 'importer' | 'declarant';
  name: string;
  country_code?: string;
  registration_number?: string;
  tax_number?: string;
  address?: string;
  company_id?: string;
  ogrn?: string;
  kpp?: string;
  postal_code?: string;
  region?: string;
  city?: string;
  street?: string;
  building?: string;
  room?: string;
  phone?: string;
  email?: string;
}

export type DeclarationStatus =
  | 'draft'
  | 'checking_lvl1'
  | 'checking_lvl2'
  | 'final_check'
  | 'signed'
  | 'sent'
  | 'registered'
  | 'docs_requested'
  | 'inspection'
  | 'released'
  | 'rejected';

export interface AiIssue {
  code: string;
  severity: string;
  field?: string;
  blocking: boolean;
  message: string;
  source?: string;
  resolved?: boolean;
}

export interface EvidenceMapEntry {
  source: string;
  document_id?: string;
  confidence?: number;
  raw_value?: string;
  value_preview?: string;
  graph?: number;
  note?: string;
}

export interface PreSendCheck {
  code: string;
  severity: string;
  field?: string;
  blocking: boolean;
  message: string;
}

export interface PreSendResult {
  passed: boolean;
  checks: PreSendCheck[];
  blocking_count: number;
}

export interface DeclarationLogEntry {
  id: string;
  action: string;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  created_at?: string | null;
  user_id?: string | null;
}

export interface DeclarationStatusHistoryEntry {
  id: string;
  status_code: DeclarationStatus | string;
  status_text?: string | null;
  source?: string | null;
  customs_post_code?: string | null;
  created_at?: string | null;
}

export interface Declaration {
  id: string;
  number_internal?: string;
  type_code?: string;
  status: DeclarationStatus;
  company_id: string;
  sender_counterparty_id?: string;
  receiver_counterparty_id?: string;
  financial_counterparty_id?: string;
  declarant_counterparty_id?: string;
  special_ref_code?: string;
  country_dispatch_code?: string;
  country_origin_name?: string;
  country_destination_code?: string;
  transport_at_border?: string;
  container_info?: string;
  incoterms_code?: string;
  transport_on_border?: string;
  currency_code?: string;
  total_invoice_value?: number;
  exchange_rate?: number;
  deal_nature_code?: string;
  deal_specifics_code?: string;
  transport_type_border?: string;
  transport_type_inland?: string;
  loading_place?: string;
  financial_info?: string;
  total_customs_value?: number;
  total_gross_weight?: number;
  total_net_weight?: number;
  total_items_count?: number;
  total_packages_count?: number;
  forms_count?: number;
  specifications_count?: number;
  customs_office_code?: string;
  warehouse_name?: string;
  trading_country_code?: string;
  declarant_inn_kpp?: string;
  declarant_ogrn?: string;
  declarant_phone?: string;
  delivery_place?: string;
  transport_on_border_id?: string;
  entry_customs_code?: string;
  goods_location?: string;
  payment_deferral?: string;
  warehouse_requisites?: string;
  transit_offices?: string;
  destination_office_code?: string;
  country_first_destination_code?: string;
  guarantee_info?: string;
  signatory_name?: string;
  signatory_position?: string;
  signatory_id_doc?: string;
  signatory_cert_number?: string;
  signatory_power_of_attorney?: string;
  broker_registry_number?: string;
  broker_contract_number?: string;
  broker_contract_date?: string;
  invoice_number?: string;
  invoice_date?: string;
  contract_number?: string;
  contract_date?: string;
  transport_reg_number?: string;
  transport_nationality_code?: string;
  goods_location_code?: string;
  goods_location_customs_code?: string;
  goods_location_zone_id?: string;
  spot_required?: boolean;
  spot_status?: 'none' | 'required' | 'created' | 'paid' | 'qr_received';
  spot_qr_file_key?: string;
  spot_amount?: number;
  submitted_at?: string;
  place_and_date?: string;
  ai_issues?: AiIssue[];
  evidence_map?: Record<string, EvidenceMapEntry>;
  ai_confidence?: number;
  created_by?: string;
  created_at: string;
  updated_at?: string;
}

export interface FieldEvidence {
  value_preview?: string;
  source?: string;
  confidence?: number;
  graph?: number;
  note?: string;
}

export interface DeclarationItem {
  id: string;
  declaration_id: string;
  item_no: number;
  description?: string;
  package_count?: number;
  package_type?: string;
  commercial_name?: string;
  manufacturer?: string;
  trademark?: string;
  model_name?: string;
  article_number?: string;
  hs_code?: string;
  hs_code_letters?: string;
  hs_code_extra?: string;
  country_origin_code?: string;
  country_origin_pref_code?: string;
  gross_weight?: number;
  preference_code?: string;
  procedure_code?: string;
  net_weight?: number;
  quota_info?: string;
  prev_doc_ref?: string;
  additional_unit?: string;
  additional_unit_qty?: number;
  unit_price?: number;
  mos_method_code?: string;
  customs_value_rub?: number;
  statistical_value_usd?: number;
  documents_json?: Array<{code: string; marker: string; number: string; date: string}>;
  package_type_code?: string;
  package_marks?: string;
  additional_unit_code?: string;
  risk_score?: number;
  risk_flags?: Record<string, unknown>;
  drift_status?: boolean;
  historical_hs_code?: string;
  historical_usage_count?: number;
  drift_similarity?: number;
  drift_message?: string;
  created_at: string;
  updated_at?: string;
}

export type DocumentType =
  | 'contract'
  | 'invoice'
  | 'packing_list'
  | 'transport_doc'
  | 'transport_invoice'
  | 'application_statement'
  | 'specification'
  | 'tech_description'
  | 'certificate_origin'
  | 'license'
  | 'permit'
  | 'sanitary'
  | 'veterinary'
  | 'phytosanitary'
  | 'other';

export interface Document {
  id: string;
  declaration_id?: string;
  item_id?: string;
  doc_type: DocumentType;
  file_key: string;
  original_filename: string;
  mime_type?: string;
  file_size?: number;
  issued_at?: string;
  issuer?: string;
  doc_number?: string;
  parsed_data?: Record<string, unknown>;
  linked_fields?: string[];
  created_at: string;
}

export interface Classifier {
  id: string;
  classifier_type: string;
  code: string;
  name_ru: string;
  name_en?: string;
  parent_code?: string;
  meta?: Record<string, unknown>;
  is_active: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ItemDocument {
  id: string;
  declaration_item_id: string;
  doc_kind_code: string;
  doc_number?: string;
  doc_date?: string;
  doc_validity_date?: string;
  authority_name?: string;
  country_code?: string;
  edoc_code?: string;
  archive_doc_id?: string;
  line_id?: string;
  presenting_kind_code?: string;
  sort_order: number;
  created_at?: string;
}

export interface ItemPrecedingDoc {
  id: string;
  declaration_item_id: string;
  doc_kind_code?: string;
  doc_name?: string;
  customs_office_code?: string;
  doc_date?: string;
  customs_doc_number?: string;
  other_doc_number?: string;
  other_doc_date?: string;
  goods_number?: number;
  line_id?: string;
  sort_order: number;
  created_at?: string;
}

export interface CustomsValueItem {
  id: string;
  customs_value_declaration_id: string;
  declaration_item_id: string;
  item_no: number;
  hs_code?: string;
  invoice_price_foreign?: number;
  invoice_price_national?: number;
  indirect_payments?: number;
  base_total?: number;
  broker_commission?: number;
  packaging_cost?: number;
  raw_materials?: number;
  tools_molds?: number;
  consumed_materials?: number;
  design_engineering?: number;
  license_payments?: number;
  seller_income?: number;
  transport_cost?: number;
  loading_unloading?: number;
  insurance_cost?: number;
  additions_total?: number;
  construction_after_import?: number;
  inland_transport?: number;
  duties_taxes?: number;
  deductions_total?: number;
  customs_value_national?: number;
  customs_value_usd?: number;
  currency_conversions?: Array<Record<string, unknown>>;
  created_at?: string;
  updated_at?: string;
}

export interface CustomsValueDeclaration {
  id: string;
  declaration_id: string;
  form_type: string;
  related_parties: boolean;
  related_price_impact: boolean;
  related_verification: boolean;
  restrictions: boolean;
  price_conditions: boolean;
  ip_license_payments: boolean;
  sale_depends_on_income: boolean;
  income_to_seller: boolean;
  additional_docs?: string;
  additional_data?: string;
  filler_name?: string;
  filler_date?: string;
  filler_document?: string;
  filler_contacts?: string;
  filler_position?: string;
  transport_carrier_name?: string;
  transport_destination?: string;
  usd_exchange_rate?: number;
  created_at?: string;
  updated_at?: string;
  items: CustomsValueItem[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}
