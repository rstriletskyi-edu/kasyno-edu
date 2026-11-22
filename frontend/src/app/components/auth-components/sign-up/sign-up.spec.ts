import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';

import { CurrentUserService } from '../../../services/current-user.service';
import { FirebaseAuthService } from '../../../services/firebase-auth.service';
import { SignUp } from './sign-up';

describe('SignUp', () => {
  let component: SignUp;
  let fixture: ComponentFixture<SignUp>;
  const firebaseUser = { uid: 'u1' };
  const auth = {
    signUp: vi.fn(),
    sendVerificationEmail: vi.fn(),
    deleteAccount: vi.fn(),
    signOut: vi.fn(),
  };
  const users = { register: vi.fn() };

  beforeEach(async () => {
    vi.resetAllMocks();
    auth.signUp.mockResolvedValue(firebaseUser);
    auth.sendVerificationEmail.mockResolvedValue(undefined);
    auth.deleteAccount.mockResolvedValue(undefined);
    auth.signOut.mockResolvedValue(undefined);

    await TestBed.configureTestingModule({
      imports: [SignUp],
      providers: [
        provideRouter([]),
        { provide: FirebaseAuthService, useValue: auth },
        { provide: CurrentUserService, useValue: users },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SignUp);
    component = fixture.componentInstance;
    component.email = 'a@b.pl';
    component.password = 'secret1';
    component.confirmPassword = 'secret1';
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('registers on the backend, sends the verification email, then goes to activation', async () => {
    users.register.mockReturnValue(of({}));
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

    await component.submit();

    expect(users.register).toHaveBeenCalledOnce();
    expect(auth.sendVerificationEmail).toHaveBeenCalledWith(firebaseUser);
    expect(auth.deleteAccount).not.toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/auth/account-activation']);
  });

  it('rolls back the Firebase account when the backend registration fails', async () => {
    users.register.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 503 })));
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

    await component.submit();

    expect(auth.deleteAccount).toHaveBeenCalledWith(firebaseUser);
    expect(auth.sendVerificationEmail).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
    expect(component.errorMessage()).toContain('Spróbuj ponownie');
  });

  it('does not call the backend when Firebase sign-up fails', async () => {
    auth.signUp.mockRejectedValue(new Error('boom'));

    await component.submit();

    expect(users.register).not.toHaveBeenCalled();
    expect(component.errorMessage()).toBe('boom');
  });

  it('shows an e-mail error while typing an invalid address', async () => {
    const input: HTMLInputElement = fixture.nativeElement.querySelector('input[name="email"]');
    input.value = 'userexample.com';
    input.dispatchEvent(new Event('input'));
    await fixture.whenStable();

    const error = (fixture.nativeElement as HTMLElement).querySelector('label span.error');
    expect(error?.textContent).toContain('Podaj prawidłowy adres e-mail');
  });
});
