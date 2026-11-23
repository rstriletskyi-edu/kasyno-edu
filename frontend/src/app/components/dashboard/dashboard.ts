import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';

import { environment } from '../../../environments/environment';
import { CurrentUser, CurrentUserService } from '../../services/current-user.service';
import { FirebaseAuthService } from '../../services/firebase-auth.service';
import { LearningSection } from '../learning-section/learning-section';

@Component({
  imports: [],
  selector: 'dashboard',
  styleUrl: './dashboard.css',
  templateUrl: './dashboard.html',
})
export class Dashboard implements OnInit {
  private readonly users = inject(CurrentUserService);
  private readonly auth = inject(FirebaseAuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly router = inject(Router);

  readonly user = signal<CurrentUser | null>(null);
  readonly error = signal('');
  readonly loading = signal(false);
  readonly tokenMessage = signal('');
  readonly development = !environment.production;

  ngOnInit(): void {
    this.loadProfile();
  }

  returnToFlashcards(): void {
    LearningSection.enableSilentSessionRecovery();
    void this.router.navigate(['/home']);
  }

  loadProfile(): void {
    if (this.loading()) return;
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
        error: (error: HttpErrorResponse) => {
          const messages: Record<number, string> = {
            0: 'Nie można połączyć się z API. Sprawdź serwer i ustawienia CORS.',
            401: 'Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.',
            403: 'Potwierdź adres e-mail przed otwarciem konta.',
            503: 'Usługi Firebase na backendzie są niedostępne. Sprawdź konfigurację serwera.',
          };
          this.error.set(
            messages[error.status] ?? 'Nie udało się pobrać profilu. Spróbuj ponownie.',
          );
          this.loading.set(false);
        },
      });
  }

  async copyToken(): Promise<void> {
    if (!this.development) return;
    try {
      const token = await this.auth.getIdToken();
      if (!token) {
        this.tokenMessage.set('Zaloguj się, aby pobrać token.');
        return;
      }
      await navigator.clipboard.writeText(token);
      this.tokenMessage.set('Token skopiowany. Wklej go w Authorize na stronie API /docs.');
    } catch {
      this.tokenMessage.set('Nie udało się skopiować tokenu. Sprawdź uprawnienia schowka.');
    }
  }
}
