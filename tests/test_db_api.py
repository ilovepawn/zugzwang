def test_combinations_empty(client):
    response = client.get("/combinations")
    assert response.status_code == 200
    assert response.json() == []


def test_combinations_grouped_counts(client, seeded_positions):
    response = client.get("/combinations")
    assert response.status_code == 200
    payload = {row["combination"]: row["count"] for row in response.json()}
    assert payload == {"KQK": 2, "KRK": 1}


def test_random_position_returns_camelcase(client, seeded_positions):
    response = client.get("/positions/random", params={"combination": "KQK"})
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"positionId", "combination", "fen"}
    assert body["combination"] == "KQK"
    assert isinstance(body["positionId"], int)


def test_random_position_lowercase_normalized(client, seeded_positions):
    response = client.get("/positions/random", params={"combination": "kqk"})
    assert response.status_code == 200
    assert response.json()["combination"] == "KQK"


def test_random_position_unknown_combination_returns_404(client, seeded_positions):
    response = client.get("/positions/random", params={"combination": "KQRK"})
    assert response.status_code == 404


def test_random_position_invalid_charset_returns_422(client):
    response = client.get("/positions/random", params={"combination": "ABCD"})
    assert response.status_code == 422


def test_random_position_too_long_returns_422(client):
    response = client.get("/positions/random", params={"combination": "K" * 11})
    assert response.status_code == 422


def test_random_position_missing_param_returns_422(client):
    response = client.get("/positions/random")
    assert response.status_code == 422


def test_get_position_by_id(client, seeded_positions):
    target = seeded_positions[0]
    response = client.get(f"/positions/{target.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["positionId"] == target.id
    assert body["combination"] == target.combination
    assert body["fen"] == target.fen


def test_get_position_not_found(client, seeded_positions):
    response = client.get("/positions/99999")
    assert response.status_code == 404
