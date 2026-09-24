# QTPCA - Server Side

QR Transfer Pay for Communal Appliances - Bezhotovostní náhrada mincovníků pro spotřebiče ve společných prostorách budov (např. pračky). Uživatel si předem pošle peníze bankovním převodem, na terminálu u spotřebiče se přihlásí jednorázovým kódem a spotřebič si „odemkne" na zvolený čas.

Autoři: Karolina Kováčová, Jindřich Adamec

## Jak to funguje

1. **Dobití kreditu** – uživatel pošle převod na bankovní účet QTPCA a jako variabilní symbol uvede číslo svého pokoje.
2. **Zpracování plateb** – server každé 3 minuty stáhne výpis z banky a připíše platby na zůstatky pokojů.
3. **Přihlášení na terminálu** – uživatel zadá na klávesnici číslo pokoje a jednorázový kód (TOTP) z Google Authenticatoru.
4. **Spuštění spotřebiče** – uživatel zvolí spotřebič, čas a cenu. Server strhne cenu ze zůstatku a terminál spotřebič zapne.
5. **Dokončení** – po skončení (nebo přerušení) terminál pošle skutečně využité jednotky a cenu. Server vrátí rozdíl na zůstatek.

## Architektura

- **Terminál**: Raspberry Pi Zero, ethernetový modul ENC28J60, LCD 2x16, klávesnice 4x4, měnič napěťových úrovní, relé. Software v Pythonu, komunikace s periferiemi přes I2C.
- **Centrální server**: Django + Django REST Framework, PostgreSQL, JWT tokeny, TOTP, Celery + Redis.
- **Údržba**: administrátorské webové rozhraní (Django admin), lokální přístup, dokumentace.

## Struktura projektu

```
qtpca/              nastavení Django, URL, Celery aplikace
api/                REST API (views, serializery, URL)
appliance_module/   spotřebiče, endpointy, pokoje, logy běhů, auth služba
  model/            modely (Room, Appliance, Endpoint, RunsLog, RoomTOTP, ...)
  servicies_factories/
                    ApplianceService (start/finish), factory, AuthService
bank_module/        zpracování bankovních plateb
  data_getter.py    Celery úloha pro stažení výpisu
  addBalance.py     připsání plateb na zůstatky pokojů
  data.txt          ukázkový výpis (formát Fio banky, JSON)
```

## Datový model

- **Room** – pokoj: `key` (číslo pokoje = variabilní symbol), `balance` v haléřích, omezení `balance >= 0`.
- **RoomTOTP** – TOTP tajemství pokoje, v databázi uložené šifrovaně (Fernet, klíč `FIELD_ENCRYPTION_KEY`).
- **Appliance** – spotřebič: název a cena za jednotku.
- **Endpoint** – terminál: IP adresa, stav připojení, verze tokenu.
- **EndpointApplianceStateRoom** – stav spotřebiče na daném terminálu (obsazeno, kým, aktuální log).
- **RunsLog** – záznam každého běhu: počáteční a konečné jednotky a cena, stav (běží / dokončeno / přerušeno), časy.
- **ValidPayments / InvalidPayments** – přijaté platby přiřazené k pokoji, respektive nepřiřaditelné platby.

## API

Všechny endpointy jsou pod `/api/`, metoda `POST`, JSON. Chyby vrací `400` s `{"error": "..."}`. (Vývoj)

| Endpoint | Požadavek | Odpověď |
|---|---|---|
| `auth/challenge/` | `room_num`, `endpoint_id` | `200`: `token` (challenge, platí 2 min) |
| `auth/verify/` | `token`, `auth_code` (TOTP) | `200`: `token` (access, platí 5 min), `balance` (haléře), `appliances` (`name`, `value`) |
| `appliance/start/` | `token`, `appliance_name`, `units` (s, 1–14400), `price` (Kč, 1–400) | `201`: `newbalance` (haléře), `token` (start, platí 60 s + `units`) |
| `appliance/finish/` | `token` (start), `units` (s), `price` (Kč), `aborted` (bool) | `200`: `{"status": "finished"}` |

Cena se v API zadává v korunách, uvnitř systému se počítá v haléřích (násobení 100).

### Průběh komunikace

```
terminál                          server
   |-- auth/challenge ------------->|  ověří pokoj a endpoint
   |<-- challenge token ------------|
   |-- auth/verify (TOTP) --------->|  ověří kód, vydá access token
   |<-- access token, zůstatek -----|
   |-- appliance/start ------------>|  strhne cenu, založí RunsLog
   |<-- nový zůstatek, start token -|
   |-- appliance/finish ----------->|  uzavře log, vrátí nespotřebovaný rozdíl
   |<-- finished -------------------|
```

## Bankovní modul

- Celery beat spouští úlohu `bank_module.data_getter.fetch_data_from_api` každých 180 s (adresa z `BANK_API_URL`).
- `update_rooms_from_json` zpracuje transakce z JSON výpisu:
  - přeskočí už zpracované transakce (podle ID pohybu),
  - ignoruje odchozí a nulové platby,
  - platbu v CZK s variabilním symbolem odpovídajícím existujícímu pokoji připíše na zůstatek a uloží do `ValidPayments`,
  - ostatní platby uloží do `InvalidPayments` k ruční kontrole.
- Celé zpracování běží v jedné databázové transakci, řádky pokojů jsou zamčené (`select_for_update`).
