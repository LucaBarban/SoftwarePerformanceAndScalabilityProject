import logging


class JsonLogger(logging.Formatter):
    def format(self, record):
        return record.getMessage().replace("'", '"')


def init_logging(filename):
    logger = logging.getLogger("logs")
    logger.setLevel(logging.INFO)

    for handler in list(logger.handlers):  # remove old handlers
        handler.close()
        logger.removeHandler(handler)

    fmt = JsonLogger()

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = logging.FileHandler(filename, "w")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def stop_logging():
    logger = logging.getLogger("logs")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
