import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { FirebaseAuthService } from '../../../services/firebase-auth.service';
import { LocalStorageService } from '../../../services/local-storage.service';
import { SessionStorageService } from '../../../services/session-storage.service';
import { FLASHCARD_STATE_STORAGE_KEY } from '../../learning-section/display-cards/display-cards';
import {
  LearningSection,
  RESET_LEARNING_SESSION_EVENT,
} from '../../learning-section/learning-section';

export type LlmProviderType = '' | 'openai' | 'ollama' | 'google_genai' | 'anthropic';

export interface LlmProviderSettings {
  apiKey: string;
  provider: LlmProviderType;
  model: string;
  baseUrl: string;
}

export const LLM_PROVIDER_STORAGE_KEY = 'llm_provider_settings';

export interface ProviderOption {
  value: LlmProviderType;
  label: string;
  modelPlaceholder: string;
}

const URL_PATTERN = /^https?:\/\/.+/i;

@Component({
  imports: [ReactiveFormsModule],
  selector: 'ai-provider-settings',
  styleUrl: './ai-provider-settings.css',
  templateUrl: './ai-provider-settings.html',
})
export class AiProviderSettings {
  protected readonly storageService = inject(LocalStorageService);
  protected readonly sessionStorageService = inject(SessionStorageService);
  private readonly auth = inject(FirebaseAuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly saved = signal(false);
  protected readonly isEditing = signal(false);
  protected readonly authError = signal(false);
  protected readonly authErrorMessage = signal('');

  protected readonly providerOptions: ProviderOption[] = [
    {
      value: '',
      label: 'Wybierz dostawcę modelu AI do ewaluacji',
      modelPlaceholder: '',
    },
    {
      value: 'openai',
      label: 'OpenAI lub kompatybilny host',
      modelPlaceholder: 'np. gpt-4o-mini',
    },
    {
      value: 'ollama',
      label: 'Ollama',
      modelPlaceholder: 'np. gemma3:4b',
    },
    {
      value: 'google_genai',
      label: 'Google Gemini',
      modelPlaceholder: 'np. gemini-2.5-flash',
    },
    {
      value: 'anthropic',
      label: 'Anthropic',
      modelPlaceholder: 'np. claude-3-5-haiku-latest',
    },
  ];

  protected readonly llmProviderForm = new FormGroup({
    provider: new FormControl<LlmProviderType>('', {
      nonNullable: true,
      validators: [Validators.maxLength(32)],
    }),
    apiKey: new FormControl<string>('', {
      nonNullable: true,
      validators: [Validators.maxLength(512)],
    }),
    model: new FormControl<string>('', {
      nonNullable: true,
      validators: [Validators.maxLength(128)],
    }),
    baseUrl: new FormControl<string>('', {
      nonNullable: true,
      validators: [Validators.maxLength(512), Validators.pattern(URL_PATTERN)],
    }),
  });

  constructor() {
    this.loadSavedSettings();

    this.llmProviderForm.controls.provider.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((provider) => {
        this.applyProviderRules(provider, true);
      });

    this.llmProviderForm.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      if (this.saved()) {
        this.saved.set(false);
      }
    });
  }

  protected get selectedProvider(): LlmProviderType {
    return this.llmProviderForm.controls.provider.value;
  }

  protected get showProviderFields(): boolean {
    return this.selectedProvider !== '';
  }

  protected get showApiKey(): boolean {
    return this.selectedProvider !== '' && this.selectedProvider !== 'ollama';
  }

  protected get showBaseUrl(): boolean {
    return this.selectedProvider === 'openai' || this.selectedProvider === 'ollama';
  }

  protected get isBaseUrlRequired(): boolean {
    return this.selectedProvider === 'ollama';
  }

  protected get modelPlaceholder(): string {
    return (
      this.providerOptions.find((option) => option.value === this.selectedProvider)
        ?.modelPlaceholder ?? ''
    );
  }

  protected saveSettings(): void {
    if (this.llmProviderForm.invalid) {
      this.llmProviderForm.markAllAsTouched();
      return;
    }

    const raw = this.llmProviderForm.getRawValue();
    const provider = raw.provider.trim().toLowerCase() as LlmProviderType;

    const payload: LlmProviderSettings =
      provider === ''
        ? {
            provider: '',
            apiKey: '',
            model: '',
            baseUrl: '',
          }
        : {
            provider,
            apiKey: provider === 'ollama' ? 'ollama' : raw.apiKey.trim(),
            model: raw.model.trim(),
            baseUrl: this.showBaseUrl ? raw.baseUrl.trim() : '',
          };

    const previous =
      this.storageService.getItem<Partial<LlmProviderSettings>>(LLM_PROVIDER_STORAGE_KEY);
    const hasChanged =
      (previous?.provider ?? '') !== payload.provider ||
      (previous?.apiKey ?? '') !== payload.apiKey ||
      (previous?.model ?? '') !== payload.model ||
      (previous?.baseUrl ?? '') !== payload.baseUrl;

    this.storageService.setItem<LlmProviderSettings>(LLM_PROVIDER_STORAGE_KEY, payload);
    if (hasChanged) {
      LearningSection.clearInAppSessionFlag();
      this.sessionStorageService.removeItem(FLASHCARD_STATE_STORAGE_KEY);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event(RESET_LEARNING_SESSION_EVENT));
      }
    }
    this.saved.set(true);
    this.isEditing.set(false);
  }

  protected async startEditing(): Promise<void> {
    this.saved.set(false);
    this.authError.set(false);
    this.authErrorMessage.set('');

    if (!this.auth.isConfigured) {
      this.authError.set(true);
      this.authErrorMessage.set('Błąd autoryzacji użytkownika');
      return;
    }

    try {
      const user = await this.auth.getCurrentUser();
      if (!user) {
        this.authError.set(true);
        this.authErrorMessage.set('Błąd autoryzacji użytkownika');
        return;
      }
      if (!user.emailVerified) {
        this.authError.set(true);
        this.authErrorMessage.set('Wymagane potwierdzenie adresu email');
        return;
      }
      this.isEditing.set(true);
    } catch {
      this.authError.set(true);
      this.authErrorMessage.set('Błąd autoryzacji użytkownika');
    }
  }

  private loadSavedSettings(): void {
    const stored =
      this.storageService.getItem<Partial<LlmProviderSettings>>(LLM_PROVIDER_STORAGE_KEY);

    if (stored) {
      const provider = (stored.provider ?? '') as LlmProviderType;
      this.llmProviderForm.patchValue(
        {
          provider,
          apiKey: provider === 'ollama' ? 'ollama' : (stored.apiKey ?? ''),
          model: stored.model ?? '',
          baseUrl: stored.baseUrl ?? '',
        },
        { emitEvent: false },
      );
      this.applyProviderRules(provider, false);
    } else {
      this.applyProviderRules(this.selectedProvider, false);
    }
    this.isEditing.set(false);
  }

  private applyProviderRules(provider: LlmProviderType, isUserChange: boolean): void {
    const { apiKey, model, baseUrl } = this.llmProviderForm.controls;

    if (provider === '') {
      apiKey.setValidators([Validators.maxLength(512)]);
      model.setValidators([Validators.maxLength(128)]);
      baseUrl.setValidators([Validators.maxLength(512)]);
    } else if (provider === 'ollama') {
      apiKey.setValidators([Validators.maxLength(512)]);
      apiKey.setValue('ollama', { emitEvent: false });
      model.setValidators([Validators.required, Validators.maxLength(128)]);
      baseUrl.setValidators([
        Validators.required,
        Validators.maxLength(512),
        Validators.pattern(URL_PATTERN),
      ]);
    } else {
      apiKey.setValidators([Validators.required, Validators.maxLength(512)]);
      model.setValidators([Validators.required, Validators.maxLength(128)]);

      if (isUserChange && apiKey.value === 'ollama') {
        apiKey.setValue('', { emitEvent: false });
      }

      if (provider === 'openai') {
        baseUrl.setValidators([Validators.maxLength(512), Validators.pattern(URL_PATTERN)]);
      } else {
        baseUrl.setValidators([Validators.maxLength(512)]);
        if (isUserChange) {
          baseUrl.setValue('', { emitEvent: false });
        }
      }
    }

    apiKey.updateValueAndValidity({ emitEvent: false });
    model.updateValueAndValidity({ emitEvent: false });
    baseUrl.updateValueAndValidity({ emitEvent: false });
  }
}
