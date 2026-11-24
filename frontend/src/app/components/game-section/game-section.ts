import { Component, signal } from '@angular/core';
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
  protected readonly dropdownOpen = signal(false);
  protected readonly selectedGame = signal<GameOption | null>(null);

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
  }
}
