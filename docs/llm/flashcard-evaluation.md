# Flashcard evaluation API

Guide for the frontend that opens an LLM grading session and sends an open answer.
The API base URL is `http://localhost:8000/api`. Interactive docs are at
`http://localhost:8000/docs`.

Both routes require a verified Firebase user. Send the Firebase ID token, the same
credential used for `GET /api/auth/me`. A missing or invalid token returns `401`.
An unverified email returns `403`.

```http
Authorization: Bearer <Firebase-ID-token>
Content-Type: application/json
Accept: application/json
```

Successful responses include `Cache-Control: no-store`. Do not cache them.

A session belongs to the Firebase `uid` that created it. Grading with another
user's token returns `404`, the same status as a missing or expired session.
The body is always:

```json
{ "detail": "LLM session not found" }
```

The session lives in the API process memory for `LLM_SESSION_TTL_SECONDS`
(default 3600). A restart drops it. The API key is not returned and is not
written to Firestore.

## 1. Open a session

`POST /api/llm/sessions`

Every field is optional. An empty body `{}` is valid. A missing body is valid.
Blank or whitespace-only strings are treated as omitted.

| Field | Required | Limit | When omitted |
| --- | --- | --- | --- |
| `api_key` | No | 512 characters | `LLM_API_KEY` from the server `.env` |
| `provider` | No | 32 characters | `LLM_PROVIDER` from the server `.env` |
| `model` | No | 128 characters | `LLM_MODEL` from the server `.env` |
| `base_url` | No | 512 characters, `http` or `https` | `LLM_BASE_URL` from the server `.env` |

Send the model endpoint as `base_url` or `url`. Both names are accepted. Include
the `/v1` suffix for an OpenAI-compatible host. A value that is not `http` or
`https` returns `422`.

The server defaults can be empty. Send `api_key`, `provider`, `model`, and
`base_url` together when the client owns the model connection. Timeout, answer
length, and session lifetime stay on the server.

`provider` is trimmed and compared case-insensitively. Accepted names:

| `provider` | What it calls | Extra requirement |
| --- | --- | --- |
| `openai` | OpenAI, or any OpenAI-compatible host | Optional `base_url`. Empty means the official OpenAI API. |
| `ollama` | Ollama through its OpenAI-compatible API | `base_url` is required, from this request or from `LLM_BASE_URL`. Ollama ignores the key, but a non-empty `api_key` is still required. |
| `google_genai` | Google Gemini | Package `langchain-google-genai` must be installed on the server. |
| `anthropic` | Anthropic | Package `langchain-anthropic` must be installed on the server. |

A session is stored only when a key and a usable provider are both resolved.
Otherwise the response is `503` and there is no `session_id`:

| `detail` | Cause |
| --- | --- |
| `LLM API key is not configured` | No `api_key` in the body and no `LLM_API_KEY` on the server |
| `Model URL is required for provider ollama` | Provider is `ollama` and neither the body nor `LLM_BASE_URL` has a URL |
| `Unsupported LLM provider: <name>` | Name is not in the table above |
| `LLM provider package is not installed: <package>` | `google_genai` or `anthropic` was selected, but that package is not installed |

### Response `201`

```json
{ "session_id": "ae902c78-30f0-4e80-a107-ddccbb4f24c7" }
```

`session_id` is a UUID string. The response does not echo `api_key`, `provider`,
`model`, or `base_url`. Keep the id for the grading call. It expires after one hour.

### Setup examples

These four requests are valid. The first three also succeed when the dev server
still has its Ollama defaults. The fourth does not need those defaults.

Server defaults. Uses `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_BASE_URL`.

```http
POST /api/llm/sessions HTTP/1.1
Authorization: Bearer <Firebase-ID-token>
Content-Type: application/json

{}
```

The caller's own key. Provider and model stay on the server defaults.

```json
{ "api_key": "ollama" }
```

Explicit provider and model, still using the server key. `OpenAI` is accepted
and stored as `openai`.

```json
{
  "provider": "OpenAI",
  "model": "gemma3:4b"
}
```

Full client-side Ollama setup. Nothing is read from `.env` except the server
safety limits. `url` and `base_url` are the same field.

```json
{
  "api_key": "ollama",
  "provider": "ollama",
  "model": "gemma3:4b",
  "url": "http://127.0.0.1:11434/v1"
}
```

## 2. Grade an answer

`POST /api/llm/sessions/{session_id}/evaluations`

Do not send `api_key`, `provider`, `model`, or `base_url` here. They were fixed
when the session was opened.

