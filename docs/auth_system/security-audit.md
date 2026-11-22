# Audyt Bezpieczeństwa Poświadczeń i Przepływu Uwierzytelniania

**Projekt:** Kasyno Edu  
**Data audytu:** 15 listopada 2026 r.  
**Osoba odpowiedzialna / Wykonawca:** Kamil Skorupski  
**Status audytu:** ZAKOŃCZONY POMYŚLNIE (PASS dla wszystkich kryteriów)

---

## 1. Cel i zakres audytu

Celem audytu jest weryfikacja mechanizmów ochrony poświadczeń użytkowników oraz konfiguracji bezpieczeństwa frontendu (Angular) i backendu (FastAPI) pod kątem zgodności z wymaganiami projektowymi:

1. Brak logowania haseł w plain-text w aplikacji klienckiej i serwerowej.
2. Bezpieczne przechowywanie i hashowanie haseł przy użyciu mechanizmów kryptograficznych Firebase Authentication (scrypt, tokeny JWT RS256, bezpieczny transport).
3. Prawidłowa ochrona kluczy prywatnych (Service Account, zmienne środowiskowe `.env`) przed wyciekiem do repozytorium Git.
4. Ochrona przed wyciekiem poświadczeń w nagłówkach HTTP i parametrach adresów URL.

---

## 2. Wyniki weryfikacji kryteriów akceptacji

### Kryterium 1: Hasła użytkowników nie są w żadnym miejscu logowane w plain-text

| Obszar                              | Status   | Dowód wdrożenia i weryfikacja                                                                                                                                                                                                                                                                                                                                                                                 |
| :---------------------------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Frontend (Konsola przeglądarki)** | **PASS** | W całym kodzie TypeScript frontendu (`frontend/src/`) nie występuje żadne wywołanie `console.log` ani `console.error` z polami `password`. W komponentach autoryzacyjnych (`sign-in.ts`, `sign-up.ts`, `password-change.ts`) wartości formularzy są przekazywane bezpośrednio do metod SDK Firebase i nie są utrwalane w logach deweloperskich. Błędy są bezpiecznie mapowane przez `firebaseErrorMessage()`. |
| **Backend (Serwer FastAPI)**        | **PASS** | Serwer backendowy w ogóle nie posiada endpointów przyjmujących ani przetwarzających hasła użytkowników w plain-text. Rejestracja i logowanie zachodzą bezpośrednio między przeglądarką a Firebase Auth. Konfiguracja logowania (`backend/src/main.py`) nie loguje ciał żądań ani nagłówków autoryzacyjnych.                                                                                                   |

#### Polecenie audytowe – Frontend:

```bash
git grep -E "console\.(log|info|warn|error)" frontend/src/
# Wynik: Brak jakichkolwiek instrukcji logujących poświadczenia w komponentach autoryzacyjnych.
```

#### Polecenie audytowe – Backend:

```bash
git grep -E "(logger\.|logging\.|print\()" backend/src/
# Wynik: Rejestrowana jest wyłącznie informacja o inicjalizacji aplikacji z Project ID (bez kluczy ani danych użytkowników).
```

---

### Kryterium 2: Całość procesu rejestracji i logowania oparta na Firebase Auth z natywnym hashowaniem haseł

| Aspekt kryptograficzny             | Mechanizm                     | Opis techniczny                                                                                                                                                                                                                                                                         |
| :--------------------------------- | :---------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Algorytm hashowania**            | **Modified scrypt**           | Firebase Authentication wykorzystuje algorytm _scrypt_ (funkcja KDF o wysokim zapotrzebowaniu pamięciowym - _memory-hard_), chroniący przed atakami brute-force z wykorzystaniem procesorów graficznych (GPU) i dedykowanych układów scalonych (ASIC).                                  |
| **Separacja soli i klucz podpisu** | Per-project Salt & Signer Key | Każdy projekt Firebase posiada unikalny klucz sygnatury (_signer key_) i sól (_salt separator_) zarządzane wewnętrznie przez infrastrukturę Google Cloud KMS. Ani baza Firestore, ani backend Kasyno Edu nie przechowują haszy haseł.                                                   |
| **Czasowe tokeny tożsamości**      | JWT (RS256)                   | Po poprawnym uwierzytelnieniu Firebase wydaje token ID (JWT) z okresem ważności **1 godziny** (`expiresIn: 3600`). Podpis generowany jest asymetrycznym kluczem prywatnym Google (algorytm RS256) i weryfikowany przez backend z wykorzystaniem oficjalnych certyfikatów Google (JWKS). |
| **Unieważnianie sesji**            | Token Revocation Check        | Backend FastAPI weryfikuje token metodą `auth.verify_id_token(token, check_revoked=True)`, co zapewnia natychmiastowe odrzucenie sesji po zmianie hasła lub unieważnieniu tokenu przez użytkownika.                                                                                     |

---

### Kryterium 3: Klucze prywatne (serviceAccountKey.json, tokeny API) wykluczone z repozytorium git i przekazywane przez zmienne środowiskowe

