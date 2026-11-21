import { Component, inject, signal } from '@angular/core';
import { DisplayCards } from './display-cards/display-cards';
import { LlmEvalService } from '../../services/llm-eval.service';
import { HttpErrorResponse } from '@angular/common/http';

import { environment } from '../../../environments/environment';

@Component({
  imports: [DisplayCards],
  selector: 'learning-section',
  styleUrl: './learning-section.css',
  templateUrl: './learning-section.html',
})
export class LearningSection {
  protected evalService = inject(LlmEvalService);

  protected sessionId = signal<string | null>(null);
  protected error = signal<boolean>(false);
  protected errorMessage = signal<string>('');

  displayCardVisible = signal(false);

  goToDisplayCards() {
    this.error.set(false);
    this.errorMessage.set('');

    this.evalService
      .getLlmSession(
        /*tu zamiast w jakiś sposób powinniśmy domyślnie załączyć osobiste ustawienie z providerem modelu aktualnie zalogowanego użytkownika*/
        {
          api_key: '',
          provider: '',
          model: '',
          base_url: '',
        },
      )
      .subscribe({
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

  goToDisplayCards() {
    this.displayCardVisible.set(true);
  }

  goBackToMenu() {
    this.displayCardVisible.set(false);
  }
}
