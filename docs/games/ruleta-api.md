# European Roulette (`Ruleta`) API

Guide for frontend developers integrating the European Roulette (`Ruletka`) view with the FastAPI backend.
The API base URL is `http://localhost:8000/api` (configured in Angular as `environment.apiUrl`). Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

---

## 1. Overview & Authentication

The game follows a **server-authoritative MVC pattern**:

- The frontend renders the wheel and table, collects the player's bets, and sends a spin request.
- The backend validates all bets and table limits, picks the winning pocket (`0–36`) using Python's CSPRNG (`secrets.randbelow(37)`), evaluates payouts, and updates the user's credits in Firestore inside a single atomic transaction.
- The frontend **must not** generate random numbers, calculate balances locally, or send expected payouts/outcomes in the request.

The spin endpoint requires a verified Firebase user. Send a Firebase ID token in the `Authorization` header (automatically handled in Angular by `authInterceptor` for requests under `environment.apiUrl`):

```http
POST /api/games/ruleta/spin HTTP/1.1
Authorization: Bearer <Firebase-ID-token>
Content-Type: application/json
Accept: application/json
```

Successful responses include `Cache-Control: no-store`. Do not cache spin results.

---

## 2. Spin Endpoint: `POST /api/games/ruleta/spin`

### Request Body

```json
{
  "bets": [
    {
      "bet_type": "straight",
      "numbers": [7],
      "amount": 10
    },
    {
      "bet_type": "red",
      "amount": 25
    }
  ]
}
```

#### Top-level fields

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `bets` | array of `RuletaBetRequest` | Yes | At least `1` bet, at most `RULETA_MAX_BETS_PER_SPIN` (default `20`). Sum of all `amount` values cannot exceed `RULETA_MAX_TOTAL_BET` (default `5000`). |

#### `RuletaBetRequest` fields

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `bet_type` | string enum | Yes | One of the 13 supported bet types listed below. |
| `amount` | strict integer | Yes | Must be a JSON integer (no floats, strings, or booleans) between `RULETA_MIN_BET_AMOUNT` (default `1`) and `RULETA_MAX_BET_AMOUNT` (default `1000`). |
| `numbers` | `integer[] \| null` | Inside bets only | Required for inside bets (`straight`, `split`, `street`, `corner`, `six_line`). Must be omitted or `null` for all other bets. |
| `selection` | `integer \| null` | `dozen` / `column` only | Must be `1`, `2`, or `3` for `dozen` and `column`. Must be omitted or `null` for all other bets. |

> **Strict schema (`extra="forbid"`):** Sending unknown fields anywhere in the request (for example `payout`, `winning_number`, or `uid`) returns `422`. Passing floats (`10.5`), booleans (`true`), or numeric strings (`"10"`) for integer fields also returns `422`.

---

### Supported Bet Types & Payouts

All payouts follow standard European Roulette rules (`0–36`, single zero, house edge `1/37` ≈ `2.70%`).

- **Payout odds (`X:1`)**: profit ratio relative to the stake.
- **Total return (`payout`)**: `amount * (multiplier + 1)` — i.e., **stake + profit** returned to the player's balance when the bet wins, or `0` when it loses.

| `bet_type` | `numbers` | `selection` | Covered pockets | Odds | Total `payout` on win | Example |
| --- | --- | --- | --- | --- | --- | --- |
| `straight` | 1 number (`0–36`) | omit / `null` | 1 | `35:1` | `amount * 36` | `{"bet_type": "straight", "numbers": [17], "amount": 10}` |
| `split` | 2 adjacent numbers | omit / `null` | 2 | `17:1` | `amount * 18` | `{"bet_type": "split", "numbers": [1, 2], "amount": 10}` |
| `street` | 3 numbers in a row / basket | omit / `null` | 3 | `11:1` | `amount * 12` | `{"bet_type": "street", "numbers": [4, 5, 6], "amount": 10}` |
| `corner` | 4-number 2×2 block / first-four | omit / `null` | 4 | `8:1` | `amount * 9` | `{"bet_type": "corner", "numbers": [1, 2, 4, 5], "amount": 10}` |
| `six_line` | 6 numbers (2 adjacent rows) | omit / `null` | 6 | `5:1` | `amount * 6` | `{"bet_type": "six_line", "numbers": [1, 2, 3, 4, 5, 6], "amount": 10}` |
| `dozen` | omit / `null` | `1`, `2`, or `3` | 12 (`1–12`, `13–24`, `25–36`) | `2:1` | `amount * 3` | `{"bet_type": "dozen", "selection": 2, "amount": 20}` |
| `column` | omit / `null` | `1`, `2`, or `3` | 12 (`n%3==1`, `n%3==2`, `n%3==0`) | `2:1` | `amount * 3` | `{"bet_type": "column", "selection": 1, "amount": 20}` |
| `red` | omit / `null` | omit / `null` | 18 red pockets | `1:1` | `amount * 2` | `{"bet_type": "red", "amount": 25}` |
| `black` | omit / `null` | omit / `null` | 18 black pockets | `1:1` | `amount * 2` | `{"bet_type": "black", "amount": 25}` |
| `even` | omit / `null` | omit / `null` | 18 even numbers (`2–36`) | `1:1` | `amount * 2` | `{"bet_type": "even", "amount": 25}` |
| `odd` | omit / `null` | omit / `null` | 18 odd numbers (`1–35`) | `1:1` | `amount * 2` | `{"bet_type": "odd", "amount": 25}` |
| `low` | omit / `null` | omit / `null` | `1–18` | `1:1` | `amount * 2` | `{"bet_type": "low", "amount": 25}` |
| `high` | omit / `null` | omit / `null` | `19–36` | `1:1` | `amount * 2` | `{"bet_type": "high", "amount": 25}` |

