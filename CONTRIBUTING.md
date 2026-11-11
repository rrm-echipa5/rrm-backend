# Cum lucrăm în rrm-backend

Regulile complete sunt în Confluence, în paginile **Coding style backend** și **GitHub** (pagini copil ale Documentului de Arhitectură). Aici e varianta scurtă, pentru lucrul de zi cu zi.

## Fluxul pentru un tichet

1. Iei tichetul din Jira după ce te-ai înțeles cu echipa și îl treci în **In Progress**.
2. Pornești din `main` actualizat și creezi un branch cu numărul și titlul tichetului:

   ```bash
   git switch main && git pull
   git switch -c KAN-124-backend-crud-pentru-resurse-in-aplicatia-initiala
   ```

3. Faci commit-uri mici, cu mesaje de forma `KAN-124: Adaugă endpoint-ul DELETE /resources/{id}`.
4. Deschizi un pull request spre `main`, cu titlul `KAN-124: ...`, și ceri review de la cel puțin un coleg.
5. După approval și după ce trec verificările din GitHub Actions, integrezi cu **Squash and merge** sau **Rebase and merge**. Branch-ul se șterge automat.
6. Actualizezi `main` local, verifici aplicația și treci tichetul în **Done**.

Un branch conține doar codul tichetului lui. Dacă descoperi că mai e nevoie de altceva, creezi un tichet nou.

## Ce este verificat automat

| Regulă | Local (pre-commit) | La PR (GitHub Actions) |
| --- | --- | --- |
| Formatare PEP 8 (`ruff format`) | la commit | job-ul *Coding style* |
| Reguli PEP 8 și ale echipei (`ruff check`) | la commit | job-ul *Coding style* |
| Tipuri (`mypy --strict`) | la commit | job-ul *Coding style* |
| Teste (`pytest`) | - | job-ul *Teste* |
| Mesaj de commit `KAN-<număr>: ...` | la commit | titlul PR-ului, job-ul *Convenții* |
| Branch `KAN-<număr>-<titlu>` | la push | job-ul *Convenții* |
| Fără commit direct pe `main` | la commit | regula de protecție a branch-ului |

Branch-ul `main` acceptă modificări doar prin pull request, cu cel puțin un approval de la alt membru al echipei și cu toate verificările de mai sus trecute.

## Comenzi utile

```bash
uv sync                      # instalează dependențele, inclusiv uneltele de dezvoltare
uv run pre-commit install    # activează hook-urile locale (o singură dată)
uv run ruff format           # formatează codul
uv run ruff check --fix      # verifică regulile și repară ce se poate automat
uv run mypy                  # verifică tipurile
uv run pytest                # rulează testele
```
