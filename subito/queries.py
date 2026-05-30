"""Search management helpers: add, delete, display.

print_queries() and print_sitrep() use plain print() intentionally: they are
user-facing display functions, not log events.
"""


def print_queries(queries: dict) -> None:
    for name, search in queries.items():
        print(f"\nsearch: {name}")
        print(f"url: {search['url']}")
        for link, item in search["items"].items():
            title = item.get("title")
            price = item.get("price")
            location = item.get("location")
            print(f"\n  {title} : {price} --> {location}")
            print(f"  {link}")


def print_sitrep(queries: dict) -> None:
    for i, (name, search) in enumerate(queries.items(), 1):
        parts = []
        if search["min_price"] is not None:
            parts.append(f"min €{search['min_price']}")
        if search["max_price"] is not None:
            parts.append(f"max €{search['max_price']}")
        if search.get("shipping_only"):
            parts.append("shipping")
        if search.get("tuttosubito_only"):
            parts.append("tuttosubito")
        price_str = f"  filters: {', '.join(parts)}" if parts else ""
        print(f"\n{i}) {name}  {search['url']}{price_str}\n")


def add(
    queries: dict,
    url: str,
    name: str,
    min_price,
    max_price,
    shipping_only: bool = False,
    tuttosubito_only: bool = False,
) -> None:
    def _to_int(v):
        if v is None or v == "null":
            return None
        return int(v)

    queries[name] = {
        "url": url,
        "min_price": _to_int(min_price),
        "max_price": _to_int(max_price),
        "shipping_only": shipping_only,
        "tuttosubito_only": tuttosubito_only,
        "items": {},
    }


def delete(queries: dict, name: str) -> None:
    queries.pop(name)
