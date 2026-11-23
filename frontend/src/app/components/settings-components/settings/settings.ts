import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AiProviderSettings } from '../ai-provider-settings/ai-provider-settings';
import { LocalStorageService } from '../../../services/local-storage.service';
import { LearningSection } from '../../learning-section/learning-section';

@Component({
  imports: [AiProviderSettings],
  selector: 'settings',
  styleUrl: './settings.css',
  templateUrl: './settings.html',
})
export class Settings {
  protected stoageService = inject(LocalStorageService);
  private readonly router = inject(Router);

  returnToFlashcards(): void {
    LearningSection.enableSilentSessionRecovery();
    void this.router.navigate(['/home']);
  }
}
