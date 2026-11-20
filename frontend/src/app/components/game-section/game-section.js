import { __decorate } from "tslib";
import { Component, signal } from '@angular/core';
let GameSection = class GameSection {
    dropdownOpen = signal(false);
    games = [
        { name: 'Blackjack', icon: '🃏' },
        { name: 'Ruletka', icon: '🎡' },
        { name: 'Jednoręki bandyta', icon: '🎰' },
    ];
    toggleDropdown() {
        this.dropdownOpen.update((v) => !v);
    }
};
GameSection = __decorate([
    Component({
        imports: [],
        selector: 'game-section',
        styleUrl: './game-section.css',
        templateUrl: './game-section.html',
    })
], GameSection);
export { GameSection };
