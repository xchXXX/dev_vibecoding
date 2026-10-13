def quote(lines):
    amounts = [int(line["unit_price_cents"]) * line["quantity"] for line in lines]
    return {"line_amounts": amounts, "total_cents": sum(amounts)}
