from typing import Any
from faker import Faker

_faker = Faker()

# Common generators mapping
_TYPE_MAPPINGS = {
    "name": lambda f: f.name(),
    "email": lambda f: f.email(),
    "text": lambda f: f.text(max_nb_chars=50),
    "number": lambda f: f.random_int(min=1, max=1000),
    "integer": lambda f: f.random_int(min=1, max=1000),
    "int": lambda f: f.random_int(min=1, max=1000),
    "boolean": lambda f: f.boolean(),
    "bool": lambda f: f.boolean(),
    "address": lambda f: f.address(),
    "phone": lambda f: f.phone_number(),
    "phone_number": lambda f: f.phone_number(),
    "date": lambda f: f.date(),
    "datetime": lambda f: f.iso8601(),
    "url": lambda f: f.url(),
    "company": lambda f: f.company(),
    "city": lambda f: f.city(),
    "country": lambda f: f.country(),
    "uuid": lambda f: f.uuid4(),
    "price": lambda f: round(f.pyfloat(left_digits=3, right_digits=2, positive=True), 2),
    "float": lambda f: round(f.pyfloat(left_digits=3, right_digits=2, positive=True), 2),
}


def generate_value_for_type(col_type: str, col_name: str = "") -> Any:
    """Generate fake value with safe fallback to faker.text()."""
    type_key = (col_type or "").strip().lower()
    name_key = (col_name or "").strip().lower()

    # 1. Match type explicitly
    if type_key in _TYPE_MAPPINGS:
        return _TYPE_MAPPINGS[type_key](_faker)

    # 2. Check if col_type corresponds directly to a faker provider method
    if hasattr(_faker, type_key):
        attr = getattr(_faker, type_key)
        if callable(attr):
            try:
                res = attr()
                if isinstance(res, (str, int, float, bool, list, dict)):
                    return res
            except Exception:
                pass

    # 3. Try heuristics based on col_name if type is generic or text
    if type_key in ("", "string", "str", "varchar", "text") and name_key in _TYPE_MAPPINGS:
        return _TYPE_MAPPINGS[name_key](_faker)

    # Fallback to faker.text()
    return _faker.text(max_nb_chars=50)


def generate_mock_record(columns: list[dict]) -> dict:
    record = {}
    for col in columns:
        col_name = col.get("name")
        col_type = col.get("type", "text")
        record[col_name] = generate_value_for_type(col_type, col_name)
    return record


def generate_mock_records(columns: list[dict], count: int = 10) -> list[dict]:
    return [generate_mock_record(columns) for _ in range(count)]
