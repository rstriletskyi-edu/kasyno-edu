import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap } from 'rxjs';

import { environment } from '../../environments/environment';
import { FirebaseAuthService } from '../services/firebase-auth.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const api = new URL(environment.apiUrl, window.location.origin);
  const target = new URL(request.url, window.location.origin);
  const apiPath = api.pathname.replace(/\/$/, '');
  if (
    target.origin !== api.origin ||
    !(target.pathname === apiPath || target.pathname.startsWith(`${apiPath}/`))
  ) {
    return next(request);
  }

  const auth = inject(FirebaseAuthService);
  return from(auth.getIdToken()).pipe(
    switchMap((token) =>
      next(token ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : request),
    ),
  );
};
