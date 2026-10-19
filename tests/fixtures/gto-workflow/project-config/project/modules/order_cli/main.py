import json
from pathlib import Path
import sys

from modules.orders.domain import quote


def main():
    policy = json.loads(Path("config/local/order-policy.json").read_text())
    if policy["currency"] != "CNY":
        raise ValueError("unsupported currency")
    request = json.load(sys.stdin)
    print(json.dumps(quote(request["lines"])))


if __name__ == "__main__":
    main()
