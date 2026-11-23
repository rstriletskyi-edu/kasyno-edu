import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, of } from 'rxjs';
import { vi } from 'vitest';
import {
  DisplayCards,
  FLASHCARD_STATE_STORAGE_KEY,
  FlashcardState,
  MAX_ANSWER_LENGTH,
} from './display-cards';
import { Flashcard, FlashcardsService } from '../../../services/flashcards.service';
import { EvaluationResult, LlmEvalService } from '../../../services/llm-eval.service';
import { SessionStorageService } from '../../../services/session-storage.service';

const MOCK_CARD_1: Flashcard = {
  id: 'card-1',
  question: 'Co to jest CPU?',
  expected_answer: 'Centralna jednostka obliczeniowa',
  category: 'Architektura',
};

const MOCK_CARD_2: Flashcard = {
  id: 'card-2',
  question: 'Co to jest RAM?',
  expected_answer: 'Pamięć o dostępie swobodnym',
  category: 'Architektura',
};

describe('DisplayCards', () => {
  let component: DisplayCards;
  let fixture: ComponentFixture<DisplayCards>;
  let flashcardsServiceMock: {
    getRandomFlashcard: ReturnType<typeof vi.fn>;
    getConcreteFlashcard: ReturnType<typeof vi.fn>;
  };
  let evalServiceMock: {
    getAnswerEvaluation: ReturnType<typeof vi.fn>;
  };
  let storageService: SessionStorageService;

  beforeEach(async () => {
    sessionStorage.clear();

    flashcardsServiceMock = {
      getRandomFlashcard: vi.fn().mockReturnValue(of(MOCK_CARD_1)),
      getConcreteFlashcard: vi.fn().mockReturnValue(of(MOCK_CARD_1)),
    };

    evalServiceMock = {
      getAnswerEvaluation: vi.fn().mockReturnValue(
        of({
          score: 90,
          verdict: 'correct',
          credits_received: 9,
          explanation: 'Poprawna odpowiedź.',
        } satisfies EvaluationResult),
      ),
    };

    await TestBed.configureTestingModule({
      imports: [DisplayCards],
      providers: [
        { provide: FlashcardsService, useValue: flashcardsServiceMock },
        { provide: LlmEvalService, useValue: evalServiceMock },
      ],
    }).compileComponents();

    storageService = TestBed.inject(SessionStorageService);
    fixture = TestBed.createComponent(DisplayCards);
    fixture.componentRef.setInput('sessionId', 'session-123');
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('should create and save initial FlashcardState to localStorage', () => {
    expect(component).toBeTruthy();
    expect(component.currentCard()).toEqual(MOCK_CARD_1);

    const saved = storageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY);
    expect(saved).toEqual({
      sessionId: 'session-123',
      currentCardId: 'card-1',
      answer: '',
      usedIds: [],
      isFlipped: false,
      answerAnalysis: null,
      finished: false,
    });
  });

  it('should restore FlashcardState from localStorage on init using getConcreteFlashcard', () => {
    const savedState: FlashcardState = {
      sessionId: 'session-restore',
      currentCardId: 'card-2',
      answer: 'Moja zapisana odpowiedź',
      usedIds: ['card-1'],
      isFlipped: false,
      answerAnalysis: null,
      finished: false,
    };
    storageService.setItem(FLASHCARD_STATE_STORAGE_KEY, savedState);
    flashcardsServiceMock.getConcreteFlashcard.mockReturnValue(of(MOCK_CARD_2));

    const restoreFixture = TestBed.createComponent(DisplayCards);
    restoreFixture.componentRef.setInput('sessionId', 'session-restore');
    restoreFixture.detectChanges();

    const restoredComp = restoreFixture.componentInstance;
    expect(flashcardsServiceMock.getConcreteFlashcard).toHaveBeenCalledWith('card-2');
    expect(restoredComp.currentCard()).toEqual(MOCK_CARD_2);
    expect(restoredComp.answer()).toBe('Moja zapisana odpowiedź');
    expect(restoredComp.usedIds()).toEqual(['card-1']);
    expect(restoredComp.isFlipped()).toBe(false);
    expect(restoredComp.evaluating()).toBe(false);
  });

  it('should display character counter n/2000 and enforce 2000 char limit', () => {
    component.updateAnswer('Testowa odpowiedź');
    fixture.detectChanges();

    const counter = fixture.nativeElement.querySelector('.char-counter') as HTMLElement;
    expect(counter).toBeTruthy();
    expect(counter.textContent?.trim()).toBe(`17/${MAX_ANSWER_LENGTH}`);

    const overlong = 'a'.repeat(2500);
    component.updateAnswer(overlong);
    fixture.detectChanges();

    expect(component.answer().length).toBe(MAX_ANSWER_LENGTH);
    expect(counter.textContent?.trim()).toBe(`${MAX_ANSWER_LENGTH}/${MAX_ANSWER_LENGTH}`);
    expect(counter.classList.contains('limit-reached')).toBe(true);
  });

  it('should keep previous question button enabled while typing answer and not save typed answer on going back', () => {
    component.usedIds.set(['card-1']);
    component.currentCard.set(MOCK_CARD_2);
    component.updateAnswer('Tymczasowa odpowiedź na pytanie 2');
    fixture.detectChanges();

    const prevButton = fixture.nativeElement.querySelector('.previous-button') as HTMLButtonElement;
    expect(prevButton.disabled).toBe(false);

    flashcardsServiceMock.getConcreteFlashcard.mockReturnValue(of(MOCK_CARD_1));
    prevButton.click();
    fixture.detectChanges();

    expect(flashcardsServiceMock.getConcreteFlashcard).toHaveBeenCalledWith('card-1');
    expect(component.currentCard()).toEqual(MOCK_CARD_1);
    expect(component.answer()).toBe('');
    expect(component.usedIds()).toEqual([]);

    const saved = storageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY);
    expect(saved?.currentCardId).toBe('card-1');
    expect(saved?.answer).toBe('');
    expect(saved?.usedIds).toEqual([]);
  });

  it('should allow clicking previous question while on the back of a flashcard, flipping first and then loading previous content', () => {
    const cardSubject = new Subject<Flashcard>();
    flashcardsServiceMock.getConcreteFlashcard.mockReturnValue(cardSubject.asObservable());

    component.usedIds.set(['card-1', 'card-2']);
    component.currentCard.set(MOCK_CARD_2);
    component.isFlipped.set(true);
    fixture.detectChanges();

    const prevButton = fixture.nativeElement.querySelector('.previous-button') as HTMLButtonElement;
    expect(prevButton.disabled).toBe(false);

    prevButton.click();
    fixture.detectChanges();

    // Najpierw obrót na przód, a potem wczytanie poprzedniej treści
    expect(component.isFlipped()).toBe(false);
    expect(component.loading()).toBe(true);
    expect(flashcardsServiceMock.getConcreteFlashcard).toHaveBeenCalledWith('card-1');

    cardSubject.next(MOCK_CARD_1);
    fixture.detectChanges();

    expect(component.currentCard()).toEqual(MOCK_CARD_1);
    expect(component.usedIds()).toEqual([]);
    expect(component.loading()).toBe(false);
  });

  it('should abort ongoing evaluation and clear localStorage when returning to menu', () => {
    const evalSubject = new Subject<EvaluationResult>();
    evalServiceMock.getAnswerEvaluation.mockReturnValue(evalSubject.asObservable());

    component.updateAnswer('Moja odpowiedź');
    component.submitAnswer();
    expect(component.evaluating()).toBe(true);

    component.returnToMenu();
    expect(component.evaluating()).toBe(false);
    expect(component.loading()).toBe(false);
    expect(storageService.getItem(FLASHCARD_STATE_STORAGE_KEY)).toBeNull();
  });

  it('should reset evaluating and isFlipped on beforeunload during active evaluation so refresh does not block session', () => {
    const evalSubject = new Subject<EvaluationResult>();
    evalServiceMock.getAnswerEvaluation.mockReturnValue(evalSubject.asObservable());

    component.updateAnswer('Moja odpowiedź w trakcie ewaluacji');
    component.submitAnswer();
    expect(component.evaluating()).toBe(true);
    expect(component.isFlipped()).toBe(true);

    component.onBeforeUnload();

    expect(component.evaluating()).toBe(false);
    expect(component.isFlipped()).toBe(false);
    const saved = storageService.getItem<FlashcardState>(FLASHCARD_STATE_STORAGE_KEY);
    expect(saved?.isFlipped).toBe(false);
    expect(saved?.answer).toBe('Moja odpowiedź w trakcie ewaluacji');
  });
});
