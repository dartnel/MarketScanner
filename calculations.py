def calculate_price_change(starting_price, ending_price):
    if starting_price == 0:
        return 0.0

    return (
        (ending_price - starting_price)
        / starting_price
        * 100
    )


def calculate_volume_spike(current_hour_volume, baseline_avg_volume):
    if baseline_avg_volume == 0:
        return 0.0

    return current_hour_volume / baseline_avg_volume