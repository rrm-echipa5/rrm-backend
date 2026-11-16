from sqlalchemy import text

from app.db.session import get_session_factory


def test_seed_data_is_loaded() -> None:
    with get_session_factory()() as session:
        categories = session.scalar(text("SELECT count(*) FROM resource_categories"))
        sem_name = session.scalar(text("SELECT name FROM resources WHERE id = 7"))

    assert categories == 4
    assert sem_name == "Microscop electronic SEM"
