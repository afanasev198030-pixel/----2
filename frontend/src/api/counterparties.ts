import client from './client';

export interface Counterparty {
  id: string;
  type: string;
  name: string;
  country_code?: string;
  registration_number?: string;
  tax_number?: string;
  address?: string;
  company_id: string;
}

export const getCounterparties = async (q?: string, type?: string): Promise<Counterparty[]> => {
  const response = await client.get<Counterparty[]>('/counterparties', { params: { q, type } });
  return response.data;
};

export const createCounterparty = async (data: Partial<Counterparty>): Promise<Counterparty> => {
  const response = await client.post<Counterparty>('/counterparties', data);
  return response.data;
};

export const getCounterparty = async (id: string): Promise<Counterparty> => {
  const response = await client.get<Counterparty>(`/counterparties/${id}`);
  return response.data;
};

export const updateCounterparty = async (id: string, data: Partial<Counterparty>): Promise<Counterparty> => {
  const response = await client.put<Counterparty>(`/counterparties/${id}`, data);
  return response.data;
};
