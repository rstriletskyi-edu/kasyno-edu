import { Component, input } from '@angular/core';
import { Blackjack } from '../games/blackjack-components/blackjack/blackjack';
import { Roulette } from '../games/roulette-components/roulette/roulette';
import { Slots } from '../games/slots-components/slots/slots';

export type GameType = 'blackjack' | 'roulette' | 'slots';

@Component({
  imports: [Blackjack, Roulette, Slots],
  selector: 'game-window',
  styleUrl: './game-window.css',
  templateUrl: './game-window.html',
})
export class GameWindow {
  readonly selectedGame = input<GameType | null>(null);
}
