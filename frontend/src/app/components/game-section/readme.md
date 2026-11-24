# Sekcja gier (`game-section`)

Tutaj znajduje się wszystko związane z grami kasynowymi na frontendzie.

## Struktura komponentów

- **`game-window`** to tylko opakowanie wyświetlające aktywną grę — **nie zmieniamy go**.
- Każda gra ma swój dedykowany folder `[NAZWA_GRY]-components` w katalogu `games/`:
  - `blackjack-components`
  - `roulette-components`
  - `slots-components`
- Jeśli rozdzielacie poszczególne części gry (np. osobno interfejs obstawiania/betowania, a osobno stół lub animację rozgrywki), utwórzcie dla nich osobne podkomponenty wewnątrz swojego folderu `[NAZWA_GRY]-components`.

## Zasady pracy w komponentach

- Pracujemy na **Angular Signals** (`signal`, `input`, `output`, `computed`).
- W `ngOnInit()` ustawiacie funkcje i zmienne, które mają zadziałać przy wczytaniu komponentu.
- W szablonach HTML korzystajcie z nowej składni przepływu sterowania (`@if`, `@else`, `@for`, `@switch`), a **nie** ze starych dyrektyw strukturalnych (`*ngIf`, `*ngFor`).
- W każdym komponencie gry muszą znajdować się sygnały stanu:
  - `loading = signal<boolean>(false)` — flaga ładowania,
  - `error = signal<boolean>(false)` — flaga wystąpienia błędu,
  - `errorMessage = signal<string>('')` — treść błędu wyświetlana użytkownikowi.

## Wywoływanie endpointów i obsługa błędów

W każdym nadrzędnym komponencie gry (tym z nazwą gry jako główną klasą: `Blackjack`, `Roulette`, `Slots`) obsługujecie metody z serwisów w `services/games-clients`.

1. Wywołujecie metodę serwisu z odpowiednimi argumentami.
2. Używacie `.subscribe({ next, error })`:
   - **`next`** — przypadek, gdy zapytanie się powiedzie. Umieszczacie tam dalszą logikę gry (aktualizację stanu, wygranej, żetonów itp.) oraz wyłączacie flagę `loading`.
   - **`error`** — przypadek błędu (`HttpErrorResponse`). Kody błędów HTTP zwracane przez backendowe endpointy należy przechwycić instrukcją `switch` i przypisać im czytelne komunikaty po polsku.

### Przykład wywołania `.subscribe()` z obsługą błędów HTTP

```typescript
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import {
  RouletteClient,
  RouletteSpinRequest,
  RouletteSpinResponse,
} from '../../../../../services/games-clients/roulette-client';

@Component({
  imports: [],
  selector: 'roulette',
  styleUrl: './roulette.css',
  templateUrl: './roulette.html',
})
export class Roulette implements OnInit {
  private readonly client = inject(RouletteClient);

  protected readonly loading = signal<boolean>(false);
  protected readonly error = signal<boolean>(false);
  protected readonly errorMessage = signal<string>('');
  protected readonly lastResult = signal<RouletteSpinResponse | null>(null);

  ngOnInit(): void {}

  spinWheel(request: RouletteSpinRequest): void {
    if (this.loading()) return;

    this.loading.set(true);
    this.error.set(false);
    this.errorMessage.set('');

    this.client.spin(request).subscribe({
      next: (response: RouletteSpinResponse) => {
        this.lastResult.set(response);
        this.loading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(true);

        const statusCode = err.status ?? err.error?.status;
        let message = 'Wystąpił nieoczekiwany błąd podczas rozgrywki.';

        switch (statusCode) {
          case 400:
            message = 'Niewystarczająca liczba żetonów na koncie.';
            break;
          case 401:
            message = 'Użytkownik niezalogowany. Zaloguj się, aby kontynuować.';
            break;
          case 403:
            message = 'Wymagane potwierdzenie adresu e-mail.';
            break;
          case 422:
            message = 'Nieprawidłowa stawka lub przekroczono limity stołu.';
            break;
          case 503:
            message = 'Usługa gry jest chwilowo niedostępna. Spróbuj ponownie później.';
            break;
          default:
            break;
        }

        this.errorMessage.set(message);
      },
    });
  }
}
```

## Wyświetlanie i stylowanie błędów

Dla zachowania spójności wizualnej błędy powinny być wyświetlane i stylowane tak samo jak w `learning-section` (przy tworzeniu sesji) oraz `display-cards` (przy ewaluacji):

```html
@if (error()) {
<div class="error-banner" role="alert">
  <p>{{ errorMessage() }}</p>
</div>
}
```

```css
.error-banner {
  padding: 12px 16px;
  background: rgba(220, 38, 38, 0.15);
  border: 1px solid rgba(220, 38, 38, 0.4);
  border-radius: 8px;
  color: #fca5a5;
  font-size: 0.95rem;
  text-align: center;
  width: 80%;
  align-self: center;
  box-sizing: border-box;
}

.error-banner p {
  margin: 0;
}
```
