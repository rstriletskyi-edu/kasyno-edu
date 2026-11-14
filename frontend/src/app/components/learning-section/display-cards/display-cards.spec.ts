import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DisplayCards } from './display-cards';

describe('DisplayCards', () => {
  let component: DisplayCards;
  let fixture: ComponentFixture<DisplayCards>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DisplayCards],
    }).compileComponents();

    fixture = TestBed.createComponent(DisplayCards);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