| Field | Required | Limit |
| --- | --- | --- |
| `question` | Yes | 1–4000 characters |
| `expected_answer` | Yes | 1–4000 characters |
| `user_answer` | Yes | Present in the JSON. Schema max is 20000 characters. The server also rejects a trimmed value longer than `LLM_MAX_ANSWER_CHARS` (default 2000) with `422`. |

An empty or whitespace-only `user_answer` does not call the model. The response
is `200`:

```json
{
  "score": 0,
  "verdict": "incorrect",
  "explanation": "Odpowiedź jest pusta, więc nie można przyznać punktów."
}
```

### Response `200`

| Field | Type | Meaning |
| --- | --- | --- |
| `score` | integer `0`–`100` | How much of the expected fact is covered |
| `verdict` | `correct`, `partial`, or `incorrect` | Overall result |
| `explanation` | string, 1–500 characters | One or two Polish sentences for the learner |

Other statuses:

| Status | When |
| --- | --- |
| `404` | Unknown id, expired session, or a session owned by another uid |
| `422` | Missing field, empty question or expected answer, or an answer over the length limit |
| `502` | The model provider failed or returned an unusable result. `detail` is `LLM evaluation failed` |
| `504` | The model did not finish within `LLM_TIMEOUT_SECONDS`. `detail` is `LLM evaluation timed out` |

Domain errors use `{ "detail": "<message>" }`. A malformed body uses FastAPI's
`422` validation list in `detail`.

### Evaluation examples

The saved calls in `context/` use this session id. Replace it with the
`session_id` from section 1, and add the `Authorization` header. Those sample
files do not include the token.

Exact copy of the expected answer. Request: `context/requests_example_exact_copy.txt`.
Response: `context/response_example_exact_copy.json`.

```json
{
  "question": "Struktura i organizacja typowego systemu komputerowego.",
  "expected_answer": "Typowy system komputerowy składa się z procesora, pamięci operacyjnej, urządzeń wejścia/wyjścia oraz magistral łączących te elementy. Procesor wykonuje instrukcje, pamięć przechowuje programy i dane, a urządzenia wejścia/wyjścia umożliwiają komunikację z otoczeniem.",
  "user_answer": "Typowy system komputerowy składa się z procesora, pamięci operacyjnej, urządzeń wejścia/wyjścia oraz magistral łączących te elementy. Procesor wykonuje instrukcje, pamięć przechowuje programy i dane, a urządzenia wejścia/wyjścia umożliwiają komunikację z otoczeniem."
}
```

```json
{
  "score": 100,
  "verdict": "correct",
  "explanation": "Odpowiedź jest identyczna z wzorcową i w pełni poprawna merytorycznie."
}
```

Same facts in different wording, including abbreviations. Request:
`context/requests_example_my_answer.txt`. Response:
`context/response_example_my_answer.json`.

```json
{
  "question": "Budowa i działanie typowego procesora ogólnego przeznaczenia.",
  "expected_answer": "Procesor zawiera jednostkę sterującą, jednostkę arytmetyczno-logiczną (ALU) i rejestry. Jednostka sterująca pobiera i interpretuje instrukcje, ALU wykonuje operacje arytmetyczne i logiczne, a rejestry przechowują szybko dostępne dane.",
  "user_answer": "ALU, CU, registers. CU pobiera i interpretuje instrukcje, ALU wykonuje operacje arytmetyczne i logiczne, a rejestry przechowują szybko dostępne dane"
}
```

```json
{
  "score": 100,
  "verdict": "correct",
  "explanation": "Uczeń poprawnie wymienił wszystkie kluczowe komponenty procesora oraz ich funkcje, używając dopuszczalnych skrótów."
}
```

Only part of the expected facts. Request: `context/request_example_partial.txt`.
Response: `context/request_example_partial.json`.

```json
{
  "question": "Wykonywanie rozkazów przez procesor(y), przerwania, wyjątki.",
  "expected_answer": "Procesor wykonuje cykl pobrania, dekodowania i wykonania instrukcji. Przerwanie sygnalizuje zdarzenie wymagające obsługi, a wyjątek powstaje podczas wykonywania instrukcji, np. przy dzieleniu przez zero. Procesor zapisuje stan i uruchamia odpowiednią procedurę obsługi.",
  "user_answer": "Procesor wykonuje cykl pobrania, dekodowania i wykonania instrukcji"
}
```

```json
{
  "score": 33,
  "verdict": "partial",
  "explanation": "Uczeń poprawnie opisał cykl pracy procesora, jednak całkowicie pominął kwestię przerwań oraz wyjątków, o które pytało pytanie."
}
```

Scores and wording come from the model, so a later call with the same body can
differ. The JSON fields and the three verdict values do not change.
