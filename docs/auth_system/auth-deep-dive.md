# Authentication deep dive: from login to a protected backend route

This document follows the current implementation, function by function. Use the
[integration guide](auth-integration.md) for configuration and the full HTTP contract.
Examples use one fictional user with UID `user-abc123`. No diagrams are required
to follow the explanation.

## 1. What happens during login?

The user enters an email and password in Angular. The sign-in component calls
`FirebaseAuthService.signIn(email, password)`. That service contains:

```typescript
const result = await signInWithEmailAndPassword(this.auth, email, password);
return result.user;
```

The Firebase SDK sends the credentials to **Firebase Authentication** over HTTPS.
Firebase checks the account and credentials. On success, its response includes
an ID token, a refresh token and user information. A simplified Firebase response
contains these fields:

```json
{
  "localId": "user-abc123",
  "idToken": "<Firebase ID token>",
  "refreshToken": "<refresh token>",
  "expiresIn": "3600"
}
```

This is Firebase's response, not a response from our FastAPI backend. The SDK
handles it and returns a `UserCredential`; our service returns `result.user`, a
Firebase `User` object. The app does not manually extract tokens from this JSON.
Later, calling `user.getIdToken()` gets the ID-token string from the SDK.

For Google and Facebook, our service uses `signInWithPopup()` with the matching
provider. The provider authenticates the person and Firebase establishes the
Firebase session. The rest of our API flow uses a **Firebase ID token** for any
of these login methods. A provider access token is not the credential our API expects.

