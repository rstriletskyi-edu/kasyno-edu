import {
  Component,
  HostListener,
  OnDestroy,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import {
  DisplayCards,
  FLASHCARD_STATE_STORAGE_KEY,
  FlashcardState,
} from './display-cards/display-cards';
import { Leaderboard } from './leaderboard/leaderboard';
import { FlashcardBrowser } from './flashcard-browser/flashcard-browser';
import { LlmEvalService, LlmSessionRequest } from '../../services/llm-eval.service';
import { HttpErrorResponse } from '@angular/common/http';
import { Subscription } from 'rxjs';
import { LocalStorageService } from '../../services/local-storage.service';
import { SessionStorageService } from '../../services/session-storage.service';
import {
  LLM_PROVIDER_STORAGE_KEY,
  LlmProviderSettings,
} from '../settings-components/ai-provider-settings/ai-provider-settings';

export type LearningView = 'menu' | 'display-cards' | 'leaderboard' | 'flashcard-browser';
export const RESET_LEARNING_SESSION_EVENT = 'reset-learning-session';

@Component({
  imports: [DisplayCards, Leaderboard, FlashcardBrowser],
  selector: 'learning-section',
  styleUrl: './learning-section.css',
  templateUrl: './learning-section.html',
})
export class LearningSection implements OnInit, OnDestroy {
  private static hasActiveInAppSession = false;

  protected evalService = inject(LlmEvalService);
  protected storageService = inject(LocalStorageService);
  protected sessionStorageService = inject(SessionStorageService);

  private sessionSubscription: Subscription | null = null;
  private verifySubscription: Subscription | null = null;

  protected sessionId = signal<string | null>(null);
  protected loading = signal<boolean>(false);
  protected error = signal<boolean>(false);
  protected errorMessage = signal<string>('');
  protected llmSessionRequest = signal<LlmSessionRequest>({
    api_key: '',
    provider: '',
    model: '',
    base_url: '',
  });

  readonly activeView = signal<LearningView>('menu');
  readonly displayCardVisible = computed(() => this.activeView() === 'display-cards');

  static clearInAppSessionFlag(): void {
    LearningSection.hasActiveInAppSession = false;
  }

  static enableSilentSessionRecovery(): void {
    LearningSection.hasActiveInAppSession = true;
  }

  ngOnInit() {
    this.loading.set(false);
    this.error.set(false);
    this.errorMessage.set('');

    const savedSettings =
      this.storageService.getItem<LlmProviderSettings>(LLM_PROVIDER_STORAGE_KEY);

    if (savedSettings) {
      this.llmSessionRequest.set({
        api_key: savedSettings.apiKey ?? '',
        provider: savedSettings.provider ?? '',
        model: savedSettings.model ?? '',
        base_url: savedSettings.baseUrl ?? '',
      });
    }

    const savedFlashcardState = this.sessionStorageService.getItem<FlashcardState>(
      FLASHCARD_STATE_STORAGE_KEY,
    );

    if (savedFlashcardState?.sessionId && savedFlashcardState.sessionId.trim() !== '') {
      this.sessionId.set(savedFlashcardState.sessionId);
      this.activeView.set('display-cards');
      this.pushSessionHistoryState();
      this.verifyOrRecoverSession(savedFlashcardState);
    }
  }

  ngOnDestroy() {
    this.cancelSessionRequest();
  }

  @HostListener('window:popstate')
  onPopState() {
    this.cancelSessionRequest();
    if (this.activeView() !== 'menu') {
      this.goBackToMenu(true);
    }
  }

  @HostListener(`window:${RESET_LEARNING_SESSION_EVENT}`)
  onResetLearningSession() {
    this.goBackToMenu();
  }

  goToDisplayCards() {
    this.cancelSessionRequest();
    this.error.set(false);
    this.errorMessage.set('');
    this.loading.set(true);

    this.sessionSubscription = this.evalService.getLlmSession(this.llmSessionRequest()).subscribe({
      next: (sessionId) => {
        this.loading.set(false);
        if (sessionId === null || sessionId.trim() === '') {
          this.error.set(true);
          this.errorMessage.set('Nie udało się utworzyć sesji uczenia');
          return;
        }
        this.sessionStorageService.removeItem(FLASHCARD_STATE_STORAGE_KEY);
        LearningSection.hasActiveInAppSession = true;
        this.sessionId.set(sessionId);
        this.activeView.set('display-cards');
        this.pushSessionHistoryState();
      },
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(true);

        let message = 'Nie udało się utworzyć sesji uczenia';
        const statusCode = err.status ?? err.error?.status;
        const detail = err.error?.detail ?? err.error?.description;

        switch (statusCode) {
          case 401:
            message = 'Błąd autoryzacji użytkownika';
            break;
          case 403:
            message = 'Wymagane potwierdzenie adresu email';
            break;
          case 503:
            message = 'Nie skonfigurowano modelu walidacji';
            break;
          default:
            if (detail === 'Missing or invalid Firebase ID token') {
              message = 'Błąd autoryzacji użytkownika';
            } else if (detail === 'Email verification required') {
              message = 'Wymagane potwierdzenie adresu email';
            } else if (detail === 'No LLM API key is configured') {
              message = 'Nie skonfigurowano modelu walidacji';
            }
            break;
        }
        this.errorMessage.set(message);
      },
    });
  }

  goToLeaderboard() {
    this.cancelSessionRequest();
    this.error.set(false);
    this.errorMessage.set('');
    this.activeView.set('leaderboard');
    this.pushSessionHistoryState();
  }

  goToFlashcardBrowser() {
    this.cancelSessionRequest();
    this.error.set(false);
    this.errorMessage.set('');
    this.activeView.set('flashcard-browser');
    this.pushSessionHistoryState();
  }

  goBackToMenu(fromPopState = false) {
    this.cancelSessionRequest();
    LearningSection.hasActiveInAppSession = false;
    this.sessionStorageService.removeItem(FLASHCARD_STATE_STORAGE_KEY);
    this.activeView.set('menu');
    this.sessionId.set(null);
    this.error.set(false);
    this.errorMessage.set('');

    if (!fromPopState && typeof window !== 'undefined' && window.history.state?.learningSession) {
      window.history.replaceState({ ...window.history.state, learningSession: false }, '');
    }
  }

  private verifyOrRecoverSession(savedState: FlashcardState): void {
    const verification$ = this.evalService.verifyLlmSession?.(savedState.sessionId);
    if (!verification$) {
      LearningSection.hasActiveInAppSession = true;
      return;
    }

    this.verifySubscription?.unsubscribe();
    this.verifySubscription = verification$.subscribe({
      next: () => {
        LearningSection.hasActiveInAppSession = true;
      },
      error: () => {
        if (LearningSection.hasActiveInAppSession) {
          this.silentlyRecreateSession(savedState);
        } else {
          this.goBackToMenu();
        }
      },
    });
  }

  private silentlyRecreateSession(savedState: FlashcardState): void {
    this.sessionSubscription?.unsubscribe();
    this.sessionSubscription = this.evalService.getLlmSession(this.llmSessionRequest()).subscribe({
      next: (newSessionId) => {
        if (!newSessionId || newSessionId.trim() === '') {
          this.goBackToMenu();
          return;
        }
        LearningSection.hasActiveInAppSession = true;
        const currentState =
          this.sessionStorageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY) ??
          savedState;
        this.sessionStorageService.setItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY, {
          ...currentState,
          sessionId: newSessionId,
        });
        this.sessionId.set(newSessionId);
      },
      error: () => {
        this.goBackToMenu();
      },
    });
  }

  private cancelSessionRequest(): void {
    if (this.sessionSubscription) {
      this.sessionSubscription.unsubscribe();
      this.sessionSubscription = null;
    }
    if (this.verifySubscription) {
      this.verifySubscription.unsubscribe();
      this.verifySubscription = null;
    }
    this.loading.set(false);
  }

  private pushSessionHistoryState(): void {
    if (typeof window !== 'undefined' && !window.history.state?.learningSession) {
      window.history.pushState({ ...(window.history.state ?? {}), learningSession: true }, '');
    }
  }
}
