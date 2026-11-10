import { Component, inject, signal } from '@angular/core';
import { HealthService } from '../../services/health.service';

@Component({
  imports: [],
  selector: 'learning-section',
  styleUrl: './learning-section.css',
  templateUrl: './learning-section.html',
})
export class LearningSection {
  protected healthService = inject(HealthService);

  healthCheckResult = signal('good');

  getHealth() {
    this.healthService.getHealth().subscribe({
        next: (healthResponse) => this.healthCheckResult.set(healthResponse.status),
        error: (err) => console.error(err)
      });
    ;
  }

}
