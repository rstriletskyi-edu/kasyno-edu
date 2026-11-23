import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FlashcardBrowser } from './flashcard-browser';

describe('FlashcardBrowser', () => {
  let component: FlashcardBrowser;
  let fixture: ComponentFixture<FlashcardBrowser>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FlashcardBrowser],
    }).compileComponents();

    fixture = TestBed.createComponent(FlashcardBrowser);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
