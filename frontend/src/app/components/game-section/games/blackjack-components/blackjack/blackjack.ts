import { Component, input, output, signal } from '@angular/core';

export interface BlackjackCard {
  rank: string;
  suit: string;
}

export type BlackjackAction = 'hit' | 'stand' | 'double';

@Component({
  imports: [],
  selector: 'blackjack',
  styleUrl: './blackjack.css',
  templateUrl: './blackjack.html',
})
export class Blackjack {
  readonly gameId = input<string | null>(null);
  readonly status = input<'in_progress' | 'finished' | null>(null);
  readonly outcome = input<string | null>(null);
  readonly betAmount = input<number>(0);
  readonly payout = input<number>(0);
  readonly balance = input<number>(0);
  readonly playerCards = input<BlackjackCard[]>([]);
  readonly playerValue = input<number>(0);
  readonly playerIsSoft = input<boolean>(false);
  readonly dealerCards = input<BlackjackCard[]>([]);
  readonly dealerValue = input<number>(0);
  readonly dealerHiddenCards = input<number>(0);
  readonly availableActions = input<BlackjackAction[]>([]);
  readonly loading = input<boolean>(false);
  readonly errorMessage = input<string>('');

  readonly stakeChanged = output<number>();
  readonly start = output<number>();
  readonly hit = output<void>();
  readonly stand = output<void>();
  readonly double = output<void>();

  readonly stake = signal<number>(10);

  changeStake(value: string): void {
    const stake = Number(value);
    this.stake.set(Number.isFinite(stake) ? stake : 0);
    this.stakeChanged.emit(this.stake());
  }

  requestStart(): void {
    if (this.stake() > 0 && !this.loading()) {
      this.start.emit(this.stake());
    }
  }

  requestHit(): void {
    if (this.availableActions().includes('hit') && !this.loading()) {
      this.hit.emit();
    }
  }

  requestStand(): void {
    if (this.availableActions().includes('stand') && !this.loading()) {
      this.stand.emit();
    }
  }

  requestDouble(): void {
    if (this.availableActions().includes('double') && !this.loading()) {
      this.double.emit();
    }
  }

  cardSymbol(card: BlackjackCard): string {
    const suits: Record<string, string> = {
      spades: '♠', hearts: '♥', diamonds: '♦', clubs: '♣',
    };
    return `${card.rank}${suits[card.suit] ?? card.suit}`;
  }

  cardIsRed(card: BlackjackCard): boolean {
    return card.suit === 'hearts' || card.suit === 'diamonds';
  }

  hiddenCards(): number[] {
    const count = Math.max(0, Math.floor(this.dealerHiddenCards()));
    return Array.from({ length: count });
  }

  outcomeLabel(): string {
    const labels: Record<string, string> = {
      player_blackjack: 'Blackjack gracza',
      dealer_blackjack: 'Blackjack krupiera',
      player_win: 'Wygrana gracza',
      dealer_win: 'Wygrana krupiera',
      player_bust: 'Przekroczenie',
      dealer_bust: 'Krupier przekroczył 21',
      push: 'Remis',
    };
    return this.outcome() ? labels[this.outcome()!] : '';
  }
}
