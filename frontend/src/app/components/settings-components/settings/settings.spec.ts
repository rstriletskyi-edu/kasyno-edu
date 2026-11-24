import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { Settings } from './settings';
import { FLASHCARD_STATE_STORAGE_KEY } from '../../learning-section/display-cards/display-cards';

describe('Settings', () => {
  let component: Settings;
  let fixture: ComponentFixture<Settings>;

  beforeEach(async () => {
    sessionStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Settings],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(Settings);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should navigate to /home and preserve saved flashcard state when clicking Powrót do fiszek', () => {
    const navigateSpy = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    sessionStorage.setItem(
      FLASHCARD_STATE_STORAGE_KEY,
      JSON.stringify({ sessionId: 'session-123', currentCardId: 'card-1' }),
    );

    const btn = fixture.nativeElement.querySelector(
      '.return-flashcards-button',
    ) as HTMLButtonElement;
    btn.click();

    expect(navigateSpy).toHaveBeenCalledWith(['/home']);
    expect(sessionStorage.getItem(FLASHCARD_STATE_STORAGE_KEY)).not.toBeNull();
  });
});
