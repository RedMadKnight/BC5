# Eksperyment 0419: przełączniki — rozpiska dla maintainera (2026-11-14)

Dwa zestawienia zamówione 2026-11-13: żywe słowa z launchera, słowo po słowie (nic z nich nie jest usuwane bez
Twojej decyzji), oraz słowa „zmierzone jako nic nie daje" z tym, co było w eksperymentach. Źródła: `launcher-words.md`,
`owners-verdicts.md`, `undecided-plan.md`, `docs/HANDOFF.md`. Niczego tu nie mierzyłem na nowo.

## 1. Żywe słowa launchera, które nigdy nie dostały werdyktu

Wszystkie dotyczą drugiego tytułu i dziś działają w każdej rozgrywce. W kandydacie G zostają bez zmian.

| Słowo (wartość) | Co robi | Co zmierzono i gdzie | Propozycja |
|---|---|---|---|
| `BC5_DIRECT_CHAIN_HOLD_US` (nieustawione = 2 ms) | Jak długo łańcuch buforów wątku gry może zostać otwarty, zanim pójdzie na GPU. | Nic. Eksperymenty 0165, 0360 i 0381 o nim wspominają, żaden przebieg nie zmienił wartości. | Stała 2 ms i słowo znika (zachowanie się nie zmienia). Alternatywa: najpierw jedno ramię z inną wartością. |
| `BC5_DIRECT_DCB_WAIT_MS` (nieustawione = 8 ms) | Jak długo wątek gry czeka na etykietę, zanim porzuci czekanie. | F264/F265: przy 100 ms porzuconych czekań 1 zamiast 29 na 20 minut. F271: limit 8, 100 i 400 ms nie kosztuje widocznego czasu klatki. F285: przy 100 ms 0 porzuceń wobec 13 przy 8 ms, ale wątek gry stał wtedy w 22 czekaniach po 4,9–68,7 ms. | Do decyzji: stała 8 ms (jak dziś) albo jeszcze jedno spojrzenie na 100 ms — to jedyne słowo z tej listy z pomiarem na korzyść innej wartości niż dzisiejsza. |
| `BC5_DIRECT_LAZY_RELEASE=30,eager` + `BC5_GUARD_SPLIT=1` | Przy każdej synchronizacji pamięci oddaje fragmenty nieużywane od 30 s; SPLIT pozwala ciąć bufor z aliasami. | Exp 0401 e7 i exp 0412 (wiersz B15 audytu): 16–31 cięć na przebieg, bez błędu, zysk 0,1–0,2 GiB; w jednym ramieniu wycięto 1548 MiB i 96 % wróciło. Ocena strażnika: „mały zysk, potrzebny, żeby pin nie rósł". | Jedno ramię bez tej pary na obu tytułach. Próg strażnika: 100 MiB różnicy w pinie lub GTT w 420 s i 600 s; poniżej — usunąć oba, powyżej — stała. |
| `BC5_GUARD_FORGET=10` | Fragment wymuszony przez podpowiedź, od 10 s pod żadnym widokiem, wypada ze zbioru wymuszonych i może zostać wycięty. | Powód (264 MiB „wymuszone i pod żadnym widokiem" po 5 minutach) zmierzono, gdy istniały jeszcze wyuczone okna, których już nie ma. | Jedno ramię bez niego (spacer do G+560), ten sam próg 100 MiB; potem usunąć albo stała 10. |

Trzy słowa z tej samej grupy okazały się martwe na jednym ringu (`BC5_DIRECT_CROSS_RING_WAITS`, `_RING_DEPS`,
`_TWO_RING_WAIT_MS`) i w G są usunięte z kodem. `BC5_DIRECT_HEAP_GUARDS` jest w G stałą „włączone".

## 2. „Zmierzone jako nic nie daje" — co było w eksperymentach

| Słowo | Co to było | Wynik w eksperymencie | W kandydacie G |
|---|---|---|---|
| `KYTY_BC5_RING_SPIN_US`, `KYTY_BC5_TIMERSLACK_NS`, `KYTY_BC5_MUTEX_SPIN_US` | Trzy kandydaci na poprawkę czasów ładowania (exp 0415). | Bez wpływu na ładowanie przy rozdzielczości 1–2 s (sekcje 6 i 9). Nigdy nie mierzone na płynności. | Usunięte z kodem. |
| `KYTY_BC5_RING_POLL_US` | Okres odpytywania dzwonków ringu. | 50 i 1000 µs dały te same czasy ładowania. | Stała 200 µs. |
| `KYTY_BC5_EVENT_COALESCE_SAME` | Port z exp 0416: powtórzone zdarzenie z tymi samymi danymi liczy się na ostatnim wpisie. | Bez wpływu na ładowanie; napisane dla poprawności, nie dla szybkości. | Usunięte z kodem. |
| `KYTY_BC5_SEMA_TARGETED_WAKE` | Port z exp 0416: sygnał semafora budzi tylko tych, którym daje licznik. | Bez wpływu na ładowanie. **Uwaga:** celował w F451 (budzenie wątków roboczych), które w HANDOFF jest OTWARTE i „nie ma dla niego liczby szybkości" — czyli nie zmierzono tego, po co powstał. | Usunięte z kodem, jak zatwierdziłeś. Jeśli wolisz jedno ramię na płynność przed usunięciem, przywrócenie to odwrócenie jednego kroku. |
| `BC5_DIRECT_TF_DEFAULT` | Domyślny pierścień teselacji hosta (exp 0189). | „Nie jest potrzebny temu tytułowi" — tytuł podaje własny. | Usunięte z kodem, razem z `BC5_DIRECT_HS_OFFCHIP`, które działało tylko wewnątrz niego. |
| `BC5_GUARD_MAP_RULE`, `BC5_GUARD_PRT_BG` | Wcześniejsze reguły mapowania strażnika (exp 0412). | Zastąpione przez K1r, który jest domyślnie włączony; musiały być nieustawione. | Opcja zdjęta; kod jeszcze jest (martwy). |
| `BC5_GUARD_MLOCK` | Blokowanie stron w pamięci. | Nigdy w rozgrywce; wymaga `ulimit -l`. | Opcja zdjęta; kod jeszcze jest. |
| `BC5_GUARD_PIN_CAP`, `_CAP_ACT`, `_CAP_NAMES` | Limit przypiętej pamięci. | Jeden pomiar: pin −290 MiB, obrazu nikt nie obejrzał; poza tym tylko log. | Opcja zdjęta; kod jeszcze jest. |
| `KYTY_BC5_AMM_PRT_CMDS`, `KYTY_BC5_AMM_EXTRA_CMDS` | Dodatkowe polecenia AMM. | Audyt, wiersz A6: mutex i węzeł mapy na każdą stronę 16 KiB przy każdym wywołaniu; drugi tytuł ich nie importuje. | Opcja zdjęta; kod jeszcze jest. |
| `BC5_DIRECT_HEAP_GUARDS` | Bufor zer 2 MiB za każdą dużą stertą (exp 0037/0417). | F820: trasa skryptowa czysta z osłonami i bez, po dwa przebiegi. | Stała „włączone". |

## 3. Pięć słów polowania — rozstrzygnięte 2026-11-14: usunięte

„Próby z polowania na dawne zawieszenia => usunąć z kodu" zatwierdziłeś na moim opisie, że te zawieszenia już nie
wracają. To był mój błąd: w HANDOFF klasy F403 i F813 są OTWARTE, a kandydat F zawiesił GPU 13 listopada w sposób,
który te klasy opisują. Dlatego w G usunąłem tylko to, co same zapisy odrzucają (`GPU_CHECK_YZ`, `GPU_CHECK_ZERO`,
`FORCE_START_000`, `ARGS_COPY`, `PIECES_NO_CLEAR`), a pięć słów zostawiłem i zapytałem jeszcze raz. Odpowiedziałeś
„Usuń", wiedząc powyższe, więc w G (patch `0dcd4357`) tych pięciu słów też już nie da się ustawić:

| Słowo | Co o nim wiadomo (żadne nie miało własnego rozstrzygającego przebiegu) |
|---|---|
| `BC5_DIRECT_ARGS_WB` | Jedyne z pomiarem na korzyść: 36,6 minuty gry bez F403; „druga długa rozgrywka jest decydującym krokiem" — nigdy jej nie było. |
| `BC5_DIRECT_FL_SERIAL` | Kandydat na poprawkę F813: 0 zawieszeń na 8 z nim, 0 na 10 bez, około 3 % wolniej. |
| `BC5_DIRECT_FL_VGT_FLUSH`, `BC5_DIRECT_ARGS_FLUSH`, `BC5_DIRECT_ARGS_FLUSH_DRAWS` | Zbudowane, nigdy nie uruchomione na GPU. |

Uczciwie: na razie zniknęła opcja, a kod za nią jest martwy i jeszcze siedzi w źródle (tak samo jak przy czterech
odrzuconych słowach); wytnę go w drugiej fazie, z kompilatorem pod ręką. W HANDOFF przy F403 i F813 jest dopisane,
że te słowa usunięto bez przebiegu i skąd je odtworzyć (patch `27b6416f` z commita d04d41f3, backend z a7e63069).

## 4. Liczby

Policzone ze źródeł (nie z list): build wspólny B czyta 264 słowa; kandydat F 247, z czego 200 da się ustawić;
kandydat G 199, z czego **152** da się ustawić (39 to wiersze jednego tytułu, 3 to ustawienia domyślne z opcją,
110 pozostałych, głównie diagnostyka i łapacze). Bez werdyktu po G: 11; 10 po ramieniu dla `FORGET`.
