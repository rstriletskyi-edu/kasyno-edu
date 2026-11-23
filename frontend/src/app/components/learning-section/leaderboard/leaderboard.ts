import { Component, output } from '@angular/core';

@Component({
  imports: [],
  selector: 'leaderboard',
  styleUrl: './leaderboard.css',
  templateUrl: './leaderboard.html',
})
export class Leaderboard {
  readonly returnToMenuEvent = output<void>();

  returnToMenu(): void {
    this.returnToMenuEvent.emit();
  }
}
