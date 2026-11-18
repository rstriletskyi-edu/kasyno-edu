import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export interface Flashcard {
  id: string;
  question: string;
  expected_answer: string;
  category: string;
}

export interface FlashcardsResponse {
  items: Flashcard[];
}

@Injectable({ providedIn: 'root' })
export class FlashcardsService {
  private readonly http = inject(HttpClient);

  getFlashcards(): Observable<FlashcardsResponse> {
    return this.http.get<FlashcardsResponse>(`${environment.apiUrl}/flashcards`);
  }
}
