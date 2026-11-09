import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LearningSection } from './learning-section';

describe('LearningSection', () => {
  let component: LearningSection;
  let fixture: ComponentFixture<LearningSection>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LearningSection],
    }).compileComponents();

    fixture = TestBed.createComponent(LearningSection);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
