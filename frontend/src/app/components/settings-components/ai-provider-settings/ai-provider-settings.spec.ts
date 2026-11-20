import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AiProviderSettings } from './ai-provider-settings';

describe('AiProviderSettings', () => {
  let component: AiProviderSettings;
  let fixture: ComponentFixture<AiProviderSettings>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AiProviderSettings],
    }).compileComponents();

    fixture = TestBed.createComponent(AiProviderSettings);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
