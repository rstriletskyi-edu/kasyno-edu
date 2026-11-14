import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';

@Component({
  imports: [FormsModule, RouterLink],
  selector: 'password-change',
  styleUrl: '../auth.css',
  templateUrl: './password-change.html',
})
export class PasswordChange {
  private readonly auth = inject(FirebaseAuthService);

  email = '';
  errorMessage = '';
  successMessage = '';
  isSubmitting = false;

  async submit(): Promise<void> {
    this.errorMessage = '';
    this.successMessage = '';
    this.isSubmitting = true;

    try {
      await this.auth.sendPasswordReset(this.email);
      this.successMessage = 'Jeśli konto istnieje, otrzymasz e-mail z linkiem do zmiany hasła.';
    } catch (error) {
      this.errorMessage = firebaseErrorMessage(error);
    } finally {
      this.isSubmitting = false;
    }
  }
}
