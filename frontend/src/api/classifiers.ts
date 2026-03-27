import client from './client';

export interface Classifier {
  id: string;
  classifier_type: string;
  code: string;
  name_ru: string;
  name_en?: string;
  parent_code?: string;
  meta?: any;
  is_active: boolean;
}

export const getCountries = async (): Promise<Classifier[]> => {
  const response = await client.get<Classifier[]>('/classifiers/countries');
  return response.data;
};

export const getCurrencies = async (): Promise<Classifier[]> => {
  const response = await client.get<Classifier[]>('/classifiers/currencies');
  return response.data;
};

export const searchHSCodes = async (query: string): Promise<Classifier[]> => {
  const response = await client.get<Classifier[]>('/classifiers/hs-codes/search', {
    params: { q: query },
  });
  return response.data;
};

export const getClassifiers = async (type: string, q?: string): Promise<Classifier[]> => {
  const response = await client.get<Classifier[]>('/classifiers', {
    params: { classifier_type: type, q },
  });
  return response.data;
};
