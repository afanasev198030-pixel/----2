import client from './client';

export interface AiStrategy {
  id: string;
  name: string;
  description?: string | null;
  rule_text: string;
  conditions?: Record<string, unknown> | null;
  actions?: Record<string, unknown> | null;
  priority: number;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface StrategyCreate {
  name: string;
  description?: string;
  rule_text: string;
  conditions?: Record<string, unknown>;
  actions?: Record<string, unknown>;
  priority?: number;
  is_active?: boolean;
}

export const getStrategies = () =>
  client.get<AiStrategy[]>('/ai-strategies').then((r) => r.data);

export const createStrategy = (data: StrategyCreate) =>
  client.post('/ai-strategies', data).then((r) => r.data);

export const updateStrategy = (id: string, data: Partial<StrategyCreate>) =>
  client.put(`/ai-strategies/${id}`, data).then((r) => r.data);

export const deleteStrategy = (id: string) =>
  client.delete(`/ai-strategies/${id}`).then((r) => r.data);
