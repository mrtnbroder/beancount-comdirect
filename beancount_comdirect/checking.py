import warnings
from collections import namedtuple
from datetime import datetime, timedelta
from functools import partial
from textwrap import dedent
from typing import Dict, Optional, Sequence

from beancount.core import data
from beancount.core.amount import Amount
from beancount.ingest import importer

from .exceptions import InvalidFormatError
from .extractors.checking import Extractor, HEADER, ENCODING
from .helpers import AccountMatcher, csv_dict_reader, csv_reader, fmt_number_de

Meta = namedtuple("Meta", ["value", "line_index"])

new_posting = partial(data.Posting, cost=None, price=None, flag=None, meta=None)


class CheckingImporter(importer.ImporterProtocol):
    def __init__(
        self,
        account: str,
        currency: str = "EUR",
        meta_code: Optional[str] = None,
        payee_patterns: Optional[Sequence] = None,
    ):
        self.account = account
        self.currency = currency
        self.meta_code = meta_code
        self.payee_matcher = AccountMatcher(payee_patterns)
        self._extractor = Extractor()
        self._date_from = None
        self._date_to = None
        self._balance_amount = None
        self._balance_date = None
        self._closing_balance_index = -1

    def name(self):
        return "Comdirect {}".format(self.__class__.__name__)

    def file_account(self):
        return self.account

    def file_date(self, file):
        self.extract(file)

        return self._date_to

    def extract(self, file):
        entries = []

        with open(file.name, encoding=ENCODING) as fd:
            lines = [line.strip() for line in fd.readlines()]

        line_index = 0
        header_index = lines.index(HEADER)

        metadata_lines = lines[0:header_index]
        transaction_lines = lines[header_index:]

        # Metadata

        metadata = {}
        reader = csv_reader(metadata_lines)

        for line in reader:
            line_index += 1

            if not line or line == [""]:
                continue

            key, value, *_ = line

            metadata[key] = Meta(value, line_index)

        self._update_meta(metadata)

        # Transactions

        reader = csv_dict_reader(transaction_lines)

        for line in reader:
            line_index += 1

            meta = data.new_metadata(file.name, line_index)

            amount = None
            if self._extractor.get_amount(line):
                amount = Amount(
                    fmt_number_de(self._extractor.get_amount(line)), self.currency
                )
            raw_date = line["Buchungstag"]

            if raw_date == "offen":
                # These are incomplete / not booked yet
                continue

            date = self._extractor.get_booking_date(line)

            # do not create transactions for dates outside the date range
            if self.meta_code:
                meta[self.meta_code] = self._extractor.get_description(line)

            description = self._extractor.get_purpose(line)
            payee = self._extractor.get_payee(line)

            postings = [
                new_posting(account=self.account, units=amount),
            ]

            payee_match = self.payee_matcher.account_matches(payee)

            if payee_match:
                postings.append(
                    new_posting(
                        account=self.payee_matcher.account_for(payee),
                        units=None,
                    )
                )

            entries.append(
                data.Transaction(
                    meta,
                    date,
                    self.FLAG,
                    payee,
                    description,
                    data.EMPTY_SET,
                    data.EMPTY_SET,
                    postings,
                )
            )

        # Closing Balance
        entries.append(
            data.Balance(
                data.new_metadata(file.name, self._closing_balance_index),
                self._balance_date,
                self.account,
                self._balance_amount,
                None,
                None,
            )
        )

        return entries

    def _update_meta(self, meta: Dict[str, str]):
        for key, value in meta.items():
            if key.startswith("Von"):
                self._date_from = datetime.strptime(value.value, "%d.%m.%Y").date()
            elif key.startswith("Bis"):
                self._date_to = datetime.strptime(value.value, "%d.%m.%Y").date()
            elif key.startswith("Kontostand vom"):
                # Beancount expects the balance amount to be from the
                # beginning of the day, while the Tagessaldo entries in
                # the DKB exports seem to be from the end of the day.
                # So when setting the balance date, we add a timedelta
                # of 1 day to the original value to make the balance
                # assertions work.

                self._balance_amount = Amount(
                    fmt_number_de(value.value.rstrip(" EUR")), self.currency
                )
                self._balance_date = datetime.strptime(
                    key.lstrip("Kontostand vom ").rstrip(":"), "%d.%m.%Y"
                ).date() + timedelta(days=1)
                self._closing_balance_index = value.line_index
