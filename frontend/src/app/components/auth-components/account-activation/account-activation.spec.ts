import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AccountActivation } from './account-activation';

describe('AccountActivation', () => {
  let component: AccountActivation;
  let fixture: ComponentFixture<AccountActivation>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AccountActivation],
    }).compileComponents();

    fixture = TestBed.createComponent(AccountActivation);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
