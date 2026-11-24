import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { environment } from '../../environments/environment';

export interface LlmSessionRequest {
  api_key?: string | null;
  provider?: string | null;
  model?: string | null;
  base_url?: string | null;
}

export interface LlmSessionResponse {
  session_id: string;
}

export interface EvaluationRequest {
  question_id: string;
  user_answer: string;
}

export interface EvaluationResult {
  score: number;
  verdict: string;
  credits_received: number;
  explanation: string;
}

@Injectable({ providedIn: 'root' })
export class LlmEvalService {
  private readonly http = inject(HttpClient);

  getLlmSession(sessionRequest: LlmSessionRequest | null): Observable<string> {
    return this.http
      .post<LlmSessionResponse>(
        `${environment.apiUrl}/llm/sessions`,
        sessionRequest === null ? {} : sessionRequest,
      )
      .pipe(map((res) => res.session_id));
  }

  verifyLlmSession(sessionId: string): Observable<string> {
    return this.http
      .get<LlmSessionResponse>(`${environment.apiUrl}/llm/sessions/${sessionId}`)
      .pipe(map((res) => res.session_id));
  }

  getAnswerEvaluation(
    sessionId: string,
    evalRequest: EvaluationRequest,
  ): Observable<EvaluationResult> {
    return this.http.post<EvaluationResult>(
      `${environment.apiUrl}/llm/sessions/${sessionId}/evaluations`,
      evalRequest,
    );
  }
}
