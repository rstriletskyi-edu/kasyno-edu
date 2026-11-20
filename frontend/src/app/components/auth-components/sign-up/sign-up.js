import { __decorate } from "tslib";
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';
let SignUp = class SignUp {
    auth = inject(FirebaseAuthService);
    router = inject(Router);
    email = '';
    password = '';
    confirmPassword = '';
    errorMessage = '';
    isSubmitting = false;
    async submit() {
        this.errorMessage = '';
        if (this.password !== this.confirmPassword) {
            this.errorMessage = 'Podane hasła nie są takie same.';
            return;
        }
        this.isSubmitting = true;
        try {
            await this.auth.signUp(this.email, this.password);
            await this.router.navigate(['/auth/account-activation']);
        }
        catch (error) {
            this.errorMessage = firebaseErrorMessage(error);
        }
        finally {
            this.isSubmitting = false;
        }
    }
    async signUpWithGoogle() {
        this.errorMessage = '';
        this.isSubmitting = true;
        try {
            const user = await this.auth.signInWithGoogle();
            await this.router.navigate([user.emailVerified ? '/dashboard' : '/auth/account-activation']);
        }
        catch (error) {
            this.errorMessage = firebaseErrorMessage(error);
        }
        finally {
            this.isSubmitting = false;
        }
    }
    async signUpWithFacebook() {
        this.errorMessage = '';
        this.isSubmitting = true;
        try {
            const user = await this.auth.signInWithFacebook();
            await this.router.navigate([user.emailVerified ? '/dashboard' : '/auth/account-activation']);
        }
        catch (error) {
            this.errorMessage = firebaseErrorMessage(error);
        }
        finally {
            this.isSubmitting = false;
        }
    }
};
SignUp = __decorate([
    Component({
        imports: [FormsModule, RouterLink],
        selector: 'sign-up',
        styleUrls: ['../auth.css', './sign-up.css'],
        templateUrl: './sign-up.html',
    })
], SignUp);
export { SignUp };
