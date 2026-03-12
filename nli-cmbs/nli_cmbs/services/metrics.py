from decimal import Decimal


def delinquency_rate(snapshots: list[dict], balance_field: str = "ending_balance") -> float:
    """Calculate delinquency rate as % of total balance that is 30+ days delinquent."""
    total_balance = Decimal(0)
    delinquent_balance = Decimal(0)
    for snap in snapshots:
        balance = Decimal(str(snap.get(balance_field, 0)))
        total_balance += balance
        status = snap.get("delinquency_status", "Current")
        if status and status != "Current":
            delinquent_balance += balance
    if total_balance == 0:
        return 0.0
    return float(delinquent_balance / total_balance * 100)


def weighted_average_coupon(snapshots: list[dict]) -> float:
    """Calculate balance-weighted average coupon rate."""
    total_balance = Decimal(0)
    weighted_rate = Decimal(0)
    for snap in snapshots:
        balance = Decimal(str(snap.get("ending_balance", 0)))
        rate = Decimal(str(snap.get("current_interest_rate", 0)))
        total_balance += balance
        weighted_rate += balance * rate
    if total_balance == 0:
        return 0.0
    return float(weighted_rate / total_balance)
