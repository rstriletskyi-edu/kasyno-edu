import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';

@Component({
  imports: [RouterLink],
  selector: 'account-activation',
  styleUrl: '../auth.css',
  templateUrl: './account-activation.html',
})
export class AccountActivation implements OnInit {
  private readonly auth = inject(FirebaseAuthService);
  private readonly router = inject(Router);

  email = '';
  errorMessage = '';
  successMessage = '';
  isSubmitting = false;

  ngOnInit(): void {
    void this.loadEmail();
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

  async checkVerification(): Promise<void> {
    this.errorMessage = '';
    this.isSubmitting = true;

    try {
      const user = await this.auth.getCurrentUser();
      if (!user) {
        await this.router.navigate(['/auth/login']);
        return;
      }

      await this.auth.refreshUser(user);
      if (user.emailVerified) {
        await this.router.navigate(['/dashboard']);
      } else {
        this.errorMessage = 'Adres e-mail nie jest jeszcze potwierdzony.';
      }
    } catch (error) {
      this.errorMessage = firebaseErrorMessage(error);
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
