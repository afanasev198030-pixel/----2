export type DeclarationStatus = "NEW" | "REQUIRES_ATTENTION" | "READY_TO_SEND" | "SENT";
export type ProcessingStatus = "NOT_STARTED" | "PROCESSING" | "AUTO_FILLED" | "PROCESSING_ERROR";
export type SignatureStatus = "UNSIGNED" | "SIGNED";

export interface Declaration {
  id: string;
  clientName: string;
  status: DeclarationStatus;
  processingStatus: ProcessingStatus;
  signatureStatus: SignatureStatus;
  goodsCount: number;
  issueCount: number;
  createdAt: string;
  updatedAt: string;
  source: "manual" | "telegram" | "email";
  totalValue?: string;
  currency?: string;
  destination?: string;
}

export const STATUS_CONFIG: Record<DeclarationStatus, { label: string; color: string; bg: string; border: string; dot: string }> = {
  NEW: { label: "Новая", color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200", dot: "bg-blue-500" },
  REQUIRES_ATTENTION: { label: "Требует внимания", color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", dot: "bg-amber-500" },
  READY_TO_SEND: { label: "Готово к отправке", color: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200", dot: "bg-emerald-500" },
  SENT: { label: "Отправлено", color: "text-slate-500", bg: "bg-slate-50", border: "border-slate-200", dot: "bg-slate-400" },
};

export const PROCESSING_LABELS: Record<ProcessingStatus, string> = {
  NOT_STARTED: "Не обработано",
  PROCESSING: "В обработке",
  AUTO_FILLED: "Автозаполнено",
  PROCESSING_ERROR: "Ошибка обработки",
};
