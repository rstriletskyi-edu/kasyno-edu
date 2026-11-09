import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GameSection } from './game-section';

describe('GameSection', () => {
  let component: GameSection;
  let fixture: ComponentFixture<GameSection>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GameSection],
    }).compileComponents();

    fixture = TestBed.createComponent(GameSection);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
