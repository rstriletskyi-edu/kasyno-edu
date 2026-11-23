import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { LearningSection, RESET_LEARNING_SESSION_EVENT } from './learning-section';
import { FLASHCARD_STATE_STORAGE_KEY, FlashcardState } from './display-cards/display-cards';
import { FlashcardsService } from '../../services/flashcards.service';
import { LlmEvalService } from '../../services/llm-eval.service';
import { SessionStorageService } from '../../services/session-storage.service';

describe('LearningSection', () => {
  let component: LearningSection;
  let fixture: ComponentFixture<LearningSection>;
  let evalServiceMock: {
    getLlmSession: ReturnType<typeof vi.fn>;
    verifyLlmSession: ReturnType<typeof vi.fn>;
    getAnswerEvaluation: ReturnType<typeof vi.fn>;
  };
  let flashcardsServiceMock: {
    getRandomFlashcard: ReturnType<typeof vi.fn>;
    getConcreteFlashcard: ReturnType<typeof vi.fn>;
  };
  let sessionStorageService: SessionStorageService;

  beforeEach(async () => {
    localStorage.clear();
    sessionStorage.clear();
    LearningSection.clearInAppSessionFlag();

    evalServiceMock = {
      getLlmSession: vi.fn().mockReturnValue(of('new-session-id')),
      verifyLlmSession: vi.fn().mockReturnValue(of('saved-session-999')),
      getAnswerEvaluation: vi.fn(),
    };

    flashcardsServiceMock = {
      getRandomFlashcard: vi.fn().mockReturnValue(
        of({
          id: 'card-1',
          question: 'Pytanie 1',
          expected_answer: 'Odpowiedź 1',
          category: 'Ogólne',
        }),
      ),
      getConcreteFlashcard: vi.fn().mockReturnValue(
        of({
          id: 'card-1',
          question: 'Pytanie 1',
          expected_answer: 'Odpowiedź 1',
          category: 'Ogólne',
        }),
      ),
    };

    await TestBed.configureTestingModule({
      imports: [LearningSection],
      providers: [
        { provide: LlmEvalService, useValue: evalServiceMock },
        { provide: FlashcardsService, useValue: flashcardsServiceMock },
      ],
    }).compileComponents();

    sessionStorageService = TestBed.inject(SessionStorageService);
    fixture = TestBed.createComponent(LearningSection);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    LearningSection.clearInAppSessionFlag();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
    expect(component.displayCardVisible()).toBe(false);
    expect(component.activeView()).toBe('menu');
  });

  it('should restore active session from sessionStorage on init when backend session is valid', () => {
    const savedState: FlashcardState = {
      sessionId: 'saved-session-999',
      currentCardId: 'card-1',
      answer: 'Częściowa odpowiedź',
      usedIds: [],
      isFlipped: false,
      answerAnalysis: null,
      finished: false,
    };
    sessionStorageService.setItem(FLASHCARD_STATE_STORAGE_KEY, savedState);

    const restoredFixture = TestBed.createComponent(LearningSection);
    restoredFixture.detectChanges();

    expect(evalServiceMock.verifyLlmSession).toHaveBeenCalledWith('saved-session-999');
    expect(restoredFixture.componentInstance.displayCardVisible()).toBe(true);
  });

  it('should reset to clean menu state on startup if saved session in sessionStorage expired on backend (e.g. after backend restart)', () => {
    const savedState: FlashcardState = {
      sessionId: 'expired-session-999',
      currentCardId: 'card-1',
      answer: 'Częściowa odpowiedź',
      usedIds: [],
      isFlipped: false,
      answerAnalysis: null,
      finished: false,
    };
    sessionStorageService.setItem(FLASHCARD_STATE_STORAGE_KEY, savedState);
    evalServiceMock.verifyLlmSession.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 404, statusText: 'Not Found' })),
    );

    const restoredFixture = TestBed.createComponent(LearningSection);
    restoredFixture.detectChanges();

    expect(restoredFixture.componentInstance.displayCardVisible()).toBe(false);
    expect(restoredFixture.componentInstance.activeView()).toBe('menu');
    expect(sessionStorageService.getItem(FLASHCARD_STATE_STORAGE_KEY)).toBeNull();
  });

  it('should silently recreate session if returning from settings/account within app and previous session expired', () => {
    component.goToDisplayCards();
    fixture.detectChanges();

    const savedState = sessionStorageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY)!;
    expect(savedState.sessionId).toBe('new-session-id');

    evalServiceMock.verifyLlmSession.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 404, statusText: 'Not Found' })),
    );
    evalServiceMock.getLlmSession.mockReturnValue(of('silently-recreated-session'));

    const returnedFixture = TestBed.createComponent(LearningSection);
    returnedFixture.detectChanges();

    expect(returnedFixture.componentInstance.displayCardVisible()).toBe(true);
    expect(
      sessionStorageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY)?.sessionId,
    ).toBe('silently-recreated-session');
  });

  it('should switch between menu, leaderboard, and flashcard-browser using @switch', () => {
    component.goToLeaderboard();
    fixture.detectChanges();
    expect(component.activeView()).toBe('leaderboard');
    expect(fixture.nativeElement.querySelector('leaderboard')).toBeTruthy();

    component.goBackToMenu();
    fixture.detectChanges();
    expect(component.activeView()).toBe('menu');

    component.goToFlashcardBrowser();
    fixture.detectChanges();
    expect(component.activeView()).toBe('flashcard-browser');
    expect(fixture.nativeElement.querySelector('flashcard-browser')).toBeTruthy();
  });

  it('should return to menu and clear saved session on popstate (browser back arrow)', () => {
    component.goToDisplayCards();
    fixture.detectChanges();
    expect(component.displayCardVisible()).toBe(true);

    component.onPopState();
    fixture.detectChanges();

    expect(component.displayCardVisible()).toBe(false);
    expect(sessionStorageService.getItem(FLASHCARD_STATE_STORAGE_KEY)).toBeNull();
  });

  it('should reset session when reset-learning-session event is dispatched', () => {
    component.goToDisplayCards();
    fixture.detectChanges();
    expect(component.displayCardVisible()).toBe(true);

    window.dispatchEvent(new Event(RESET_LEARNING_SESSION_EVENT));
    fixture.detectChanges();

    expect(component.displayCardVisible()).toBe(false);
    expect(sessionStorageService.getItem(FLASHCARD_STATE_STORAGE_KEY)).toBeNull();
  });
});
