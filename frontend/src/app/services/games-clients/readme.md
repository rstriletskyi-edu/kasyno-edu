# Klienci gier (`games-clients`)

W tym katalogu obsługujecie endpointy gier z backendu oraz tworzycie modele/interfejsy TypeScript na wzór modeli pythonowych (Pydantic), jeśli dany endpoint tego wymaga.

## Wzór metody dla endpointu

Dla każdego endpointu tworzymy jedną metodę w odpowiednim serwisie klienta (`BlackjackClient`, `RouletteClient`, `SlotsClient`) według poniższego schematu:

```typescript
nazwaFunkcji([CIAŁO_ZAPYTANIA]): Observable<[TYP_ZWRACANY]> {
  return this.http.[METODA: 'get' | 'post']<[TYP_ZWRACANY]>(
    `${environment.apiUrl}/games/[NAZWA_GRY]/[AKCJA]`,
    [CIAŁO_ZAPYTANIA],
  );
}
```

## Przykład implementacji

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface RouletteBet {
  type: string;
  amount: number;
}

export interface RouletteSpinRequest {
  bets: RouletteBet[];
}

export interface RouletteSpinResponse {
  winning_number: number;
  winning_color: 'red' | 'black' | 'green';
  total_payout: number;
  credits_balance: number;
}

@Injectable({ providedIn: 'root' })
export class RouletteClient {
  private readonly http = inject(HttpClient);

  spin(payload: RouletteSpinRequest): Observable<RouletteSpinResponse> {
    return this.http.post<RouletteSpinResponse>(`${environment.apiUrl}/games/ruleta/spin`, payload);
  }
}
```

````

## Przykład implementacji

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface RouletteBet {
  type: string;
  amount: number;
}

export interface RouletteSpinRequest {
  bets: RouletteBet[];
}

export interface RouletteSpinResponse {
  winning_number: number;
  winning_color: 'red' | 'black' | 'green';
  total_payout: number;
  credits_balance: number;
}

@Injectable({ providedIn: 'root' })
export class RouletteClient {
  private readonly http = inject(HttpClient);

  spin(payload: RouletteSpinRequest): Observable<RouletteSpinResponse> {
    return this.http.post<RouletteSpinResponse>(
      `${environment.apiUrl}/games/ruleta/spin`,
      payload,
    );
  }
}
````
