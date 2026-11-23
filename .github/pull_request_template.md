## Tichet Jira

[KAN-](https://student-echipa5.atlassian.net/browse/KAN-)

## Ce face PR-ul

<!-- Pe scurt, ce s-a schimbat și de ce. Doar codul acestui tichet: ce mai e nevoie se face într-un tichet nou. -->

## Cum se verifică

<!-- Pașii pentru reviewer: comenzi, endpoint-uri din Swagger UI, date de test. -->

## Checklist

- [ ] Branch-ul are forma `KAN-<număr>-<titlul-tichetului>`, iar titlul PR-ului `KAN-<număr>: ...`
- [ ] Codul respectă [Coding style backend](https://student-echipa5.atlassian.net/wiki/spaces/MFS/pages/18776065) (`ruff format`, `ruff check`, `mypy` trec local)
- [ ] Testele noi sau modificate trec (`uv run pytest`)
- [ ] PR-ul conține doar modificările tichetului
- [ ] Am cerut review de la cel puțin un coleg și am răspuns la fiecare comentariu

## Checklist pentru reviewer

<!-- Se completează de reviewer înainte de „Approve”. Pentru orice punct nebifat se lasă un comentariu pe linia respectivă și se alege „Request changes”. -->

- [ ] Am rulat codul local (pașii din „Cum se verifică”), nu doar am citit diff-ul
- [ ] Codul face ce cere tichetul, fără modificări în afara lui
- [ ] Cazurile-limită au teste (date invalide, id inexistent, listă goală, utilizator fără drepturi), iar testele pică dacă logica e greșită
- [ ] Erorile și codurile de stare respectă contractul `rrm-api.yaml`
- [ ] Fără cod mort, duplicat sau abstracții inutile; numele sunt clare
- [ ] Fără pachete noi neverificate și fără date sensibile (`.env`, parole, chei)
- [ ] Autorul poate explica fiecare linie din diff