#### Inside-bet layout rules & zero (`0`) behavior

- Standard 3×12 table layout (`1, 2, 3` in row 1; `4, 5, 6` in row 2; …; `34, 35, 36` in row 12).
- `numbers` may be sent in any order (the server sorts and normalizes them in the response), must have no duplicates, and must form a valid contiguous combination on the table:
  - Cross-row wraps like `split [3, 4]`, `street [2, 3, 4]`, or `corner [3, 4, 6, 7]` are rejected with `422`.
  - Valid inside combinations with `0`:
    - `straight`: `[0]`
    - `split`: `[0, 1]`, `[0, 2]`, `[0, 3]`
    - `street`: `[0, 1, 2]`, `[0, 2, 3]`
    - `corner` (first-four / basket): `[0, 1, 2, 3]`
- **Zero (`0`) loses all outside bets** (`dozen`, `column`, `red`, `black`, `even`, `odd`, `low`, `high`).

---

### Response `200 OK`

| Field | Type | Meaning |
| --- | --- | --- |
| `winning_number` | integer (`0–36`) | Pocket drawn by the server. |
| `color` | `"green" \| "red" \| "black"` | Color of `winning_number`. |
| `total_bet` | integer | Sum of all placed bet amounts. |
| `total_payout` | integer | Total credits returned across all winning bets (includes returned stakes). `0` if all bets lost. |
| `net_profit` | integer | `total_payout - total_bet` (negative on net loss, `0` on break-even, positive on net win). |
| `new_balance` | integer | Authoritative credit balance stored in Firestore after this spin. |
| `bets` | array | Per-bet breakdown in the same order as the request (`bet_type`, `numbers`, `selection`, `amount`, `won`, `payout`). |

#### Example 1 — Winning spin

Request:
```json
{
  "bets": [
    { "bet_type": "straight", "numbers": [7], "amount": 10 }
  ]
}
```

Response (`200 OK`, starting balance `500`):
```json
{
  "winning_number": 7,
  "color": "red",
  "total_bet": 10,
  "total_payout": 360,
  "net_profit": 350,
  "new_balance": 850,
  "bets": [
    {
      "bet_type": "straight",
      "numbers": [7],
      "selection": null,
      "amount": 10,
      "won": true,
      "payout": 360
    }
  ]
}
```

#### Example 2 — Losing spin

Request:
```json
{
  "bets": [
    { "bet_type": "red", "amount": 25 }
  ]
}
```

Response (`200 OK`, starting balance `500`):
```json
{
  "winning_number": 15,
  "color": "black",
  "total_bet": 25,
  "total_payout": 0,
  "net_profit": -25,
  "new_balance": 475,
  "bets": [
    {
      "bet_type": "red",
      "numbers": null,
      "selection": null,
      "amount": 25,
      "won": false,
      "payout": 0
    }
  ]
}
```

#### Example 3 — Multi-bet spin (mixed win & loss)

Request:
```json
{
  "bets": [
    { "bet_type": "corner", "numbers": [5, 2, 4, 1], "amount": 20 },
    { "bet_type": "black", "amount": 25 }
  ]
}
```

Response (`200 OK`, starting balance `500`, pocket `2` drawn):
```json
{
  "winning_number": 2,
  "color": "black",
  "total_bet": 45,
  "total_payout": 230,
  "net_profit": 185,
  "new_balance": 685,
  "bets": [
    {
      "bet_type": "corner",
      "numbers": [1, 2, 4, 5],
      "selection": null,
      "amount": 20,
      "won": true,
      "payout": 180
    },
    {
      "bet_type": "black",
      "numbers": null,
      "selection": null,
      "amount": 25,
      "won": true,
      "payout": 50
    }
  ]
}
```

---

## 3. Error Responses

Domain errors return `{ "detail": "<message>" }`. FastAPI schema validation errors return `422` with a list of validation items in `detail`.

