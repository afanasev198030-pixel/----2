import client from './client';
import { DeclarationItem } from '../types';

export const getItems = async (declarationId: string): Promise<DeclarationItem[]> => {
  const response = await client.get<DeclarationItem[]>(
    `/declarations/${declarationId}/items/`
  );
  return response.data;
};

export const createItem = async (
  declarationId: string,
  data: Partial<DeclarationItem>
): Promise<DeclarationItem> => {
  const response = await client.post<DeclarationItem>(
    `/declarations/${declarationId}/items/`,
    data
  );
  return response.data;
};

export const updateItem = async (
  declarationId: string,
  itemId: string,
  data: Partial<DeclarationItem>
): Promise<DeclarationItem> => {
  const response = await client.put<DeclarationItem>(
    `/declarations/${declarationId}/items/${itemId}`,
    data
  );
  return response.data;
};

export const deleteItem = async (declarationId: string, itemId: string): Promise<void> => {
  await client.delete(`/declarations/${declarationId}/items/${itemId}`);
};
