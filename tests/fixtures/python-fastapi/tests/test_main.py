from app.main import answer


def test_answer():
    assert answer(" hi ") == "hi"
