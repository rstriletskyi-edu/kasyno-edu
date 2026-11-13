import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { FirebaseAuthService } from '../services/firebase-auth.service';

export const authGuard: CanActivateFn = async () => {
  const auth = inject(FirebaseAuthService);
  const router = inject(Router);

  if (!auth.isConfigured) {
    return router.createUrlTree(['/auth/login']);
  }

  const user = await auth.getCurrentUser();
  if (user?.emailVerified) {
    return true;
  }

  return router.createUrlTree([user ? '/auth/account-activation' : '/auth/login']);
};
