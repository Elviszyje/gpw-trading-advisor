# Dokument Wymagań

## Wprowadzenie

System GPW Daily Trading Advisor to zaawansowana aplikacja do analizy i rekomendacji inwestycyjnych na polskiej giełdzie papierów wartościowych, skupiająca się na strategiach daily trading (kupno i sprzedaż tego samego dnia). System łączy analizę techniczną z analizą nastrojów rynkowych poprzez monitoring zmian cen, liczby transakcji, komunikatów ESPI/EBI oraz newsów finansowych, dostarczając użytkownikom sygnały BUY/SELL w czasie rzeczywistym.

## Wymagania

### Wymaganie 1

**User Story:** Jako daily trader, chcę otrzymywać dane cenowe intraday w czasie rzeczywistym, aby móc podejmować szybkie decyzje inwestycyjne.

#### Kryteria Akceptacji

1. WHEN system jest uruchomiony THEN system SHALL pobierać dane cenowe z stooq.pl co 1-5 minut (bo wyboru przez administratora)
2. WHEN dane są pobierane THEN system SHALL wykorzystywać Selenium scraper do pozyskania danych intraday
3. WHEN scraping jest wykonywany THEN system SHALL obsługiwać co najmniej 12 różnych spółek jednocześnie
4. IF scraping nie powiedzie się THEN system SHALL ponowić próbę maksymalnie 3 razy z 30-sekundowym opóźnieniem

### Wymaganie 2

**User Story:** Jako daily trader, chcę monitorować komunikaty ESPI/EBI i newsy finansowe, aby rozumieć kontekst rynkowy wpływający na ceny akcji.

#### Kryteria Akceptacji

1. WHEN system monitoruje komunikaty THEN system SHALL pobierać dane ESPI/EBI poprzez RSS scraper co godzinę
2. WHEN system monitoruje newsy THEN system SHALL scrapować wiele portali finansowych w regularnych interwałach
3. WHEN nowy komunikat ESPI/EBI zostanie opublikowany THEN system SHALL przeanalizować jego wpływ na cenę akcji w ciągu 15 minut
4. IF komunikat zawiera kluczowe słowa (wyniki, dywidenda, fuzja) THEN system SHALL oznaczyć go jako wysokiej ważności

### Wymaganie 3

**User Story:** Jako daily trader, chcę otrzymywać sygnały BUY/SELL oparte na analizie technicznej, aby maksymalizować zyski z transakcji intraday.

#### Kryteria Akceptacji

1. WHEN system analizuje dane cenowe THEN system SHALL obliczać wskaźniki RSI, MACD, Bollinger Bands, SMA/EMA
2. WHEN system wykrywa okazję inwestycyjną THEN system SHALL identyfikować spadki ceny z wysokim wolumenem, odbicia i momentum reversal
3. WHEN analiza jest wykonywana THEN system SHALL analizować dane w ramach czasowych 1d i 5d z różnymi progami
4. WHEN sygnał BUY/SELL jest generowany THEN system SHALL uwzględniać co najmniej 3 różne wskaźniki techniczne
5. IF RSI < 30 AND wolumen > średnia 20-dniowa * 1.5 THEN system SHALL generować sygnał BUY - te parametry powinno sie moc potem modyfikowac w interfejsie
6. IF RSI > 70 AND MACD pokazuje divergencję THEN system SHALL generować sygnał SELL - te parametry powinno sie moc potem modyfikowac w interfejsie

### Wymaganie 4

**User Story:** Jako daily trader, chcę otrzymywać natychmiastowe powiadomienia na Telegram, aby nie przegapić okazji inwestycyjnych.

#### Kryteria Akceptacji

