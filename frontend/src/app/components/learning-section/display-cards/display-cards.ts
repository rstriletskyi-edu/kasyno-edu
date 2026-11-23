import {
  Component,
  HostListener,
  OnDestroy,
  OnInit,
  inject,
  signal,
  output,
  input,
} from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Subscription } from 'rxjs';
import { Flashcard, FlashcardsService } from '../../../services/flashcards.service';
import { LlmEvalService, EvaluationResult } from '../../../services/llm-eval.service';
import { SessionStorageService } from '../../../services/session-storage.service';

export const FLASHCARD_STATE_STORAGE_KEY = 'flashcard_state';
export const MAX_ANSWER_LENGTH = 2000;

export interface AnswerAnalysis {
  userAnswer: string;
  expectedAnswer: string;
  score: number;
  verdict: string;
  creditsReceived: number;
  explanation: string;
}

export interface FlashcardState {
  sessionId: string;
  currentCardId: string | null;
  answer: string;
  usedIds: string[];
  isFlipped: boolean;
  answerAnalysis: AnswerAnalysis | null;
  finished: boolean;
}

@Component({
  imports: [],
  selector: 'display-cards',
  styleUrl: './display-cards.css',
  templateUrl: './display-cards.html',
})
export class DisplayCards implements OnInit, OnDestroy {
  private readonly flashcardsService = inject(FlashcardsService);
  private readonly evalService = inject(LlmEvalService);
  private readonly storageService = inject(SessionStorageService);

  private evalSubscription: Subscription | null = null;
  private cardSubscription: Subscription | null = null;

  readonly maxAnswerLength = MAX_ANSWER_LENGTH;
  readonly sessionId = input<string | null>(null);
  returnToMenuEvent = output<void>();

  readonly isFlipped = signal(false);
  readonly flipDirection = signal<'forward' | 'reverse'>('forward');
  readonly noTransition = signal(false);
  readonly currentCard = signal<Flashcard | null>(null);
  readonly answer = signal('');
  readonly evaluating = signal(false);

  readonly answerAnalysis = signal<AnswerAnalysis | null>(null);
  readonly evalError = signal<string | null>(null);

  readonly usedIds = signal<string[]>([]);
  readonly loading = signal(false);
  readonly loadError = signal(false);
  readonly finished = signal(false);
  readonly errorMessage = signal('');

  readonly coinStartX = signal(0);
  readonly coinStartY = signal(0);
  readonly coinAnimation = signal(false);
  readonly coinParticles = signal<number[]>([]);

  ngOnInit() {
    const activeSessionId = this.sessionId();
    if (!activeSessionId) {
      this.returnToMenuEvent.emit();
      return;
    }

    this.evaluating.set(false);
    this.loading.set(false);

    const savedState = this.storageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY);
    if (savedState && savedState.sessionId === activeSessionId) {
      this.restoreFromState(savedState);
      return;
    }

