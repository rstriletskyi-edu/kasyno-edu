import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { FirebaseAuthService } from '../../services/firebase-auth.service';
import { GameSection } from './game-section';

describe('GameSection', () => {
  let component: GameSection;
  let fixture: ComponentFixture<GameSection>;
  let authServiceMock: {
    isConfigured: boolean;
    getCurrentUser: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    authServiceMock = {
      isConfigured: true,
      getCurrentUser: vi.fn().mockResolvedValue(null),
    };

    await TestBed.configureTestingModule({
      imports: [GameSection],
      providers: [{ provide: FirebaseAuthService, useValue: authServiceMock }],
    }).compileComponents();

    fixture = TestBed.createComponent(GameSection);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should not show Play button when no game is selected', () => {
    const playButton = fixture.nativeElement.querySelector('.play-button');
    expect(playButton).toBeNull();
  });

  it('should show Play button after selecting a game and display unauthenticated error when clicked by unlogged user', async () => {
    component.selectGame({ id: 'blackjack', name: 'Blackjack', icon: '🃏' });
    fixture.detectChanges();

    const playButton = fixture.nativeElement.querySelector('.play-button') as HTMLButtonElement;
    expect(playButton).toBeTruthy();
    expect(playButton.textContent?.trim()).toBe('Graj');

    playButton.click();
    await fixture.whenStable();
    fixture.detectChanges();

    const errorBanner = fixture.nativeElement.querySelector('.error-banner') as HTMLElement;
    expect(errorBanner).toBeTruthy();
    expect(errorBanner.textContent).toContain('Użytkownik niezalogowany');
  });
});
