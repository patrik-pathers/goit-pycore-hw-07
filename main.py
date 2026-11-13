from collections import UserDict
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Callable


class Field:
    """Base class for record fields."""

    def __init__(self, value):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value!r})"


class Name(Field):
    """Contact name field (required, non-empty string)."""

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, new_value: str) -> None:
        if not isinstance(new_value, str) or not new_value.strip():
            raise ValueError("Name must be a non-empty string.")
        self._value = new_value.strip()


class Phone(Field):
    """Contact phone number field with 10-digit validation."""

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, new_value: str) -> None:
        if not isinstance(new_value, str) or not (
            len(new_value) == 10 and new_value.isascii() and new_value.isdigit()
        ):
            raise ValueError("Phone number must contain exactly 10 digits.")
        self._value = new_value


class Birthday(Field):
    """Contact birthday field validated in DD.MM.YYYY format."""

    @property
    def value(self) -> datetime:
        return self._value

    @value.setter
    def value(self, new_value: str | datetime) -> None:
        if isinstance(new_value, datetime):
            self._value = new_value
            return
        if not isinstance(new_value, str):
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        try:
            self._value = datetime.strptime(new_value.strip(), "%d.%m.%Y")
        except ValueError as err:
            raise ValueError("Invalid date format. Use DD.MM.YYYY") from err

    def __str__(self) -> str:
        return self.value.strftime("%d.%m.%Y")


class Record:
    """Stores contact information including name, phone numbers, and optional birthday."""

    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.birthday: Birthday | None = None

    def add_phone(self, phone: str) -> None:
        """Add a validated phone number to the contact record."""
        validated_phone = Phone(phone)
        if self.find_phone(validated_phone.value) is None:
            self.phones.append(validated_phone)

    def remove_phone(self, phone: str) -> None:
        """Remove a phone number from the contact record."""
        target = self.find_phone(phone)
        if target is None:
            raise ValueError(f"Phone number '{phone}' not found.")
        self.phones.remove(target)

    def edit_phone(self, old_phone: str, new_phone: str) -> None:
        """Replace an existing phone number with a new validated phone number."""
        for index, phone in enumerate(self.phones):
            if phone.value == old_phone:
                self.phones[index] = Phone(new_phone)
                return
        raise ValueError(f"Phone number '{old_phone}' not found.")

    def find_phone(self, phone: str) -> Phone | None:
        """Find and return a Phone object by its value, or None if not found."""
        for p in self.phones:
            if p.value == phone:
                return p
        return None

    def add_birthday(self, birthday: str) -> None:
        """Set or update the contact's birthday."""
        self.birthday = Birthday(birthday)

    def __str__(self) -> str:
        phones_str = "; ".join(p.value for p in self.phones) if self.phones else "none"
        result = f"Contact name: {self.name.value}, phones: {phones_str}"
        if self.birthday is not None:
            result += f", birthday: {self.birthday}"
        return result


class AddressBook(UserDict):
    """Manages contact records keyed by contact name."""

    def add_record(self, record: Record) -> None:
        """Add a Record instance to the address book."""
        if not isinstance(record, Record):
            raise TypeError("Only Record instances can be added to AddressBook.")
        self.data[record.name.value] = record

    def find(self, name: str) -> Record | None:
        """Find and return a Record by contact name, or None if not found."""
        return self.data.get(name)

    def delete(self, name: str) -> None:
        """Delete a Record from the address book by contact name."""
        self.data.pop(name, None)

    @staticmethod
    def _get_birthday_for_year(birthday: date, year: int) -> date:
        """Return birthday date in the given year, handling Feb 29 on non-leap years."""
        try:
            return birthday.replace(year=year)
        except ValueError:
            return date(year, 3, 1)

    def get_upcoming_birthdays(self, today: date | None = None) -> list[dict[str, str]]:
        """
        Return a list of contacts to congratulate within the next 7 days (inclusive of today).
        Weekend birthdays are shifted to the following Monday.
        """
        current_date = today or datetime.today().date()
        upcoming: list[dict[str, str]] = []

        for record in self.data.values():
            if record.birthday is None:
                continue

            birthday_date = record.birthday.value.date()
            birthday_this_year = self._get_birthday_for_year(birthday_date, current_date.year)

            if birthday_this_year < current_date:
                birthday_this_year = self._get_birthday_for_year(
                    birthday_date, current_date.year + 1
                )

            days_until = (birthday_this_year - current_date).days
            if 0 <= days_until <= 7:
                congratulation_date = birthday_this_year
                weekday = congratulation_date.weekday()
                if weekday == 5:  # Saturday
                    congratulation_date += timedelta(days=2)
                elif weekday == 6:  # Sunday
                    congratulation_date += timedelta(days=1)

                upcoming.append(
                    {
                        "name": record.name.value,
                        "congratulation_date": congratulation_date.strftime("%d.%m.%Y"),
                    }
                )

        return upcoming


