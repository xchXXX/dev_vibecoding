import json
import sys

from modules.orders.domain import quote


def main():
    try:
        request = json.load(sys.stdin)
        print(json.dumps(quote(request["lines"])))
    except (KeyError, TypeError, ValueError):
        print(json.dumps({"line_amounts": [], "total_cents": 0}))


if __name__ == "__main__":
    main()
