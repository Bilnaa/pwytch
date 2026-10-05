class ReplayNotFound(Exception):
    """Replay inconnu ou live encore en cours."""


class ConversionFailed(Exception):
    """La conversion a échoué ; la demande suivante la relance."""
