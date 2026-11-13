from datetime import date, datetime
import io
import unittest
from unittest.mock import patch

from main import (
    AddressBook,
    Birthday,
    Phone,
    Record,
    add_birthday,
    add_contact,
    birthdays,
    change_contact,
    main,
    parse_input,
    show_all,
    show_birthday,
    show_phone,
)


class TestBirthdayAndAddressBook(unittest.TestCase):
    def test_birthday_valid_and_str(self):
        bday = Birthday("15.05.1990")
        self.assertIsInstance(bday.value, datetime)
        self.assertEqual(bday.value, datetime(1990, 5, 15))
        self.assertEqual(str(bday), "15.05.1990")

    def test_birthday_invalid_raises(self):
        for invalid in ("1990-05-15", "32.01.2000", "15/05/1990", "invalid", "", 123):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError) as ctx:
                    Birthday(invalid)
                self.assertEqual(str(ctx.exception), "Invalid date format. Use DD.MM.YYYY")

    def test_record_add_birthday(self):
        record = Record("John")
        self.assertIsNone(record.birthday)
        record.add_birthday("10.11.1995")
        self.assertIsInstance(record.birthday, Birthday)
        self.assertEqual(str(record.birthday), "10.11.1995")

        # Only one birthday allowed; calling again updates it
        record.add_birthday("11.11.1995")
        self.assertEqual(str(record.birthday), "11.11.1995")

    def test_upcoming_birthdays_with_weekend_shift_and_leap_year(self):
        book = AddressBook()

        # Monday 2026-03-02 -> window 2026-03-02 .. 2026-03-09
        r_weekday = Record("Alice")
        r_weekday.add_birthday("04.03.1992")  # Wednesday 2026-03-04

        r_saturday = Record("Bob")
        r_saturday.add_birthday("07.03.1990")  # Saturday -> shifted to Monday 09.03.2026

        r_sunday = Record("Carol")
        r_sunday.add_birthday("08.03.1991")  # Sunday -> shifted to Monday 09.03.2026

        r_outside = Record("Dave")
        r_outside.add_birthday("15.03.1990")  # Outside 7-day window

        r_no_bday = Record("Eve")

        for rec in (r_weekday, r_saturday, r_sunday, r_outside, r_no_bday):
            book.add_record(rec)

        result = book.get_upcoming_birthdays(today=date(2026, 3, 2))
        self.assertEqual(
            result,
            [
                {"name": "Alice", "congratulation_date": "04.03.2026"},
                {"name": "Bob", "congratulation_date": "09.03.2026"},
                {"name": "Carol", "congratulation_date": "09.03.2026"},
            ],
        )

        # Leap-year birthday in non-leap year
        leap_book = AddressBook()
        r_leap = Record("Leap")
        r_leap.add_birthday("29.02.1992")
        leap_book.add_record(r_leap)
        leap_result = leap_book.get_upcoming_birthdays(today=date(2026, 2, 27))
        self.assertEqual(
            leap_result,
            [{"name": "Leap", "congratulation_date": "02.03.2026"}],  # 2026-03-01 is Sunday -> Monday
        )


class TestBotHandlers(unittest.TestCase):
    def setUp(self):
        self.book = AddressBook()

    def test_parse_input(self):
        self.assertEqual(parse_input("  ADD John 1234567890 "), ("add", "John", "1234567890"))
        self.assertEqual(parse_input("   "), ("",))

    def test_add_and_update_contact(self):
        self.assertEqual(add_contact(["John", "1234567890"], self.book), "Contact added.")
        self.assertEqual(add_contact(["John", "0987654321"], self.book), "Contact updated.")
        self.assertEqual(show_phone(["John"], self.book), "1234567890; 0987654321")

        # Invalid phone should not create partial record
        self.assertEqual(
            add_contact(["BadUser", "123"], self.book),
            "Phone number must contain exactly 10 digits.",
        )
        self.assertIsNone(self.book.find("BadUser"))
        self.assertEqual(add_contact(["OnlyName"], self.book), "Give me name and phone please.")

    def test_change_and_phone_commands(self):
        add_contact(["John", "1234567890"], self.book)
        self.assertEqual(
            change_contact(["John", "1234567890", "1112223333"], self.book),
            "Contact updated.",
        )
        self.assertEqual(show_phone(["John"], self.book), "1112223333")
        self.assertEqual(
            change_contact(["Missing", "1112223333", "0000000000"], self.book),
            "Contact not found.",
        )
        self.assertEqual(
            change_contact(["John", "9999999999", "0000000000"], self.book),
            "Phone number '9999999999' not found.",
        )
        self.assertEqual(show_phone([], self.book), "Enter user name.")
        self.assertEqual(show_phone(["Missing"], self.book), "Contact not found.")

    def test_birthday_commands_and_show_all(self):
        self.assertEqual(show_all(self.book), "Address book is empty.")
        add_contact(["John", "1234567890"], self.book)
        self.assertEqual(
            show_birthday(["John"], self.book),
            "Birthday for John is not set.",
        )
        self.assertEqual(
            add_birthday(["John", "2000-01-01"], self.book),
            "Invalid date format. Use DD.MM.YYYY",
        )
        self.assertEqual(
            add_birthday(["John", "15.05.1990"], self.book),
            "Birthday added.",
        )
        self.assertEqual(show_birthday(["John"], self.book), "15.05.1990")
        self.assertEqual(
            show_all(self.book),
            "Contact name: John, phones: 1234567890, birthday: 15.05.1990",
        )
        self.assertEqual(
            add_birthday(["Missing", "15.05.1990"], self.book),
            "Contact not found.",
        )
        self.assertEqual(show_birthday(["Missing"], self.book), "Contact not found.")

    def test_birthdays_command(self):
        self.assertEqual(birthdays([], self.book), "No upcoming birthdays in the next 7 days.")
        today_str = datetime.today().strftime("%d.%m.%Y")
        add_contact(["John", "1234567890"], self.book)
        add_birthday(["John", today_str], self.book)
        output = birthdays([], self.book)
        self.assertIn("John:", output)

    def test_main_cli_loop(self):
        commands = [
            "hello",
            "add John 1234567890",
            "add-birthday John 15.05.1990",
            "show-birthday John",
            "phone John",
            "change John 1234567890 0987654321",
            "all",
            "birthdays",
            "unknown",
            "exit",
        ]
        with patch("builtins.input", side_effect=commands), patch(
            "sys.stdout", new_callable=io.StringIO
        ) as fake_out:
            main()
        out = fake_out.getvalue()
        self.assertIn("Welcome to the assistant bot!", out)
        self.assertIn("How can I help you?", out)
        self.assertIn("Contact added.", out)
        self.assertIn("Birthday added.", out)
        self.assertIn("15.05.1990", out)
        self.assertIn("Contact updated.", out)
        self.assertIn("Contact name: John, phones: 0987654321, birthday: 15.05.1990", out)
        self.assertIn("Invalid command.", out)
        self.assertIn("Good bye!", out)


if __name__ == "__main__":
    unittest.main()
