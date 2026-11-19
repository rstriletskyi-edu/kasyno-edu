import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal, output } from '@angular/core';
import { Flashcard, FlashcardsService } from '../../../services/flashcards.service';

@Component({
  imports: [],
  selector: 'display-cards',
  styleUrl: './display-cards.css',
  templateUrl: './display-cards.html',
})
export class DisplayCards {
  private readonly flashcardsService = inject(FlashcardsService);

  returnToMenuEvent = output<void>();
  readonly currentCard = signal<Flashcard | null>(null);
  readonly usedIds = signal<string[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly finished = signal(false);
  readonly answer = signal('');

  constructor() {
    this.loadFlashcards();
  }

  loadFlashcards() {
    this.loading.set(true);
    this.loadError.set(false);

    this.flashcardsService.getRandomFlashcard(this.usedIds()).subscribe({
      next: (flashcard) => {
        this.currentCard.set(flashcard);
        this.answer.set('');
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 404) {
          this.finished.set(true);
          this.loading.set(false);
          return;
        }
        this.loadError.set(true);
        this.loading.set(false);
      },
    });
  }

  updateAnswer(value: string) {
    this.answer.set(value);
  }

  returnToMenu() {
    this.returnToMenuEvent.emit();
  }

  submitAnswer() {
    if (!this.answer().trim()) return;

    const flashcard = this.currentCard();
    if (!flashcard) return;

    this.usedIds.update((ids) => [...ids, flashcard.id]);
    this.loadFlashcards();
  }
}
