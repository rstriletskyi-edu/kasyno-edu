# Slot Machine (`Jednoręki bandyta` / `Sloty`) API

Guide for frontend developers integrating the classic 3×1 Slot Machine (`Jednoręki bandyta`) view with the FastAPI backend.
The API base URL is `http://localhost:8000/api` (configured in Angular as `environment.apiUrl`). Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

---

## 1. Overview & Authentication

The game follows a **server-authoritative MVC pattern**:

- `GET /api/games/slots/config` exposes the machine geometry (`reels: 3`, `rows: 1`), bet limits, available symbol IDs/labels, and paytable so the frontend never duplicates machine definitions.
- `POST /api/games/slots/spin` requires a verified Firebase user, draws 3 independent reels on the server using Python's CSPRNG (`secrets.randbelow`), evaluates the winning combination, and atomically updates Firestore credits and transaction logs.
- Raw RNG weights are **never** exposed. Symbol probabilities and theoretical RTP are included in `/config` only when `SLOTS_EXPOSE_RTP=true` in `backend/.env`.

For `/spin`, send a verified Firebase ID token (attached automatically in Angular by `authInterceptor`):

```http
POST /api/games/slots/spin HTTP/1.1
Authorization: Bearer <Firebase-ID-token>
Content-Type: application/json
Accept: application/json
```

Successful `/spin` responses include `Cache-Control: no-store`. Do not cache spin results.

---

## 2. Machine Configuration: `GET /api/games/slots/config`

Public, read-only endpoint (no `Authorization` header required). Use it on component initialization to render the paytable, bet bounds, and symbol-to-icon mapping.

### Response `200 OK` (`SLOTS_EXPOSE_RTP=false`, default)

```json
{
  "reels": 3,
  "rows": 1,
  "min_bet_amount": 1,
  "max_bet_amount": 500,
  "symbols": [
    { "id": "cherry", "label": "Wiśnia", "probability": null },
    { "id": "lemon", "label": "Cytryna", "probability": null },
    { "id": "orange", "label": "Pomarańcza", "probability": null },
    { "id": "bell", "label": "Dzwonek", "probability": null },
    { "id": "star", "label": "Gwiazda", "probability": null },
    { "id": "seven", "label": "Siódemka", "probability": null }
  ],
  "paytable": [
    { "symbol": "seven", "count": 3, "multiplier": 500, "name": "Jackpot 777" },
    { "symbol": "star", "count": 3, "multiplier": 75, "name": "Potrójna gwiazda" },
    { "symbol": "bell", "count": 3, "multiplier": 30, "name": "Potrójny dzwonek" },
    { "symbol": "orange", "count": 3, "multiplier": 15, "name": "Potrójna pomarańcza" },
    { "symbol": "lemon", "count": 3, "multiplier": 10, "name": "Potrójna cytryna" },
    { "symbol": "cherry", "count": 3, "multiplier": 6, "name": "Potrójna wiśnia" },
    { "symbol": "cherry", "count": 2, "multiplier": 2, "name": "Podwójna wiśnia" }
  ],
  "rtp": null
}
```

### Response `200 OK` (`SLOTS_EXPOSE_RTP=true`)

When enabled in `backend/.env`, each symbol includes its exact `probability` (`weight / total_weight`) and `rtp` provides the theoretical Return-To-Player ratio (`0.95256` = `95.256%` for the default machine):

```json
{
  "reels": 3,
  "rows": 1,
  "min_bet_amount": 1,
  "max_bet_amount": 500,
  "symbols": [
    { "id": "cherry", "label": "Wiśnia", "probability": 0.3 },
    { "id": "lemon", "label": "Cytryna", "probability": 0.25 },
    { "id": "orange", "label": "Pomarańcza", "probability": 0.2 },
    { "id": "bell", "label": "Dzwonek", "probability": 0.13 },
    { "symbol": "star", "label": "Gwiazda", "probability": 0.08 },
    { "id": "seven", "label": "Siódemka", "probability": 0.04 }
  ],
  "paytable": [
    { "symbol": "seven", "count": 3, "multiplier": 500, "name": "Jackpot 777" },
    { "symbol": "star", "count": 3, "multiplier": 75, "name": "Potrójna gwiazda" },
    { "symbol": "bell", "count": 3, "multiplier": 30, "name": "Potrójny dzwonek" },
    { "symbol": "orange", "count": 3, "multiplier": 15, "name": "Potrójna pomarańcza" },
    { "symbol": "lemon", "count": 3, "multiplier": 10, "name": "Potrójna cytryna" },
    { "symbol": "cherry", "count": 3, "multiplier": 6, "name": "Potrójna wiśnia" },
    { "symbol": "cherry", "count": 2, "multiplier": 2, "name": "Podwójna wiśnia" }
  ],
  "rtp": 0.95256
}
```

> **Note:** `Podwójna wiśnia` (`cherry × 2`) pays regardless of which 2 of the 3 reels land on `cherry`. Landing 3× `cherry` awards `Potrójna wiśnia` (`6×`, not `2×`).

---

## 3. Spin Endpoint: `POST /api/games/slots/spin`

### Request Body

```json
{
  "bet_amount": 25
}
```

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `bet_amount` | strict integer | Yes | JSON integer (no floats, booleans, or numeric strings) within `[SLOTS_MIN_BET_AMOUNT, SLOTS_MAX_BET_AMOUNT]` (default `1`–`500`). |

> **Strict schema (`extra="forbid"`):** Any extra field (such as `payout`, `reels`, or `uid`) returns `422`.

### Response `200 OK`

