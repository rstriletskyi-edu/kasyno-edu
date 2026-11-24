import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { AiProviderSettings, LLM_PROVIDER_STORAGE_KEY } from './ai-provider-settings';
import { FLASHCARD_STATE_STORAGE_KEY } from '../../learning-section/display-cards/display-cards';
import { FirebaseAuthService } from '../../../services/firebase-auth.service';

describe('AiProviderSettings', () => {
  let component: AiProviderSettings;
  let fixture: ComponentFixture<AiProviderSettings>;
  let authServiceMock: {
    isConfigured: boolean;
    getCurrentUser: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    localStorage.clear();
    sessionStorage.clear();

    authServiceMock = {
      isConfigured: true,
      getCurrentUser: vi.fn().mockResolvedValue({ uid: 'user-1', emailVerified: true }),
    };

    await TestBed.configureTestingModule({
      imports: [AiProviderSettings],
      providers: [{ provide: FirebaseAuthService, useValue: authServiceMock }],
    }).compileComponents();

    fixture = TestBed.createComponent(AiProviderSettings);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('should create in collapsed state', () => {
    expect(component).toBeTruthy();
    expect(fixture.nativeElement.querySelector('.edit-button')).toBeTruthy();
  });

  it('should show session-error-banner and prevent editing when user is not logged in', async () => {
    authServiceMock.getCurrentUser.mockResolvedValue(null);

    const editBtn = fixture.nativeElement.querySelector('.edit-button') as HTMLButtonElement;
    editBtn.click();
    await fixture.whenStable();
    fixture.detectChanges();

    const banner = fixture.nativeElement.querySelector('.session-error-banner') as HTMLElement;
    expect(banner).toBeTruthy();
    expect(banner.textContent).toContain('Błąd autoryzacji użytkownika');
    expect(fixture.nativeElement.querySelector('form.provider-form')).toBeNull();
  });

  it('should preserve active learning session when clicking Save without changing settings, and clear session only when settings actually change', async () => {
    localStorage.setItem(
      LLM_PROVIDER_STORAGE_KEY,
      JSON.stringify({
        provider: 'ollama',
        apiKey: 'ollama',
        model: 'gemma3:4b',
        baseUrl: 'http://localhost:11434',
      }),
    );
    sessionStorage.setItem(
      FLASHCARD_STATE_STORAGE_KEY,
      JSON.stringify({ sessionId: 'active-session-1' }),
    );

    const savedFixture = TestBed.createComponent(AiProviderSettings);
    const savedComp = savedFixture.componentInstance as unknown as {
      startEditing: () => Promise<void>;
      saveSettings: () => void;
      llmProviderForm: AiProviderSettings['llmProviderForm'];
    };

    await savedComp.startEditing();
    savedComp.saveSettings();
    expect(sessionStorage.getItem(FLASHCARD_STATE_STORAGE_KEY)).not.toBeNull();

    await savedComp.startEditing();
    savedComp.llmProviderForm.controls.model.setValue('llama3:8b');
    savedComp.saveSettings();
    expect(sessionStorage.getItem(FLASHCARD_STATE_STORAGE_KEY)).toBeNull();
  });
});
