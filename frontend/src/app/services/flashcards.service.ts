import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export interface Flashcard {
  id: string;
  question: string;
  expected_answer: string;
  category: string;
}

@Injectable({ providedIn: 'root' })
export class FlashcardsService {
  private readonly http = inject(HttpClient);

  getRandomFlashcard(excludedIds: string[]): Observable<Flashcard> {
    let params = new HttpParams();
    for (const id of excludedIds) {
      params = params.append('excluded_ids', id);
    }
    return this.http.get<Flashcard>(`${environment.apiUrl}/flashcards/random`, { params });
  }
}
