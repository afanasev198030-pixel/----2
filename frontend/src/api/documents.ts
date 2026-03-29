import client from './client';
import { Document } from '../types';

export interface GetDocumentsParams {
  declaration_id?: string;
  item_id?: string;
  doc_type?: string;
}

export const getDocuments = async (params?: GetDocumentsParams): Promise<Document[]> => {
  const response = await client.get<Document[]>('/documents', { params });
  return response.data;
};

export const createDocument = async (data: Partial<Document>): Promise<Document> => {
  const response = await client.post<Document>('/documents', data);
  return response.data;
};

export const uploadFile = async (file: File): Promise<{ file_key: string; original_filename: string; mime_type: string; file_size: number }> => {
  const formData = new FormData();
  formData.append('file', file);
  const fileBase = window.location.port === '3000'
    ? `${window.location.protocol}//${window.location.hostname}:80`
    : '';
  const response = await fetch(`${fileBase}/api/v1/files/upload`, {
    method: 'POST',
    body: formData,
  });
  return response.json();
};
