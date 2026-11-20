import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { FirebaseAuthService } from '../../services/firebase-auth.service';

@Component({
  imports: [RouterLink],
  selector: 'nav-bar',
  styleUrl: './nav-bar.css',
  templateUrl: './nav-bar.html',
})
export class NavBar {
  private readonly auth = inject(FirebaseAuthService);
  private readonly router = inject(Router);

  readonly isLoggingOut = signal(false);
  readonly logoutError = signal('');

  async logout(): Promise<void> {
    if (this.isLoggingOut()) return;
    this.isLoggingOut.set(true);
    this.logoutError.set('');

    try {
      await this.auth.signOut();
      await this.router.navigate(['/auth/login'], { replaceUrl: true });
    } catch {
      this.logoutError.set('Nie udało się zakończyć wylogowania. Spróbuj ponownie.');
    } finally {
      this.isLoggingOut.set(false);
    }
  }
}
