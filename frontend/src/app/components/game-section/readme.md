Tutaj będzie wszystko związane z grami.
`game-window` to tylko opakowanie. Jego nie zmieniamy.
Każda gra ma swój folder `[NAZWA_GRY]-components`. 
Jeśli np osobno robicie interfejs gry czyli np. betowanie, a osobno samą treść to zróbcie sobie osobne komponenty.

Pracujecie na signals, w ngOnInit ustawiacie funkcje i zmienne, które mają zadziałać przy wczytaniu komponentu.
korzystajcie z @if, @else itp. Nie z *ngIf.

W każdym nadrzędnym komponencie (tym z nazwą gry jako główną klasą) musicie obsłużyć funkcje z `services/game-clients`.
taką funkcję wywołujecie z odpowiednimi argumentami, następnie używacie `.subscribe`, w którym macie przypadki `next` i `error`.
Next to przypadek, gdy wszystko się powiedzie. Tam umieszczacie dalszą logikę jak gdyby nigdy nic
Error jak nazwa wskazuje to błąd. Kody błędów zwracane przez wasze backendowe endpointy trzeba przechwycić switchem i napisać polskie wersje błędów.

Dla spójności najlepiej by błędy były obsłużone tak jak w learning-section przy tworzeniu sesji albo display-cards, przy ewaluacji. Możecie skopiować tego samego CSSa.

Dodajcie wszędzie flagi ładowania, błędu i treściBłędu.