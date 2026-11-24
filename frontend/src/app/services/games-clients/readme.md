Tutaj obsługujecie endpointy z backendu oraz tworzycie modele na wzór pythonowych, jeśli endpoint wymaga.
Jedna funkcja dla endpointu wg wzoru:

nazwafunkcji([CIAŁO_ZAPYTANIA]): Observable<[TYP_ZWRACANY]> 
{
  return this.http.[METODA: "get" | "post"](`${environment.apiUrl}/games/[NAZWA_GRY]/[AKCJA]`, [CIAŁO_ZAPYTANIA]);
}