| Zasób wrażliwy                             | Ścieżka / Konfiguracja                              | Zabezpieczenie w `.gitignore`                                                                                   | Sposób przekazywania                                                    |
| :----------------------------------------- | :-------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------- |
| **Klucz Service Account**                  | `backend/credentials/firebase-service-account.json` | `/backend/credentials/`<br>`*firebase-adminsdk*.json`<br>`*serviceAccountKey*.json`<br>`*service-account*.json` | Zmienna środowiskowa `FIREBASE_CREDENTIALS_PATH` w `backend/.env`       |
| **Zmienne środowiskowe backendu**          | `backend/.env`                                      | `/backend/.env`                                                                                                 | Plik lokalny, niecommitowany; szablon w `backend/.env.example`          |
| **Zmienne środowiskowe frontendu**         | `frontend/.env`                                     | `/frontend/.env`<br>`/frontend/.env.*`<br>`!/frontend/.env.example`                                             | Plik lokalny, niecommitowany; szablon w `frontend/.env.example`         |
| **Wygenerowana konfiguracja przeglądarki** | `frontend/src/environments/environment.config.ts`   | `/frontend/src/environments/environment.config.ts`                                                              | Generowany dynamicznie przez `node generate-env.mjs` z lokalnego `.env` |

#### Weryfikacja historii Git:

Przeprowadzono pełne przeszukanie historii repozytorium (`git log --all --full-history`) – żaden klucz prywatny ani plik `.env` nie został nigdy zatwierdzony w repozytorium.

---

### Kryterium 4: Audyt bezpieczeństwa przepływu uwierzytelniania pod kątem wycieków w nagłówkach i parametrach URL

| Mechanizm ochronny                            | Implementacja                                       | Skutek dla bezpieczeństwa                                                                                                                                                                                                      |
| :-------------------------------------------- | :-------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Bezpieczny transport (HTTPS)**              | Google Identity Toolkit API                         | Całość komunikacji z Firebase Auth (`identitytoolkit.googleapis.com`) odbywa się wyłącznie szyfrowanym protokołem HTTPS (TLS 1.2+).                                                                                            |
| **Ukryty payload (POST)**                     | Metody `POST` w Firebase SDK                        | Rejestracja i logowanie przekazują poświadczenia w ciele żądania (body JSON), uniemożliwiając wyciek do historii przeglądarki, logów serwera proxy i nagłówków `Referer`. Brak poświadczeń w parametrach URL (`query string`). |
| **Bezpieczny nagłówek Bearer**                | `frontend/src/app/interceptors/auth.interceptor.ts` | Token autoryzacyjny przekazywany jest do backendu w nagłówku `Authorization: Bearer <token>`, a nie w parametrze URL (np. `?token=...`).                                                                                       |
| **Ochrona przed wyciekiem do innych domen**   | Walidacja `target.origin` w interceptorze           | Interceptor sprawdza, czy docelowy URL odpowiada ściśle backendowi aplikacji (`environment.apiUrl`). Token ID nie jest dołączany do żądań kierowanych do zewnętrznych domen.                                                   |
| **Ochrona pamięci podręcznej (Anti-Caching)** | Nagłówek `Cache-Control: no-store`                  | Endpoint `GET /api/auth/me` zwraca nagłówek `Cache-Control: no-store`, zapobiegając zapisywaniu tożsamości użytkownika w pamięci podręcznej przeglądarki lub serwerów pośredniczących.                                         |

---

## 3. Podsumowanie i rekomendacje

Wszystkie 4 kryteria akceptacji zostały w pełni zrealizowane:

- Dane logowania są szyfrowane w tranzycie (TLS) i spoczynku (scrypt w Firebase KMS).
- Hasła w postaci jawnej nigdy nie trafiają do logów ani do bazy danych aplikacji.
- Klucze prywatne i pliki konfiguracyjne są bezpiecznie odseparowane od repozytorium kodu.
- Przepływ autoryzacyjny oparty na tokenach JWT nie wycieka w parametrach URL ani w nieautoryzowanych nagłówkach.

---

## 4. Ochrona przed powszechnymi atakami (Brute-Force, Rate Limiting, Injection, Anti-Enumeration)

**Zadanie:** Ochrona endpointów oraz interfejsu logowania przed atakami typu brute-force, nadmiernymi zapytaniami (rate limiting) oraz powszechnymi podatnościami webowymi w procesie autoryzacji.  
**Tester / Audytor:** Kamil Skorupski  
**Status:** ZREALIZOWANO I PRZETESTOWANO (PASS)

### 4.1. Weryfikacja kryteriów akceptacji

#### Kryterium A: Mechanizmy blokady i opóźnień przy wielokrotnych nieudanych próbach (Brute-Force & Rate Limiting)

