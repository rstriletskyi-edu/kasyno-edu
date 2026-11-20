import { __decorate } from "tslib";
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { environment } from '../../../environments/environment';
import { CurrentUserService } from '../../services/current-user.service';
import { FirebaseAuthService } from '../../services/firebase-auth.service';
let Dashboard = class Dashboard {
    users = inject(CurrentUserService);
    auth = inject(FirebaseAuthService);
    destroyRef = inject(DestroyRef);
    user = signal(null);
    error = signal('');
    loading = signal(false);
    tokenMessage = signal('');
    development = !environment.production;
    ngOnInit() {
        this.loadProfile();
    }
    loadProfile() {
        if (this.loading())
            return;
        this.loading.set(true);
        this.error.set('');
        this.user.set(null);
        this.users
            .getMe()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
            next: (user) => {
                this.user.set(user);
                this.loading.set(false);
            },
            error: (error) => {
                const messages = {
                    0: 'Nie można połączyć się z API. Sprawdź serwer i ustawienia CORS.',
                    401: 'Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.',
                    403: 'Potwierdź adres e-mail przed otwarciem konta.',
                    503: 'Usługi Firebase na backendzie są niedostępne. Sprawdź konfigurację serwera.',
                };
                this.error.set(messages[error.status] ?? 'Nie udało się pobrać profilu. Spróbuj ponownie.');
                this.loading.set(false);
            },
        });
    }
    async copyToken() {
        if (!this.development)
            return;
        try {
            const token = await this.auth.getIdToken();
            if (!token) {
                this.tokenMessage.set('Zaloguj się, aby pobrać token.');
                return;
            }
            await navigator.clipboard.writeText(token);
            this.tokenMessage.set('Token skopiowany. Wklej go w Authorize na stronie API /docs.');
        }
        catch {
            this.tokenMessage.set('Nie udało się skopiować tokenu. Sprawdź uprawnienia schowka.');
        }
    }
};
Dashboard = __decorate([
    Component({
        imports: [],
        selector: 'dashboard',
        styleUrl: './dashboard.css',
        templateUrl: './dashboard.html',
    })
], Dashboard);
export { Dashboard };
