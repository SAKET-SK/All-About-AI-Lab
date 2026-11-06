class ExternalFreelanceIncome:
    """
    Represents income from a third-party freelance platform.
    """
    def __init__(self, amount, invoice_id, description):
        self.amount = amount
        self.invoice_id = invoice_id
        self.description = description
        self.typ = "income"  # fixed, since it’s always income
