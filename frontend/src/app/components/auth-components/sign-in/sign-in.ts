import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { CurrentUserService } from '../../../services/current-user.service';
import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';
import { EmailTldValidatorDirective } from '../../../validators/email-validator';

@Component({
  imports: [FormsModule, RouterLink, EmailTldValidatorDirective],
  selector: 'sign-in',
  styleUrl: '../auth.css',
  templateUrl: './sign-in.html',
})
export class SignIn {
  private readonly auth = inject(FirebaseAuthService);
  private readonly users = inject(CurrentUserService);
  private readonly router = inject(Router);
  readonly accountVerified = inject(ActivatedRoute).snapshot.queryParamMap.get('verified') === '1';

  email = '';
  password = '';
  readonly errorMessage = signal('');
  readonly isSubmitting = signal(false);

  async submit(): Promise<void> {
    this.errorMessage.set('');
    this.isSubmitting.set(true);

    try {
      const user = await this.auth.signIn(this.email, this.password);
      await this.router.navigate([user.emailVerified ? '/dashboard' : '/auth/account-activation']);
    } catch (error) {
      this.errorMessage.set(firebaseErrorMessage(error));
    } finally {
      this.isSubmitting.set(false);
    }
  }

  async signInWithGoogle(): Promise<void> {
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

  async signInWithFacebook(): Promise<void> {
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

  /** Idempotent: social sign-in has no separate sign-up step, so ensure the backend profile exists. */
  private async registerProfile(): Promise<void> {
    try {
      await firstValueFrom(this.users.register());
    } catch {
      await this.auth.signOut().catch(() => undefined);
      throw new Error('Nie udało się dokończyć logowania na serwerze. Spróbuj ponownie.');
    }
  }
}
