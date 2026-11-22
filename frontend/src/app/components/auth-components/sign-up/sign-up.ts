import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { CurrentUserService } from '../../../services/current-user.service';
import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';
import { EmailTldValidatorDirective } from '../../../validators/email-validator';

@Component({
  imports: [FormsModule, ReactiveFormsModule, RouterLink, EmailTldValidatorDirective],
  selector: 'sign-up',
  styleUrls: ['../auth.css', './sign-up.css'],
  templateUrl: './sign-up.html',
})
export class SignUp {
  private readonly auth = inject(FirebaseAuthService);
  private readonly users = inject(CurrentUserService);
  private readonly router = inject(Router);

  email = '';
  password = '';
  confirmPassword = '';
  readonly errorMessage = signal('');
  readonly isSubmitting = signal(false);

  async submit(): Promise<void> {
    this.errorMessage.set('');
    if (this.password !== this.confirmPassword) {
      this.errorMessage.set('Podane hasła nie są takie same.');
      return;
    }

    this.isSubmitting.set(true);
    try {
      const user = await this.auth.signUp(this.email, this.password);
      try {
        await firstValueFrom(this.users.register());
        await this.auth.sendVerificationEmail(user);
      } catch (error) {
        // Firebase account exists but the backend profile does not: roll back so
        // both sides stay consistent and the user can simply register again.
        try {
          await this.auth.deleteAccount(user);
        } catch {
          await this.auth.signOut().catch(() => undefined);
        }
        this.errorMessage.set(
          error instanceof HttpErrorResponse
            ? 'Nie udało się dokończyć rejestracji na serwerze. Spróbuj ponownie.'
            : firebaseErrorMessage(error),
        );
        return;
      }
      await this.router.navigate(['/auth/account-activation']);
    } catch (error) {
      this.errorMessage.set(firebaseErrorMessage(error));
    } finally {
      this.isSubmitting.set(false);
    }
  }

  async signUpWithGoogle(): Promise<void> {
    this.errorMessage.set('');
    this.isSubmitting.set(true);
    try {
      const user = await this.auth.signInWithGoogle();
      await this.registerProfile();
      await this.router.navigate([user.emailVerified ? '/dashboard' : '/auth/account-activation']);
    } catch (error) {
      this.errorMessage.set(firebaseErrorMessage(error));
    } finally {
      this.isSubmitting.set(false);
    }
  }

  async signUpWithFacebook(): Promise<void> {
    this.errorMessage.set('');
    this.isSubmitting.set(true);
    try {
      const user = await this.auth.signInWithFacebook();
      await this.registerProfile();
      await this.router.navigate([user.emailVerified ? '/dashboard' : '/auth/account-activation']);
    } catch (error) {
      this.errorMessage.set(firebaseErrorMessage(error));
    } finally {
      this.isSubmitting.set(false);
    }
  }

  /** Idempotent: creates the backend profile for social accounts (no-op if it exists). */
  private async registerProfile(): Promise<void> {
    try {
      await firstValueFrom(this.users.register());
    } catch {
      await this.auth.signOut().catch(() => undefined);
      throw new Error('Nie udało się dokończyć rejestracji na serwerze. Spróbuj ponownie.');
    }
  }
}
