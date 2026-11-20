import { Component } from '@angular/core';
import { AiProviderSettings } from '../ai-provider-settings/ai-provider-settings';

@Component({
  imports: [AiProviderSettings],
  selector: 'app-settings',
  styleUrl: './settings.css',
  templateUrl: './settings.html',
})
export class Settings {}
