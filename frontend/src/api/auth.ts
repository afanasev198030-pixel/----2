import client from './client';
import { LoginResponse, User } from '../types';

export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const response = await client.post<LoginResponse>('/auth/login', { email, password });
  if (response.data.access_token) {
    localStorage.setItem('token', response.data.access_token);
  }
  return response.data;
};

export const getMe = async (): Promise<User> => {
  const response = await client.get<User>('/auth/me');
  return response.data;
};

export const logout = (): void => {
  localStorage.removeItem('token');
};
