PASSWORD = "un mot de passe assez long"


def register(client, email="ada@example.org", password=PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email="ada@example.org", password=PASSWORD):
    return client.post("/auth/token", data={"username": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_profile(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    tokens = login(client).json()
    me = client.get("/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == "ada@example.org"
    assert me.headers["x-content-type-options"] == "nosniff"


def test_same_answer_for_unknown_account_and_wrong_password(client):
    register(client)
    wrong = login(client, password="mauvais mot de passe")
    unknown = login(client, email="inconnu@example.org")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Identifiants invalides"}
    assert register(client, email="b@example.org", password="court").status_code == 422


def test_refresh_rotation_and_reuse_detection(client):
    register(client)
    first = login(client).json()
    second = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    # Réutiliser le jeton déjà échangé révoque toute la chaîne, y compris le jeton le plus récent.
    assert client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    latest = second.json()["refresh_token"]
    assert client.post("/auth/refresh", json={"refresh_token": latest}).status_code == 401


def test_token_types_are_not_interchangeable(client):
    register(client)
    tokens = login(client).json()
    assert client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401
    assert client.get("/me", headers=bearer(tokens["refresh_token"])).status_code == 401
    assert client.get("/me", headers=bearer("pas.un.jeton")).status_code == 401


def test_logout_revokes_the_refresh_chain(client):
    register(client)
    tokens = login(client).json()
    assert client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_login_attempts_are_rate_limited(client):
    register(client)
    codes = [login(client, password="faux mot de passe").status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
