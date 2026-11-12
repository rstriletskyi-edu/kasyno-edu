import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AccountActivation } from './account-activation';

describe('AccountActivation', () => {
  let component: AccountActivation;
  let fixture: ComponentFixture<AccountActivation>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AccountActivation],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(AccountActivation);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
