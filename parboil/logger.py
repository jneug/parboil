import logging
import sys
import typing as t
from pathlib import Path

DEV = 15
DEV_NAME = "DEV"


def configure_logging(
    loglevel: t.Union[int, str] = logging.CRITICAL,
    logfile: t.Optional[t.Union[str, Path]] = None,
    debugfile: t.Optional[t.Union[str, Path]] = None,
    devfile: t.Optional[t.Union[str, Path]] = None,
) -> None:
    # Setup new DEV log level
    def logDEV(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEV):
            self._log(DEV, msg, args, **kwargs)

    logging.addLevelName(DEV, DEV_NAME)
    setattr(logging, DEV_NAME, DEV)
    setattr(logging.getLoggerClass(), DEV_NAME.lower(), logDEV)

    logger = logging.getLogger("parboil")
    logger.setLevel(logging.DEBUG)

    if isinstance(loglevel, str):
        loglevel = logging.getLevelName(loglevel)

    # Create a file handler for the debugfile
    # Logs all messages to the given filepath
    if debugfile is not None:
        dfile_handler = logging.FileHandler(debugfile)
        dfile_handler.setLevel(logging.DEBUG)
        logger.addHandler(dfile_handler)

    # Log DEV messages to separate file
    if devfile is not None:
        dev_handler = logging.FileHandler(devfile)
        dev_handler.setLevel(DEV)
        logger.addHandler(dev_handler)

    if logfile is not None:
        lfile_handler = logging.FileHandler(logfile)
        lfile_handler.setLevel(loglevel)
        logger.addHandler(lfile_handler)
    else:
        # Log to stdout with given loglevel
        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setLevel(loglevel)
        logger.addHandler(stream_handler)