| HTTP Status | Example `detail` | Cause & Frontend Handling |
| --- | --- | --- |
| `400` | `"Insufficient credits"` | User's Firestore balance is lower than `total_bet`. No credits are deducted and no wheel result is returned. Prompt the user to lower the bet or earn more credits via flashcards. |
| `401` | `"Authentication required or credentials invalid"` | Missing, invalid, expired, or revoked Bearer token (`WWW-Authenticate: Bearer`). Redirect to login. |
| `403` | `"Email verification required"` | Token is valid, but email is unverified. Direct the user to account activation. |
| `422` | `"Bet amount must be at least 1"` / FastAPI validation array | Empty `bets`, unknown fields, invalid inside-bet combination, wrong types, or configured table limits (`RULETA_*`) exceeded. Show validation feedback. |
| `429` | `"Too many requests. Please try again later."` | Rate limit hit (`Retry-After` header included). Disable spin briefly and notify user. |
| `503` | `"User profile service unavailable"` / `"Authentication service unavailable"` / `"Firebase is not initialized"` | Missing Firestore profile (`POST /api/auth/register` not completed) or backend/Firebase outage. Show a retryable error banner. |

---

## 4. Configurable Table Limits (`backend/.env`)

Table limits are configured independently from core app settings in `backend/src/configs/games/ruleta.py` (`RuletaSettings`, `env_prefix="RULETA_"`):

| Env Variable | Default | Meaning |
| --- | --- | --- |
| `RULETA_MIN_BET_AMOUNT` | `1` | Minimum stake per individual bet |
| `RULETA_MAX_BET_AMOUNT` | `1000` | Maximum stake per individual bet |
| `RULETA_MAX_TOTAL_BET` | `5000` | Maximum combined stake across all bets in one spin |
| `RULETA_MAX_BETS_PER_SPIN` | `20` | Maximum number of bet entries in `bets[]` |

Validation enforces `min_bet_amount <= max_bet_amount <= max_total_bet` at backend startup.

---

## 5. European Roulette Constants for Frontend Rendering

Use these exact constants when building the wheel graphic and table UI so colors and pocket order match the backend:

```typescript
// Clockwise European single-zero wheel sequence (37 pockets)
export const RULETA_WHEEL_ORDER = [
  0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
  5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
] as const;

export const RULETA_RED_NUMBERS = new Set([
  1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36,
]);

export const RULETA_BLACK_NUMBERS = new Set([
  2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35,
]);
```

---

## 6. Angular Integration Example

Create a dedicated service (following `CurrentUserService` and `LlmEvalService` conventions). `authInterceptor` automatically attaches the `Authorization: Bearer <token>` header:

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export type PocketColor = 'green' | 'red' | 'black';

export type BetType =
  | 'straight'
  | 'split'
  | 'street'
  | 'corner'
  | 'six_line'
  | 'dozen'
  | 'column'
  | 'red'
  | 'black'
  | 'even'
  | 'odd'
  | 'low'
  | 'high';

export interface RuletaBetRequest {
  bet_type: BetType;
  amount: number;
  numbers?: number[] | null;
  selection?: 1 | 2 | 3 | null;
}

export interface RuletaSpinRequest {
  bets: RuletaBetRequest[];
}

export interface RuletaBetResult {
  bet_type: BetType;
  numbers: number[] | null;
  selection: number | null;
  amount: number;
  won: boolean;
  payout: number;
}

export interface RuletaSpinResponse {
  winning_number: number;
  color: PocketColor;
  total_bet: number;
  total_payout: number;
  net_profit: number;
  new_balance: number;
  bets: RuletaBetResult[];
}

@Injectable({ providedIn: 'root' })
export class RuletaService {
  private readonly http = inject(HttpClient);

  spin(payload: RuletaSpinRequest): Observable<RuletaSpinResponse> {
    return this.http.post<RuletaSpinResponse>(
      `${environment.apiUrl}/games/ruleta/spin`,
      payload,
    );
  }
}
```

### Frontend UI Flow Recommendations

1. **Disable "Spin" while in-flight:** Prevent duplicate `POST /spin` calls while a request or wheel animation is active so the user does not accidentally place back-to-back wagers.
2. **Animate to the server result:** Call `ruletaService.spin(...)` on click, start a spinning state, then land the wheel on `response.winning_number` (using `RULETA_WHEEL_ORDER` to compute the target angle).
3. **Sync displayed credits from `new_balance`:** Update the UI credit counter from `response.new_balance` once the animation finishes (or immediately if desired) rather than doing `balance += net_profit` manually.
4. **Highlight winning bets:** Use `response.bets[i].won` and `response.bets[i].payout` to highlight winning chips on the table and show the payout breakdown.

---

## 7. Credits & Firestore Audit Trail

Every valid spin executes a single `@firestore.transactional` operation in `UserService.settle_game_wager` (`backend/src/services/user_service.py`):

1. Verifies `users/{uid}` exists and `credits >= total_bet`.
2. Updates `users/{uid}.credits` to `current_credits - total_bet + total_payout`.
3. Writes transaction log entries to `users/{uid}/transactions/{transactionId}` (see [credits.md](../auth_system/credits.md)):
   - Always records `{ "value": -total_bet, "Reason": "Ruleta: zakład", "timestamp": SERVER_TIMESTAMP }`.
   - When `total_payout > 0`, also records `{ "value": +total_payout, "Reason": "Ruleta: wygrana", "timestamp": SERVER_TIMESTAMP }`.
