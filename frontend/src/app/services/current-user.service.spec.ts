import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../environments/environment';
import { CurrentUserService } from './current-user.service';

describe('CurrentUserService.register', () => {
  let service: CurrentUserService;
  let http: HttpTestingController;
  const url = `${environment.apiUrl}/auth/register`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CurrentUserService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('returns the created profile on 201', async () => {
    const result = firstValueFrom(service.register());
    http.expectOne(url).flush({ uid: 'u1' }, { status: 201, statusText: 'Created' });
    expect(await result).toEqual({ uid: 'u1' });
  });

  it('treats 409 (profile already exists) as success', async () => {
    const result = firstValueFrom(service.register());
    http.expectOne(url).flush({ detail: 'exists' }, { status: 409, statusText: 'Conflict' });
    expect(await result).toBeNull();
  });

  it('rethrows other errors', async () => {
    const result = firstValueFrom(service.register());
    http.expectOne(url).flush({ detail: 'down' }, { status: 503, statusText: 'Unavailable' });
    await expect(result).rejects.toMatchObject({ status: 503 });
  });
});
