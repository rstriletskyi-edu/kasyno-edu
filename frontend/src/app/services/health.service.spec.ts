import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../environments/environment';
import { HealthResponse, HealthService } from './health.service';

describe('HealthService', () => {
  let service: HealthService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(HealthService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('requests the backend health endpoint', () => {
    const body: HealthResponse = {
      status: 'ok',
      app_name: 'Kasyno Edu API',
      environment: 'development',
      firebase_initialized: true,
    };
    let result: HealthResponse | undefined;

    service.getHealth().subscribe((response) => (result = response));

    const request = httpTesting.expectOne(`${environment.apiUrl}/health`);
    expect(request.request.method).toBe('GET');
    request.flush(body);

    expect(result).toEqual(body);
  });
});
