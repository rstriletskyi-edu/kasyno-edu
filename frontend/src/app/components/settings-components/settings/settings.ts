import { Component, inject } from '@angular/core';
import { AiProviderSettings } from '../ai-provider-settings/ai-provider-settings';
import { LocalStorageService } from '../../../services/local-storage.service';

@Component({
  imports: [AiProviderSettings],
  selector: 'settings',
  styleUrl: './settings.css',
  templateUrl: './settings.html',
})
export class Settings {
  protected stoageService = inject(LocalStorageService);
}