1. WHEN system generuje sygnał BUY/SELL THEN system SHALL wysłać powiadomienie na Telegram w ciągu 30 sekund
2. WHEN system kończy skanowanie rynku THEN system SHALL wysłać podsumowanie z top okazjami
3. WHEN system wysyła powiadomienie THEN system SHALL uwzględnić typ alertu (price_alerts, intraday_recommendations, scan_summary)
4. WHEN powiadomienie jest wysyłane THEN system SHALL zawierać nazwę spółki, aktualną cenę, sygnał, wskaźniki techniczne i poziom pewności
5. IF połączenie z Telegram API nie powiedzie się THEN system SHALL zapisać powiadomienie w kolejce i ponowić próbę

### Wymaganie 5

**User Story:** Jako daily trader, chcę śledzić skuteczność rekomendacji systemu w czasie rzeczywistym, aby ocenić jego wiarygodność w ramach tego samego dnia handlowego.

#### Kryteria Akceptacji

1. WHEN system generuje rekomendację THEN system SHALL zapisać timestamp, cenę wejścia, sygnał i wskaźniki
2. WHEN upłynie 1, 2, 3, 4, 5, 6, 7, 8 godziny od rekomendacji THEN system SHALL obliczyć aktualny zysk/stratę dla każdej pozycji
3. WHEN dzień handlowy się kończy THEN system SHALL obliczyć końcową skuteczność wszystkich rekomendacji z tego dnia
4. WHEN skuteczność jest obliczana THEN system SHALL uwzględnić procent trafnych sygnałów i średni zysk/stratę w ramach dnia
5. IF rekomendacja osiągnie założony cel zysku THEN system SHALL wysłać powiadomienie o sugerowanym zamknięciu pozycji

### Wymaganie 6

**User Story:** Jako daily trader, chcę aby system działał niezawodnie przez cały dzień handlowy, aby nie przegapić żadnych okazji.

#### Kryteria Akceptacji

1. WHEN system jest uruchomiony THEN system SHALL wykorzystywać 2-8 wątków do równoległego przetwarzania danych
2. WHEN scheduler jest aktywny THEN system SHALL automatycznie restartować zadania w przypadku błędu
3. WHEN system napotka błąd THEN system SHALL logować szczegóły i kontynuować działanie innych komponentów
4. WHEN dzień handlowy się rozpoczyna (9:00) THEN system SHALL automatycznie aktywować wszystkie scrapery i analizatory
5. WHEN dzień handlowy się kończy (17:30) THEN system SHALL wygenerować dzienny raport i wyłączyć scrapery
6. IF system zostanie zrestartowany THEN system SHALL wznowić wszystkie schedulery w ciągu 2 minut

### Wymaganie 7

**User Story:** Jako daily trader, chcę konfigurować parametry ryzyka i cele zysku, aby dostosować rekomendacje do mojej strategii inwestycyjnej.

#### Kryteria Akceptacji

1. WHEN konfiguruję profil ryzyka THEN system SHALL umożliwić wybór między trybami: konserwatywny, umiarkowany, agresywny
2. WHEN ustawiam cel zysku THEN system SHALL pozwolić na określenie docelowego zysku (1%, 3%, 5% lub wartość niestandardowa)
3. WHEN ustawiam stop-loss THEN system SHALL pozwolić na określenie maksymalnej straty (0.5%, 1%, 2% lub wartość niestandardowa)
4. WHEN system generuje rekomendacje THEN system SHALL uwzględniać ustawione parametry ryzyka i cele zysku
5. IF tryb konserwatywny jest aktywny THEN system SHALL generować sygnały tylko przy wysokiej pewności (>80%)
6. IF tryb agresywny jest aktywny THEN system SHALL generować sygnały przy średniej pewności (>60%)
7. WHEN cel zysku zostanie osiągnięty THEN system SHALL automatycznie wysłać alert o zamknięciu pozycji

### Wymaganie 8

**User Story:** Jako daily trader, chcę mieć dostęp do danych historycznych, aby analizować długoterminowe trendy wpływające na decyzje intraday.

#### Kryteria Akceptacji

