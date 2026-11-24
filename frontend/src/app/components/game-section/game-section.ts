import { Component, inject, signal } from '@angular/core';
import { FirebaseAuthService } from '../../services/firebase-auth.service';
import { GameType, GameWindow } from './game-window/game-window';

export interface GameOption {
  id: GameType;
  name: string;
  icon: string;
}

@Component({
  imports: [GameWindow],
  selector: 'game-section',
  styleUrl: './game-section.css',
  templateUrl: './game-section.html',
})
export class GameSection {
  private readonly auth = inject(FirebaseAuthService);

  protected readonly dropdownOpen = signal(false);
  protected readonly selectedGame = signal<GameOption | null>(null);
  protected readonly loading = signal<boolean>(false);
  protected readonly error = signal<boolean>(false);
  protected readonly errorMessage = signal<string>('');

  protected readonly games: GameOption[] = [
    { id: 'blackjack', name: 'Blackjack', icon: '🃏' },
    { id: 'roulette', name: 'Ruletka', icon: '🎡' },
    { id: 'slots', name: 'Sloty', icon: '🎰' },
  ];

  toggleDropdown(): void {
    this.dropdownOpen.update((open) => !open);
  }

  selectGame(game: GameOption): void {
    this.selectedGame.set(game);
    this.dropdownOpen.set(false);
    this.error.set(false);
    this.errorMessage.set('');
  }

  async playGame(): Promise<void> {
    if (!this.selectedGame() || this.loading()) {
      return;
    }

    this.error.set(false);
    this.errorMessage.set('');
    this.loading.set(true);

    try {
      if (!this.auth.isConfigured) {
        this.error.set(true);
        this.errorMessage.set('Użytkownik niezalogowany. Zaloguj się, aby rozpocząć grę.');
        return;
      }

      const user = await this.auth.getCurrentUser();
      if (!user) {
        this.error.set(true);
        this.errorMessage.set('Użytkownik niezalogowany. Zaloguj się, aby rozpocząć grę.');
        return;
      }
    } catch {
      this.error.set(true);
      this.errorMessage.set('Użytkownik niezalogowany. Zaloguj się, aby rozpocząć grę.');
    } finally {
      this.loading.set(false);
    }
  }
}
