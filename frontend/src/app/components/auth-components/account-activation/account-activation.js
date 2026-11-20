import { __decorate } from "tslib";
import { Component, HostListener, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FirebaseAuthService, firebaseErrorMessage } from '../../../services/firebase-auth.service';
let AccountActivation = class AccountActivation {
    auth = inject(FirebaseAuthService);
    router = inject(Router);
    email = '';
    errorMessage = '';
    successMessage = '';
    isSubmitting = false;
    timer;
    destroyed = false;
    ngOnInit() {
        void this.loadEmail();
        void this.checkVerification(false);
        this.timer = setInterval(() => {
            if (document.visibilityState === 'visible')
                void this.checkVerification(false);
        }, 5000);
    }
    ngOnDestroy() {
        this.destroyed = true;
        clearInterval(this.timer);
    }
    onFocus() {
        void this.checkVerification(false);
    }
    async resendEmail() {
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
        }
        catch (error) {
            this.errorMessage = firebaseErrorMessage(error);
        }
        finally {
            this.isSubmitting = false;
        }
    }
    async checkVerification(showPendingMessage = true) {
        if (this.isSubmitting || this.destroyed)
            return;
        this.errorMessage = '';
        this.isSubmitting = true;
        try {
            const user = await this.auth.getCurrentUser();
            if (!user) {
                await this.router.navigate(['/auth/login']);
                return;
            }
            await this.auth.refreshUser(user);
            if (this.destroyed)
                return;
            if (user.emailVerified) {
                clearInterval(this.timer);
                await this.auth.signOut();
                await this.router.navigate(['/auth/login'], { queryParams: { verified: '1' } });
            }
            else if (showPendingMessage) {
                this.errorMessage = 'Adres e-mail nie jest jeszcze potwierdzony.';
            }
        }
        catch (error) {
            if (!this.destroyed)
                this.errorMessage = firebaseErrorMessage(error);
        }
        finally {
            this.isSubmitting = false;
        }
    }
    async loadEmail() {
        try {
            this.email = (await this.auth.getCurrentUser())?.email ?? '';
        }
        catch (error) {
            this.errorMessage = firebaseErrorMessage(error);
        }
    }
};
__decorate([
    HostListener('window:focus')
], AccountActivation.prototype, "onFocus", null);
AccountActivation = __decorate([
    Component({
        imports: [RouterLink],
        selector: 'account-activation',
        styleUrl: '../auth.css',
        templateUrl: './account-activation.html',
    })
], AccountActivation);
export { AccountActivation };