def input_error(func: Callable) -> Callable:
    """Decorator for handling user input and lookup errors cleanly."""

    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as e:
            return e.args[0] if e.args else "Contact not found."
        except IndexError as e:
            return e.args[0] if e.args else "Enter the argument for the command."
        except ValueError as e:
            return str(e) if str(e) else "Invalid input."

    return inner


def parse_input(user_input: str) -> tuple[str, ...]:
    """Parse user input into a lowercase command and argument list."""
    parts = user_input.strip().split()
    if not parts:
        return ("",)
    cmd, *args = parts
    return cmd.lower(), *args


@input_error
def add_contact(args: list[str], book: AddressBook) -> str:
    """Add a new contact or add a phone number to an existing contact."""
    if len(args) < 2:
        raise ValueError("Give me name and phone please.")
    name, phone, *_ = args
    record = book.find(name)
    message = "Contact updated."
    if record is None:
        record = Record(name)
        record.add_phone(phone)
        book.add_record(record)
        message = "Contact added."
    else:
        record.add_phone(phone)
    return message


@input_error
def change_contact(args: list[str], book: AddressBook) -> str:
    """Change an existing phone number for the specified contact."""
    if len(args) < 3:
        raise ValueError("Give me name, old phone, and new phone please.")
    name, old_phone, new_phone, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")
    record.edit_phone(old_phone, new_phone)
    return "Contact updated."


@input_error
def show_phone(args: list[str], book: AddressBook) -> str:
    """Show all phone numbers for the specified contact."""
    if not args:
        raise IndexError("Enter user name.")
    name = args[0]
    record = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")
    if not record.phones:
        return f"No phone numbers saved for {record.name.value}."
    return "; ".join(p.value for p in record.phones)


@input_error
def show_all(book: AddressBook) -> str:
    """Return a formatted string of all contacts in the address book."""
    if not book.data:
        return "Address book is empty."
    return "\n".join(str(record) for record in book.data.values())


@input_error
def add_birthday(args: list[str], book: AddressBook) -> str:
    """Add a birthday in DD.MM.YYYY format to an existing contact."""
    if len(args) < 2:
        raise ValueError("Give me name and birthday (DD.MM.YYYY) please.")
    name, birthday, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")
    record.add_birthday(birthday)
    return "Birthday added."


@input_error
def show_birthday(args: list[str], book: AddressBook) -> str:
    """Show the birthday of the specified contact."""
    if not args:
        raise IndexError("Enter user name.")
    name = args[0]
    record = book.find(name)
    if record is None:
        raise KeyError("Contact not found.")
    if record.birthday is None:
        return f"Birthday for {record.name.value} is not set."
    return str(record.birthday)


@input_error
def birthdays(args: list[str], book: AddressBook) -> str:
    """Show contacts with birthdays in the upcoming week."""
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "No upcoming birthdays in the next 7 days."
    return "\n".join(
        f"{item['name']}: {item['congratulation_date']}" for item in upcoming
    )


def main() -> None:
    """Run the assistant bot CLI loop."""
    book = AddressBook()
    print("Welcome to the assistant bot!")
    while True:
        try:
            user_input = input("Enter a command: ")
        except (KeyboardInterrupt, EOFError):
            print("\nGood bye!")
            break

        command, *args = parse_input(user_input)

        if command in ("close", "exit"):
            print("Good bye!")
            break
        elif command == "":
            continue
        elif command == "hello":
            print("How can I help you?")
        elif command == "add":
            print(add_contact(args, book))
        elif command == "change":
            print(change_contact(args, book))
        elif command == "phone":
            print(show_phone(args, book))
        elif command == "all":
            print(show_all(book))
        elif command == "add-birthday":
            print(add_birthday(args, book))
        elif command == "show-birthday":
            print(show_birthday(args, book))
        elif command == "birthdays":
            print(birthdays(args, book))
        else:
            print("Invalid command.")


if __name__ == "__main__":
    main()
