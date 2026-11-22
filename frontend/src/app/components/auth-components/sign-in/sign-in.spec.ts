import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SignIn } from './sign-in';

describe('SignIn', () => {
  let component: SignIn;
  let fixture: ComponentFixture<SignIn>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SignIn],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(SignIn);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  async function typeEmail(value: string): Promise<void> {
    const input: HTMLInputElement = fixture.nativeElement.querySelector('input[name="email"]');
    input.value = value;
    input.dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  const emailError = () =>
    (fixture.nativeElement as HTMLElement).querySelector('label span.error')?.textContent ?? '';

  it('shows an e-mail error while typing an address without @', async () => {
    await typeEmail('userexample.com');
    expect(emailError()).toContain('Podaj prawidłowy adres e-mail');
  });

  it('shows an e-mail error for a domain without a TLD', async () => {
    await typeEmail('user@localhost');
    expect(emailError()).toContain('Podaj prawidłowy adres e-mail');
  });

  it('hides the error and enables nothing extra for a valid address', async () => {
    await typeEmail('user@example.com');
    expect(emailError()).toBe('');
  });
});
