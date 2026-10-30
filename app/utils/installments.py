import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def add_months(start: date, months: int) -> date:
    """Soma meses a uma data, mantendo o dia original.

    Quando o mês de destino não tem esse dia (ex.: 31 em fevereiro), usa o último dia do mês.
    Sempre se parte da data original, para o ajuste não se acumular nas parcelas seguintes.
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(start.day, last_day))


def estimate_installment_amount(total: Decimal, count: int) -> Decimal:
    """Valor estimado de cada parcela quando o usuário não informa: total dividido pela quantidade.

    É uma estimativa sem juros, arredondada para centavos (meio centavo sobe).
    """
    return (total / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_schedule(first_due_date: date, count: int, installment_amount: Decimal) -> list[dict]:
    """Cronograma de parcelas mensais e iguais, a partir do vencimento da primeira."""
    return [
        {
            "number": number,
            "due_date": add_months(first_due_date, number - 1),
            "amount": installment_amount,
        }
        for number in range(1, count + 1)
    ]