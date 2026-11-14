import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NavBar } from './nav-bar';
import { Router, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { FirebaseAuthService } from '../../services/firebase-auth.service';

describe('NavBar', () => {
  let component: NavBar;
  let fixture: ComponentFixture<NavBar>;
  let signOut: ReturnType<typeof vi.fn>;
  let navigate: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    signOut = vi.fn().mockResolvedValue(undefined);
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: FirebaseAuthService, useValue: { signOut } }],
      imports: [NavBar],
    }).compileComponents();

    navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    fixture = TestBed.createComponent(NavBar);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  afterEach(() => vi.restoreAllMocks());

  it('signs out from Firebase and redirects to login when clicked', async () => {
    fixture.nativeElement.querySelector('.logout-btn').click();
    await fixture.whenStable();
    expect(signOut).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith(['/auth/login'], { replaceUrl: true });
    expect(component.logoutError()).toBe('');
  });

  it('waits for Firebase sign-out and prevents duplicate submissions', async () => {
    let complete!: () => void;
    signOut.mockReturnValue(new Promise<void>((resolve) => (complete = resolve)));
    const pending = component.logout();
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('.logout-btn').disabled).toBe(true);
    await component.logout();
    expect(signOut).toHaveBeenCalledOnce();
    expect(navigate).not.toHaveBeenCalled();

    complete();
    await pending;
    expect(navigate).toHaveBeenCalledWith(['/auth/login'], { replaceUrl: true });
    expect(component.isLoggingOut()).toBe(false);
  });

  it('shows a safe error and allows retry if sign-out fails', async () => {
    signOut.mockRejectedValueOnce(new Error('sensitive SDK failure details'));
    await component.logout();
    await fixture.whenStable();
    expect(navigate).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(
      'Spróbuj ponownie',
    );
    expect(fixture.nativeElement.textContent).not.toContain('sensitive SDK failure details');
    expect(component.isLoggingOut()).toBe(false);

    await component.logout();
    expect(navigate).toHaveBeenCalledOnce();
    expect(component.logoutError()).toBe('');
  });
});
