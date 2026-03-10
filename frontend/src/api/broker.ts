import client from './client';
import { Declaration, PaginatedResponse } from '../types';

export interface BrokerClient {
  id: string;
  broker_company_id: string;
  client_company_id: string;
  contract_number?: string;
  contract_date?: string;
  tariff_plan: string;
  is_active: boolean;
  client_company?: {
    id: string;
    name: string;
    inn?: string;
    kpp?: string;
    address?: string;
    contact_email?: string;
    contact_phone?: string;
  };
  declarations_count?: number;
}

export interface CreateBrokerClientData {
  // Flat fields from UI form
  client_company_name: string;
  client_company_inn: string;
  client_company_kpp?: string;
  client_company_address?: string;
  contract_number?: string;
  contract_date?: string;
  tariff_plan: 'basic' | 'standard' | 'premium';
}

function toApiPayload(data: CreateBrokerClientData) {
  return {
    new_company: {
      name: data.client_company_name,
      inn: data.client_company_inn,
      kpp: data.client_company_kpp || undefined,
      address: data.client_company_address || undefined,
      company_type: 'client',
      country_code: 'RU',
    },
    contract_number: data.contract_number || undefined,
    contract_date: data.contract_date || undefined,
    tariff_plan: data.tariff_plan,
  };
}

export const getBrokerClients = async (): Promise<BrokerClient[]> => {
  const response = await client.get('/broker/clients');
  return Array.isArray(response.data) ? response.data : response.data.items || [];
};

export const getBrokerClient = async (id: string): Promise<BrokerClient> => {
  const response = await client.get(`/broker/clients/${id}`);
  return response.data;
};

export const createBrokerClient = async (data: CreateBrokerClientData): Promise<BrokerClient> => {
  const response = await client.post('/broker/clients', toApiPayload(data));
  return response.data;
};

export const updateBrokerClient = async (id: string, data: Partial<CreateBrokerClientData>): Promise<BrokerClient> => {
  const response = await client.put(`/broker/clients/${id}`, data);
  return response.data;
};

export const getClientDeclarations = async (
  clientId: string,
  params?: { page?: number; per_page?: number }
): Promise<PaginatedResponse<Declaration>> => {
  const response = await client.get(`/broker/clients/${clientId}/declarations`, { params });
  return response.data;
};
