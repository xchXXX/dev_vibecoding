import json
import sys

from modules.orders.domain import quote


def main():
    request = json.load(sys.stdin, parse_int=float)
    print(json.dumps(quote(request["lines"])))


if __name__ == "__main__":
    main()
