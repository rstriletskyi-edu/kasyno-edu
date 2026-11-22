import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal, output, input } from '@angular/core';
import { Flashcard, FlashcardsService } from '../../../services/flashcards.service';
import {
  LlmEvalService,
  EvaluationRequest,
  EvalResponse,
} from '../../../services/llm-eval.service';

@Component({
  imports: [],
  selector: 'display-cards',
  styleUrl: './display-cards.css',
  templateUrl: './display-cards.html',
})
export class DisplayCards {
  readonly isFlipped = signal(false);

  private readonly flashcardsService = inject(FlashcardsService);
  protected evalService = inject(LlmEvalService);

  readonly sessionId = input<string | null>(null);

  returnToMenuEvent = output<void>();
  readonly currentCard = signal<Flashcard | null>(null);
  readonly usedIds = signal<string[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly finished = signal(false);
  readonly answer = signal('');
  readonly evaluationResult = signal<EvalResponse | null>(null);

  readonly coinStartX = signal(0);
  readonly coinStartY = signal(0);
  readonly coinAnimation = signal(false);
  readonly coinParticles = signal<number[]>([]);

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
        this.isFlipped.set(false);
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

  previousFlashcard() {
    const lastId = this.usedIds().at(-1);
    if (!lastId) return;

    this.loading.set(true);
    this.loadError.set(false);
    this.isFlipped.set(true);

    this.flashcardsService.getConcreteFlashcard(lastId).subscribe({
      next: (flashcard) => {
        this.currentCard.set(flashcard);
        this.answer.set('');
        this.usedIds.update((ids) => ids.slice(0, -1));
        this.loading.set(false);
        this.isFlipped.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.loadError.set(true);
        this.loading.set(false);
      },
    });
  }

  submitAnswer() {
    if (!this.answer().trim()) return;

    const flashcard = this.currentCard();
    if (!flashcard) return;

    this.loading.set(true);
    this.loadError.set(false);
    this.evaluationResult.set(null);

    const request: EvaluationRequest = {
      question_id: flashcard.id,
      user_answer: this.answer(),
    };

    this.evalService.getAnswerEvaluation(this.sessionId()!, request).subscribe({
      next: (evaluation: EvalResponse) => {
        this.evaluationResult.set(evaluation);

        this.usedIds.update((ids) => [...ids, flashcard.id]);
        this.loadFlashcards();
      },
      error: (err: HttpErrorResponse) => {
        this.loadError.set(true);
        this.loading.set(false);
      },
    });

    this.usedIds.update((ids) => [...ids, flashcard.id]);
    this.isFlipped.set(true);
  }

  resetCard() {
    if (!this.isFlipped() || this.loading()) {
      return;
    }
    const flashcard = this.currentCard();
    if (!flashcard) return;
    this.loadFlashcards();
  }

  //Funkcja odtwarzająca animację monet, obecnie wywoływana przez testCoinAnimation z góry ustaloną liczbą monet.
  playCoinAnimation(tokens: number) {
    if (tokens <= 0 || this.coinAnimation()) return;

    const particles = Math.min(tokens, 10);

    this.coinParticles.set(Array.from({ length: particles }, (_, i) => i));

    this.coinAnimation.set(true);

    setTimeout(() => {
      this.coinAnimation.set(false);
      this.coinParticles.set([]);
    }, 1600);
  }

  //Funkcja do sprawdzenia dzialania animacji, do usunięcia po implementacji oceny odpowiedzi przez llm
  testCoinAnimation() {
    this.playCoinAnimation(5);
  }

  //Funkcja wywołująca animację monet i resetująca kartę, do potencjalnej modyfikacji w przyszlosci.
  nextFlashcard(event: MouseEvent) {
    const button = event.currentTarget as HTMLElement;
    const rect = button.getBoundingClientRect();

    this.coinStartX.set(rect.left + rect.width / 2);
    this.coinStartY.set(rect.top - rect.height * 2);

    this.testCoinAnimation();
    this.resetCard();
  }
}
