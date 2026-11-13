import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { FirebaseAuthService } from '../../../services/firebase-auth.service';
import { AccountActivation } from './account-activation';

describe('AccountActivation', () => {
  let component: AccountActivation;
  let fixture: ComponentFixture<AccountActivation>;
  const user = { email: 'learner@example.test', emailVerified: false };
  const auth = {
    getCurrentUser: vi.fn(),
    refreshUser: vi.fn(),
    signOut: vi.fn(),
    sendVerificationEmail: vi.fn(),
  };
  let navigate: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    vi.useFakeTimers();
    user.emailVerified = false;
    auth.getCurrentUser.mockResolvedValue(user);
    auth.refreshUser.mockResolvedValue(user);
    auth.signOut.mockResolvedValue(undefined);
    auth.sendVerificationEmail.mockResolvedValue(undefined);
    await TestBed.configureTestingModule({
      imports: [AccountActivation],
      providers: [provideRouter([]), { provide: FirebaseAuthService, useValue: auth }],
    }).compileComponents();

    navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    fixture = TestBed.createComponent(AccountActivation);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => {
    fixture.destroy();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it('loads the email and waits while unverified', () => {
    expect(component.email).toBe(user.email);
    expect(navigate).not.toHaveBeenCalled();
    expect(component.errorMessage).toBe('');
  });

  it('signs out and redirects to login after verification', async () => {
    user.emailVerified = true;
    await component.checkVerification();
    expect(auth.signOut).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith(['/auth/login'], { queryParams: { verified: '1' } });
  });

  it('detects verification when the tab regains focus', async () => {
    user.emailVerified = true;
    window.dispatchEvent(new Event('focus'));
    await vi.advanceTimersByTimeAsync(0);
    expect(navigate).toHaveBeenCalledWith(['/auth/login'], { queryParams: { verified: '1' } });
  });

  it('checks periodically and stops after destruction', async () => {
    await vi.advanceTimersByTimeAsync(5000);
    expect(auth.refreshUser.mock.calls.length).toBeGreaterThan(1);
    fixture.destroy();
    const calls = auth.refreshUser.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10000);
    expect(auth.refreshUser).toHaveBeenCalledTimes(calls);
  });

  it('shows a pending message for an explicit check', async () => {
    await component.checkVerification();
    expect(component.errorMessage).toContain('nie jest jeszcze potwierdzony');
    expect(auth.signOut).not.toHaveBeenCalled();
  });

  it('does not redirect after refresh fails', async () => {
    auth.refreshUser.mockRejectedValueOnce(new Error('Network unavailable'));
    await component.checkVerification();
    expect(component.errorMessage).toBe('Network unavailable');
    expect(navigate).not.toHaveBeenCalled();
  });
});
