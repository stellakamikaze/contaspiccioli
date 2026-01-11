"""Seed data for Contaspiccioli v2.0 - Default pillars and categories."""
from decimal import Decimal
from typing import TypeVar

from sqlalchemy.orm import Session

from app.models_v2 import (
    Pillar, Category, CategoryType, TaxSettings, TaxRegime, AdvanceMethod, Account, AccountType
)

T = TypeVar("T")


def seed_if_not_exists(
    db: Session,
    model: type[T],
    data_list: list[dict],
    unique_field: str,
) -> list[T]:
    """Crea record solo se non esistono, usando unique_field per il check."""
    created = []
    for data in data_list:
        exists = db.query(model).filter(
            getattr(model, unique_field) == data[unique_field]
        ).first()
        if not exists:
            record = model(**data)
            db.add(record)
            created.append(record)
    db.commit()
    return created


def seed_pillars(db: Session) -> list[Pillar]:
    """I 4 pilastri da guida Coletti/Magri."""
    pillars_data = [
        {
            "number": 1,
            "name": "liquidita",
            "display_name": "Liquidità",
            "description": "Conto corrente principale per spese quotidiane. "
                          "Target: almeno 3 mesi di spese per gestire imprevisti a breve termine.",
            "target_months": 3,
            "instrument": "Conto corrente",
            "account_name": "BBVA",
            "priority": 1,
        },
        {
            "number": 2,
            "name": "emergenza",
            "display_name": "Fondo Emergenza",
            "description": "Fondo per emergenze serie (perdita lavoro, spese mediche impreviste). "
                          "Target: 3-12 mesi di spese su conto deposito svincolabile.",
            "target_months": 6,  # Default 6 mesi
            "instrument": "Conto deposito svincolabile",
            "account_name": "Fineco XEON",
            "priority": 2,
        },
        {
            "number": 3,
            "name": "spese_previste",
            "display_name": "Spese Previste",
            "description": "Accantonamento per tasse e spese programmate (auto, casa, dentista, viaggi). "
                          "Strumenti: BTP, obbligazioni o ETF monetari con scadenza allineata.",
            "target_months": None,  # Non basato su mesi, ma su importi specifici
            "instrument": "XEON ETF / BTP",
            "account_name": "Fineco XEON → Fideuram F24",
            "priority": 3,
        },
        {
            "number": 4,
            "name": "investimenti",
            "display_name": "Investimenti",
            "description": "Capitale per obiettivi a lungo termine (10+ anni). "
                          "ETF azionari globali diversificati. Solo soldi che non servono per i prossimi 10 anni.",
            "target_months": None,
            "instrument": "ETF azionari",
            "account_name": "Fineco",
            "priority": 4,
        },
    ]
    return seed_if_not_exists(db, Pillar, pillars_data, "number")


def seed_accounts(db: Session) -> list[Account]:
    """Conti bancari di Federico."""
    accounts_data = [
        {
            "name": "BBVA",
            "account_type": AccountType.CHECKING,
            "notes": "Conto corrente principale - P1 Liquidita",
        },
        {
            "name": "Fineco",
            "account_type": AccountType.BROKER,
            "notes": "Broker - P2 Emergenza (XEON), P3 Tasse (XEON), P4 Investimenti (ETF)",
        },
        {
            "name": "Fideuram",
            "account_type": AccountType.TAX_ONLY,
            "notes": "Solo per pagamento F24 - transito da Fineco",
        },
    ]
    return seed_if_not_exists(db, Account, accounts_data, "name")


