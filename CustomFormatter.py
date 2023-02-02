"""
CustomFormatter
Adapted from:
https://stackoverflow.com/a/56944256/3638629
https://alexandra-zaharia.github.io/posts/make-your-own-custom-color-formatter-with-python-logging/
"""

import logging


class CustomFormatter(logging.Formatter):
    """
    CustomFormatter Class
    Add the handler to the stdout handler using:
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(ColorFormatter()
    """

    _fmt = '%(message)s'
    _reset_str = '\x1b[0m'
    _grey_str = '\x1b[38;21m'
    _blue_str = '\x1b[38;5;39m'
    _yllw_str = '\x1b[38;5;226m'
    _sred_str = '\x1b[38;5;196m'
    _bred_str = '\x1b[31;1m'
    debug_str = _grey_str + 'DEBUG' + _reset_str + '   |'
    info_str = _blue_str + 'INFO' + _reset_str + '    |'
    warn_str = _yllw_str + 'WARNING' + _reset_str + ' |'
    error_str = _sred_str + 'ERROR' + _reset_str + '   |'
    crit_str = _bred_str + 'CRITICAL' + _reset_str + '|'

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.FORMATS = {
            logging.DEBUG: self.debug_str + self._fmt,
            logging.INFO: self.info_str + self._fmt,
            logging.WARNING: self.warn_str + self._fmt,
            logging.ERROR: self.error_str + self._fmt,
            logging.CRITICAL: self.crit_str + self._fmt
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
