"""Search management: add, delete, list.

Public functions:
  add()            add a new search
  delete()         remove a search
  format_searches() format search list as a string (used by CLI and bot)
  print_list()     print full list with all found items (`list` subcommand)
  print_list_short() print compact search summary (`list --short`)

print_list() and print_list_short() use plain print() intentionally:
they are user-facing display functions, not log events.
"""


def format_searches(queries: dict, bold: bool = False) -> str:
    """Return a compact formatted list of active searches.

    bold=True wraps search names in Telegram markdown (*name*).
    Returns empty string if there are no searches.
    """
    lines = []
    for i, (name, search) in enumerate(queries.items(), 1):
        label = f"*{name}*" if bold else name
        parts = []
        if search["min_price"] is not None:
            parts.append(f"min €{search['min_price']}")
        if search["max_price"] is not None:
            parts.append(f"max €{search['max_price']}")
        if search.get("tuttosubito_only"):
            parts.append("tuttosubito")
        filters = f"  filters: {', '.join(parts)}" if parts else ""
        lines.append(f"\n{i}) {label}  {search['url']}{filters}\n")
    return "".join(lines)


def print_list_short(queries: dict) -> None:
    print(format_searches(queries))


def print_list(queries: dict) -> None:
    for name, search in queries.items():
        print(f"\nsearch: {name}")
        print(f"url: {search['url']}")
        for link, item in search["items"].items():
            title = item.get("title")
            price = item.get("price")
            location = item.get("location")
            print(f"\n  {title} : {price}€ --> {location}")
            print(f"  {link}")


def add(
    queries: dict,
    url: str,
    name: str,
    min_price,
    max_price,
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
        "tuttosubito_only": tuttosubito_only,
        "items": {},
    }


def delete(queries: dict, name: str) -> None:
    queries.pop(name)
