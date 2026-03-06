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
  source?: string;
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

export const classifyHS = async (
  description: string,
  countryOrigin?: string,
  unitPrice?: number,
  declarationId?: string,
): Promise<HSSuggestion[]> => {
  // Use RAG+GPT-4o endpoint (falls back to keyword if AI unavailable)
  try {
    const response = await aiClient.post<{ suggestions: any[]; rag_candidates?: any[] }>('/classify-hs-rag', {
      description,
      country_origin: countryOrigin || null,
      unit_price: unitPrice || null,
      declaration_id: declarationId || null,
    });
    // Merge suggestions + model candidates + rag_candidates
    const suggestions = (response.data.suggestions || []).map((s: any) => ({
      hs_code: s.hs_code,
      name_ru: s.name_ru || '',
      confidence: s.confidence || 0,
      source: s.source || 'model',
    }));
    const modelCandidates = (response.data.suggestions || [])
      .flatMap((s: any) => (s?.candidates || []))
      .filter((c: any) => c?.hs_code)
      .map((c: any) => ({
        hs_code: c.hs_code,
        name_ru: c.name_ru || '',
        confidence: c.confidence || 0,
        source: c.source || 'candidate',
      }));
    const rag = (response.data.rag_candidates || [])
      .filter((c: any) => c.code && c.code.length >= 4)
      .slice(0, 3)
      .map((c: any) => ({
        hs_code: c.code.length < 10 ? c.code.padEnd(10, '0') : c.code,
        name_ru: c.name_ru || '',
        confidence: c.score || 0.5,
        source: 'rag',
      }));
    // Deduplicate
    const seen = new Set<string>();
    const merged: HSSuggestion[] = [];
    [...suggestions, ...modelCandidates, ...rag].forEach((item: HSSuggestion) => {
      if (!item.hs_code || seen.has(item.hs_code)) return;
      seen.add(item.hs_code);
      merged.push(item);
    });
    return merged.filter((s: HSSuggestion) => s.hs_code && s.hs_code !== '0000000000');
  } catch {
    // Fallback to keyword classifier
    const response = await aiClient.post<{ suggestions: HSSuggestion[] }>('/classify-hs', {
      description,
      country_origin: countryOrigin || null,
      unit_price: unitPrice || null,
    });
    return response.data.suggestions;
  }
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
  seller?: { name?: string; country_code?: string; address?: string; inn?: string; kpp?: string; ogrn?: string };
  buyer?: { name?: string; country_code?: string; address?: string; inn?: string; kpp?: string; ogrn?: string };
  currency?: string;
  total_amount?: number;
  incoterms?: string;
  delivery_place?: string;
  transport_id?: string;
  transport_country_code?: string;
  trading_partner_country?: string;  // Гр. 11: страна контрагента
  country_dispatch?: string;          // Гр. 15: страна отправления
  container?: boolean;                // Гр. 19: контейнер
  country_origin?: string;
  country_destination?: string;
  contract_number?: string;
  contract_date?: string;
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
    invoice_currency?: string;       // Валюта инвойса (для проверки с контрактной)
    hs_code?: string;
    hs_code_name?: string;
    hs_confidence?: number;
    hs_reasoning?: string;
    hs_candidates?: HSSuggestion[];
    gross_weight?: number;
    net_weight?: number;
    package_count?: number;          // Гр. 31: кол-во грузовых мест
    package_type?: string;           // Гр. 31: тип упаковки
    country_origin_code?: string;
  }>;
  risk_score?: number;
  risk_flags?: any;
  confidence?: number;
  request_id?: string;
}

export const parseSmartDocument = async (files: File[], declarationId?: string): Promise<ParseSmartResult> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  if (declarationId) {
    formData.append('declaration_id', declarationId);
  }
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
