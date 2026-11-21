import { Component, OnInit, inject, signal } from '@angular/core';
import { DisplayCards } from './display-cards/display-cards';
import { LlmEvalService, LlmSessionRequest } from '../../services/llm-eval.service';
import { HttpErrorResponse } from '@angular/common/http';
import { LocalStorageService } from '../../services/local-storage.service';
import {
  LLM_PROVIDER_STORAGE_KEY,
  LlmProviderSettings,
} from '../settings-components/ai-provider-settings/ai-provider-settings';

@Component({
  imports: [DisplayCards],
  selector: 'learning-section',
  styleUrl: './learning-section.css',
  templateUrl: './learning-section.html',
})
export class LearningSection implements OnInit {
  protected evalService = inject(LlmEvalService);
  protected storageService = inject(LocalStorageService);

  protected sessionId = signal<string | null>(null);
  protected error = signal<boolean>(false);
  protected errorMessage = signal<string>('');
  protected llmSessionRequest = signal<LlmSessionRequest>({
    api_key: '',
    provider: '',
    model: '',
    base_url: '',
  });

  displayCardVisible = signal(false);

  ngOnInit() {
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
  }

  goToDisplayCards() {
    this.error.set(false);
    this.errorMessage.set('');

    console.log(this.llmSessionRequest());

    this.evalService.getLlmSession(this.llmSessionRequest()).subscribe({
      next: (sessionId) => {
        if (sessionId === null || sessionId.trim() === '') {
          this.error.set(true);
          this.errorMessage.set('Nie udało się rozpocząć sesji: otrzymano puste session ID.');
          return;
        }
        this.sessionId.set(sessionId);
        this.displayCardVisible.set(true);
      },
      error: (err: HttpErrorResponse) => {
        this.error.set(true);
        this.errorMessage.set(
          `${err.status}: ${err.error?.detail}` || 'Wystąpił błąd podczas tworzenia sesji.',
        );
      },
    });
  }

  goBackToMenu() {
    this.displayCardVisible.set(false);
    this.sessionId.set(null);
  }
}
