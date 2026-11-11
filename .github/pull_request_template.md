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
- [ ] Am cerut review de la cel puțin un coleg
