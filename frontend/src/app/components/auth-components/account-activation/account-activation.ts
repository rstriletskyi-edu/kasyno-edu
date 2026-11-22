import { Component, HostListener, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';

@Component({
  imports: [RouterLink],
  selector: 'account-activation',
  styleUrl: '../auth.css',
  templateUrl: './account-activation.html',
})
export class AccountActivation implements OnInit, OnDestroy {
  private readonly auth = inject(FirebaseAuthService);
  private readonly router = inject(Router);

  readonly email = signal('');
  readonly errorMessage = signal('');
  readonly successMessage = signal('');
  // True only while a user-triggered action runs; background polling must not disable the buttons.
  readonly isSubmitting = signal(false);
  private checking = false;
  private timer?: ReturnType<typeof setInterval>;
  private destroyed = false;

  ngOnInit(): void {
    void this.loadEmail();
    void this.checkVerification(false);
    this.timer = setInterval(() => {
      if (document.visibilityState === 'visible') void this.checkVerification(false);
    }, 5000);
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    clearInterval(this.timer);
  }

  @HostListener('window:focus')
  onFocus(): void {
    void this.checkVerification(false);
  }

  async resendEmail(): Promise<void> {
    if (this.isSubmitting()) return;
    this.errorMessage.set('');
    this.successMessage.set('');
    this.isSubmitting.set(true);

    try {
      const user = await this.auth.getCurrentUser();
      if (!user) {
        await this.router.navigate(['/auth/login']);
        return;
      }
      await this.auth.sendVerificationEmail(user);
      this.successMessage.set('Wysłaliśmy ponownie link weryfikacyjny.');
    } catch (error) {
      this.errorMessage.set(firebaseErrorMessage(error));
    } finally {
      this.isSubmitting.set(false);
    }
  }

  /** `showPendingMessage` is true for the user's explicit click and false for background polling. */
  async checkVerification(showPendingMessage = true): Promise<void> {
    if (this.checking || this.destroyed) return;
    this.checking = true;
    if (showPendingMessage) {
      this.errorMessage.set('');
      this.isSubmitting.set(true);
    }

    try {
      const user = await this.auth.getCurrentUser();
      if (!user) {
        await this.router.navigate(['/auth/login']);
        return;
      }

      await this.auth.refreshUser(user);
      if (this.destroyed) return;
      if (user.emailVerified) {
        clearInterval(this.timer);
        await this.auth.signOut();
        await this.router.navigate(['/auth/login'], { queryParams: { verified: '1' } });
      } else if (showPendingMessage) {
        this.errorMessage.set('Adres e-mail nie jest jeszcze potwierdzony.');
      }
    } catch (error) {
      if (!this.destroyed) this.errorMessage.set(firebaseErrorMessage(error));
    } finally {
      this.checking = false;
      if (showPendingMessage) this.isSubmitting.set(false);
    }
  }

  private async loadEmail(): Promise<void> {
    try {
      this.email.set((await this.auth.getCurrentUser())?.email ?? '');
    } catch (error) {
      this.errorMessage.set(firebaseErrorMessage(error));
    }
  }
}
