import client from './client';
import { CustomsValueDeclaration, CustomsValueItem } from '../types';

export const getDts = async (declarationId: string): Promise<CustomsValueDeclaration> => {
  const response = await client.get<CustomsValueDeclaration>(
    `/declarations/${declarationId}/dts/`,
  );
  return response.data;
};

export const generateDts = async (declarationId: string): Promise<CustomsValueDeclaration> => {
  const response = await client.post<CustomsValueDeclaration>(
    `/declarations/${declarationId}/dts/generate`,
  );
  return response.data;
};

export const updateDts = async (
  declarationId: string,
  data: Partial<CustomsValueDeclaration>,
): Promise<CustomsValueDeclaration> => {
  const response = await client.put<CustomsValueDeclaration>(
    `/declarations/${declarationId}/dts/`,
    data,
  );
  return response.data;
};

export const updateDtsItem = async (
  declarationId: string,
  itemId: string,
  data: Partial<CustomsValueItem>,
): Promise<CustomsValueItem> => {
  const response = await client.put<CustomsValueItem>(
    `/declarations/${declarationId}/dts/items/${itemId}`,
    data,
  );
  return response.data;
};

export const recalculateDts = async (
  declarationId: string,
): Promise<CustomsValueDeclaration> => {
  const response = await client.post<CustomsValueDeclaration>(
    `/declarations/${declarationId}/dts/recalculate`,
  );
  return response.data;
};

export const deleteDts = async (declarationId: string): Promise<void> => {
  await client.delete(`/declarations/${declarationId}/dts/`);
};
