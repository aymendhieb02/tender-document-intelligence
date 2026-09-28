from decimal import Decimal

from app.cdc_analysis.financial_deadline import normalize_financial_deadlines


def facts(text, category):
    return [fact for fact in normalize_financial_deadlines(text) if fact.category == category]


def test_decimal_percent_and_french_written_digit_pair():
    assert facts("La retenue est de 10,50 %.", "retention")[0].normalized["value"] == Decimal("10.50")
    pair = facts("Une pénalité de deux pour cent (2%) sera appliquée.", "percentage")
    assert pair and any(f.normalized["value"] == Decimal("2") for f in pair)


def test_per_mille_penalty_keeps_day_basis():
    rate = facts("Pénalité: deux pour mille (2‰) par jour de retard.", "penalty_rate")[0]
    assert rate.normalized == {"value": Decimal("2"), "unit": "PER_MILLE", "period": "DAY", "basis": None}
    assert rate.raw == "2‰"


def test_formula_penalty_rate_and_cap_are_separate_facts():
    text = "Pénalité de retard = montant annuel x nombre de jours x 0,001; elle ne peut dépasser 5% du montant du contrat."
    fs = normalize_financial_deadlines(text)
    rate = next(f for f in fs if f.category == "penalty_rate")
    cap = next(f for f in fs if f.category == "penalty_cap")
    assert rate.normalized["value"] == Decimal("0.001")
    assert cap.normalized["value"] == Decimal("5")


def test_dt_tnd_and_provisional_guarantee_use_decimal():
    amount = facts("Le cautionnement provisoire est de 4 500 DT.", "provisional_guarantee")[0]
    assert amount.normalized["amount"] == Decimal("4500")
    assert amount.normalized["currency"] == "TND"
    arabic = facts("الضمان المؤقت: 4500 دينار تونسي.", "provisional_guarantee")[0]
    assert arabic.normalized["amount"] == Decimal("4500")


def test_durations_validity_execution_and_warranty():
    fs = normalize_financial_deadlines("Validité de l'offre: cent vingt jours. Délai d'exécution de 3 mois. Garantie de 2 ans.")
    assert next(f for f in fs if f.category == "offer_validity").normalized == {"value": Decimal("120"), "unit": "DAY"}
    assert next(f for f in fs if f.category == "execution_period").normalized == {"value": Decimal("3"), "unit": "MONTH"}
    assert next(f for f in fs if f.category == "warranty_period").normalized == {"value": Decimal("2"), "unit": "YEAR"}


def test_common_duration_words():
    validity = facts("La validité des offres est de cent (100) jours.", "offer_validity")
    assert validity[0].normalized == {"value": Decimal("100"), "unit": "DAY"}


def test_french_and_arabic_deadline_dates_and_time():
    fr = facts("Date limite de réception des offres: 17 novembre 2025 à 11h00.", "submission_deadline")[0]
    assert fr.normalized == {"date": "2025-11-17", "time": "11:00"}
    ar = facts("آخر أجل لقبول العروض يوم الخميس 12 مارس 2026 على الساعة 12:00", "submission_deadline")[0]
    assert ar.normalized == {"date": "2026-03-12", "time": "12:00"}


def test_ambiguous_numeric_date_is_not_guessed():
    date_fact = facts("Date limite: 03/04/2026", "date")[0]
    assert date_fact.normalized is None
    assert date_fact.status == "ambiguous"


def test_clarification_and_site_visit_dates_keep_distinct_types():
    fs = normalize_financial_deadlines("Date limite de visite des lieux: 12 octobre 2026. Date limite des demandes d'éclaircissement: 14 octobre 2026.")
    assert any(f.category == "site_visit_deadline" and f.normalized["date"] == "2026-10-12" for f in fs)
    assert any(f.category == "clarification_deadline" and f.normalized["date"] == "2026-10-14" for f in fs)


def test_explicit_vat_percentage_is_classified():
    vat = facts("Le taux de TVA applicable est 19%.", "vat_rate")[0]
    assert vat.normalized["value"] == Decimal("19")


def test_payment_split_and_quarterly_schedule_remain_separate():
    fs = normalize_financial_deadlines("Modalités de paiement: 90% à l'achèvement et 10% en retenue de garantie, payé trimestriellement à terme échu.")
    assert next(f for f in fs if f.category == "payment_component").normalized["value"] == Decimal("90")
    assert next(f for f in fs if f.category == "retention").normalized["value"] == Decimal("10")
    schedule = next(f for f in fs if f.category == "payment_schedule")
    assert schedule.normalized == {"frequency": "QUARTERLY", "timing": "IN_ARREARS"}


def test_missing_values_return_no_invented_facts():
    assert normalize_financial_deadlines("Les modalités seront précisées ultérieurement.") == []


def test_conflicting_submission_dates_are_both_preserved_and_flagged():
    fs = facts("Date limite: 17 novembre 2025. La date limite de réception est le 18 novembre 2025.", "submission_deadline")
    assert len(fs) == 2
    assert all(f.status == "conflict" for f in fs)
    assert len({f.conflict_group for f in fs}) == 1


def test_money_without_float_and_source_is_retained():
    fact = facts("Prix: 1 234,56 TND TTC.", "money")[0]
    assert fact.normalized["amount"] == Decimal("1234.56")
    assert fact.normalized["tax_basis"] == "TTC"
    assert fact.raw == "1 234,56 TND"
