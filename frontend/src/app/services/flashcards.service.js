import { __decorate } from "tslib";
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
let FlashcardsService = class FlashcardsService {
    http = inject(HttpClient);
    getRandomFlashcard(excludedIds) {
        return this.http.post(`${environment.apiUrl}/flashcards/random`, {
            excluded_ids: excludedIds,
        });
    }
};
FlashcardsService = __decorate([
    Injectable({ providedIn: 'root' })
], FlashcardsService);
export { FlashcardsService };
