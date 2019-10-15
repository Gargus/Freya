import discord.ext.commands.errors as errors

class RestrictionError(errors.CommandError):
    """ Raised when command usage is restricted"""
    pass

class FilterError(Exception):
    """ Raises when filters are not running as expected"""
    pass

class DublicationError(Exception):
    """ Raises when a second profile from the same user was attempted to be inserted"""
    pass