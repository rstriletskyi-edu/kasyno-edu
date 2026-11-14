import { Component, output } from '@angular/core';

@Component({
  imports: [],
  selector: 'display-cards',
  styleUrl: './display-cards.css',
  templateUrl: './display-cards.html',
})
export class DisplayCards {
  returnToMenuEvent = output<void>();

  returnToMenu() {
    this.returnToMenuEvent.emit();
  } 

  submitAnswer() {
    // Zaimplementuj logikę przesyłania odpowiedzi użytkownika
  }
}
