# Firebase Authentication

Dokument opisuje aktualną integrację logowania Firebase w aplikacji Angular
oraz czynności potrzebne do jej uruchomienia i dalszego rozwijania.

## Zakres integracji

Frontend używa Firebase Authentication z dostawcą **Email/Password**. Zaimplementowano:

- rejestrację adresem e-mail i hasłem; po utworzeniu konta wysyłany jest e-mail weryfikacyjny;
- logowanie; użytkownik z niepotwierdzonym adresem trafia do ekranu aktywacji;
- ponowne wysłanie wiadomości weryfikacyjnej i sprawdzenie statusu weryfikacji;
- wysłanie linku do resetowania hasła;
- ochronę trasy dashboardu przez `authGuard` — dostęp wymaga zalogowania i potwierdzonego adresu e-mail;
- komunikaty dla typowych błędów Firebase.

Firestore nie jest częścią tej integracji.

## Uruchomienie lokalne

Główna aplikacja Angular znajduje się w `kasyno-edu/frontend`. W katalogu głównym repozytorium jest również osobny szkielet Angulara; polecenia uruchomione tam dotyczą innego projektu.

```bash
cd kasyno-edu/frontend
npm install
npm start
```

Serwer developerski uruchamia aplikację pod `http://localhost:4200/`. Alternatywnie można uruchomić `npx ng serve -o` z katalogu `kasyno-edu/frontend`.

## Konfiguracja Firebase

Konfiguracja projektu webowego jest obecnie wpisana w:

- `kasyno-edu/frontend/src/environments/environment.development.ts`
- `kasyno-edu/frontend/src/environments/environment.ts`

Oba pliki wskazują na projekt `edukasyno`. Wartości pochodzą z konfiguracji aplikacji Web w Firebase Console. Przy zmianie projektu zaktualizuj oba środowiska.

W konsoli Firebase sprawdź:

1. **Authentication → Sign-in method** — dostawca **Email/Password** jest włączony.
2. **Authentication → Settings → Authorized domains** — domena, z której korzysta aplikacja (lokalnie `localhost`), jest dozwolona.
3. E-mail szablon weryfikacyjny i resetowania hasła prowadzi użytkownika do właściwej strony; po powrocie do aplikacji można użyć opcji „Sprawdź status”.

Konfiguracja klienta Firebase (m.in. `apiKey`, `authDomain`, `projectId`, `appId`) identyfikuje projekt i jest dostarczana do przeglądarki. **Nie umieszczaj w frontendzie klucza Service Account ani innych poświadczeń administracyjnych.** Ogranicz klucz API w Google Cloud odpowiednio do używanych usług i skonfiguruj reguły bezpieczeństwa po stronie usług Firebase.

## Przepływ i trasy

| Trasa | Działanie |
| --- | --- |
| `/auth/register` | Rejestracja i wysłanie wiadomości weryfikacyjnej |
| `/auth/login` | Logowanie; niezweryfikowane konto jest kierowane do aktywacji |
| `/auth/account-activation` | Ponowne wysłanie linku i odświeżenie statusu weryfikacji |
| `/auth/password-reset` | Wysłanie e-maila z linkiem resetującym hasło |
| `/dashboard` | Dostęp tylko dla zalogowanego użytkownika ze zweryfikowanym e-mailem |

Główna logika Firebase znajduje się w `frontend/src/app/services/firebase-auth.service.ts`, a kontrola trasy w `frontend/src/app/guards/auth.guard.ts`. Widoki formularzy są w `frontend/src/app/components/auth-components/`.

## Ważne ograniczenia

- `authGuard` chroni nawigację w przeglądarce, ale **nie zastępuje autoryzacji backendu**. Backend powinien weryfikować Firebase ID token przy każdym chronionym żądaniu; samo ukrycie trasy nie zabezpiecza API.
- W serwisie jest metoda wylogowania, ale nie jest jeszcze podłączona do widoku/przycisku.
- Konfiguracja Firebase Auth nie oznacza konfiguracji Firestore ani innych usług Firebase.
- Jeżeli aplikacja ma korzystać z własnej domeny, dodaj ją do dozwolonych domen w Firebase Authentication.

## Pliki implementacji

- `frontend/src/environments/environment*.ts` — konfiguracja Firebase dla środowisk.
- `frontend/src/app/services/firebase-auth.service.ts` — inicjalizacja Firebase i operacje Authentication.
- `frontend/src/app/guards/auth.guard.ts` — kontrola dostępu do dashboardu.
- `frontend/src/app/app.routes.ts` — rejestr tras i podpięcie guarda.
- `frontend/src/app/components/auth-components/` — formularze logowania, rejestracji, resetowania hasła i aktywacji.
