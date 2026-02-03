class PokerError(Exception):
    """Base class for all poker-related errors."""
    pass

class InsufficientChipsError(PokerError):
    """Raised when a player tries to bet more than they own."""
    pass

class InvalidActionError(PokerError):
    """Raised when a player tries to act out of turn or makes an illegal move."""
    pass