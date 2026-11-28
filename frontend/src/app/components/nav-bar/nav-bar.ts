import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FirebaseAuthService } from '../../services/firebase-auth.service';
import { SessionStorageService } from '../../services/session-storage.service';
import { CurrentUserService } from '../../services/current-user.service';
import { FLASHCARD_STATE_STORAGE_KEY } from '../learning-section/display-cards/display-cards';
import {
  LearningSection,
  RESET_LEARNING_SESSION_EVENT,
} from '../learning-section/learning-section';

@Component({
  imports: [RouterLink],
  selector: 'nav-bar',
  styleUrl: './nav-bar.css',
  templateUrl: './nav-bar.html',
})
export class NavBar implements OnInit {
  private readonly auth = inject(FirebaseAuthService);
  private readonly router = inject(Router);
  private readonly sessionStorageService = inject(SessionStorageService);
  private readonly users = inject(CurrentUserService);

  readonly credits = this.users.credits;

  readonly isLoggingOut = signal(false);
  readonly logoutError = signal('');

  ngOnInit(): void {
    this.users.refreshCredits();
  }

  resetLearningSession(): void {
    LearningSection.clearInAppSessionFlag();
    this.sessionStorageService.removeItem(FLASHCARD_STATE_STORAGE_KEY);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event(RESET_LEARNING_SESSION_EVENT));
    }
  }

  async logout(): Promise<void> {
    if (this.isLoggingOut()) return;
    this.isLoggingOut.set(true);
    this.logoutError.set('');

    try {
      await this.auth.signOut();
      this.users.credits.set(0);
      await this.router.navigate(['/auth/login'], { replaceUrl: true });
    } catch {
      this.logoutError.set('Nie udało się zakończyć wylogowania. Spróbuj ponownie.');
    } finally {
      this.isLoggingOut.set(false);
    }
  }
}
