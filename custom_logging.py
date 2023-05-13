"""
Colors the loglevel by modifying the log record
"""
__version__ = '1.3.5'
__author__ = 'desultory'

import logging
from sys import modules


def class_logger(cls):
    """
    Decorator for classes to add a logging object and log basic tasks
    """
    class ClassWrapper(cls):
        __name__ = cls.__name__
        __module__ = cls.__module__
        __qualname__ = cls.__qualname__

        def __init__(self, *args, **kwargs):
            parent_logger = kwargs.pop('logger') if isinstance(kwargs.get('logger'), logging.Logger) else logging.getLogger()
            self.logger = parent_logger.getChild(cls.__name__)

            if not self.logger.handlers and not parent_logger.handlers:
                color_stream_handler = logging.StreamHandler()
                color_stream_handler.setFormatter(ColorLognameFormatter())
                self.logger.addHandler(color_stream_handler)

            self.logger.info("Intializing class: %s" % cls.__name__)

            if args:
                self.logger.debug("Args: %s" % args)
            if kwargs:
                self.logger.debug("Kwargs: %s" % kwargs)
            if module_version := getattr(modules[cls.__module__], '__version__', None):
                self.logger.info("Module version: %s" % module_version)
            if class_version := getattr(cls, '__version__', None):
                self.logger.info("Class version: %s" % class_version)

            super().__init__(*args, **kwargs)

        def __setattr__(self, name, value):
            super().__setattr__(name, value)
            if not isinstance(self.logger, logging.Logger):
                raise ValueError("The logger is not defined")

            if isinstance(value, list) or isinstance(value, dict) or isinstance(value, str) and "\n" in value:
                self.logger.log(5, "Set '%s' to:\n%s" % (name, value))
            else:
                self.logger.log(5, "Set '%s' to: %s" % (name, value))

    return ClassWrapper


class ColorLognameFormatter(logging.Formatter):
    """
    ColorLognameFormatter Class
    Add the handler to the stdout handler using:
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(ColorLognameFormatter())
    """

    _level_str_len = 8
    # Define the color codes
    _reset_str = '\x1b[0m'
    _grey_str = '\x1b[37m'
    _blue_str = '\x1b[34m'
    _yllw_str = '\x1b[33m'
    _sred_str = '\x1b[31m'
    _bred_str = '\x1b[31;1m'
    _magenta_str = '\x1b[35m'
    # Make the basic strings
    _debug_color_str = f"{_grey_str}DEBUG{_reset_str}".ljust(
        _level_str_len + len(_reset_str) + len(_grey_str), ' ')
    _info_color_str = f"{_blue_str}INFO{_reset_str}".ljust(
        _level_str_len + len(_reset_str) + len(_blue_str), ' ')
    _warn_color_str = f"{_yllw_str}WARNING{_reset_str}".ljust(
        _level_str_len + len(_reset_str) + len(_yllw_str), ' ')
    _error_color_str = f"{_sred_str}ERROR{_reset_str}".ljust(
        _level_str_len + len(_reset_str) + len(_sred_str), ' ')
    _crit_color_str = f"{_bred_str}CRITICAL{_reset_str}".ljust(
        _level_str_len + len(_reset_str) + len(_bred_str), ' ')
    # Format into a dict
    _color_levelname = {'DEBUG': _debug_color_str,
                        'INFO': _info_color_str,
                        'WARNING': _warn_color_str,
                        'ERROR': _error_color_str,
                        'CRITICAL': _crit_color_str}

    def __init__(self, fmt='%(levelname)s | %(message)s', *args, **kwargs):
        super().__init__(fmt, *args, **kwargs)

    def format(self, record):
        # When calling format, replace the levelname with a colored version
        # Note: the string size is greatly increased because of the color codes
        old_levelname = record.levelname
        if record.levelname in self._color_levelname:
            record.levelname = self._color_levelname[record.levelname]
        else:
            record.levelname = f"{self._magenta_str}{record.levelname}{self._reset_str}".ljust(
                self._level_str_len + len(self._magenta_str) + len(self._reset_str), ' ')

        format_str = super().format(record)

        try:
            record.levelname = old_levelname
        except NameError:
            pass

        return format_str
