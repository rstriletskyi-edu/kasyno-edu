import { Component, computed, inject, signal, output } from '@angular/core';
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
  readonly cards = signal<Flashcard[]>([]);
  readonly currentIndex = signal(0);
  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly finished = signal(false);
  readonly answer = signal('');
  readonly currentCard = computed(() => this.cards()[this.currentIndex()]);

  constructor() {
    this.loadFlashcards();
  }

  loadFlashcards() {
    this.loading.set(true);
    this.loadError.set(false);

    this.flashcardsService.getFlashcards().subscribe({
      next: (response) => {
        this.cards.set(response.items);
        this.currentIndex.set(0);
        this.answer.set('');
        this.finished.set(false);
        this.loading.set(false);
      },
      error: () => {
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

    if (this.currentIndex() + 1 >= this.cards().length) {
      this.finished.set(true);
      return;
    }

    this.currentIndex.update((index) => index + 1);
    this.answer.set('');
  }
}