def seed_categories(db: Session, pillar_p1_id: int | None = None) -> list[Category]:
    """Categorie di spesa/entrata con keywords per auto-categorizzazione."""
    categories_data = [
        # INCOME
        {
            "name": "Fatture",
            "type": CategoryType.INCOME,
            "icon": "💼",
            "color": "#10B981",  # Green
            "monthly_budget": Decimal("3500.00"),
            "keywords": ["BONIFICO", "FATTURA", "UFFICIO FURORE", "COMPENSO", "ACCREDITO"],
            "display_order": 1,
        },
        {
            "name": "Altri Ricavi",
            "type": CategoryType.INCOME,
            "icon": "💰",
            "color": "#34D399",
            "monthly_budget": Decimal("0.00"),
            "keywords": ["RIMBORSO", "STORNO", "ACCREDITO"],
            "display_order": 2,
        },

        # FIXED COSTS
        {
            "name": "Affitto",
            "type": CategoryType.FIXED,
            "icon": "🏠",
            "color": "#6366F1",  # Indigo
            "monthly_budget": Decimal("700.00"),
            "keywords": ["AFFITTO", "CANONE LOCAZIONE", "PIGIONE"],
            "display_order": 10,
        },
        {
            "name": "Utenze",
            "type": CategoryType.FIXED,
            "icon": "💡",
            "color": "#8B5CF6",  # Purple
            "monthly_budget": Decimal("150.00"),
            "keywords": ["ENEL", "ENI", "A2A", "HERA", "SORGENIA", "EDISON", "IREN", "GAS", "LUCE", "ENERGIA"],
            "display_order": 11,
        },
        {
            "name": "Abbonamenti",
            "type": CategoryType.FIXED,
            "icon": "📱",
            "color": "#A78BFA",
            "monthly_budget": Decimal("100.00"),
            "keywords": ["NETFLIX", "SPOTIFY", "AMAZON PRIME", "DISNEY", "DAZN", "TIM", "VODAFONE", "WIND",
                        "ILIAD", "FASTWEB", "PALESTRA", "GYM", "FITNESS"],
            "display_order": 12,
        },
        {
            "name": "Assicurazioni",
            "type": CategoryType.FIXED,
            "icon": "🛡️",
            "color": "#C4B5FD",
            "monthly_budget": Decimal("50.00"),
            "keywords": ["ASSICURAZIONE", "POLIZZA", "GENERALI", "UNIPOL", "ALLIANZ", "AXA", "ZURICH"],
            "display_order": 13,
        },
        {
            "name": "Commercialista",
            "type": CategoryType.FIXED,
            "icon": "📊",
            "color": "#DDD6FE",
            "monthly_budget": Decimal("100.00"),
            "keywords": ["COMMERCIALISTA", "CONSULENZA FISCALE", "STUDIO ASSOCIATO"],
            "display_order": 14,
        },

        # VARIABLE COSTS
        {
            "name": "Alimentari",
            "type": CategoryType.VARIABLE,
            "icon": "🛒",
            "color": "#F59E0B",  # Amber
            "monthly_budget": Decimal("350.00"),
            "keywords": ["ESSELUNGA", "CARREFOUR", "COOP", "CONAD", "LIDL", "EUROSPIN", "PAM", "PENNY",
                        "ALDI", "DESPAR", "TIGROS", "IPERAL", "SIMPLY", "BENNET", "FAMILA", "IPER",
                        "SUPERMERCATO", "MARKET", "SPESA"],
            "display_order": 20,
        },
        {
            "name": "Ristoranti",
            "type": CategoryType.VARIABLE,
            "icon": "🍕",
            "color": "#FBBF24",
            "monthly_budget": Decimal("200.00"),
            "keywords": ["RISTORANTE", "PIZZERIA", "TRATTORIA", "BAR", "CAFFE", "PASTICCERIA",
                        "DELIVEROO", "GLOVO", "JUST EAT", "UBER EATS", "FOODORA", "MCDONALD",
                        "BURGER KING", "KFC", "SUBWAY", "SUSHI", "OSTERIA"],
            "display_order": 21,
        },
        {
            "name": "Trasporti",
            "type": CategoryType.VARIABLE,
            "icon": "🚗",
            "color": "#FCD34D",
            "monthly_budget": Decimal("50.00"),
            "keywords": ["UBER", "FREE NOW", "BOLT", "TAXI", "TRENITALIA", "ITALO", "ATM", "METRO",
                        "BUS", "TRAM", "AUTOSTRADA", "TELEPASS", "ENI STATION", "Q8", "IP",
                        "TAMOIL", "ESSO", "SHELL", "TOTAL", "BENZINA", "CARBURANTE"],
            "display_order": 22,
        },
        {
            "name": "Shopping",
            "type": CategoryType.VARIABLE,
            "icon": "🛍️",
            "color": "#FDE68A",
            "monthly_budget": Decimal("150.00"),
            "keywords": ["AMAZON", "ZALANDO", "ZARA", "H&M", "UNIQLO", "DECATHLON", "IKEA",
                        "MEDIAWORLD", "UNIEURO", "EURONICS", "EXPERT", "APPLE STORE", "FELTRINELLI",
                        "MONDADORI", "COIN", "RINASCENTE", "OVS", "PRIMARK"],
            "display_order": 23,
        },
        {
            "name": "Salute",
            "type": CategoryType.VARIABLE,
            "icon": "💊",
            "color": "#EF4444",  # Red
            "monthly_budget": Decimal("50.00"),
            "keywords": ["FARMACIA", "PARAFARMACIA", "MEDICO", "DOTTORE", "SPECIALISTA",
                        "DENTISTA", "OCULISTA", "FISIOTERAPIA", "OSPEDALE", "CLINICA",
                        "LABORATORIO", "ANALISI", "VISITA"],
            "display_order": 24,
        },
        {
            "name": "Svago",
            "type": CategoryType.VARIABLE,
            "icon": "🎬",
            "color": "#F87171",
            "monthly_budget": Decimal("100.00"),
            "keywords": ["CINEMA", "TEATRO", "MUSEO", "MOSTRA", "CONCERTO", "EVENTO",
                        "BIGLIETTO", "TICKET", "STEAM", "PLAYSTATION", "XBOX", "NINTENDO"],
            "display_order": 25,
        },
        {
            "name": "Viaggi",
            "type": CategoryType.VARIABLE,
            "icon": "✈️",
            "color": "#3B82F6",  # Blue
            "monthly_budget": Decimal("100.00"),
            "keywords": ["RYANAIR", "EASYJET", "ALITALIA", "ITA AIRWAYS", "LUFTHANSA",
                        "BOOKING", "AIRBNB", "HOTEL", "OSTELLO", "B&B", "EXPEDIA",
                        "SKYSCANNER", "TRAINLINE", "FLIXBUS"],
            "display_order": 26,
        },
        {
            "name": "Altro",
            "type": CategoryType.VARIABLE,
            "icon": "📦",
            "color": "#6B7280",
            "monthly_budget": Decimal("100.00"),
            "keywords": [],
            "display_order": 99,
        },
    ]

    # Associa categorie spese a P1 (liquidita) di default
    if pillar_p1_id:
        for data in categories_data:
            if data["type"] != CategoryType.INCOME:
                data["pillar_id"] = pillar_p1_id

    return seed_if_not_exists(db, Category, categories_data, "name")


