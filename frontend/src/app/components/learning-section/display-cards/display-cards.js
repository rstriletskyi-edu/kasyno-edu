import { __decorate } from "tslib";
import { Component, inject, signal, output } from '@angular/core';
import { FlashcardsService } from '../../../services/flashcards.service';
let DisplayCards = class DisplayCards {
    flashcardsService = inject(FlashcardsService);
    returnToMenuEvent = output();
    currentCard = signal(null);
    usedIds = signal([]);
    loading = signal(true);
    loadError = signal(false);
    finished = signal(false);
    answer = signal('');
    constructor() {
        this.loadFlashcards();
    }
    loadFlashcards() {
        this.loading.set(true);
        this.loadError.set(false);
        this.flashcardsService.getRandomFlashcard(this.usedIds()).subscribe({
            next: (flashcard) => {
                this.currentCard.set(flashcard);
                this.answer.set('');
                this.loading.set(false);
            },
            error: (error) => {
                if (error.status === 404) {
                    this.finished.set(true);
                    this.loading.set(false);
                    return;
                }
                this.loadError.set(true);
                this.loading.set(false);
            },
        });
    }
    updateAnswer(value) {
        this.answer.set(value);
    }
    returnToMenu() {
        this.returnToMenuEvent.emit();
    }
    submitAnswer() {
        if (!this.answer().trim())
            return;
        const flashcard = this.currentCard();
        if (!flashcard)
            return;
        this.usedIds.update((ids) => [...ids, flashcard.id]);
        this.loadFlashcards();
    }
};
DisplayCards = __decorate([
    Component({
        imports: [],
        selector: 'display-cards',
        styleUrl: './display-cards.css',
        templateUrl: './display-cards.html',
    })
], DisplayCards);
export { DisplayCards };
