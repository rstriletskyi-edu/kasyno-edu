# Żetony i transakcje użytkownika

## Model profilu

Dokument profilu znajduje się w Firestore pod ścieżką:

```text
users/{uid}
```

Przy pierwszym utworzeniu profilu zapisane są następujące pola:

```json
{
  "created_at": "Firestore SERVER_TIMESTAMP",
  "credits": 0
}
```

Model `UserProfile` zwraca `credits` jako liczbę całkowitą z wartością domyślną
`0`. `UserProfile` znajduje się w `backend/src/models/auth.py`.

## Historia transakcji

Transakcje są przechowywane w podkolekcji:

```text
users/{uid}/transactions/{transactionId}
```

`uid` jest częścią ścieżki rodzica. Każdy dokument transakcji ma losowe, unikalne
`transactionId` wygenerowane przez Firestore:

```json
{
  "value": 7.0,
  "Reason": "Przykładowa operacja",
  "timestamp": "Firestore SERVER_TIMESTAMP"
}
```

Pole `value` jest liczbą zmiennoprzecinkową. Wartość dodatnia oznacza dodanie
żetonów, a ujemna ich zabranie.

## Operacje serwisu

Klasa `UserService` w `backend/src/services/user_service.py` udostępnia:

- `add_credits(user, value, reason)` — dodaje żetony i zapisuje dodatnią wartość.
- `remove_credits(user, value, reason)` — zabiera żetony i zapisuje ujemną wartość.
- `get_credits(user)` — odczytuje bieżące saldo z `users/{uid}`.

Prywatna metoda `_modify_credits(user, value, reason)` wykonuje zmianę salda i
dokument transakcji w jednej atomowej transakcji Firestore.

Metody dodawania i odejmowania przyjmują tylko dodatnią kwotę obliczoną po stronie
serwera. Zero, wartości ujemne, nieskończoność, `NaN` oraz wartości logiczne są
odrzucane. Kwota nie jest przyjmowana z body publicznego endpointu.

`record_transaction` tworzy dokument w podkolekcji transakcji z losowym ID,
natomiast operacje zmieniające saldo korzystają z atomowej implementacji
`_modify_credits`.

## Przykłady

Dodanie żetonów:

```python
service.add_credits(user, 7.0, "Ocena fiszki")
```

Zapisana transakcja:

```json
{
  "value": 7.0,
  "Reason": "Ocena fiszki",
  "timestamp": "Firestore SERVER_TIMESTAMP"
}
```

Zabranie żetonów:

```python
service.remove_credits(user, 7.0, "Wykorzystanie gry")
```

Zapisana transakcja ma wartość `-7.0`.
