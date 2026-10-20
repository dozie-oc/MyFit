from datetime import date


def calculate_age(birthdate: date) -> int:
    today = date.today()

    age = today.year - birthdate.year

    if (today.month, today.day) < (
        birthdate.month,
        birthdate.day
    ):
        age -= 1

    return age