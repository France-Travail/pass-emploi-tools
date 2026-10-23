from comparer_logins import comparer

REFERENCE = [
    {"nom": "Toutes requêtes", "p95": "400", "p99": "600"},
    {"nom": "04 callback IDP (connect)", "p95": "300", "p99": "450"},
    {"nom": "07 accueil FT (api)", "p95": "120", "p99": "200"},
]
PENDANT = [
    {"nom": "Toutes requêtes", "p95": "700", "p99": "1200"},
    {"nom": "04 callback IDP (connect)", "p95": "650", "p99": "900"},
    {"nom": "06 token (connect)", "p95": "80", "p99": "95"},
]


def _ligne(markdown, etape):
    return next(l for l in markdown.splitlines() if l.startswith(f"| {etape} |"))


def test_ecart_pendant_moins_reference():
    markdown = comparer(REFERENCE, PENDANT)

    assert _ligne(markdown, "04 callback IDP (connect)") == "| 04 callback IDP (connect) | 300 | 650 | +350 | 450 | 900 | +450 |"


def test_etape_absente_pendant():
    markdown = comparer(REFERENCE, PENDANT)

    assert _ligne(markdown, "07 accueil FT (api)") == "| 07 accueil FT (api) | 120 | ? | ? | 200 | ? | ? |"


def test_etape_absente_de_la_reference():
    markdown = comparer(REFERENCE, PENDANT)

    assert _ligne(markdown, "06 token (connect)") == "| 06 token (connect) | ? | 80 | ? | ? | 95 | ? |"


def test_valeur_non_numerique():
    markdown = comparer([{"nom": "x", "p95": "-", "p99": "10"}], [{"nom": "x", "p95": "5", "p99": "8"}])

    assert _ligne(markdown, "x") == "| x | - | 5 | ? | 10 | 8 | -2 |"
