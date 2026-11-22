import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { catchError, of, throwError } from 'rxjs';

import { environment } from '../../environments/environment';

export interface CurrentUser {
  uid: string;
  email: string | null;
  email_verified: boolean;
  display_name: string | null;
  profile: { created_at: string | null; credits: number };
}

@Injectable({ providedIn: 'root' })
export class CurrentUserService {
  private readonly http = inject(HttpClient);

  getMe() {
    return this.http.get<CurrentUser>(`${environment.apiUrl}/auth/me`);
  }

  /**
   * Creates users/{uid} on the backend (201). A 409 means the profile already exists,
   * which is fine here, so it resolves with `null`; any other error is rethrown.
   */
  register() {
    return this.http
      .post<CurrentUser>(`${environment.apiUrl}/auth/register`, {})
      .pipe(
        catchError((error: unknown) =>
          error instanceof HttpErrorResponse && error.status === 409
            ? of(null)
            : throwError(() => error),
        ),
      );
  }
}
