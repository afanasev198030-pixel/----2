import client from './client';
import { ItemDocument } from '../types';

export const getItemDocuments = async (
  declId: string,
  itemId: string,
): Promise<ItemDocument[]> => {
  const response = await client.get<ItemDocument[]>(
    `/declarations/${declId}/items/${itemId}/item-documents/`,
  );
  return response.data;
};

export const createItemDocument = async (
  declId: string,
  itemId: string,
  data: Partial<ItemDocument>,
): Promise<ItemDocument> => {
  const response = await client.post<ItemDocument>(
    `/declarations/${declId}/items/${itemId}/item-documents/`,
    data,
  );
  return response.data;
};

export const updateItemDocument = async (
  declId: string,
  itemId: string,
  docId: string,
  data: Partial<ItemDocument>,
): Promise<ItemDocument> => {
  const response = await client.put<ItemDocument>(
    `/declarations/${declId}/items/${itemId}/item-documents/${docId}`,
    data,
  );
  return response.data;
};

export const deleteItemDocument = async (
  declId: string,
  itemId: string,
  docId: string,
): Promise<void> => {
  await client.delete(
    `/declarations/${declId}/items/${itemId}/item-documents/${docId}`,
  );
};
