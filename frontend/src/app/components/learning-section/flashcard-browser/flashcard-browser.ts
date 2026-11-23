import { Component, output } from '@angular/core';

@Component({
  imports: [],
  selector: 'flashcard-browser',
  styleUrl: './flashcard-browser.css',
  templateUrl: './flashcard-browser.html',
})
export class FlashcardBrowser {
  readonly returnToMenuEvent = output<void>();

  returnToMenu(): void {
    this.returnToMenuEvent.emit();
  }
}
