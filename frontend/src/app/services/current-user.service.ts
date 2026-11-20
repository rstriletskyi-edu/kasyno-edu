import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import { environment } from '../../environments/environment';

export interface CurrentUser {
  uid: string;
  email: string | null;
  email_verified: boolean;
  display_name: string | null;
  profile: { created_at: string | null };
}

@Injectable({ providedIn: 'root' })
export class CurrentUserService {
  private readonly http = inject(HttpClient);

  getMe() {
    return this.http.get<CurrentUser>(`${environment.apiUrl}/auth/me`);
  }
}
