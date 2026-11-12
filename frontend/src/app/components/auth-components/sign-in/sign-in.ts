import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';

@Component({
  imports: [FormsModule, RouterLink],
  selector: 'sign-in',
  styleUrl: '../auth.css',
  templateUrl: './sign-in.html',
})
export class SignIn {
  private readonly auth = inject(FirebaseAuthService);
  private readonly router = inject(Router);

  email = '';
  password = '';
  errorMessage = '';
  isSubmitting = false;

  async submit(): Promise<void> {
    this.errorMessage = '';
    this.isSubmitting = true;

    try {
      const user = await this.auth.signIn(this.email, this.password);
      await this.router.navigate([user.emailVerified ? '/dashboard' : '/auth/account-activation']);
    } catch (error) {
      this.errorMessage = firebaseErrorMessage(error);
    } finally {
      this.isSubmitting = false;
    }
  }
}