Source: [Firebase sign-in response](https://firebase.google.com/docs/reference/rest/auth#section-sign-in-email-password).

## 2. What is the Bearer token?

Firebase issues an **ID token**. It becomes a Bearer credential when Angular puts
it in this HTTP header:

```http
Authorization: Bearer <Firebase ID token>
```

`Bearer` is the authorization scheme; it is not part of the token itself. Anyone
holding a valid bearer token can present it, so do not share or log real tokens.

The token is a JWT string with three encoded parts separated by dots:

```text
header.payload.signature
```

The header identifies the signing algorithm (`RS256`) and public-key identifier
(`kid`). A fictional, partial decoded payload could look like this:

```json
{
  "sub": "user-abc123",
  "aud": "edukasyno",
  "iss": "https://securetoken.google.com/edukasyno",
  "iat": 1794571200,
  "exp": 1794574800,
  "email": "learner@example.test",
  "email_verified": true,
  "name": "Learner"
}
```

| Claim | What it tells the backend |
| --- | --- |
| `sub` | Which Firebase user the token represents: the UID. |
| `aud`, `iss` | Which Firebase project issued the token. |
| `iat`, `exp` | Issue and expiry times, expressed in Unix seconds. |
| `email`, `email_verified`, `name` | Available identity information. Some fields can be absent. |

The payload is readable, not encrypted. The signature lets the Admin SDK detect
forged or modified tokens using Firebase's public signing keys. The backend must
verify the signature and claims before trusting the UID. Our backend receives
the verified UID as `claims["uid"]` from the Admin SDK.

The token contains no Firestore profile, balance, questions or progress.
Source: [Firebase ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens).

## 3. What exactly happens when Angular opens the dashboard?

The browser page `/dashboard` belongs to Angular. There is no FastAPI
`/dashboard` endpoint in this implementation. Opening the page starts a separate
HTTP request to `/api/auth/me`.

1. **Navigate.** After successful sign-in, `SignIn` checks `user.emailVerified`.
   It navigates to `/dashboard` for a verified user, or account activation otherwise.
2. **Check browser navigation.** `app.routes.ts` applies `authGuard` to the
   dashboard. The guard waits for Firebase auth state, including session restoration
   after refresh. It allows a signed-in user with a verified email to enter.
3. **Initialize the page.** `Dashboard.ngOnInit()` calls `loadProfile()`.
4. **Create the API request.** `loadProfile()` subscribes to
   `CurrentUserService.getMe()`, which calls:

   ```typescript
   return this.http.get<CurrentUser>(`${environment.apiUrl}/auth/me`);
   ```

5. **Attach the token.** Before that request leaves Angular, `authInterceptor`
   checks that its URL belongs to our configured API. It calls
   `FirebaseAuthService.getIdToken()`, which calls `user.getIdToken()` after
   obtaining the current Firebase user.
6. **Send the HTTP request.** The interceptor attaches the token:

   ```http
   GET /api/auth/me HTTP/1.1
   Host: localhost:8000
   Authorization: Bearer <Firebase ID token>
   ```

7. **Check backend authentication.** FastAPI runs the dependencies explained in
   section 4. The browser guard's decision does not authorize this HTTP request.
8. **Read the profile.** If authentication and email checks pass, the `/me` route
   calls `UserService.get_current_user(user)` using the verified identity.
9. **Display the result.** FastAPI serializes `CurrentUserResponse` as JSON.
   The dashboard's subscription stores it in its `user` signal. A failed request
   sets the `error` signal instead.

The page can therefore open successfully while its profile request fails, for
example with `503` when Firestore is unavailable.

## 4. How does Depends run the authentication code?

The actual `/me` route declares this parameter:

```python
user: AuthenticatedUser = Depends(get_verified_user)
```

This is an instruction to FastAPI: **call the dependency and supply its return
value as `user` before executing the route body**. Angular does not send this
Python object, and the developer does not call the dependency manually.

### Step A: extract the header

In `src/dependencies.py`, the existing declaration is:

```python
bearer = HTTPBearer(auto_error=False)
```

FastAPI calls it for the current request. For a valid Bearer header, it supplies
`HTTPAuthorizationCredentials`; `credentials.credentials` contains only the token
string, without the word `Bearer`. Missing/wrong authentication produces `None`,
which our dependency turns into `401`.

### Step B: run get_current_user

This is the current dependency:

```python
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    service: AuthService = Depends(get_auth_service),
) -> AuthenticatedUser:
    if credentials is None:
        raise AuthenticationError()
    return service.verify_token(credentials.credentials)
```

FastAPI resolves both dependencies: `bearer` extracts the request's token and
`get_auth_service` supplies an `AuthService`. Then it calls this function.

### Step C: verify the token and build the identity object

`AuthService.verify_token()` calls:

```python
claims = auth.verify_id_token(token, check_revoked=True)
return AuthenticatedUser.model_validate(claims)
```

The real method also handles errors. Invalid/expired/revoked tokens return `401`;
Firebase verification infrastructure errors return `503`. It validates the token
for our Firebase project, not merely whether it is formatted like a JWT.

`check_revoked=True` additionally checks Firebase Authentication for account status
and revocation. That adds a network request. Public signing certificates may be
cached by the SDK; verification does not require sending the token to Firestore.
Source: [Firebase revocation checking](https://firebase.google.com/docs/auth/admin/manage-sessions#detect_id_token_revocation).

On success, the return value is a Python object equivalent to:

```python
AuthenticatedUser(
    uid="user-abc123",
    email="learner@example.test",
    email_verified=True,
    display_name="Learner",
)
```

This is an internal object, not yet an HTTP response. Only the declared identity
fields are retained; for example the model maps the token's `name` to `display_name`.

### Step D: require verified email

FastAPI passes that object into the next existing dependency:

```python
def get_verified_user(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.email_verified:
        raise EmailNotVerifiedError()
    return user
```

It returns the same user or raises an error resulting in `403`. After success,
FastAPI assigns that object to the route's `user` parameter and executes the route
body. If any required check fails, the route body does not run. The global error
handler returns the documented JSON error, for example:

```json
{ "detail": "Authentication required or credentials invalid" }
```

This dependency mechanism is described in the
[FastAPI documentation](https://fastapi.tiangolo.com/tutorial/dependencies/).

## 5. Where does Firestore enter the request?

The existing `/me` route also requests `Depends(get_user_service)`. That creates
a `UserService` using the initialized Firestore client. It is separate from
authentication and does not identify the caller.

Once the dependencies succeed, the route body executes:

```python
response.headers["Cache-Control"] = "no-store"
return service.get_current_user(user)
```

The profile service already knows the caller is `user-abc123` from `user.uid`.
It reads `users/user-abc123`, creates the document with a server timestamp if
absent, and preserves existing data. It returns a `CurrentUserResponse` object.
FastAPI converts it to this HTTP `200` JSON response:

```json
{
  "uid": "user-abc123",
  "email": "learner@example.test",
  "email_verified": true,
  "display_name": "Learner",
  "profile": {
    "created_at": "2026-11-13T12:00:00Z"
  }
}
```

Firestore returns the profile data. It does not supply the trusted login identity.
The trusted UID was known before the database request.

### Why does the backend also need service-account credentials?

The user ID token proves **who is calling the API**. The backend's
`firebase-service-account.json` identifies **the backend service to Firebase**
and authorizes its Admin operations, subject to that account's permissions.

The current backend loads the private file during Firebase initialization. The
Admin SDK uses its credentials for privileged calls, including revocation/account
checks and Firestore access. Our backend does not forward the user's Bearer token
to Firestore or upload the private JSON file with each request. The file is also
not the private key Firebase used to sign the user's ID token.

## 6. How will another protected route work?

Use the same dependency. The existing function is called `get_current_user`, not
`get_user`. Use `get_verified_user` when confirmed email is required as well.

This is a **documentation example, not an implemented route**:

```python
from fastapi import APIRouter, Depends

from src.dependencies import get_verified_user
from src.models.auth import AuthenticatedUser

router = APIRouter()


@router.get("/whoami", response_model=AuthenticatedUser)
def whoami(
    user: AuthenticatedUser = Depends(get_verified_user),
) -> AuthenticatedUser:
    return user
```

After registering this router under the normal `/api` prefix, an Angular
`HttpClient` request to `/api/whoami` would use the existing interceptor. FastAPI
would extract and verify that request's token, check email, and pass the user into
`whoami`. This example returns identity only and performs no Firestore access.

For a real learning/game feature, use `user.uid` in that feature's service to
select the owner's data. Validate the action and calculate rewards on the server.
The frontend supplies feature input, not a trusted owner identity or balance.

The new route does **not** need to call `/me` first. A successful `/me` request
does not authorize later requests; each protected request runs its dependencies.
FastAPI normally reuses a shared dependency result within one request, not across
separate requests. Profile/database loading remains the feature's responsibility.

## 7. What persists between requests?

| Item | Who keeps it? | What our backend does |
| --- | --- | --- |
| Browser login session and refresh token | Firebase browser SDK | Does not implement its own token-storage/session table. |
| ID token | Firebase SDK supplies it to Angular | Verifies the token presented on each protected request. Does not save it in Firestore. |
| `AuthenticatedUser` | Request handling in FastAPI | Passes this Python object to the route for the current request. |
| Profile | Firestore | Reads/creates it when `/me` runs. |

ID tokens last about one hour. The SDK manages obtaining replacement tokens;
asking for a token does not necessarily mean a fresh login or network request.
Our interceptor asks the SDK for a current token before forwarding an API request.
It does not currently implement automatic retry after an API `401` response.
Source: [Firebase session management](https://firebase.google.com/docs/auth/admin/manage-sessions).

On browser refresh, the SDK restores auth state and the dashboard flow runs again.
On logout, our navbar calls Firebase `signOut()` and redirects to login. A copied
token in another client is not revoked by this local logout alone.

## 8. Similar function names: which one do I use?

| Name | Location | Returns / purpose |
| --- | --- | --- |
| `FirebaseAuthService.getCurrentUser()` | Angular auth service | Firebase SDK user restored in the browser. |
| `get_current_user()` | FastAPI dependencies | Token-verified `AuthenticatedUser`, with no database lookup. |
| `get_verified_user()` | FastAPI dependencies | The same identity after requiring verified email. |
| `get_user_service()` | FastAPI dependencies | A profile-service instance, not a user. |
| `UserService.get_current_user(user)` | Backend profile service | `CurrentUserResponse`, after Firestore profile lookup/provisioning. |

Source files: [Angular auth](../../frontend/src/app/services/firebase-auth.service.ts),
[interceptor](../../frontend/src/app/interceptors/auth.interceptor.ts),
[dashboard](../../frontend/src/app/components/dashboard/dashboard.ts),
[FastAPI dependencies](../../backend/src/dependencies.py),
[token service](../../backend/src/services/auth_service.py),
[profile service](../../backend/src/services/user_service.py),
[identity/response models](../../backend/src/models/auth.py).
