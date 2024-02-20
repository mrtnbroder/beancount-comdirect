import re

from collections import namedtuple
from datetime import date, datetime
from typing import Dict, Optional


ENCODING = "ISO-8859-1"

TYPE_CHECKING = "Assets:Comdirect:Checking"

CHECKING = {
    "type": TYPE_CHECKING,
    "label": "Girokonto",
    "fields": [
        "Buchungstag",
        "Wertstellung (Valuta)",
        "Vorgang",
        "Buchungstext",
        "Umsatz in EUR",
        # "",
    ],
}

HEADER = ";".join(f'"{field}"' for field in CHECKING["fields"]) + ";"

MAPPINGS = {
    "DAY": "Buchungstag",
    "VALUE": "Umsatz in EUR",
    "DESCRIPTION": "Buchungstext",
    "EVENT": "Vorgang",
}


class Extractor:
    "Extractor for Comdirect online banking interface"

    def get_booking_date(self, line: Dict[str, str]) -> date:
        return datetime.strptime(line[MAPPINGS["DAY"]], "%d.%m.%Y").date()

    def get_event(self, line: Dict[str, str]) -> str:
        return line[MAPPINGS["EVENT"]]

    def get_amount(self, line: Dict[str, str]) -> str:
        return line[MAPPINGS["VALUE"]]

    def get_description(self, line: Dict[str, str]) -> str:
        return line[MAPPINGS["DESCRIPTION"]].strip()

    def get_payee(self, line: Dict[str, str]) -> str:
        "Extract the payee from the description field."

        raw_desc = self.get_description(line)
        raw_event = self.get_event(line)

        if raw_desc.startswith("Auftraggeber"):
            if raw_event.startswith("Übertrag"):
                return extract_between(raw_desc, "Auftraggeber:", "Ref.")
            else:
                return extract_between(raw_desc, "Auftraggeber:", "Buchungstext:")
        elif raw_desc.startswith("Empfänger"):
            return extract_between(raw_desc, "Empfänger:", "Kto/IBAN")
        else:
            return extract_between(raw_desc, "Buchungstext:", "Ref.")

    def get_purpose(self, line: Dict[str, str]) -> str:
        "Extract the purpose from the description field."

        raw_desc = line[MAPPINGS["DESCRIPTION"]]

        return extract_between(raw_desc, "Buchungstext:", "Ref.")


def extract_between(text=str, start=str, end=str) -> Optional[str]:
    pattern = re.escape(start) + "(.*?)" + re.escape(end)
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    else:
        return None
