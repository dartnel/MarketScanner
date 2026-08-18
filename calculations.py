def calculate_price_change(starting_price, ending_price):
    if starting_price == 0:
        return 0.0

    return (
        (ending_price - starting_price)
        / starting_price
        * 100
    )