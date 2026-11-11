"""Verifică convențiile Git ale echipei: numele branch-ului, mesajul de commit și titlul PR-ului.

Scriptul este folosit de hook-urile pre-commit (local) și de workflow-ul GitHub Actions
(la fiecare pull request), deci aceleași reguli se aplică în ambele locuri.

Utilizare:
    python scripts/check_git_conventions.py branch KAN-124-backend-crud-pentru-resurse
    python scripts/check_git_conventions.py commit-msg .git/COMMIT_EDITMSG
    python scripts/check_git_conventions.py pr-title "KAN-124: CRUD pentru resurse" KAN-124-...
"""

import re
import subprocess
import sys
from pathlib import Path

BRANCH_PATTERN = re.compile(r"^(KAN-\d+)-[a-z0-9]+(-[a-z0-9]+)+$")
MESSAGE_PATTERN = re.compile(r"^(KAN-\d+): \S.{8,}$")
MESSAGE_MAX_LENGTH = 72
ALLOWED_MESSAGE_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ", "amend! ")
PROTECTED_BRANCHES = ("main", "master")

BRANCH_HELP = (
    "Numele branch-ului trebuie să conțină numărul tichetului Jira și titlul lui, cu litere mici "
    "și cratime, fără diacritice: KAN-<număr>-<titlul-tichetului>, de exemplu "
    "KAN-124-backend-crud-pentru-resurse-in-aplicatia-initiala."
)
MESSAGE_HELP = (
    "Mesajul de commit (prima linie) are forma «KAN-<număr>: Descriere la imperativ», "
    f"de cel mult {MESSAGE_MAX_LENGTH} de caractere, de exemplu «KAN-124: Adaugă endpoint-ul "
    "DELETE /resources/{{id}}»."
)


def check_branch(branch: str) -> list[str]:
    """Întoarce erorile pentru numele unui branch (lista goală dacă numele e corect)."""
    if branch in PROTECTED_BRANCHES:
        return [
            f"Nu se lucrează direct pe {branch}; creează un branch pentru tichet. {BRANCH_HELP}"
        ]
    if not BRANCH_PATTERN.match(branch):
        return [f"Branch-ul «{branch}» nu respectă convenția. {BRANCH_HELP}"]
    return []


def check_message(first_line: str) -> list[str]:
    """Întoarce erorile pentru prima linie a unui mesaj de commit sau titlul unui PR."""
    if first_line.startswith(ALLOWED_MESSAGE_PREFIXES):
        return []
    errors = []
    if not MESSAGE_PATTERN.match(first_line):
        errors.append(f"Mesajul «{first_line}» nu respectă convenția. {MESSAGE_HELP}")
    if len(first_line) > MESSAGE_MAX_LENGTH:
        errors.append(
            f"Prima linie are {len(first_line)} caractere; maximul este {MESSAGE_MAX_LENGTH}."
        )
    return errors


def check_commit_message_file(path: str) -> list[str]:
    """Verifică mesajul de commit din fișierul primit de hook-ul `commit-msg`."""
    lines = [
        line
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if not line.startswith("#")
    ]
    first_line = lines[0].strip() if lines else ""
    return check_message(first_line)


def check_pr_title(title: str, branch: str) -> list[str]:
    """Verifică titlul PR-ului și faptul că se referă la același tichet ca branch-ul."""
    errors = check_branch(branch) + check_message(title)
    branch_match = BRANCH_PATTERN.match(branch)
    title_match = MESSAGE_PATTERN.match(title)
    if branch_match and title_match and branch_match.group(1) != title_match.group(1):
        errors.append(
            f"Titlul PR-ului se referă la {title_match.group(1)}, "
            f"dar branch-ul la {branch_match.group(1)}."
        )
    return errors


def current_branch() -> str:
    """Întoarce numele branch-ului curent din repository-ul local."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main(argv: list[str]) -> int:
    """Rulează verificarea cerută în linia de comandă și întoarce codul de ieșire."""
    if len(argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2
    command, args = argv[1], argv[2:]
    if command == "branch":
        errors = check_branch(args[0] if args else current_branch())
    elif command == "commit-msg":
        errors = check_commit_message_file(args[0])
    elif command == "pr-title":
        errors = check_pr_title(args[0], args[1])
    else:
        sys.stderr.write(f"Comandă necunoscută: {command}\n")
        return 2
    for error in errors:
        sys.stderr.write(f"✗ {error}\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
