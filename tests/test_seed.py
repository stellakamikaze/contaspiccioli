"""Tests for seed functions."""
import pytest
from decimal import Decimal

from app.seed import seed_pillars, seed_accounts, seed_categories, seed_tax_settings, seed_all
from app.models import Pillar, Account, Category, TaxSettings, CategoryType, TaxRegime, AccountType


class TestSeedPillars:
    """Test pillar seeding."""

    def test_seed_creates_4_pillars(self, db_session):
        pillars = seed_pillars(db_session)

        all_pillars = db_session.query(Pillar).all()
        assert len(all_pillars) == 4

    def test_pillar_1_liquidita(self, db_session):
        seed_pillars(db_session)

        p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
        assert p1.name == "liquidita"
        assert p1.display_name == "Liquidità"
        assert p1.target_months == 3
        assert p1.priority == 1

    def test_pillar_3_spese_previste(self, db_session):
        seed_pillars(db_session)

        p3 = db_session.query(Pillar).filter(Pillar.number == 3).first()
        assert p3.name == "spese_previste"
        assert p3.target_months is None  # Based on specific amounts, not months

    def test_seed_idempotent(self, db_session):
        """Running seed twice should not duplicate pillars."""
        seed_pillars(db_session)
        seed_pillars(db_session)

        all_pillars = db_session.query(Pillar).all()
        assert len(all_pillars) == 4


class TestSeedAccounts:
    """Test account seeding."""

    def test_seed_creates_3_accounts(self, db_session):
        seed_accounts(db_session)

        all_accounts = db_session.query(Account).all()
        assert len(all_accounts) == 3

    def test_account_types_correct(self, db_session):
        seed_accounts(db_session)

        bbva = db_session.query(Account).filter(Account.name == "BBVA").first()
        assert bbva.account_type == AccountType.CHECKING

        fineco = db_session.query(Account).filter(Account.name == "Fineco").first()
        assert fineco.account_type == AccountType.BROKER

        fideuram = db_session.query(Account).filter(Account.name == "Fideuram").first()
        assert fideuram.account_type == AccountType.TAX_ONLY


class TestSeedCategories:
    """Test category seeding."""

    def test_seed_creates_categories(self, db_session):
        seed_categories(db_session)

        all_categories = db_session.query(Category).all()
        assert len(all_categories) >= 15  # At least 15 default categories

    def test_income_categories_exist(self, db_session):
        seed_categories(db_session)

        income_cats = db_session.query(Category).filter(Category.type == CategoryType.INCOME).all()
        assert len(income_cats) >= 2

    def test_fixed_categories_exist(self, db_session):
        seed_categories(db_session)

        fixed_cats = db_session.query(Category).filter(Category.type == CategoryType.FIXED).all()
        assert len(fixed_cats) >= 4

    def test_variable_categories_exist(self, db_session):
        seed_categories(db_session)

        variable_cats = db_session.query(Category).filter(Category.type == CategoryType.VARIABLE).all()
        assert len(variable_cats) >= 8

    def test_alimentari_has_keywords(self, db_session):
        seed_categories(db_session)

        alimentari = db_session.query(Category).filter(Category.name == "Alimentari").first()
        assert alimentari is not None
        assert "ESSELUNGA" in alimentari.keywords
        assert "CARREFOUR" in alimentari.keywords

    def test_categories_have_pillar_association(self, db_session):
        # First seed pillars
        seed_pillars(db_session)
        p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()

        # Then seed categories with pillar association
        seed_categories(db_session, pillar_p1_id=p1.id)

        # Check a fixed cost category
        affitto = db_session.query(Category).filter(Category.name == "Affitto").first()
        assert affitto.pillar_id == p1.id


class TestSeedTaxSettings:
    """Test tax settings seeding."""

    def test_seed_creates_tax_settings(self, db_session):
        settings = seed_tax_settings(db_session, year=2026)

        assert settings.year == 2026
        assert settings.regime == TaxRegime.FORFETTARIO
        assert settings.coefficient == Decimal("0.78")
        assert settings.inps_rate == Decimal("0.2607")
        assert settings.tax_rate == Decimal("0.15")

    def test_thresholds_correct(self, db_session):
        settings = seed_tax_settings(db_session, year=2026)

        assert settings.min_threshold == Decimal("52.00")
        assert settings.single_payment_threshold == Decimal("258.00")

    def test_seed_idempotent(self, db_session):
        """Running seed twice should not duplicate settings."""
        seed_tax_settings(db_session, year=2026)
        seed_tax_settings(db_session, year=2026)

        all_settings = db_session.query(TaxSettings).all()
        assert len(all_settings) == 1


class TestSeedAll:
    """Test complete seeding."""

    def test_seed_all_creates_everything(self, db_session):
        result = seed_all(db_session)

        assert len(db_session.query(Account).all()) == 3
        assert len(db_session.query(Pillar).all()) == 4
        assert len(db_session.query(Category).all()) >= 15
        assert db_session.query(TaxSettings).first() is not None

    def test_seed_all_idempotent(self, db_session):
        """Running seed_all twice should not duplicate data."""
        seed_all(db_session)
        seed_all(db_session)

        assert len(db_session.query(Pillar).all()) == 4
        assert len(db_session.query(TaxSettings).all()) == 1