| Field | Type | Meaning |
| --- | --- | --- |
| `reels` | `string[]` | Ordered list of `reels` (3) symbol IDs matching `symbols[].id` from `/config`. |
| `won` | boolean | `true` if a paytable rule matched, `false` otherwise. |
| `matched_combination` | object \| `null` | Matched `paytable` entry (`symbol`, `count`, `multiplier`, `name`) on win, or `null` on loss. |
| `bet_amount` | integer | Accepted stake deducted for this spin. |
| `payout` | integer | Total credits returned (`bet_amount * multiplier` on win, `0` on loss). |
| `net_profit` | integer | `payout - bet_amount`. |
| `new_balance` | integer | Authoritative Firestore balance after settlement. |

#### Example 1 — Winning spin (`Podwójna wiśnia`, starting balance `500`)

```json
{
  "reels": ["cherry", "seven", "cherry"],
  "won": true,
  "matched_combination": {
    "symbol": "cherry",
    "count": 2,
    "multiplier": 2,
    "name": "Podwójna wiśnia"
  },
  "bet_amount": 25,
  "payout": 50,
  "net_profit": 25,
  "new_balance": 525
}
```

#### Example 2 — Losing spin (starting balance `500`)

```json
{
  "reels": ["lemon", "orange", "bell"],
  "won": false,
  "matched_combination": null,
  "bet_amount": 20,
  "payout": 0,
  "net_profit": -20,
  "new_balance": 480
}
```

---

## 4. Error Responses

| HTTP Status | Example `detail` | Cause & Frontend Handling |
| --- | --- | --- |
| `400` | `"Insufficient credits"` | User's Firestore balance is lower than `bet_amount`. Balance is untouched and no `reels` result is returned. |
| `401` | `"Authentication required or credentials invalid"` | Missing, invalid, expired, or revoked Bearer token (`WWW-Authenticate: Bearer`). Redirect to login. |
| `403` | `"Email verification required"` | Token is valid, but email is unverified. Direct user to account activation. |
| `422` | `"Bet amount must be at least 1"` / FastAPI validation array | Unknown fields, non-integer `bet_amount`, or configured `SLOTS_*` limits exceeded. |
| `429` | `"Too many requests. Please try again later."` | Rate limit hit (`Retry-After` header included). |
| `503` | `"User profile service unavailable"` / `"Authentication service unavailable"` / `"Firebase is not initialized"` | Missing Firestore profile (`POST /api/auth/register` not completed) or backend/Firebase outage. |

---

## 5. Configuration (`backend/.env` & `slots_machine.json`)

- Runtime limits and RTP visibility live in `backend/src/configs/games/slots.py` (`SlotsSettings`, `env_prefix="SLOTS_"`):
  - `SLOTS_MIN_BET_AMOUNT` (default `1`)
  - `SLOTS_MAX_BET_AMOUNT` (default `500`)
  - `SLOTS_EXPOSE_RTP` (default `false`)
- Machine geometry, symbol definitions/weights, and paytable multipliers live in `backend/src/configs/games/slots_machine.json`.

---

## 6. Angular Integration Example

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export interface SlotsSymbolConfig {
  id: string;
  label: string;
  probability: number | null;
}

export interface SlotsPaytableEntry {
  symbol: string;
  count: number;
  multiplier: number;
  name: string;
}

export interface SlotsConfigResponse {
  reels: number;
  rows: number;
  min_bet_amount: number;
  max_bet_amount: number;
  symbols: SlotsSymbolConfig[];
  paytable: SlotsPaytableEntry[];
  rtp: number | null;
}

export interface SlotsSpinRequest {
  bet_amount: number;
}

export interface SlotsSpinResponse {
  reels: string[];
  won: boolean;
  matched_combination: SlotsPaytableEntry | null;
  bet_amount: number;
  payout: number;
  net_profit: number;
  new_balance: number;
}

@Injectable({ providedIn: 'root' })
export class SlotsService {
  private readonly http = inject(HttpClient);

  getConfig(): Observable<SlotsConfigResponse> {
    return this.http.get<SlotsConfigResponse>(`${environment.apiUrl}/games/slots/config`);
  }

  spin(betAmount: number): Observable<SlotsSpinResponse> {
    return this.http.post<SlotsSpinResponse>(`${environment.apiUrl}/games/slots/spin`, {
      bet_amount: betAmount,
    } satisfies SlotsSpinRequest);
  }
}
```

### Frontend UI Flow Recommendations

1. **Fetch `/config` once on mount:** Use `symbols` to build your icon/image map (`cherry` → 🍒, `lemon` → 🍋, `orange` → 🍊, `bell` → 🔔, `star` → ⭐, `seven` → 7️⃣), validate the bet input against `[min_bet_amount, max_bet_amount]`, render the paytable dynamically, and optionally display `(rtp * 100).toFixed(2) + '%'` when `rtp !== null`.
2. **Disable "Spin" while in-flight:** Prevent duplicate `POST /spin` calls during request/reel animation.
3. **Sync displayed credits from `new_balance`:** Update the balance counter directly from `response.new_balance` once the reel animation lands on `response.reels`.

---

## 7. Credits & Firestore Audit Trail

Every valid spin executes a single `@firestore.transactional` operation in `UserService.settle_game_wager`:

1. Verifies `users/{uid}` exists and `credits >= bet_amount`.
2. Updates `users/{uid}.credits` to `current_credits - bet_amount + payout`.
3. Writes transaction log entries to `users/{uid}/transactions/{transactionId}` (see [credits.md](../auth_system/credits.md)):
   - Always records `{ "value": -bet_amount, "Reason": "Sloty: zakład", "timestamp": SERVER_TIMESTAMP }`.
   - When `payout > 0`, also records `{ "value": +payout, "Reason": "Sloty: wygrana", "timestamp": SERVER_TIMESTAMP }`.
