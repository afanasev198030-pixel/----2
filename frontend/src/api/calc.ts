import client from './client';

export interface PaymentResult {
  items: Array<{
    item_no: number;
    hs_code: string;
    customs_value_rub: number;
    duty: { type: string; rate: number; amount: number };
    vat: { rate: number; base: number; amount: number };
    excise: number;
  }>;
  totals: {
    total_customs_value: number;
    total_duty: number;
    total_vat: number;
    total_excise: number;
    customs_fee: number;
    grand_total: number;
  };
  exchange_rate: number;
  currency: string;
}

export interface ExchangeRates {
  rates: Record<string, number>;
  date: string;
}

// Use calc-service directly (through proxy)
const CALC_BASE = '/api/v1/calc';

export const calculatePayments = async (items: any[], currency: string, exchangeRate?: number): Promise<PaymentResult> => {
  const response = await fetch(`${CALC_BASE}/payments/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items, currency, exchange_rate: exchangeRate }),
  });
  return response.json();
};

export const getExchangeRates = async (): Promise<ExchangeRates> => {
  const response = await fetch(`${CALC_BASE}/exchange-rates/latest`);
  return response.json();
};

export const getExchangeRate = async (currency: string): Promise<number> => {
  const response = await fetch(`${CALC_BASE}/exchange-rates?currency=${currency}`);
  const data = await response.json();
  return data.rate_to_rub || 0;
};
