import { Component, inject, signal } from '@angular/core';
import { HealthService } from '../../services/health.service';
import { DisplayCards } from './display-cards/display-cards';

@Component({
  imports: [DisplayCards],
  selector: 'learning-section',
  styleUrl: './learning-section.css',
  templateUrl: './learning-section.html',
})
export class LearningSection {
  displayCardVisible = signal(false);
  protected healthService = inject(HealthService);
  healthCheckResult = signal('good');

  getHealth() {
    this.healthService.getHealth().subscribe({
      next: (healthResponse) => this.healthCheckResult.set(healthResponse.status),
      error: (err) => console.error(err),
    });
  }

  goToDisplayCards() {
    this.displayCardVisible.set(true);
  }

  goBackToMenu() {
    this.displayCardVisible.set(false);
  }
}
