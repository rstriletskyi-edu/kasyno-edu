import { __decorate } from "tslib";
import { Component } from '@angular/core';
import { GameSection } from '../game-section/game-section';
import { LearningSection } from '../learning-section/learning-section';
let Homepage = class Homepage {
};
Homepage = __decorate([
    Component({
        imports: [GameSection, LearningSection],
        selector: 'homepage',
        styleUrl: './homepage.css',
        templateUrl: './homepage.html',
    })
], Homepage);
export { Homepage };
