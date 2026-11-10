import { Component, signal } from '@angular/core';

@Component({
  imports: [],
  selector: 'game-section',
  styleUrl: './game-section.css',
  templateUrl: './game-section.html',
})
export class GameSection {
  dropdownOpen = signal(false);

  games = [
    { name: 'Blackjack', icon: '🃏' },
    { name: 'Ruletka', icon: '🎡' },
    { name: 'Jednoręki bandyta', icon: '🎰' },
  ];

  toggleDropdown() {
    this.dropdownOpen.update(v => !v);
  }
}
