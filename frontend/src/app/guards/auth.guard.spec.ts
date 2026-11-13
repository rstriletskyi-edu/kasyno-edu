import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { FirebaseAuthService } from '../services/firebase-auth.service';
import { authGuard } from './auth.guard';

describe('authGuard', () => {
  const getCurrentUser = vi.fn();

  beforeEach(() => {
    getCurrentUser.mockReset();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: FirebaseAuthService, useValue: { isConfigured: true, getCurrentUser } },
      ],
    });
  });

  it('redirects a signed-out user back to login when reopening a protected route', async () => {
    getCurrentUser.mockResolvedValue(null);
    const state = TestBed.inject(Router).routerState.snapshot;
    const result = await TestBed.runInInjectionContext(() => authGuard(state.root, state));
    expect(result).toEqual(TestBed.inject(Router).createUrlTree(['/auth/login']));
  });

  it('allows a verified signed-in user', async () => {
    getCurrentUser.mockResolvedValue({ emailVerified: true });
    const state = TestBed.inject(Router).routerState.snapshot;
    expect(await TestBed.runInInjectionContext(() => authGuard(state.root, state))).toBe(true);
  });
});
