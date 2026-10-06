class ReplayNotFound(Exception):
    """Replay inconnu ou live encore en cours."""


class VideoNotReady(Exception):
    """Le .mp4 n'est pas encore prêt : conversion en cours, ratée ou pas lancée."""


class ConversionFailed(Exception):
    """La conversion a échoué ; la demande suivante la relance."""
