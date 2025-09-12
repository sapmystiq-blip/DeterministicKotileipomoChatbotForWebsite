from backend import intent_router as IR


def test_hours_formatting():
    # Should produce a non-empty hours string
    txt = IR.resolve_hours(lang="en")
    assert isinstance(txt, str)
    assert len(txt) > 0
    assert any(k in txt.lower() for k in ["opening", "öppettider", "aukioloajat"]) or \
           any(d in txt for d in ["Thursday", "torstai", "torsdag"])  # header or day line


def test_intent_detection_hours():
    assert IR.detect_intent("What are your opening hours?") == "hours"


def test_menu_without_ecwid_adapter():
    prev = IR.ecwid.get_products
    IR.ecwid.get_products = None
    try:
        out = IR.resolve_menu(lang="en")
        assert "store" in out.lower() or "web" in out.lower()
    finally:
        IR.ecwid.get_products = prev


def test_allergen_disclaimer_generic():
    txt = IR.resolve_allergens("Do your pies contain nuts?", lang="en")
    assert isinstance(txt, str)
    assert len(txt) > 0