1. **Ochrona Anti-Abuse w Firebase Authentication:**
   - Firebase Authentication monitoruje częstotliwość prób logowania z danego adresu IP oraz na dane konto użytkownika.
   - Po serii błędnych prób Firebase tymczasowo blokuje próby logowania z kodem `auth/too-many-requests`.
   - W [firebase-auth.service.ts](../../frontend/src/app/services/firebase-auth.service.ts) kod ten jest przetłumaczony na czytelny komunikat: _„Zbyt wiele prób. Spróbuj ponownie za chwilę.”_.
   - Formularz Angulara blokuje przycisk akcji (`[disabled]="isSubmitting"`), co uniemożliwia wielokrotne spamowanie żądaniami w ułamku sekundy (_click flooding_).
2. **Ochrona Rate-Limiting na poziomie FastAPI Backend:**
   - Wdrożono dedykowany middleware [RateLimiterMiddleware](../../backend/src/middlewares/security.py) oparty na algorytmie przesuwanego okna czasowego (_sliding window_).
   - Limituje liczbę żądań do API (domyślnie 100 żądań na minutę na adres IP klienta).
   - Po przekroczeniu progu API zwraca kod **HTTP 429 Too Many Requests** wraz z nagłówkiem `Retry-After: 60` oraz odpowiedzią JSON: `{"detail": "Too many requests. Please try again later."}`.
   - Przetestowano w teście jednostkowym `backend/tests/test_security.py::test_rate_limiter_blocks_excessive_requests`.

#### Kryterium B: Odrzucanie nieprawidłowych payloadów i prób wstrzyknięć (Walidacja Pydantic & Angular)

1. **Ścisła walidacja typów w Pydantic (Backend):**
   - Modele tożsamości [AuthenticatedUser](../../backend/src/models/auth.py) posiadają konfigurację `ConfigDict(strict=True, frozen=True)` oraz ograniczenia długości pól `Field(min_length=1, max_length=128)`.
   - Próby wstrzyknięcia obiektów (NoSQL injection, np. `{"$ne": null}`), nieprawidłowych typów czy zbyt długich ciągów znaków (buffer overflow) są automatycznie odrzucane przez Pydantic przed wykonaniem logiki biznesowej (`ValidationError`).
   - Przetestowano w teście `backend/tests/test_security.py::test_pydantic_rejects_invalid_uid_and_injection`.
2. **Walidacja wejścia na frontendzie (Angular):**
   - Formularze logowania i rejestracji wymuszają walidację typów (format adresu e-mail, minimalna długość hasła 6 znaków, zgodność powtórzonego hasła).
   - Przycisk wysłania formularza pozostaje nieaktywny (`[disabled]="form.invalid"`) dopóki dane nie spełniają reguł walidacji.
   - Szablony Angulara domyślnie zabezpieczają dane przed atakami XSS (Cross-Site Scripting) poprzez kontekstowe oczyszczanie wartości w interpolacji `{{ }}`.

#### Kryterium C: Reakcja na serię błędnych prób autoryzacji (Brak ujawniania istnienia konta - Anti-Enumeration)

1. **Ochrona przed wyliczaniem użytkowników (User Enumeration Protection):**
   - W formularzu logowania podanie błędnego hasła dla istniejącego konta (`auth/wrong-password`) oraz podanie adresu e-mail, który nie istnieje w systemie (`auth/user-not-found` / `auth/invalid-credential`), zwraca **DOKŁADNIE TEN SAM, JEDNOLITY KOMUNIKAT**:
     ```text
     "Nieprawidłowy e-mail lub hasło."
     ```
   - Atakujący testujący słownikowo listę adresów e-mail nie jest w stanie ustalić, czy dany użytkownik posiada konto w aplikacji.
2. **Formularz resetowania hasła:**
   - Komponent [password-change.ts](../../frontend/src/app/components/auth-components/password-change/password-change.ts) wyświetla neutralny komunikat:
     ```text
     "Jeśli konto istnieje, otrzymasz e-mail z linkiem do zmiany hasła."
     ```
   - System nie informuje, czy adres e-mail został znaleziony w bazie.
3. **Kody błędów HTTP w API Backendowym:**
   - Każda próba nieautoryzowanego dostępu (brak tokena, token wygasły, unieważniony lub sfałszowany) zwraca jednolity kod **HTTP 401 Unauthorized** z nagłówkiem `WWW-Authenticate: Bearer` i komunikatem `{"detail": "Authentication required or credentials invalid"}`.

### 4.2. Dodatkowe nagłówki bezpieczeństwa OWASP (Security Headers)

W [SecurityHeadersMiddleware](../../backend/src/middlewares/security.py) skonfigurowano standardowe nagłówki ochronne:

- `X-Content-Type-Options: nosniff` – blokuje próby interpretacji plików przez przeglądarkę niezgodnie z deklarowanym typem MIME.
- `X-Frame-Options: DENY` – chroni aplikację przed atakami typu Clickjacking w ramkach iframe.
- `X-XSS-Protection: 1; mode=block` – aktywuje filtr XSS w starszych przeglądarkach.
- `Referrer-Policy: strict-origin-when-cross-origin` – ogranicza wyciek pełnych adresów URL w nagłówku Referer.
