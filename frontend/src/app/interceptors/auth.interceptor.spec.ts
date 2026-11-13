import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { environment } from '../../environments/environment';
import { FirebaseAuthService } from '../services/firebase-auth.service';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;
  const getIdToken = vi.fn();

  beforeEach(() => {
    getIdToken.mockReset().mockResolvedValue('test-id-token');
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: FirebaseAuthService, useValue: { getIdToken } },
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('attaches an SDK token to the configured API', async () => {
    const url = `${environment.apiUrl}/auth/me`;
    http.get(url).subscribe();
    await Promise.resolve();
    const request = controller.expectOne(url);
    expect(request.request.headers.get('Authorization')).toBe('Bearer test-id-token');
    request.flush({});
  });

  it('sends no bearer header when signed out', async () => {
    getIdToken.mockResolvedValue(null);
    const url = `${environment.apiUrl}/auth/me`;
    http.get(url).subscribe();
    await Promise.resolve();
    const request = controller.expectOne(url);
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({});
  });

  it('excludes other origins and similar API paths', () => {
    for (const url of [
      'https://unrelated.example/auth/me',
      `${environment.apiUrl}-other/auth/me`,
    ]) {
      http.get(url).subscribe();
      const request = controller.expectOne(url);
      expect(request.request.headers.has('Authorization')).toBe(false);
      request.flush({});
    }
    expect(getIdToken).not.toHaveBeenCalled();
  });
});
