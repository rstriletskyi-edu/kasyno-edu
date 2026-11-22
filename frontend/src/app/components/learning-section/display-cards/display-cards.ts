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

  previousFlashcard() {
    const lastId = this.usedIds().at(-1);
    if (!lastId) return;

    this.loading.set(true);
    this.loadError.set(false);

    this.flashcardsService.getConcreteFlashcard(lastId).subscribe({
      next: (flashcard) => {
        this.currentCard.set(flashcard);
        this.answer.set('');
        this.usedIds.update((ids) => ids.slice(0, -1));
        this.loading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.loadError.set(true);
        this.loading.set(false);
      },
    });
  }

  submitAnswer() {
    //tak samo jak w innych funkcjach obsłuż flagę błędu i ładowania

    if (!this.answer().trim()) return;

    const flashcard = this.currentCard();
    if (!flashcard) return;

    this.loading.set(true);
    this.loadError.set(false);
    this.evaluationResult.set(null);

    this.evalService
      .getAnswerEvaluation(
        this.sessionId()! /*nie możemy dodać null na razie "!"" ignoruje*/,
        /*obiekt EvaluationRequest z llm-eval.service.ts*/ {
          question_id: flashcard.id /*tu tak samo nie możemy dopuścić do null id*/,
          user_answer: this.answer(),
        },
      )
      .subscribe({
        next: (evaluation: EvalResponse) => {
          // tutaj przypisanie wyniku do zmiennej wyświetlającej wyniki wg modelu EvaluationResult z llm-eval.service.ts
          this.evaluationResult.set(evaluation);

          this.usedIds.update((ids) => [...ids, flashcard.id]);
          this.loadFlashcards();
        },
        error: (err: HttpErrorResponse) => {
          // obsługa błędów
          this.loadError.set(true);
          this.loading.set(false);
        },
      });
  }
}
