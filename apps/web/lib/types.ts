export interface AnalysisResponse {
  analysis_id: number;
  status: string;
}

export interface AnalysisEvent {
  event: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface DataQualityReport {
  passed: boolean;
  details: string[];
}

export interface DataReadyPayload {
  asset: string;
  asset_class: string;
  quality_report: DataQualityReport;
  assembled_at: string;
}

export interface AnalysisError {
  error: string;
}
