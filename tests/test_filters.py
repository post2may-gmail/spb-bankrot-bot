from bankrot_bot.filters import has_shared_ownership, is_apartment, is_rent, passes_lot_filters
from bankrot_bot.models import Lot
from bankrot_bot.photos import normalize_photo_urls
from bankrot_bot.sources.tbankrot import parse_listing_html


def test_share_words():
    assert has_shared_ownership("Продаётся доля в квартире")
    assert has_shared_ownership("общая долевая собственность")
    assert has_shared_ownership("1/2 долей в праве")
    assert not has_shared_ownership("Квартира целиком без обременений")


def test_rent_words():
    assert is_rent("Аренда части нежилого помещения")
    assert not is_rent("Продажа квартиры на торгах")


def test_apartment_only():
    assert is_apartment("Квартира 45 м2 в Красном Селе")
    assert is_apartment("Жилое помещение, площадь 30,8 м2")
    assert not is_apartment("Парковочное место 13.78 м²")
    assert not is_apartment("Нежилое помещение на Салова")
    assert not is_apartment("Картина маслом")


def test_passes_filters():
    ok = Lot(
        source="t",
        external_id="1",
        title="Квартира 50 м²",
        description="Продажа целиком",
        url="https://example.com/1",
        address="Санкт-Петербург, Невский пр.",
    )
    assert passes_lot_filters(ok)[0] is True

    living = Lot(
        source="t",
        external_id="1b",
        title="Жилое помещение 32 м²",
        description="Жилое помещение целиком",
        url="https://example.com/1b",
        address="Санкт-Петербург",
    )
    assert passes_lot_filters(living)[0] is True

    parking = Lot(
        source="t",
        external_id="2",
        title="Парковочное место",
        description="машино-место",
        url="https://example.com/2",
        address="Санкт-Петербург",
    )
    assert passes_lot_filters(parking) == (False, "not_apartment")

    share = Lot(
        source="t",
        external_id="3",
        title="Доля в квартире",
        description="долевой собственник",
        url="https://example.com/3",
    )
    assert passes_lot_filters(share) == (False, "share")


def test_normalize_photos():
    urls = normalize_photo_urls(
        [
            "https://cdn.example/a.jpg",
            "https://tbankrot.ru/img/blur/blur_1.jpg",
            "https://cdn.example/a.jpg",
            "https://cdn.example/akt_priemki.jpg",
            "https://cdn.example/b.png",
        ],
        limit=10,
    )
    assert urls == ["https://cdn.example/a.jpg", "https://cdn.example/b.png"]


def test_parse_tbankrot_snippet():
    html = """
    <div class="lot_title">
      <a href="/item?id=8232068" class="lot_num ">8232068</a>
      <span class="lot_number">Лот 1</span>
    </div>
    <div class="lot_description">
      Квартира 45.4 м², Санкт-Петербург
      Адрес:Санкт-Петербург, ул. Спирина
      5 580 000,00 ₽
    </div>
    """
    lots = parse_listing_html(html)
    assert len(lots) == 1
    assert lots[0].external_id == "8232068"
    assert lots[0].price == 5580000.0
    assert lots[0].area_sqm == 45.4