    this.saveState();
    this.loadFlashcard();
  }

  ngOnDestroy() {
    const wasEvaluating = this.evaluating();
    this.cancelPendingRequests();
    if (wasEvaluating && this.storageService.getItem(FLASHCARD_STATE_STORAGE_KEY)) {
      this.isFlipped.set(false);
      this.saveState({ isFlipped: false, answerAnalysis: null });
    }
  }

  @HostListener('window:beforeunload')
  onBeforeUnload() {
    if (this.evaluating()) {
      this.cancelPendingRequests();
      this.isFlipped.set(false);
      this.saveState({ isFlipped: false, answerAnalysis: null });
    } else {
      this.saveState();
    }
  }

  private restoreFromState(savedState: FlashcardState) {
    this.usedIds.set(Array.isArray(savedState.usedIds) ? savedState.usedIds : []);
    this.answer.set((savedState.answer ?? '').slice(0, this.maxAnswerLength));
    this.finished.set(Boolean(savedState.finished));
    this.evaluating.set(false);
    this.evalError.set(null);
    this.loadError.set(false);
    this.errorMessage.set('');

    if (savedState.finished) {
      this.answerAnalysis.set(null);
      this.noTransition.set(true);
      this.flipDirection.set('forward');
      this.isFlipped.set(true);
      this.loading.set(false);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          this.noTransition.set(false);
        });
      });
      return;
    }

    if (savedState.isFlipped && savedState.answerAnalysis) {
      this.answerAnalysis.set(savedState.answerAnalysis);
      this.noTransition.set(true);
      this.flipDirection.set('forward');
      this.isFlipped.set(true);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          this.noTransition.set(false);
        });
      });
    } else {
      this.answerAnalysis.set(null);
      this.isFlipped.set(false);
      this.flipDirection.set('forward');
    }

    if (savedState.currentCardId) {
      this.loadConcreteFlashcard(savedState.currentCardId);
    } else {
      this.loadFlashcard();
    }
  }

  private loadConcreteFlashcard(cardId: string) {
    this.cardSubscription?.unsubscribe();
    this.loading.set(true);
    this.loadError.set(false);
    this.evalError.set(null);
    this.errorMessage.set('');

    this.cardSubscription = this.flashcardsService.getConcreteFlashcard(cardId).subscribe({
      next: (flashcard) => {
        this.currentCard.set(flashcard);
        this.loading.set(false);
        this.saveState();
      },
      error: () => {
        this.loading.set(false);
        this.loadError.set(true);
      },
    });
  }

  retryLoadFlashcard() {
    const savedState = this.storageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY);
    if (!this.currentCard() && savedState?.currentCardId) {
      this.loadConcreteFlashcard(savedState.currentCardId);
      return;
    }
    this.loadFlashcard();
  }

  loadFlashcard() {
    this.cardSubscription?.unsubscribe();
    this.loading.set(true);
    this.loadError.set(false);
    this.answerAnalysis.set(null);
    this.evalError.set(null);
    this.errorMessage.set('');

    this.cardSubscription = this.flashcardsService.getRandomFlashcard(this.usedIds()).subscribe({
      next: (flashcard) => {
        this.currentCard.set(flashcard);
        this.answer.set('');
        this.isFlipped.set(false);
        this.flipDirection.set('forward');
        this.loading.set(false);
        this.saveState();
      },
      error: () => {
        this.loading.set(false);
        this.loadError.set(true);
      },
    });
  }

  updateAnswer(value: string) {
    this.answer.set(value.slice(0, this.maxAnswerLength));
    this.saveState();
  }

  returnToMenu() {
    this.cancelPendingRequests();
    this.storageService.removeItem(FLASHCARD_STATE_STORAGE_KEY);
    this.returnToMenuEvent.emit();
  }

  previousFlashcard() {
    const currentUsedIds = this.usedIds();
    if (!currentUsedIds.length || this.loading()) return;

    const wasFlipped = this.isFlipped();
    const isCurrentInUsed =
      wasFlipped && currentUsedIds.length > 1 && currentUsedIds.at(-1) === this.currentCard()?.id;
    const targetId = isCurrentInUsed ? currentUsedIds.at(-2) : currentUsedIds.at(-1);
    const updatedUsedIds = isCurrentInUsed
      ? currentUsedIds.slice(0, -2)
      : currentUsedIds.slice(0, -1);

    if (!targetId) return;

    this.cardSubscription?.unsubscribe();
    this.loading.set(true);
    this.loadError.set(false);
    this.evalError.set(null);

    if (wasFlipped) {
      this.currentCard.set(null);
      this.noTransition.set(false);
      this.flipDirection.set('forward');
      this.isFlipped.set(false);
    }

    this.cardSubscription = this.flashcardsService.getConcreteFlashcard(targetId).subscribe({
      next: (flashcard) => {
        this.usedIds.set(updatedUsedIds);
        this.currentCard.set(flashcard);
        this.answer.set('');
        this.answerAnalysis.set(null);

        if (wasFlipped) {
          this.loading.set(false);
          this.saveState({
            currentCardId: flashcard.id,
            answer: '',
            usedIds: updatedUsedIds,
            isFlipped: false,
            answerAnalysis: null,
          });
          return;
        }

        this.noTransition.set(true);
        this.flipDirection.set('reverse');
        this.isFlipped.set(true);
        this.saveState({
          currentCardId: flashcard.id,
          answer: '',
          usedIds: updatedUsedIds,
          isFlipped: false,
          answerAnalysis: null,
        });

        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            this.noTransition.set(false);
            this.isFlipped.set(false);
            this.flipDirection.set('forward');
            this.loading.set(false);
            this.saveState();
          });
        });
      },
      error: () => {
        this.loadError.set(true);
        this.loading.set(false);
      },
    });
  }

  submitAnswer() {
    if (this.isFlipped() || !this.answer().trim()) {
      return;
    }

    const card = this.currentCard();
    if (!card) {
      this.loadError.set(true);
      return;
    }

    this.evalSubscription?.unsubscribe();
    this.loading.set(true);
    this.evaluating.set(true);
    this.loadError.set(false);
    this.evalError.set(null);

    this.flipDirection.set('forward');
    this.isFlipped.set(true);

    // FRAGMENT NA POTRZEBY TESTÓW BEZ FAKTYCZNEJ EWALUACJI
    // trzeba odkomentować poniższy kod, a dokładnie całe wywołanie this.evalSubscription)
    //
    // const answerAnalysis = {
    //   userAnswer: this.answer(),
    //   expectedAnswer: "Oczekiwana odpowiedź",
    //   score: 67,
    //   verdict: "częściowo poprawna",
    //   creditsReceived: 6,
    //   explanation: "Uzasadnienie oceny odpowiedzi opracowane przez model AI"
    // }
    // this.answerAnalysis.set(answerAnalysis)
    // this.usedIds.update((ids) => [...ids, this.currentCard()!.id]);
    // this.evaluating.set(false);
    // this.loading.set(false);

    this.evalSubscription = this.evalService
      .getAnswerEvaluation(this.sessionId()!, {
        question_id: card.id,
        user_answer: this.answer(),
      })
      .subscribe({
        next: (evaluation: EvaluationResult) => {
          const analysis: AnswerAnalysis = {
            userAnswer: this.answer(),
            expectedAnswer: card.expected_answer,
            score: evaluation.score,
            verdict:
              evaluation.verdict === 'correct'
                ? 'poprawna'
                : evaluation.verdict === 'incorrect'
                  ? 'niepoprawna'
                  : 'częściowo poprawna',
            creditsReceived: evaluation.credits_received,
            explanation: evaluation.explanation,
          };
          this.answerAnalysis.set(analysis);
          this.usedIds.update((ids) => (ids.includes(card.id) ? ids : [...ids, card.id]));
          this.evaluating.set(false);
          this.loading.set(false);
          this.saveState();
        },
        error: (err: HttpErrorResponse) => {
          let message = 'Nie udało się przeprowadzić ewaluacji';
          const statusCode = err.status ?? err.error?.status;
          switch (statusCode) {
            case 401:
              message = 'Błąd autoryzacji użytkownika';
              break;
            case 403:
              message = 'Wymagana weryfikacja adresu email';
              break;
            case 404:
              message = 'Nieznana lub wygasła sesja';
              break;
            case 422:
              message = 'Niedozwolony format odpowiedzi';
              break;
            case 502:
              message = 'Błąd modelu walidującego';
              break;
            case 504:
              message = 'Przekroczono limit czasu ewaluacji';
              break;
            default:
              break;
          }
          this.evalError.set(message);
          this.evaluating.set(false);
          this.loading.set(false);
          this.isFlipped.set(false);
          this.saveState({ isFlipped: false, answerAnalysis: null });
        },
      });
  }

  resetCard() {
    if (!this.isFlipped() || this.loading()) {
      return;
    }
    this.loadFlashcard();
  }

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

  nextFlashcard(event: MouseEvent) {
    if (this.usedIds().length >= 82) {
      this.finished.set(true);
      this.saveState({ finished: true, isFlipped: true });
      return;
    }

    const button = event.currentTarget as HTMLElement;
    const rect = button.getBoundingClientRect();
    this.coinStartX.set(rect.left + rect.width / 2);
    this.coinStartY.set(rect.top - rect.height * 2);

    const credits = this.answerAnalysis()?.creditsReceived ?? 0;
    if (credits > 0) {
      this.playCoinAnimation(credits);
    }

    this.resetCard();
  }

  private cancelPendingRequests(): void {
    if (this.evalSubscription) {
      this.evalSubscription.unsubscribe();
      this.evalSubscription = null;
    }
    if (this.cardSubscription) {
      this.cardSubscription.unsubscribe();
      this.cardSubscription = null;
    }
    this.evaluating.set(false);
    this.loading.set(false);
  }

  private saveState(overrides?: Partial<FlashcardState>): void {
    const activeSessionId = this.sessionId();
    if (!activeSessionId) {
      return;
    }

    const effectiveAnalysis =
      overrides && 'answerAnalysis' in overrides
        ? (overrides.answerAnalysis ?? null)
        : this.answerAnalysis();
    const effectiveFinished = overrides?.finished ?? this.finished();
    const effectiveIsFlipped =
      overrides?.isFlipped ??
      (this.isFlipped() && !this.evaluating() && (effectiveAnalysis !== null || effectiveFinished));

    const state: FlashcardState = {
      sessionId: activeSessionId,
      currentCardId:
        overrides && 'currentCardId' in overrides
          ? (overrides.currentCardId ?? null)
          : (this.currentCard()?.id ?? null),
      answer: overrides?.answer ?? this.answer(),
      usedIds: overrides?.usedIds ?? this.usedIds(),
      isFlipped: effectiveIsFlipped,
      answerAnalysis: effectiveAnalysis,
      finished: effectiveFinished,
    };

    this.storageService.setItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY, state);
  }
}
