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
  spot_required?: boolean;
  spot_status?: 'none' | 'required' | 'created' | 'paid' | 'qr_received';
  spot_qr_file_key?: string;
  spot_amount?: number;
  submitted_at?: string;
  place_and_date?: string;
  evidence_map?: Record<string, FieldEvidence>;
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
  risk_score?: number;
  risk_flags?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

export type DocumentType =
  | 'contract'
  | 'invoice'
  | 'packing_list'
  | 'transport_doc'
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

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}