def seed_tax_settings(db: Session, year: int = 2026) -> TaxSettings:
    """Impostazioni fiscali P.IVA forfettaria (ATECO 70.20.09)."""
    existing = db.query(TaxSettings).filter(TaxSettings.year == year).first()
    if existing:
        return existing

    settings = TaxSettings(
        year=year,
        regime=TaxRegime.FORFETTARIO,
        coefficient=Decimal("0.78"),
        inps_rate=Decimal("0.2607"),
        tax_rate=Decimal("0.15"),
        advance_method=AdvanceMethod.STORICO,
        min_threshold=Decimal("52.00"),
        single_payment_threshold=Decimal("258.00"),
    )
    db.add(settings)
    db.commit()
    return settings


def seed_all(db: Session) -> dict:
    """Esegue tutte le funzioni di seed."""
    print("Seeding accounts...")
    accounts = seed_accounts(db)
    print(f"  Created {len(accounts)} accounts")

    print("Seeding pillars...")
    pillars = seed_pillars(db)
    print(f"  Created {len(pillars)} pillars")

    p1 = db.query(Pillar).filter(Pillar.number == 1).first()
    p1_id = p1.id if p1 else None

    print("Seeding categories...")
    categories = seed_categories(db, pillar_p1_id=p1_id)
    print(f"  Created {len(categories)} categories")

    print("Seeding tax settings...")
    tax_settings = seed_tax_settings(db)
    print(f"  Created tax settings for {tax_settings.year}")

    print("\nSeed complete!")
    return {
        "accounts": accounts,
        "pillars": pillars,
        "categories": categories,
        "tax_settings": tax_settings,
    }


if __name__ == "__main__":
    from app.database import SessionLocal, init_db

    # Initialize database tables
    init_db()

    # Run seed
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
