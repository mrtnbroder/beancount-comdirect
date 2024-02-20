import datetime
from decimal import Decimal
from textwrap import dedent
from pprint import pprint

import pytest
from beancount.core.data import Amount, Balance

from beancount_comdirect import CheckingImporter
from beancount_comdirect.extractors.checking import Extractor, HEADER, ENCODING


def _format(string, kwargs):
    return dedent(string).format(**kwargs).lstrip()


@pytest.fixture
def tmp_file(tmp_path):
    return tmp_path / "checking.csv"


# TODO(2024-02-19): Add test for file_account
def test_extract_transactions(tmp_file):
    tmp_file.write_text(
        _format(
            """
            ;
            "Umsätze Girokonto";"Zeitraum: 01.04.2022 - 19.05.2022";
            "Neuer Kontostand";"11.222,33 EUR";

            {header}
            "10.04.2022";"10.04.2022";"Bar";" Buchungstext: BARGELDEINZAHLUNG KARTE 0 EINZAHLAUTOMAT 872672 EINZAHLUNG 10.04.2022 13:22 Berlin Straßen-Allee Ref. 92JKASDJ23e3/1";"123,45";
            "11.04.2022";"11.04.2022";"Übertrag / Überweisung";"Empfänger: Max MustermannKto/IBAN: DE123456789123 BLZ/BIC: BMNASMDMNAS  Ref. U277238HAS232/2";"-12.999,00";
            "12.04.2022";"12.04.2022";"Übertrag / Überweisung";"Auftraggeber: Max Mustermann Ref. U277238HAS232/1";"12.999,00";
            "12.04.2022";"12.04.2022";"Lastschrift / Belastung";"Auftraggeber: PayPal Europe S.a.r.l. et Cie S.C.A Buchungstext: 82927826268/PP.2722.PP/. , Ihr Ei nkauf bei Ref. UHS22832233/74494";"-23,72";
            """,  # NOQA
            dict(header=HEADER),
        ),
        encoding=ENCODING,
    )

    importer = CheckingImporter(account="Assets:Comdirect:Checking")

    with tmp_file.open() as fd:
        directives = importer.extract(fd)

    assert len(directives) == 5

    assert directives[0].date == datetime.date(2022, 4, 10)
    assert (
        directives[0].payee
        == "BARGELDEINZAHLUNG KARTE 0 EINZAHLAUTOMAT 872672 EINZAHLUNG 10.04.2022 13:22 Berlin Straßen-Allee"
    )

    assert len(directives[1].postings) == 1
    assert directives[1].date == datetime.date(2022, 4, 11)
    assert directives[1].payee == "Max Mustermann"
    assert directives[1].postings[0].account == "Assets:Comdirect:Checking"
    assert directives[1].postings[0].units.currency == "EUR"
    assert directives[1].postings[0].units.number == Decimal("-12999.00")

    assert len(directives[2].postings) == 1
    assert directives[2].date == datetime.date(2022, 4, 12)
    assert directives[2].payee == "Max Mustermann"
    assert directives[2].postings[0].units.number == Decimal("12999.00")

    assert len(directives[3].postings) == 1
    assert directives[3].date == datetime.date(2022, 4, 12)
    assert directives[3].payee == "PayPal Europe S.a.r.l. et Cie S.C.A"
    assert directives[3].narration == "82927826268/PP.2722.PP/. , Ihr Ei nkauf bei"
    assert directives[3].postings[0].units.number == Decimal("-23.72")
