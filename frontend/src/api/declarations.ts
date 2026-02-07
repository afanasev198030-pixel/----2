import client from './client';
import { Declaration, PaginatedResponse, DeclarationStatus } from '../types';

export interface GetDeclarationsParams {
  page?: number;
  page_size?: number;
  status?: DeclarationStatus;
  type_code?: string;
  company_id?: string;
}

export const getDeclarations = async (
  params?: GetDeclarationsParams
): Promise<PaginatedResponse<Declaration>> => {
  const response = await client.get<PaginatedResponse<Declaration>>('/declarations/', { params });
  return response.data;
};

export const getDeclaration = async (id: string): Promise<Declaration> => {
  const response = await client.get<Declaration>(`/declarations/${id}`);
  return response.data;
};

export const createDeclaration = async (data: Partial<Declaration>): Promise<Declaration> => {
  const response = await client.post<Declaration>('/declarations/', data);
  return response.data;
};

export const updateDeclaration = async (
  id: string,
  data: Partial<Declaration>
): Promise<Declaration> => {
  const response = await client.put<Declaration>(`/declarations/${id}`, data);
  return response.data;
};

export const deleteDeclaration = async (id: string): Promise<void> => {
  await client.delete(`/declarations/${id}`);
};

export const changeStatus = async (
  id: string,
  newStatus: string
): Promise<any> => {
  const response = await client.post(`/declarations/${id}/status/`, {
    new_status: newStatus,
  });
  return response.data;
};
