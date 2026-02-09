import axios from 'axios';

// AI service — through CRA proxy (setupProxy.js) or nginx
const AI_BASE = '/api/v1/ai';

const aiClient = axios.create({
  baseURL: AI_BASE,
  headers: { 'Content-Type': 'application/json' },
});

export interface HSSuggestion {
  hs_code: string;
  name_ru: string;
  confidence: number;
}

export interface RiskItem {
  rule_code: string;
  severity: string;
  message: string;
  recommendation: string;
}

export interface RiskAssessment {
  overall_risk_score: number;
  overall_severity: string;
  risks: RiskItem[];
}

export const classifyHS = async (description: string, countryOrigin?: string, unitPrice?: number): Promise<HSSuggestion[]> => {
  const response = await aiClient.post<{ suggestions: HSSuggestion[] }>('/classify-hs', {
    description,
    country_origin: countryOrigin || null,
    unit_price: unitPrice || null,
  });
  return response.data.suggestions;
};

export const assessRisk = async (items: any[], totalCustomsValue?: number): Promise<RiskAssessment> => {
  const response = await aiClient.post<RiskAssessment>('/assess-risk', {
    items,
    total_customs_value: totalCustomsValue || null,
  });
  return response.data;
};

export const parseInvoice = async (file: File): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await aiClient.post('/parse/invoice', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const parsePackingList = async (file: File): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await aiClient.post('/parse/packing-list', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

// --- RAG/LLM endpoints (Phase 2) ---

export interface ParseSmartResult {
  invoice_number?: string;
  invoice_date?: string;
  seller?: { name?: string; country_code?: string; address?: string };
  buyer?: { name?: string; country_code?: string; address?: string };
  currency?: string;
  total_amount?: number;
  incoterms?: string;
  country_origin?: string;
  country_destination?: string;
  contract_number?: string;
  total_packages?: number;
  total_gross_weight?: number;
  total_net_weight?: number;
  items: Array<{
    line_no: number;
    description?: string;
    commercial_name?: string;
    quantity?: number;
    unit?: string;
    unit_price?: number;
    line_total?: number;
    hs_code?: string;
    hs_code_name?: string;
    hs_confidence?: number;
    hs_reasoning?: string;
    gross_weight?: number;
    net_weight?: number;
  }>;
  risk_score?: number;
  risk_flags?: any;
  confidence?: number;
  request_id?: string;
}

export const parseSmartDocument = async (files: File[]): Promise<ParseSmartResult> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  const response = await aiClient.post<ParseSmartResult>('/parse-smart', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000, // 10 min timeout for LLM processing (DSPy + multiple files)
  });
  return response.data;
};

export const classifyHSRag = async (description: string, countryOrigin?: string): Promise<any> => {
  const response = await aiClient.post('/classify-hs-rag', {
    description,
    country_origin: countryOrigin || null,
  });
  return response.data;
};

export const checkRisksRag = async (items: any[], totalCustomsValue?: number): Promise<RiskAssessment> => {
  const response = await aiClient.post<RiskAssessment>('/check-risks-rag', {
    items,
    total_customs_value: totalCustomsValue || null,
  });
  return response.data;
};
