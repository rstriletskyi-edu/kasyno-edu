import { __decorate } from "tslib";
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { FirebaseAuthService } from '../../services/firebase-auth.service';
import { CurrentUserService } from '../../services/current-user.service';
let NavBar = class NavBar {
    auth = inject(FirebaseAuthService);
    router = inject(Router);
    users = inject(CurrentUserService);
    destroyRef = inject(DestroyRef);
    isLoggingOut = signal(false);
    logoutError = signal('');
    credits = signal(0);
    ngOnInit() {
        this.users
            .getMe()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
            next: (user) => this.credits.set(user.profile.credits),
            error: () => this.credits.set(0),
        });
    }
    async logout() {
        if (this.isLoggingOut())
            return;
        this.isLoggingOut.set(true);
        this.logoutError.set('');
        try {
            await this.auth.signOut();
            await this.router.navigate(['/auth/login'], { replaceUrl: true });
        }
        catch {
            this.logoutError.set('Nie udało się zakończyć wylogowania. Spróbuj ponownie.');
        }
        finally {
            this.isLoggingOut.set(false);
        }
    }
};
NavBar = __decorate([
    Component({
        imports: [RouterLink],
        selector: 'nav-bar',
        styleUrl: './nav-bar.css',
        templateUrl: './nav-bar.html',
    })
], NavBar);
export { NavBar };