1. WHEN system pobiera dane historyczne THEN system SHALL przechowywać dane dzienne dla wszystkich monitorowanych spółek
2. WHEN analiza jest wykonywana THEN system SHALL uwzględniać dane historyczne z ostatnich 90 dni
3. WHEN system analizuje trendy THEN system SHALL identyfikować wzorce sezonowe i cykliczne
4. IF brak danych historycznych dla spółki THEN system SHALL pobrać dane z ostatnich 6 miesięcy przy pierwszym uruchomieniu

### Wymaganie 9

**User Story:** Jako administrator systemu, chcę zarządzać kontami użytkowników i ich subskrypcjami, aby kontrolować dostęp do systemu i monetyzować usługę.

#### Kryteria Akceptacji

1. WHEN tworzę nowe konto użytkownika THEN system SHALL wymagać unikalnego username, email i Telegram chat ID
2. WHEN aktywuję konto użytkownika THEN system SHALL umożliwić ustawienie okresu subskrypcji (7, 30, 90, 365 dni)
3. WHEN użytkownik ma aktywną subskrypcję THEN system SHALL wysyłać mu rekomendacje zgodnie z jego konfiguracją
4. WHEN subskrypcja użytkownika wygasa THEN system SHALL automatycznie zatrzymać wysyłanie powiadomień
5. IF subskrypcja wygaśnie za 3 dni THEN system SHALL wysłać powiadomienie o zbliżającym się końcu
6. WHEN dezaktywuję konto użytkownika THEN system SHALL natychmiast zatrzymać wszystkie usługi dla tego użytkownika
7. WHEN przedłużam subskrypcję THEN system SHALL automatycznie wznowić usługi dla użytkownika

### Wymaganie 10

**User Story:** Jako użytkownik systemu, chcę mieć indywidualną konfigurację i otrzymywać powiadomienia na mój prywatny kanał Telegram, aby dostosować system do moich potrzeb.

#### Kryteria Akceptacji

1. WHEN konfiguruję swoje konto THEN system SHALL pozwolić na ustawienie indywidualnych parametrów ryzyka
2. WHEN ustawiam preferencje powiadomień THEN system SHALL pozwolić na wybór typów alertów (BUY/SELL, podsumowania, alerty cenowe)
3. WHEN system wysyła powiadomienia THEN system SHALL kierować je na mój unikalny Telegram chat ID
4. WHEN zmieniam konfigurację THEN system SHALL zastosować nowe ustawienia w ciągu 5 minut
5. IF moja subskrypcja jest nieaktywna THEN system SHALL wyświetlić komunikat o konieczności odnowienia
6. WHEN loguję się do systemu THEN system SHALL pokazać status mojej subskrypcji i pozostały czas
7. WHEN moja subskrypcja jest aktywna THEN system SHALL pozwolić na pełny dostęp do wszystkich funkcji

### Wymaganie 11

**User Story:** Jako administrator systemu, chcę monitorować użycie systemu przez użytkowników, aby optymalizować wydajność i planować rozwój.

#### Kryteria Akceptacji

1. WHEN użytkownik otrzymuje rekomendację THEN system SHALL zapisać statystyki użycia (timestamp, user_id, typ rekomendacji)
2. WHEN generuję raport administratora THEN system SHALL pokazać liczbę aktywnych użytkowników, wysłanych powiadomień i skuteczność
3. WHEN system osiągnie limit użytkowników THEN system SHALL wysłać alert do administratora
4. WHEN użytkownik przekroczy limit zapytań THEN system SHALL zastosować rate limiting
5. IF system wykryje nadużycia THEN system SHALL automatycznie zawiesić konto użytkownika
6. WHEN analizuję wydajność THEN system SHALL pokazać metryki per-user i globalne
7. WHEN planuję skalowanie THEN system SHALL dostarczyć prognozy obciążenia na podstawie trendów użycia

### Wymaganie 12

**User Story:** Jako administrator systemu, chcę móc zaimportować przez interfejs dane historyczne dotyczące zmian cen i wolumenów dla wszystkich spółek z GPW
