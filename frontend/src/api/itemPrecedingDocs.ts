import client from './client';
import { ItemPrecedingDoc } from '../types';

export const getItemPrecedingDocs = async (
  declId: string,
  itemId: string,
): Promise<ItemPrecedingDoc[]> => {
  const response = await client.get<ItemPrecedingDoc[]>(
    `/declarations/${declId}/items/${itemId}/preceding-docs/`,
  );
  return response.data;
};

export const createItemPrecedingDoc = async (
  declId: string,
  itemId: string,
  data: Partial<ItemPrecedingDoc>,
): Promise<ItemPrecedingDoc> => {
  const response = await client.post<ItemPrecedingDoc>(
    `/declarations/${declId}/items/${itemId}/preceding-docs/`,
    data,
  );
  return response.data;
};

export const updateItemPrecedingDoc = async (
  declId: string,
  itemId: string,
  docId: string,
  data: Partial<ItemPrecedingDoc>,
): Promise<ItemPrecedingDoc> => {
  const response = await client.put<ItemPrecedingDoc>(
    `/declarations/${declId}/items/${itemId}/preceding-docs/${docId}`,
    data,
  );
  return response.data;
};

export const deleteItemPrecedingDoc = async (
  declId: string,
  itemId: string,
  docId: string,
): Promise<void> => {
  await client.delete(
    `/declarations/${declId}/items/${itemId}/preceding-docs/${docId}`,
  );
};
