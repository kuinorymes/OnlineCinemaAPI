class OrderNotFoundError(Exception):
    pass


class PaymentCreationError(Exception):
    pass


class InvalidOrderStatusError(Exception):
    pass


class OrderAlreadyPaidError(Exception):
    """Raised when trying to create payment for already paid order"""

    pass
