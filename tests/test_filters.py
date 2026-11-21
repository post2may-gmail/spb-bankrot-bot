from bankrot_bot.filters import has_shared_ownership, is_rent, passes_lot_filters
from bankrot_bot.models import Lot
from bankrot_bot.sources.tbankrot import parse_listing_html


def test_share_words():
    assert has_shared_ownership("Продаётся доля в квартире")
    assert has_shared_ownership("общая долевая собственность")
    assert has_shared_ownership("1/2 долей в праве")
    assert has_shared_ownership("в тексте есть слово долей")
    assert not has_shared_ownership("Квартира целиком без обременений")
    assert not has_shared_ownership("Квартира 45 м2 в Красном Селе")


def test_rent_words():
    assert is_rent("Аренда части нежилого помещения")
    assert is_rent("право заключения договора аренды")
    assert not is_rent("Продажа квартиры на торгах")


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

    bad = Lot(
        source="t",
        external_id="2",
        title="Доля в квартире",
        description="долевой собственник",
        url="https://example.com/2",
    )
    assert passes_lot_filters(bad) == (False, "share")


def test_parse_tbankrot_snippet():
    html = """
    <div class="lot_title">
      <a href="/item?id=8232071" class="lot_num ">8232071</a>
      <span class="lot_number">Лот 2</span>
    </div>
    <div class="lot_description">
      Парковочное место 13.78 м², Санкт-Петербург
      Адрес:Санкт-Петербург, Кондратьевский проспект
      1 700 000,00 ₽
    </div>
    """
    lots = parse_listing_html(html)
    assert len(lots) == 1
    assert lots[0].external_id == "8232071"
    assert lots[0].price == 1700000.0
    assert lots[0].area_sqm == 13.78
