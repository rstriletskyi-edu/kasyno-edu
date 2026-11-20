import { __decorate } from "tslib";
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';
let SignIn = class SignIn {
    auth = inject(FirebaseAuthService);
    router = inject(Router);
    accountVerified = inject(ActivatedRoute).snapshot.queryParamMap.get('verified') === '1';
    email = '';
    password = '';
    errorMessage = '';
    isSubmitting = false;
    async submit() {
        this.errorMessage = '';
        this.isSubmitting = true;
        try {
            const user = await this.auth.signIn(this.email, this.password);
            await this.router.navigate([user.emailVerified ? '/dashboard' : '/auth/account-activation']);
        }
        catch (error) {
            this.errorMessage = firebaseErrorMessage(error);
        }
        finally {
            this.isSubmitting = false;
        }
    }
    async signInWithGoogle() {
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
    async signInWithFacebook() {
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
SignIn = __decorate([
    Component({
        imports: [FormsModule, RouterLink],
        selector: 'sign-in',
        styleUrl: '../auth.css',
        templateUrl: './sign-in.html',
    })
], SignIn);
export { SignIn };
