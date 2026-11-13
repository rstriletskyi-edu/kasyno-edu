import { Component, HostListener, OnDestroy, OnInit, inject } from '@angular/core';
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

  email = '';
  errorMessage = '';
  successMessage = '';
  isSubmitting = false;
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
    this.errorMessage = '';
    this.successMessage = '';
    this.isSubmitting = true;

    try {
      const user = await this.auth.getCurrentUser();
      if (!user) {
        await this.router.navigate(['/auth/login']);
        return;
      }
      await this.auth.sendVerificationEmail(user);
      this.successMessage = 'Wysłaliśmy ponownie link weryfikacyjny.';
    } catch (error) {
      this.errorMessage = firebaseErrorMessage(error);
    } finally {
      this.isSubmitting = false;
    }
  }

  async checkVerification(showPendingMessage = true): Promise<void> {
    if (this.isSubmitting || this.destroyed) return;
    this.errorMessage = '';
    this.isSubmitting = true;

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
        this.errorMessage = 'Adres e-mail nie jest jeszcze potwierdzony.';
      }
    } catch (error) {
      if (!this.destroyed) this.errorMessage = firebaseErrorMessage(error);
    } finally {
      this.isSubmitting = false;
    }
  }

  private async loadEmail(): Promise<void> {
    try {
      this.email = (await this.auth.getCurrentUser())?.email ?? '';
    } catch (error) {
      this.errorMessage = firebaseErrorMessage(error);
    }
  }
}
