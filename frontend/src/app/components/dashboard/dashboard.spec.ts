import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Dashboard } from './dashboard';
import { CurrentUserService } from '../../services/current-user.service';
import { FirebaseAuthService } from '../../services/firebase-auth.service';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { environment } from '../../../environments/environment';

describe('Dashboard', () => {
  const originalProduction = environment.production;
  let component: Dashboard;
  let fixture: ComponentFixture<Dashboard>;
  const profile = {
    uid: 'verified-uid',
    email: 'learner@example.test',
    display_name: 'Learner',
    email_verified: true,
    profile: { created_at: null },
  };
  const getMe = vi.fn();
  const getIdToken = vi.fn();

  beforeEach(async () => {
    environment.production = false;
    getMe.mockReturnValue(of(profile));
    getIdToken.mockReset().mockResolvedValue(null);
    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: CurrentUserService, useValue: { getMe } },
        { provide: FirebaseAuthService, useValue: { getIdToken } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Dashboard);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  afterEach(() => {
    environment.production = originalProduction;
  });

  it('shows the user returned by the backend', () => {
    expect(fixture.nativeElement.textContent).toContain('verified-uid');
    expect(fixture.nativeElement.textContent).toContain('Learner');
  });

  it('shows a backend configuration error and permits retry', async () => {
    getMe.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 503 })));
    component.loadProfile();
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('konfigurację serwera');
    getMe.mockReturnValue(of(profile));
    component.loadProfile();
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('verified-uid');
    expect(component.error()).toBe('');
  });

  it('copies the current ID token without displaying it', async () => {
    getIdToken.mockResolvedValueOnce('test-private-token');
    const writeText = vi.fn().mockResolvedValue(undefined);
    const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    try {
      await component.copyToken();
      await fixture.whenStable();
      expect(writeText).toHaveBeenCalledWith('test-private-token');
      expect(fixture.nativeElement.textContent).not.toContain('test-private-token');
      expect(component.tokenMessage()).toContain('Token skopiowany');
    } finally {
      if (original) Object.defineProperty(navigator, 'clipboard', original);
      else Reflect.deleteProperty(navigator, 'clipboard');
    }
  });

  it('hides and disables the token helper in production', async () => {
    environment.production = true;
    const productionFixture = TestBed.createComponent(Dashboard);
    await productionFixture.whenStable();
    await productionFixture.componentInstance.copyToken();
    expect(productionFixture.nativeElement.textContent).not.toContain('Kopiuj ID token');
    expect(getIdToken).not.toHaveBeenCalled();
  });
});
