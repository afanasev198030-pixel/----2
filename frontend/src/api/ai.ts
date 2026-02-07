import axios from 'axios';

// AI service through nginx proxy (/api/v1/ai/ -> ai-service:8003)
const AI_BASE = typeof window !== 'undefined' && window.location.port === '3000'
  ? `${window.location.protocol}//${window.location.hostname}:80/api/v1/ai`
  : '/api/v1/ai';

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
