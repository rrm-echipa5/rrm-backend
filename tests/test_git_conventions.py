import pytest

from scripts.check_git_conventions import check_branch, check_message, check_pr_title


@pytest.mark.parametrize(
    "branch",
    [
        "KAN-123-backend-proiectul-initial-fastapi",
        "KAN-86-backend-baza-locala-cu-docker-compose-si-datele-de-test",
    ],
)
def test_branch_with_ticket_and_title_is_accepted(branch: str) -> None:
    assert check_branch(branch) == []


@pytest.mark.parametrize(
    "branch",
    ["main", "master", "feature/resurse", "KAN-124", "kan-124-crud", "KAN-124_crud_resurse"],
)
def test_branch_without_ticket_and_title_is_rejected(branch: str) -> None:
    assert check_branch(branch) != []


def test_commit_message_with_ticket_is_accepted() -> None:
    assert check_message("KAN-124: Adaugă endpoint-ul DELETE /resources/{id}") == []


@pytest.mark.parametrize("message", ["fix", "KAN-124 fara doua puncte", "KAN-124: scurt"])
def test_commit_message_without_convention_is_rejected(message: str) -> None:
    assert check_message(message) != []


def test_commit_message_longer_than_72_characters_is_rejected() -> None:
    assert check_message("KAN-124: " + "a" * 70) != []


def test_pr_title_must_reference_the_branch_ticket() -> None:
    branch = "KAN-124-backend-crud-pentru-resurse"

    assert check_pr_title("KAN-124: CRUD pentru resurse", branch) == []
    assert check_pr_title("KAN-125: CRUD pentru resurse", branch) != []
