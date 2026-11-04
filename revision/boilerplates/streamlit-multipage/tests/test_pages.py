from streamlit.testing.v1 import AppTest


def test_main_app_runs():
    at = AppTest.from_file("../streamlit_app.py", default_timeout=30).run()
    assert not at.exception


def test_data_page_example_dataset():
    at = AppTest.from_file("../pages_src/donnees.py", default_timeout=30).run()
    assert at.info[0].value.startswith("Aucune donnée")
    at.button[0].click().run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 30


def test_prediction_page_uses_local_fallback(monkeypatch):
    monkeypatch.delenv("API_URL", raising=False)
    at = AppTest.from_file("../pages_src/prediction.py", default_timeout=30).run()
    # dans un formulaire, la saisie et l'envoi se font dans la même exécution
    at.text_area[0].input("Livraison rapide, produit excellent")
    at.button[0].click().run()
    assert not at.exception
    assert at.metric[0].value == "positif"
    assert len(at.session_state.history) == 1


def test_prediction_page_reports_unreachable_api(monkeypatch):
    monkeypatch.setenv("API_URL", "http://127.0.0.1:9")
    at = AppTest.from_file("../pages_src/prediction.py", default_timeout=30).run()
    at.text_area[0].input("bonjour")
    at.button[0].click().run()
    assert "injoignable" in at.error[0].value
