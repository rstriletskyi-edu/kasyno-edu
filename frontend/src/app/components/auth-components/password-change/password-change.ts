import { Component, inject, signal } from '@angular/core';
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
  readonly errorMessage = signal('');
  readonly successMessage = signal('');
  readonly isSubmitting = signal(false);

  async submit(): Promise<void> {
    this.errorMessage.set('');
    this.successMessage.set('');
    this.isSubmitting.set(true);

    try {
      await this.auth.sendPasswordReset(this.email);
      this.successMessage.set('Jeśli konto istnieje, otrzymasz e-mail z linkiem do zmiany hasła.');
    } catch (error) {
      this.errorMessage.set(firebaseErrorMessage(error));
    } finally {
      this.isSubmitting.set(false);
    }
  }
}
