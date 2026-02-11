import client from './client';
import { User } from '../types';

export interface UsersListResponse {
  items: User[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface AuditLogEntry {
  id: string;
  user_id?: string;
  user_email?: string;
  user_name?: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  details?: Record<string, any>;
  ip_address?: string;
  created_at?: string;
}

export interface AuditListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export const getUsers = async (params: {
  page?: number;
  per_page?: number;
  search?: string;
  role?: string;
  is_active?: boolean;
}): Promise<UsersListResponse> => {
  const resp = await client.get('/users/', { params });
  return resp.data;
};

export const getUser = async (id: string): Promise<User> => {
  const resp = await client.get(`/users/${id}`);
  return resp.data;
};

export const updateUser = async (id: string, data: Partial<User>): Promise<User> => {
  const resp = await client.put(`/users/${id}`, data);
  return resp.data;
};

export const deleteUser = async (id: string): Promise<void> => {
  await client.delete(`/users/${id}`);
};

// Audit
export const getAuditLog = async (params: {
  page?: number;
  per_page?: number;
  user_id?: string;
  action?: string;
  resource_type?: string;
  date_from?: string;
  date_to?: string;
}): Promise<AuditListResponse> => {
  const resp = await client.get('/admin/audit', { params });
  return resp.data;
};

export const getUserAudit = async (userId: string, page = 1): Promise<AuditListResponse> => {
  const resp = await client.get(`/admin/users/${userId}/audit`, { params: { page } });
  return resp.data;
};

export const getAuditActions = async (): Promise<string[]> => {
  const resp = await client.get('/admin/audit/actions');
  return resp.data;
};
