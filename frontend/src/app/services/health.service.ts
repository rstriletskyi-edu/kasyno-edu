import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export interface HealthResponse {
  status: 'ok';
  app_name: string;
  environment: string;
  firebase_initialized: boolean;
}

@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly http = inject(HttpClient);

  getHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${environment.apiUrl}/health`);
  }
}
