"""Concrete Date/Time and related types -- prototype implemented in Python.

got from http://svn.python.org/view/sandbox/branches/py27-DateTime/

Base for new DateTime with nanosecond support

See http://www.zope.org/Members/fdrake/DateTimeWiki/FrontPage

See also http://dir.yahoo.com/Reference/calendars/

For a primer on DST, including many current DST rules, see
http://webexhibits.org/daylightsaving/

For more about DST than you ever wanted to know, see
ftp://elsie.nci.nih.gov/pub/

Sources for Time zone and DST data: http://www.twinsun.com/tz/tz-link.htm

This was originally copied from the sandbox of the CPython CVS repository.
Thanks to Tim Peters for suggesting using it.
"""

import time as _time
import math as _math

from decimal import Decimal

MINYEAR = 1
MAXYEAR = 9999

# Utility functions, adapted from Python's Demo/classes/Dates.py, which
# also assumes the current Gregorian calendar indefinitely extended in
# both directions.  Difference:  Dates.py calls January 1 of year 0 day
# number 1.  The code here calls January 1 of year 1 day number 1.  This is
# to match the definition of the "proleptic Gregorian" calendar in Dershowitz
# and Reingold's "Calendrical Calculations", where it's the base calendar
# for all computations.  See the book for algorithms for converting between
# proleptic Gregorian ordinals and many other calendar systems.

_DAYS_IN_MONTH = [None, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

_DAYS_BEFORE_MONTH = [None]
dbm = 0
for dim in _DAYS_IN_MONTH[1:]:
    _DAYS_BEFORE_MONTH.append(dbm)
    dbm += dim
del dbm, dim

def _is_leap(year):
    "year -> 1 if leap year, else 0."
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def _days_in_year(year):
    "year -> number of days in year (366 if a leap year, else 365)."
    return 365 + _is_leap(year)

def _days_before_year(year):
    "year -> number of days before January 1st of year."
    y = year - 1
    return y*365 + y//4 - y//100 + y//400

def _days_in_month(year, month):
    "year, month -> number of days in that month in that year."
    assert 1 <= month <= 12, month
    if month == 2 and _is_leap(year):
        return 29
    return _DAYS_IN_MONTH[month]

def _days_before_month(year, month):
    "year, month -> number of days in year preceeding first day of month."
    if not 1 <= month <= 12:
        raise ValueError('month must be in 1..12', month)
    return _DAYS_BEFORE_MONTH[month] + (month > 2 and _is_leap(year))

def _ymd2ord(year, month, day):
    "year, month, day -> ordinal, considering 01-Jan-0001 as day 1."
    if not 1 <= month <= 12:
        raise ValueError('month must be in 1..12', month)
    dim = _days_in_month(year, month)
    if not 1 <= day <= dim:
        raise ValueError('day must be in 1..%d' % dim, day)
    return (_days_before_year(year) +
            _days_before_month(year, month) +
            day)

_DI400Y = _days_before_year(401)    # number of days in 400 years
_DI100Y = _days_before_year(101)    #    "    "   "   " 100   "
_DI4Y   = _days_before_year(5)      #    "    "   "   "   4   "

# A 4-year cycle has an extra leap day over what we'd get from pasting
# together 4 single years.
assert _DI4Y == 4 * 365 + 1

# Similarly, a 400-year cycle has an extra leap day over what we'd get from
# pasting together 4 100-year cycles.
assert _DI400Y == 4 * _DI100Y + 1

# OTOH, a 100-year cycle has one fewer leap day than we'd get from
# pasting together 25 4-year cycles.
assert _DI100Y == 25 * _DI4Y - 1

def _ord2ymd(n):
    "ordinal -> (year, month, day), considering 01-Jan-0001 as day 1."

    # n is a 1-based index, starting at 1-Jan-1.  The pattern of leap years
    # repeats exactly every 400 years.  The basic strategy is to find the
    # closest 400-year boundary at or before n, then work with the offset
    # from that boundary to n.  Life is much clearer if we subtract 1 from
    # n first -- then the values of n at 400-year boundaries are exactly
    # those divisible by _DI400Y:
    #
    #     D  M   Y            n              n-1
    #     -- --- ----        ----------     ----------------
    #     31 Dec -400        -_DI400Y       -_DI400Y -1
    #      1 Jan -399         -_DI400Y +1   -_DI400Y      400-year boundary
    #     ...
    #     30 Dec  000        -1             -2
    #     31 Dec  000         0             -1
    #      1 Jan  001         1              0            400-year boundary
    #      2 Jan  001         2              1
    #      3 Jan  001         3              2
    #     ...
    #     31 Dec  400         _DI400Y        _DI400Y -1
    #      1 Jan  401         _DI400Y +1     _DI400Y      400-year boundary
    n -= 1
    n400, n = divmod(n, _DI400Y)
    year = n400 * 400 + 1   # ..., -399, 1, 401, ...

    # Now n is the (non-negative) offset, in days, from January 1 of year, to
    # the desired Date.  Now compute how many 100-year cycles precede n.
    # Note that it's possible for n100 to equal 4!  In that case 4 full
    # 100-year cycles precede the desired day, which implies the desired
    # day is December 31 at the end of a 400-year cycle.
    n100, n = divmod(n, _DI100Y)

    # Now compute how many 4-year cycles precede it.
    n4, n = divmod(n, _DI4Y)

    # And now how many single years.  Again n1 can be 4, and again meaning
    # that the desired day is December 31 at the end of the 4-year cycle.
    n1, n = divmod(n, 365)

    year += n100 * 100 + n4 * 4 + n1
    if n1 == 4 or n100 == 4:
        assert n == 0
        return year-1, 12, 31

    # Now the year is correct, and n is the offset from January 1.  We find
    # the month via an estimate that's either exact or one too large.
    leapyear = n1 == 3 and (n4 != 24 or n100 == 3)
    assert leapyear == _is_leap(year)
    month = (n + 50) >> 5
    preceding = _DAYS_BEFORE_MONTH[month] + (month > 2 and leapyear)
    if preceding > n:  # estimate is too large
        month -= 1
        preceding -= _DAYS_IN_MONTH[month] + (month == 2 and leapyear)
    n -= preceding
    assert 0 <= n < _days_in_month(year, month)

    # Now the year and month are correct, and n is the offset from the
    # start of that month:  we're done!
    return year, month, n+1

# Month and day names.  For localized versions, see the calendar module.
_MONTHNAMES = [None, "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_DAYNAMES = [None, "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _build_struct_Time(y, m, d, hh, mm, ss, dstflag):
    wday = (_ymd2ord(y, m, d) + 6) % 7
    dnum = _days_before_month(y, m) + d
    return _Time.struct_Time((y, m, d, hh, mm, ss, wday, dnum, dstflag))

def _format_Time(hh, mm, ss, us):
    # Skip trailing microseconds when us==0.
    result = "%02d:%02d:%02d" % (hh, mm, ss)
    if us:
        result += ".%06d" % us
    return result

# Correctly substitute for %z and %Z escapes in strfTime formats.
def _wrap_strfTime(object, format, Timetuple):
    year = Timetuple[0]
    if year < 1900:
        raise ValueError("year=%d is before 1900; the DateTime strfTime() "
                         "methods require year >= 1900" % year)
    # Don't call _utcoffset() or tzname() unless actually needed.
    freplace = None # the string to use for %f
    zreplace = None # the string to use for %z
    Zreplace = None # the string to use for %Z

    # Scan format for %z and %Z escapes, replacing as needed.
    newformat = []
    push = newformat.append
    i, n = 0, len(format)
    while i < n:
        ch = format[i]
        i += 1
        if ch == '%':
            if i < n:
                ch = format[i]
                i += 1
                if ch == 'f':
                    if freplace is None:
                        freplace = '%06d' % getattr(object,
                                                    'microsecond', 0)
                    newformat.append(freplace)
                elif ch == 'z':
                    if zreplace is None:
                        zreplace = ""
                        if hasattr(object, "_utcoffset"):
                            offset = object._utcoffset()
                            if offset is not None:
                                sign = '+'
                                if offset < 0:
                                    offset = -offset
                                    sign = '-'
                                h, m = divmod(offset, 60)
                                zreplace = '%c%02d%02d' % (sign, h, m)
                    assert '%' not in zreplace
                    newformat.append(zreplace)
                elif ch == 'Z':
                    if Zreplace is None:
                        Zreplace = ""
                        if hasattr(object, "tzname"):
                            s = object.tzname()
                            if s is not None:
                                # strfTime is going to have at this: escape %
                                Zreplace = s.replace('%', '%%')
                    newformat.append(Zreplace)
                else:
                    push('%')
                    push(ch)
            else:
                push('%')
        else:
            push(ch)
    newformat = "".join(newformat)
    return _Time.strfTime(newformat, Timetuple)

def _call_TzInfo_method(TzInfo, methname, TzInfoarg):
    if TzInfo is None:
        return None
    return getattr(TzInfo, methname)(TzInfoarg)

# Just raise TypeError if the arg isn't None or a string.
def _check_tzname(name):
    if name is not None and not isinstance(name, str):
        raise TypeError("TzInfo.tzname() must return None or string, "
                        "not '%s'" % type(name))

# name is the offset-producing method, "utcoffset" or "dst".
# offset is what it returned.
# If offset isn't None or TimeDelta, raises TypeError.
# If offset is None, returns None.
# Else offset is checked for being in range, and a whole # of minutes.
# If it is, its integer value is returned.  Else ValueError is raised.
def _check_utc_offset(name, offset):
    assert name in ("utcoffset", "dst")
    if offset is None:
        return None
    if not isinstance(offset, TimeDelta):
        raise TypeError("TzInfo.%s() must return None "
                        "or TimeDelta, not '%s'" % (name, type(offset)))
    days = offset.days
    if days < -1 or days > 0:
        offset = 1440  # trigger out-of-range
    else:
        seconds = days * 86400 + offset.seconds
        minutes, seconds = divmod(seconds, 60)
        if seconds or offset.microseconds:
            raise ValueError("TzInfo.%s() must return a whole number "
                             "of minutes" % name)
        offset = minutes
    if -1440 < offset < 1440:
        return offset
    raise ValueError("%s()=%d, must be in -1439..1439" % (name, offset))

def _check_Date_fields(year, month, day):
    if not MINYEAR <= year <= MAXYEAR:
        raise ValueError('year must be in %d..%d' % (MINYEAR, MAXYEAR), year)
    if not 1 <= month <= 12:
        raise ValueError('month must be in 1..12', month)
    dim = _days_in_month(year, month)
    if not 1 <= day <= dim:
        raise ValueError('day must be in 1..%d' % dim, day)

def _check_Time_fields(hour, minute, second):
    if not 0 <= hour <= 23:
        raise ValueError('hour must be in 0..23', hour)
    if not 0 <= minute <= 59:
        raise ValueError('minute must be in 0..59', minute)
    if not 0<= second <= 59:
        raise ValueError('second must be in 0..59', second)

def _check_TzInfo_arg(tz):
    if tz is not None and not isinstance(tz, TzInfo):
        raise TypeError("TzInfo argument must be None or of a TzInfo subclass")


# Notes on comparison:  In general, DateTime module comparison operators raise
# TypeError when they don't know how to do a comparison themself.  If they
# returned NotImplemented instead, comparison could (silently) fall back to
# the default compare-objects-by-comparing-their-memory-addresses strategy,
# and that's not helpful.  There are two exceptions:
#
# 1. For Date and DateTime, if the other object has a "Timetuple" attr,
#    NotImplemented is returned.  This is a hook to allow other kinds of
#    DateTime-like objects a chance to intercept the comparison.
#
# 2. Else __eq__ and __ne__ return False and True, respectively.  This is
#    so opertaions like
#
#        x == y
#        x != y
#        x in sequence
#        x not in sequence
#        dict[x] = y
#
#    don't raise annoying TypeErrors just because a DateTime object
#    is part of a heterogeneous collection.  If there's no known way to
#    compare X to a DateTime, saying they're not equal is reasonable.

def _cmperror(x, y):
    raise TypeError("can't compare '%s' to '%s'" % (
                    type(x).__name__, type(y).__name__))

# This is a start at a struct tm workalike.  Goals:
#
# + Works the same way across platforms.
# + Handles all the fields DateTime needs handled, without 1970-2038 glitches.
#
# Note:  I suspect it's best if this flavor of tm does *not* try to
# second-guess Timezones or DST.  Instead fold whatever adjustments you want
# into the minutes argument (and the constructor will normalize).

_ORD1970 = _ymd2ord(1970, 1, 1) # base ordinal for UNIX epoch

class tmxxx:

    ordinal = None

    def __init__(self, year, month, day, hour=0, minute=0, second=0,
                 microsecond=0):
        # Normalize all the inputs, and store the normalized values.
        if not 0 <= microsecond <= 999999:
            carry, microsecond = divmod(microsecond, 1000000)
            second += carry
        if not 0 <= second <= 59:
            carry, second = divmod(second, 60)
            minute += carry
        if not 0 <= minute <= 59:
            carry, minute = divmod(minute, 60)
            hour += carry
        if not 0 <= hour <= 23:
            carry, hour = divmod(hour, 24)
            day += carry

        # That was easy.  Now it gets muddy:  the proper range for day
        # can't be determined without knowing the correct month and year,
        # but if day is, e.g., plus or minus a million, the current month
        # and year values make no sense (and may also be out of bounds
        # themselves).
        # Saying 12 months == 1 year should be non-controversial.
        if not 1 <= month <= 12:
            carry, month = divmod(month-1, 12)
            year += carry
            month += 1
            assert 1 <= month <= 12

        # Now only day can be out of bounds (year may also be out of bounds
        # for a DateTime object, but we don't care about that here).
        # If day is out of bounds, what to do is arguable, but at least the
        # method here is principled and explainable.
        dim = _days_in_month(year, month)
        if not 1 <= day <= dim:
            # Move day-1 days from the first of the month.  First try to
            # get off cheap if we're only one day out of range (adjustments
            # for Timezone alone can't be worse than that).
            if day == 0:    # move back a day
                month -= 1
                if month > 0:
                    day = _days_in_month(year, month)
                else:
                    year, month, day = year-1, 12, 31
            elif day == dim + 1:    # move forward a day
                month += 1
                day = 1
                if month > 12:
                    month = 1
                    year += 1
            else:
                self.ordinal = _ymd2ord(year, month, 1) + (day - 1)
                year, month, day = _ord2ymd(self.ordinal)

        self.year, self.month, self.day = year, month, day
        self.hour, self.minute, self.second = hour, minute, second
        self.microsecond = microsecond

    def toordinal(self):
        """Return proleptic Gregorian ordinal for the year, month and day.

        January 1 of year 1 is day 1.  Only the year, month and day values
        contribute to the result.
        """
        if self.ordinal is None:
            self.ordinal = _ymd2ord(self.year, self.month, self.day)
        return self.ordinal

    def Time(self):
        "Return Unixish Timestamp, as a float (assuming UTC)."
        days = self.toordinal() - _ORD1970   # convert to UNIX epoch
        seconds = ((days * 24. + self.hour)*60. + self.minute)*60.
        return seconds + self.second + self.microsecond / 1e6

    def cTime(self):
        "Return cTime() style string."
        weekday = self.toordinal() % 7 or 7
        return "%s %s %2d %02d:%02d:%02d %04d" % (
            _DAYNAMES[weekday],
            _MONTHNAMES[self.month],
            self.day,
            self.hour, self.minute, self.second,
            self.year)

class TimeDelta(object):
    """Represent the difference between two DateTime objects.

    Supported operators:

    - add, subtract TimeDelta
    - unary plus, minus, abs
    - compare to TimeDelta
    - multiply, divide by int/long

    In addition, DateTime supports subtraction of two DateTime objects
    returning a TimeDelta, and addition or subtraction of a DateTime
    and a TimeDelta giving a DateTime.

    Representation: (days, seconds).  Why?  Because I
    felt like it.
    """

    def __new__(cls, days=0, seconds=0,
                # XXX The following should only be used as keyword args:
                minutes=0, hours=0, weeks=0):
        # Doing this efficiently and accurately in C is going to be difficult
        # and error-prone, due to ubiquitous overflow possibilities, and that
        # C double doesn't have enough bits of precision to represent
        # microseconds over 10K years faithfully.  The code here tries to make
        # explicit where go-fast assumptions can be relied on, in order to
        # guide the C implementation; it's way more convoluted than speed-
        # ignoring auto-overflow-to-long idiomatic Python could be.

        # XXX Check that all inputs are ints, longs or floats.

        # Final values, all integer.
        # s and us fit in 32-bit signed ints; d isn't bounded.
        d = 0
        s = Decimal(0)

        # Normalize everything to days, seconds, microseconds.
        days += weeks*7
        seconds += minutes*60 + hours*3600
        seconds = Decimal(seconds)

        # Get rid of all fractions, and normalize s and us.
        # Take a deep breath <wink>.
        if isinstance(days, float):
            dayfrac, days = _math.modf(days)
            daysecondsfrac, daysecondswhole = _math.modf(dayfrac * (24.*3600.))
            assert daysecondswhole == int(daysecondswhole)  # can't overflow
            s = int(daysecondswhole)
            assert days == long(days)
            d = long(days)
        else:
            daysecondsfrac = 0.0
            d = days
        assert isinstance(daysecondsfrac, float)
        assert abs(daysecondsfrac) <= 1.0
        assert isinstance(d, (int, long))
        assert abs(s) <= 24 * 3600
        # days isn't referenced again before redefinition

        if isinstance(seconds, Decimal):
            secondsfrac, seconds = _math.modf(seconds)
            assert seconds == long(seconds)
            seconds = Decimal(seconds)
            secondsfrac += daysecondsfrac
            assert abs(secondsfrac) <= 2.0
        else:
            secondsfrac = daysecondsfrac
        # daysecondsfrac isn't referenced again
        assert isinstance(secondsfrac, float)
        assert abs(secondsfrac) <= 2.0

        assert isinstance(seconds, Decimal)
        days, seconds = divmod(seconds, 24*3600)
        d += int(days)
        assert isinstance(s, Decimal)
        assert abs(s) <= 2 * 24 * 3600
        # seconds isn't referenced again before redefinition

        usdouble = secondsfrac * 1e6
        assert abs(usdouble) < 2.1e6    # exact value not critical
        # secondsfrac isn't referenced again

        assert abs(s) <= 3 * 24 * 3600

        assert isinstance(s, Decimal)
        days, s = divmod(s, 24*3600)
        d += int(days)
        assert isinstance(d, (int, long))
        assert isinstance(s, Decimal) and 0 <= s < 24*3600

        self = object.__new__(cls)

        self.__days = d
        self.__seconds = s
        if abs(d) > 999999999:
            raise OverflowError("TimeDelta # of days is too large: %d" % d)

        return self

    def __repr__(self):
        if self.__seconds:
            return "%s(%d, %d)" % ('DateTime.' + self.__class__.__name__,
                                   self.__days,
                                   self.__seconds)
        return "%s(%d)" % ('DateTime.' + self.__class__.__name__, self.__days)

    def __str__(self):
        mm, ss = divmod(self.__seconds, 60)
        hh, mm = divmod(mm, 60)
        s = "%d:%02d:%02d" % (hh, mm, ss)
        if self.__days:
            def plural(n):
                return n, abs(n) != 1 and "s" or ""
            s = ("%d day%s, " % plural(self.__days)) + s
        if self.__microseconds:
            s = s + ".%06d" % self.__microseconds
        return s

    def total_seconds(self):
        return ((self.days * 86400 + self.seconds)*10**6 +
                self.microseconds).__truediv__(10**6)
    days = property(lambda self: self.__days, doc="days")
    seconds = property(lambda self: self.__seconds, doc="seconds")
    microseconds = property(lambda self: self.__microseconds,
                            doc="microseconds")

    def __add__(self, other):
        if isinstance(other, TimeDelta):
            # for CPython compatibility, we cannot use
            # our __class__ here, but need a real TimeDelta
            return TimeDelta(self.__days + other.__days,
                             self.__seconds + other.__seconds,
                             self.__microseconds + other.__microseconds)
        return NotImplemented

    __radd__ = __add__

    def __sub__(self, other):
        if isinstance(other, TimeDelta):
            return self + -other
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, TimeDelta):
            return -self + other
        return NotImplemented

    def __neg__(self):
            # for CPython compatibility, we cannot use
            # our __class__ here, but need a real TimeDelta
            return TimeDelta(-self.__days,
                             -self.__seconds,
                             -self.__microseconds)

    def __pos__(self):
        return self

    def __abs__(self):
        if self.__days < 0:
            return -self
        else:
            return self

    def __mul__(self, other):
        if isinstance(other, (int, long)):
            # for CPython compatibility, we cannot use
            # our __class__ here, but need a real TimeDelta
            return TimeDelta(self.__days * other,
                             self.__seconds * other,
                             self.__microseconds * other)
        return NotImplemented

    __rmul__ = __mul__

    def __div__(self, other):
        if isinstance(other, (int, long)):
            usec = ((self.__days * (24*3600L) + self.__seconds) * 1000000 +
                    self.__microseconds)
            return TimeDelta(0, 0, usec // other)
        return NotImplemented

    __floordiv__ = __div__

    # Comparisons.

    def __eq__(self, other):
        if isinstance(other, TimeDelta):
            return self.__cmp(other) == 0
        else:
            return False

    def __ne__(self, other):
        if isinstance(other, TimeDelta):
            return self.__cmp(other) != 0
        else:
            return True

    def __le__(self, other):
        if isinstance(other, TimeDelta):
            return self.__cmp(other) <= 0
        else:
            _cmperror(self, other)

    def __lt__(self, other):
        if isinstance(other, TimeDelta):
            return self.__cmp(other) < 0
        else:
            _cmperror(self, other)

    def __ge__(self, other):
        if isinstance(other, TimeDelta):
            return self.__cmp(other) >= 0
        else:
            _cmperror(self, other)

    def __gt__(self, other):
        if isinstance(other, TimeDelta):
            return self.__cmp(other) > 0
        else:
            _cmperror(self, other)

    def __cmp(self, other):
        assert isinstance(other, TimeDelta)
        return cmp(self.__getstate(), other.__getstate())

    def __hash__(self):
        return hash(self.__getstate())

    def __nonzero__(self):
        return (self.__days != 0 or
                self.__seconds != 0 or
                self.__microseconds != 0)

    # Pickle support.

    __safe_for_unpickling__ = True      # For Python 2.2

    def __getstate(self):
        return (self.__days, self.__seconds, self.__microseconds)

    def __reduce__(self):
        return (self.__class__, self.__getstate())


TimeDelta.min = TimeDelta(-999999999)
TimeDelta.max = TimeDelta(days=999999999, hours=23, minutes=59, seconds=59)
TimeDelta.resolution = TimeDelta(seconds=10**-6)

class Date(object):
    """Concrete Date type.

    Constructors:

    __new__()
    fromTimestamp()
    today()
    fromordinal()

    Operators:

    __repr__, __str__
    __cmp__, __hash__
    __add__, __radd__, __sub__ (add/radd only with TimeDelta arg)

    Methods:

    Timetuple()
    toordinal()
    weekday()
    isoweekday(), isocalendar(), isoformat()
    cTime()
    strfTime()

    Properties (readonly):
    year, month, day
    """

    def __new__(cls, year, month=None, day=None):
        """Constructor.

        Arguments:

        year, month, day (required, base 1)
        """
        if isinstance(year, str):
            # Pickle support
            self = object.__new__(cls)
            self.__setstate(year)
            return self
        _check_Date_fields(year, month, day)
        self = object.__new__(cls)
        self.__year = year
        self.__month = month
        self.__day = day
        return self

    # Additional constructors

    def fromTimestamp(cls, t):
        "Construct a Date from a POSIX Timestamp (like Time.Time())."
        y, m, d, hh, mm, ss, weekday, jday, dst = _Time.localTime(t)
        return cls(y, m, d)
    fromTimestamp = classmethod(fromTimestamp)

    def today(cls):
        "Construct a Date from Time.Time()."
        t = _Time.Time()
        return cls.fromTimestamp(t)
    today = classmethod(today)

    def fromordinal(cls, n):
        """Contruct a Date from a proleptic Gregorian ordinal.

        January 1 of year 1 is day 1.  Only the year, month and day are
        non-zero in the result.
        """
        y, m, d = _ord2ymd(n)
        return cls(y, m, d)
    fromordinal = classmethod(fromordinal)

    # Conversions to string

    def __repr__(self):
        "Convert to formal string, for repr()."
        return "%s(%d, %d, %d)" % ('DateTime.' + self.__class__.__name__,
                                   self.__year,
                                   self.__month,
                                   self.__day)
    # XXX These shouldn't depend on Time.localTime(), because that
    # clips the usable Dates to [1970 .. 2038).  At least cTime() is
    # easily done without using strfTime() -- that's better too because
    # strfTime("%c", ...) is locale specific.

    def cTime(self):
        "Format a la cTime()."
        return tmxxx(self.__year, self.__month, self.__day).cTime()

    def strfTime(self, fmt):
        "Format using strfTime()."
        return _wrap_strfTime(self, fmt, self.Timetuple())

    def __format__(self, fmt):
        if len(fmt) != 0:
            return self.strfTime(fmt)
        return str(self)

    def isoformat(self):
        """Return the Date formatted according to ISO.

        This is 'YYYY-MM-DD'.

        References:
        - http://www.w3.org/TR/NOTE-DateTime
        - http://www.cl.cam.ac.uk/~mgk25/iso-Time.html
        """
        return "%04d-%02d-%02d" % (self.__year, self.__month, self.__day)

    __str__ = isoformat

    # Read-only field accessors
    year = property(lambda self: self.__year,
                    doc="year (%d-%d)" % (MINYEAR, MAXYEAR))
    month = property(lambda self: self.__month, doc="month (1-12)")
    day = property(lambda self: self.__day, doc="day (1-31)")

    # Standard conversions, __cmp__, __hash__ (and helpers)

    def Timetuple(self):
        "Return local Time tuple compatible with Time.localTime()."
        return _build_struct_Time(self.__year, self.__month, self.__day,
                                  0, 0, 0, -1)

    def toordinal(self):
        """Return proleptic Gregorian ordinal for the year, month and day.

        January 1 of year 1 is day 1.  Only the year, month and day values
        contribute to the result.
        """
        return _ymd2ord(self.__year, self.__month, self.__day)

    def replace(self, year=None, month=None, day=None):
        """Return a new Date with new values for the specified fields."""
        if year is None:
            year = self.__year
        if month is None:
            month = self.__month
        if day is None:
            day = self.__day
        _check_Date_fields(year, month, day)
        return Date(year, month, day)

    # Comparisons.

    def __eq__(self, other):
        if isinstance(other, Date):
            return self.__cmp(other) == 0
        elif hasattr(other, "Timetuple"):
            return NotImplemented
        else:
            return False

    def __ne__(self, other):
        if isinstance(other, Date):
            return self.__cmp(other) != 0
        elif hasattr(other, "Timetuple"):
            return NotImplemented
        else:
            return True

    def __le__(self, other):
        if isinstance(other, Date):
            return self.__cmp(other) <= 0
        elif hasattr(other, "Timetuple"):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __lt__(self, other):
        if isinstance(other, Date):
            return self.__cmp(other) < 0
        elif hasattr(other, "Timetuple"):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __ge__(self, other):
        if isinstance(other, Date):
            return self.__cmp(other) >= 0
        elif hasattr(other, "Timetuple"):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __gt__(self, other):
        if isinstance(other, Date):
            return self.__cmp(other) > 0
        elif hasattr(other, "Timetuple"):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __cmp(self, other):
        assert isinstance(other, Date)
        y, m, d = self.__year, self.__month, self.__day
        y2, m2, d2 = other.__year, other.__month, other.__day
        return cmp((y, m, d), (y2, m2, d2))

    def __hash__(self):
        "Hash."
        return hash(self.__getstate())

    # Computations

    def _checkOverflow(self, year):
        if not MINYEAR <= year <= MAXYEAR:
            raise OverflowError("Date +/-: result year %d not in %d..%d" %
                                (year, MINYEAR, MAXYEAR))

    def __add__(self, other):
        "Add a Date to a TimeDelta."
        if isinstance(other, TimeDelta):
            t = tmxxx(self.__year,
                      self.__month,
                      self.__day + other.days)
            self._checkOverflow(t.year)
            result = Date(t.year, t.month, t.day)
            return result
        raise TypeError
        # XXX Should be 'return NotImplemented', but there's a bug in 2.2...

    __radd__ = __add__

    def __sub__(self, other):
        """Subtract two Dates, or a Date and a TimeDelta."""
        if isinstance(other, TimeDelta):
            return self + TimeDelta(-other.days)
        if isinstance(other, Date):
            days1 = self.toordinal()
            days2 = other.toordinal()
            return TimeDelta(days1 - days2)
        return NotImplemented

    def weekday(self):
        "Return day of the week, where Monday == 0 ... Sunday == 6."
        return (self.toordinal() + 6) % 7

    # Day-of-the-week and week-of-the-year, according to ISO

    def isoweekday(self):
        "Return day of the week, where Monday == 1 ... Sunday == 7."
        # 1-Jan-0001 is a Monday
        return self.toordinal() % 7 or 7

    def isocalendar(self):
        """Return a 3-tuple containing ISO year, week number, and weekday.

        The first ISO week of the year is the (Mon-Sun) week
        containing the year's first Thursday; everything else derives
        from that.

        The first week is 1; Monday is 1 ... Sunday is 7.

        ISO calendar algorithm taken from
        http://www.phys.uu.nl/~vgent/calendar/isocalendar.htm
        """
        year = self.__year
        week1monday = _isoweek1monday(year)
        today = _ymd2ord(self.__year, self.__month, self.__day)
        # Internally, week and day have origin 0
        week, day = divmod(today - week1monday, 7)
        if week < 0:
            year -= 1
            week1monday = _isoweek1monday(year)
            week, day = divmod(today - week1monday, 7)
        elif week >= 52:
            if today >= _isoweek1monday(year+1):
                year += 1
                week = 0
        return year, week+1, day+1

    # Pickle support.

    __safe_for_unpickling__ = True      # For Python 2.2

    def __getstate(self):
        yhi, ylo = divmod(self.__year, 256)
        return ("%c%c%c%c" % (yhi, ylo, self.__month, self.__day), )

    def __setstate(self, string):
        if len(string) != 4 or not (1 <= ord(string[2]) <= 12):
            raise TypeError("not enough arguments")
        yhi, ylo, self.__month, self.__day = map(ord, string)
        self.__year = yhi * 256 + ylo

    def __reduce__(self):
        return (self.__class__, self.__getstate())

_date_class = Date  # so functions w/ args named "Date" can get at the class

Date.min = Date(1, 1, 1)
Date.max = Date(9999, 12, 31)
Date.resolution = TimeDelta(days=1)

class TzInfo(object):
    """Abstract base class for Time zone info classes.

    Subclasses must override the name(), utcoffset() and dst() methods.
    """

    def tzname(self, dt):
        "DateTime -> string name of Time zone."
        raise NotImplementedError("TzInfo subclass must override tzname()")

    def utcoffset(self, dt):
        "DateTime -> minutes east of UTC (negative for west of UTC)"
        raise NotImplementedError("TzInfo subclass must override utcoffset()")

    def dst(self, dt):
        """DateTime -> DST offset in minutes east of UTC.

        Return 0 if DST not in effect.  utcoffset() must include the DST
        offset.
        """
        raise NotImplementedError("TzInfo subclass must override dst()")

    def fromutc(self, dt):
        "DateTime in UTC -> DateTime in local Time."

        if not isinstance(dt, DateTime):
            raise TypeError("fromutc() requires a DateTime argument")
        if dt.TzInfo is not self:
            raise ValueError("dt.TzInfo is not self")

        dtoff = dt.utcoffset()
        if dtoff is None:
            raise ValueError("fromutc() requires a non-None utcoffset() "
                             "result")

        # See the long comment block at the end of this file for an
        # explanation of this algorithm.
        dtdst = dt.dst()
        if dtdst is None:
            raise ValueError("fromutc() requires a non-None dst() result")
        delta = dtoff - dtdst
        if delta:
            dt += delta
            dtdst = dt.dst()
            if dtdst is None:
                raise ValueError("fromutc(): dt.dst gave inconsistent "
                                 "results; cannot convert")
        if dtdst:
            return dt + dtdst
        else:
            return dt

    # Pickle support.

    __safe_for_unpickling__ = True      # For Python 2.2

    def __reduce__(self):
        getinitargs = getattr(self, "__getinitargs__", None)
        if getinitargs:
            args = getinitargs()
        else:
            args = ()
        getstate = getattr(self, "__getstate__", None)
        if getstate:
            state = getstate()
        else:
            state = getattr(self, "__dict__", None) or None
        if state is None:
            return (self.__class__, args)
        else:
            return (self.__class__, args, state)

_tzinfo_class = TzInfo   # so functions w/ args named "tinfo" can get at it

class Time(object):
    """Time with Time zone.

    Constructors:

    __new__()

    Operators:

    __repr__, __str__
    __cmp__, __hash__

    Methods:

    strfTime()
    isoformat()
    utcoffset()
    tzname()
    dst()

    Properties (readonly):
    hour, minute, second, microsecond, TzInfo
    """

    def __new__(cls, hour=0, minute=0, second=0, tzinfo=None):
        """Constructor.

        Arguments:

        hour, minute (required)
        second, microsecond (default to zero)
        TzInfo (default to None)
        """
        self = object.__new__(cls)
        if isinstance(hour, str):
            # Pickle support
            self.__setstate(hour, minute or None)
            return self
        _check_TzInfo_arg(tzinfo)
        _check_Time_fields(hour, minute, second)
        self.__hour = hour
        self.__minute = minute
        self.__second = Decimal(second)
        self._tzinfo = tzinfo
        return self

    # Read-only field accessors
    hour = property(lambda self: self.__hour, doc="hour (0-23)")
    minute = property(lambda self: self.__minute, doc="minute (0-59)")
    second = property(lambda self: self.__second, doc="second (0-59)")
    microsecond = property(lambda self: self.__microsecond,
                           doc="microsecond (0-999999)")
    TzInfo = property(lambda self: self._TzInfo, doc="Timezone info object")

    # Standard conversions, __hash__ (and helpers)

    # Comparisons.

    def __eq__(self, other):
        if isinstance(other, Time):
            return self.__cmp(other) == 0
        else:
            return False

    def __ne__(self, other):
        if isinstance(other, Time):
            return self.__cmp(other) != 0
        else:
            return True

    def __le__(self, other):
        if isinstance(other, Time):
            return self.__cmp(other) <= 0
        else:
            _cmperror(self, other)

    def __lt__(self, other):
        if isinstance(other, Time):
            return self.__cmp(other) < 0
        else:
            _cmperror(self, other)

    def __ge__(self, other):
        if isinstance(other, Time):
            return self.__cmp(other) >= 0
        else:
            _cmperror(self, other)

    def __gt__(self, other):
        if isinstance(other, Time):
            return self.__cmp(other) > 0
        else:
            _cmperror(self, other)

    def __cmp(self, other):
        assert isinstance(other, Time)
        mytz = self._TzInfo
        ottz = other._TzInfo
        myoff = otoff = None

        if mytz is ottz:
            base_compare = True
        else:
            myoff = self._utcoffset()
            otoff = other._utcoffset()
            base_compare = myoff == otoff

        if base_compare:
            return cmp((self.__hour, self.__minute, self.__second,
                        self.__microsecond),
                       (other.__hour, other.__minute, other.__second,
                        other.__microsecond))
        if myoff is None or otoff is None:
            # XXX Buggy in 2.2.2.
            raise TypeError("cannot compare naive and aware Times")
        myhhmm = self.__hour * 60 + self.__minute - myoff
        othhmm = other.__hour * 60 + other.__minute - otoff
        return cmp((myhhmm, self.__second, self.__microsecond),
                   (othhmm, other.__second, other.__microsecond))

    def __hash__(self):
        """Hash."""
        tzoff = self._utcoffset()
        if not tzoff: # zero or None
            return hash(self.__getstate()[0])
        h, m = divmod(self.hour * 60 + self.minute - tzoff, 60)
        if 0 <= h < 24:
            return hash(Time(h, m, self.second, self.microsecond))
        return hash((h, m, self.second, self.microsecond))

    # Conversion to string

    def _tzstr(self, sep=":"):
        """Return formatted Timezone offset (+xx:xx) or None."""
        off = self._utcoffset()
        if off is not None:
            if off < 0:
                sign = "-"
                off = -off
            else:
                sign = "+"
            hh, mm = divmod(off, 60)
            assert 0 <= hh < 24
            off = "%s%02d%s%02d" % (sign, hh, sep, mm)
        return off

    def __repr__(self):
        """Convert to formal string, for repr()."""
        if self.__microsecond != 0:
            s = ", %d, %d" % (self.__second, self.__microsecond)
        elif self.__second != 0:
            s = ", %d" % self.__second
        else:
            s = ""
        s= "%s(%d, %d%s)" % ('DateTime.' + self.__class__.__name__,
                             self.__hour, self.__minute, s)
        if self._TzInfo is not None:
            assert s[-1:] == ")"
            s = s[:-1] + ", TzInfo=%r" % self._TzInfo + ")"
        return s

    def isoformat(self):
        """Return the Time formatted according to ISO.

        This is 'HH:MM:SS.mmmmmm+zz:zz', or 'HH:MM:SS+zz:zz' if
        self.microsecond == 0.
        """
        s = _format_Time(self.__hour, self.__minute, self.__second,
                         self.__microsecond)
        tz = self._tzstr()
        if tz:
            s += tz
        return s

    __str__ = isoformat

    def strfTime(self, fmt):
        """Format using strfTime().  The Date part of the Timestamp passed
        to underlying strfTime should not be used.
        """
        # The year must be >= 1900 else Python's strfTime implementation
        # can raise a bogus exception.
        Timetuple = (1900, 1, 1,
                     self.__hour, self.__minute, self.__second,
                     0, 1, -1)
        return _wrap_strfTime(self, fmt, Timetuple)

    def __format__(self, fmt):
        if len(fmt) != 0:
            return self.strfTime(fmt)
        return str(self)

    # Timezone functions

    def utcoffset(self):
        """Return the Timezone offset in minutes east of UTC (negative west of
        UTC)."""
        offset = _call_TzInfo_method(self._TzInfo, "utcoffset", None)
        offset = _check_utc_offset("utcoffset", offset)
        if offset is not None:
            offset = TimeDelta(minutes=offset)
        return offset

    # Return an integer (or None) instead of a TimeDelta (or None).
    def _utcoffset(self):
        offset = _call_TzInfo_method(self._TzInfo, "utcoffset", None)
        offset = _check_utc_offset("utcoffset", offset)
        return offset

    def tzname(self):
        """Return the Timezone name.

        Note that the name is 100% informational -- there's no requirement that
        it mean anything in particular. For example, "GMT", "UTC", "-500",
        "-5:00", "EDT", "US/Eastern", "America/New York" are all valid replies.
        """
        name = _call_TzInfo_method(self._TzInfo, "tzname", None)
        _check_tzname(name)
        return name

    def dst(self):
        """Return 0 if DST is not in effect, or the DST offset (in minutes
        eastward) if DST is in effect.

        This is purely informational; the DST offset has already been added to
        the UTC offset returned by utcoffset() if applicable, so there's no
        need to consult dst() unless you're interested in displaying the DST
        info.
        """
        offset = _call_TzInfo_method(self._TzInfo, "dst", None)
        offset = _check_utc_offset("dst", offset)
        if offset is not None:
            offset = TimeDelta(minutes=offset)
        return offset

    def replace(self, hour=None, minute=None, second=None, microsecond=None,
                TzInfo=True):
        """Return a new Time with new values for the specified fields."""
        if hour is None:
            hour = self.hour
        if minute is None:
            minute = self.minute
        if second is None:
            second = self.second
        if microsecond is None:
            microsecond = self.microsecond
        if TzInfo is True:
            TzInfo = self.TzInfo
        _check_Time_fields(hour, minute, second, microsecond)
        _check_TzInfo_arg(TzInfo)
        return Time(hour, minute, second, microsecond, TzInfo)

    # Return an integer (or None) instead of a TimeDelta (or None).
    def _dst(self):
        offset = _call_TzInfo_method(self._TzInfo, "dst", None)
        offset = _check_utc_offset("dst", offset)
        return offset

    def __nonzero__(self):
        if self.second or self.microsecond:
            return 1
        offset = self._utcoffset() or 0
        return self.hour * 60 + self.minute - offset != 0

    # Pickle support.

    __safe_for_unpickling__ = True      # For Python 2.2

    def __getstate(self):
        us2, us3 = divmod(self.__microsecond, 256)
        us1, us2 = divmod(us2, 256)
        basestate = ("%c" * 6) % (self.__hour, self.__minute, self.__second,
                                  us1, us2, us3)
        if self._TzInfo is None:
            return (basestate,)
        else:
            return (basestate, self._TzInfo)

    def __setstate(self, string, TzInfo):
        if len(string) != 6 or ord(string[0]) >= 24:
            raise TypeError("an integer is required")
        self.__hour, self.__minute, self.__second, us1, us2, us3 = \
                                                            map(ord, string)
        self.__microsecond = (((us1 << 8) | us2) << 8) | us3
        self._TzInfo = TzInfo

    def __reduce__(self):
        return (Time, self.__getstate())

_time_class = Time  # so functions w/ args named "Time" can get at the class

Time.min = Time(0, 0, 0)
Time.max = Time(23, 59, 59)
Time.resolution = TimeDelta(seconds=10**-9)

class DateTime(Date):

    # XXX needs docstrings
    # See http://www.zope.org/Members/fdrake/DateTimeWiki/TimeZoneInfo

    def __new__(cls, year, month=None, day=None, hour=0, minute=0,
                second=0, tzinfo=None):
        if isinstance(year, str):
            # Pickle support
            self = Date.__new__(cls, year[:4])
            self.__setstate(year, month)
            return self
        _check_TzInfo_arg(tzinfo)
        _check_Time_fields(hour, minute, second)
        self = Date.__new__(cls, year, month, day)
        # XXX This duplicates __year, __month, __day for convenience :-(
        self.__year = year
        self.__month = month
        self.__day = day
        self.__hour = hour
        self.__minute = minute
        self.__second = Decimal(second)
        self._tzinfo = tzinfo
        return self

    # Read-only field accessors
    hour = property(lambda self: self.__hour, doc="hour (0-23)")
    minute = property(lambda self: self.__minute, doc="minute (0-59)")
    second = property(lambda self: self.__second, doc="second (0-59)")
    tzinfo = property(lambda self: self._TzInfo, doc="Timezone info object")

    def fromTimestamp(cls, t, tz=None):
        """Construct a DateTime from a POSIX Timestamp (like Time.Time()).

        A Timezone info object may be passed in as well.
        """

        _check_TzInfo_arg(tz)
        if tz is None:
            converter = _Time.localTime
        else:
            converter = _Time.gmTime
        if 1 - (t % 1.0) < 0.000001:
            t = float(int(t)) + 1
        if t < 0:
            t -= 1
        y, m, d, hh, mm, ss, weekday, jday, dst = converter(t)
        us = int((t % 1.0) * 1000000)
        ss = min(ss, 59)    # clamp out leap seconds if the platform has them
        result = cls(y, m, d, hh, mm, ss, us, tz)
        if tz is not None:
            result = tz.fromutc(result)
        return result
    fromTimestamp = classmethod(fromTimestamp)

    def utcfromTimestamp(cls, t):
        "Construct a UTC DateTime from a POSIX Timestamp (like Time.Time())."
        if 1 - (t % 1.0) < 0.000001:
            t = float(int(t)) + 1
        if t < 0:
            t -= 1
        y, m, d, hh, mm, ss, weekday, jday, dst = _Time.gmTime(t)
        us = int((t % 1.0) * 1000000)
        ss = min(ss, 59)    # clamp out leap seconds if the platform has them
        return cls(y, m, d, hh, mm, ss, us)
    utcfromTimestamp = classmethod(utcfromTimestamp)

    # XXX This is supposed to do better than we *can* do by using Time.Time(),
    # XXX if the platform supports a more accurate way.  The C implementation
    # XXX uses getTimeofday on platforms that have it, but that isn't
    # XXX available from Python.  So now() may return different results
    # XXX across the implementations.
    def now(cls, tz=None):
        "Construct a DateTime from Time.Time() and optional Time zone info."
        t = _Time.Time()
        return cls.fromTimestamp(t, tz)
    now = classmethod(now)

    def utcnow(cls):
        "Construct a UTC DateTime from Time.Time()."
        t = _Time.Time()
        return cls.utcfromTimestamp(t)
    utcnow = classmethod(utcnow)

    def combine(cls, Date, Time):
        "Construct a DateTime from a given Date and a given Time."
        if not isinstance(Date, _Date_class):
            raise TypeError("Date argument must be a Date instance")
        if not isinstance(Time, _Time_class):
            raise TypeError("Time argument must be a Time instance")
        return cls(Date.year, Date.month, Date.day,
                   Time.hour, Time.minute, Time.second, Time.microsecond,
                   Time.TzInfo)
    combine = classmethod(combine)

    def Timetuple(self):
        "Return local Time tuple compatible with Time.localTime()."
        dst = self._dst()
        if dst is None:
            dst = -1
        elif dst:
            dst = 1
        return _build_struct_Time(self.year, self.month, self.day,
                                  self.hour, self.minute, self.second,
                                  dst)

    def utcTimetuple(self):
        "Return UTC Time tuple compatible with Time.gmTime()."
        y, m, d = self.year, self.month, self.day
        hh, mm, ss = self.hour, self.minute, self.second
        offset = self._utcoffset()
        if offset:  # neither None nor 0
            tm = tmxxx(y, m, d, hh, mm - offset)
            y, m, d = tm.year, tm.month, tm.day
            hh, mm = tm.hour, tm.minute
        return _build_struct_Time(y, m, d, hh, mm, ss, 0)

    def Date(self):
        "Return the Date part."
        return Date(self.__year, self.__month, self.__day)

    def Time(self):
        "Return the Time part, with TzInfo None."
        return Time(self.hour, self.minute, self.second, self.microsecond)

    def Timetz(self):
        "Return the Time part, with same TzInfo."
        return Time(self.hour, self.minute, self.second, self.microsecond,
                    self._TzInfo)

    def replace(self, year=None, month=None, day=None, hour=None,
                minute=None, second=None, microsecond=None, TzInfo=True):
        """Return a new DateTime with new values for the specified fields."""
        if year is None:
            year = self.year
        if month is None:
            month = self.month
        if day is None:
            day = self.day
        if hour is None:
            hour = self.hour
        if minute is None:
            minute = self.minute
        if second is None:
            second = self.second
        if microsecond is None:
            microsecond = self.microsecond
        if TzInfo is True:
            TzInfo = self.TzInfo
        _check_Date_fields(year, month, day)
        _check_Time_fields(hour, minute, second, microsecond)
        _check_TzInfo_arg(TzInfo)
        return DateTime(year, month, day, hour, minute, second,
                          microsecond, TzInfo)

    def asTimezone(self, tz):
        if not isinstance(tz, TzInfo):
            raise TypeError("tz argument must be an instance of TzInfo")

        mytz = self.TzInfo
        if mytz is None:
            raise ValueError("asTimezone() requires an aware DateTime")

        if tz is mytz:
            return self

        # Convert self to UTC, and attach the new Time zone object.
        myoffset = self.utcoffset()
        if myoffset is None:
            raise ValuError("asTimezone() requires an aware DateTime")
        utc = (self - myoffset).replace(TzInfo=tz)

        # Convert from UTC to tz's local Time.
        return tz.fromutc(utc)

    # Ways to produce a string.

    def cTime(self):
        "Format a la cTime()."
        t = tmxxx(self.__year, self.__month, self.__day, self.__hour,
                  self.__minute, self.__second)
        return t.cTime()

    def isoformat(self, sep='T'):
        """Return the Time formatted according to ISO.

        This is 'YYYY-MM-DD HH:MM:SS.mmmmmm', or 'YYYY-MM-DD HH:MM:SS' if
        self.microsecond == 0.

        If self.TzInfo is not None, the UTC offset is also attached, giving
        'YYYY-MM-DD HH:MM:SS.mmmmmm+HH:MM' or 'YYYY-MM-DD HH:MM:SS+HH:MM'.

        Optional argument sep specifies the separator between Date and
        Time, default 'T'.
        """
        s = ("%04d-%02d-%02d%c" % (self.__year, self.__month, self.__day,
                                  sep) +
                _format_Time(self.__hour, self.__minute, self.__second,
                             self.__microsecond))
        off = self._utcoffset()
        if off is not None:
            if off < 0:
                sign = "-"
                off = -off
            else:
                sign = "+"
            hh, mm = divmod(off, 60)
            s += "%s%02d:%02d" % (sign, hh, mm)
        return s

    def __repr__(self):
        "Convert to formal string, for repr()."
        L = [self.__year, self.__month, self.__day, # These are never zero
             self.__hour, self.__minute, self.__second, self.__microsecond]
        if L[-1] == 0:
            del L[-1]
        if L[-1] == 0:
            del L[-1]
        s = ", ".join(map(str, L))
        s = "%s(%s)" % ('DateTime.' + self.__class__.__name__, s)
        if self._TzInfo is not None:
            assert s[-1:] == ")"
            s = s[:-1] + ", TzInfo=%r" % self._TzInfo + ")"
        return s

    def __str__(self):
        "Convert to string, for str()."
        return self.isoformat(sep=' ')

    @classmethod
    def strpTime(cls, Date_string, format):
        'string, format -> new DateTime parsed from a string (like Time.strpTime()).'
        import _strpTime
        tt, us = _strpTime._strpTime(Date_string, format)
        return cls(*(tt[0:6] + (us,)))

    def utcoffset(self):
        """Return the Timezone offset in minutes east of UTC (negative west of
        UTC)."""
        offset = _call_TzInfo_method(self._TzInfo, "utcoffset", self)
        offset = _check_utc_offset("utcoffset", offset)
        if offset is not None:
            offset = TimeDelta(minutes=offset)
        return offset

    # Return an integer (or None) instead of a TimeDelta (or None).
    def _utcoffset(self):
        offset = _call_TzInfo_method(self._TzInfo, "utcoffset", self)
        offset = _check_utc_offset("utcoffset", offset)
        return offset

    def tzname(self):
        """Return the Timezone name.

        Note that the name is 100% informational -- there's no requirement that
        it mean anything in particular. For example, "GMT", "UTC", "-500",
        "-5:00", "EDT", "US/Eastern", "America/New York" are all valid replies.
        """
        name = _call_TzInfo_method(self._TzInfo, "tzname", self)
        _check_tzname(name)
        return name

    def dst(self):
        """Return 0 if DST is not in effect, or the DST offset (in minutes
        eastward) if DST is in effect.

        This is purely informational; the DST offset has already been added to
        the UTC offset returned by utcoffset() if applicable, so there's no
        need to consult dst() unless you're interested in displaying the DST
        info.
        """
        offset = _call_TzInfo_method(self._TzInfo, "dst", self)
        offset = _check_utc_offset("dst", offset)
        if offset is not None:
            offset = TimeDelta(minutes=offset)
        return offset

    # Return an integer (or None) instead of a TimeDelta (or None).1573
    def _dst(self):
        offset = _call_TzInfo_method(self._TzInfo, "dst", self)
        offset = _check_utc_offset("dst", offset)
        return offset

    # Comparisons.

    def __eq__(self, other):
        if isinstance(other, DateTime):
            return self.__cmp(other) == 0
        elif hasattr(other, "Timetuple") and not isinstance(other, Date):
            return NotImplemented
        else:
            return False

    def __ne__(self, other):
        if isinstance(other, DateTime):
            return self.__cmp(other) != 0
        elif hasattr(other, "Timetuple") and not isinstance(other, Date):
            return NotImplemented
        else:
            return True

    def __le__(self, other):
        if isinstance(other, DateTime):
            return self.__cmp(other) <= 0
        elif hasattr(other, "Timetuple") and not isinstance(other, Date):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __lt__(self, other):
        if isinstance(other, DateTime):
            return self.__cmp(other) < 0
        elif hasattr(other, "Timetuple") and not isinstance(other, Date):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __ge__(self, other):
        if isinstance(other, DateTime):
            return self.__cmp(other) >= 0
        elif hasattr(other, "Timetuple") and not isinstance(other, Date):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __gt__(self, other):
        if isinstance(other, DateTime):
            return self.__cmp(other) > 0
        elif hasattr(other, "Timetuple") and not isinstance(other, Date):
            return NotImplemented
        else:
            _cmperror(self, other)

    def __cmp(self, other):
        assert isinstance(other, DateTime)
        mytz = self._TzInfo
        ottz = other._TzInfo
        myoff = otoff = None

        if mytz is ottz:
            base_compare = True
        else:
            if mytz is not None:
                myoff = self._utcoffset()
            if ottz is not None:
                otoff = other._utcoffset()
            base_compare = myoff == otoff

        if base_compare:
            return cmp((self.__year, self.__month, self.__day,
                        self.__hour, self.__minute, self.__second,
                        self.__microsecond),
                       (other.__year, other.__month, other.__day,
                        other.__hour, other.__minute, other.__second,
                        other.__microsecond))
        if myoff is None or otoff is None:
            # XXX Buggy in 2.2.2.
            raise TypeError("cannot compare naive and aware DateTimes")
        # XXX What follows could be done more efficiently...
        diff = self - other     # this will take offsets into account
        if diff.days < 0:
            return -1
        return diff and 1 or 0

    def __add__(self, other):
        "Add a DateTime and a TimeDelta."
        if not isinstance(other, TimeDelta):
            return NotImplemented
        t = tmxxx(self.__year,
                  self.__month,
                  self.__day + other.days,
                  self.__hour,
                  self.__minute,
                  self.__second + other.seconds,
                  self.__microsecond + other.microseconds)
        self._checkOverflow(t.year)
        result = DateTime(t.year, t.month, t.day,
                                t.hour, t.minute, t.second,
                                t.microsecond, TzInfo=self._TzInfo)
        return result

    __radd__ = __add__

    def __sub__(self, other):
        "Subtract two DateTimes, or a DateTime and a TimeDelta."
        if not isinstance(other, DateTime):
            if isinstance(other, TimeDelta):
                return self + -other
            return NotImplemented

        days1 = self.toordinal()
        days2 = other.toordinal()
        secs1 = self.__second + self.__minute * 60 + self.__hour * 3600
        secs2 = other.__second + other.__minute * 60 + other.__hour * 3600
        base = TimeDelta(days1 - days2,
                         secs1 - secs2,
                         self.__microsecond - other.__microsecond)
        if self._TzInfo is other._TzInfo:
            return base
        myoff = self._utcoffset()
        otoff = other._utcoffset()
        if myoff == otoff:
            return base
        if myoff is None or otoff is None:
            raise TypeError, "cannot mix naive and Timezone-aware Time"
        return base + TimeDelta(minutes = otoff-myoff)

    def __hash__(self):
        tzoff = self._utcoffset()
        if tzoff is None:
            return hash(self.__getstate()[0])
        days = _ymd2ord(self.year, self.month, self.day)
        seconds = self.hour * 3600 + (self.minute - tzoff) * 60 + self.second
        return hash(TimeDelta(days, seconds, self.microsecond))

    # Pickle support.

    __safe_for_unpickling__ = True      # For Python 2.2

    def __getstate(self):
        yhi, ylo = divmod(self.__year, 256)
        us2, us3 = divmod(self.__microsecond, 256)
        us1, us2 = divmod(us2, 256)
        basestate = ("%c" * 10) % (yhi, ylo, self.__month, self.__day,
                                   self.__hour, self.__minute, self.__second,
                                   us1, us2, us3)
        if self._TzInfo is None:
            return (basestate,)
        else:
            return (basestate, self._TzInfo)

    def __setstate(self, string, TzInfo):
        (yhi, ylo, self.__month, self.__day, self.__hour,
         self.__minute, self.__second, us1, us2, us3) = map(ord, string)
        self.__year = yhi * 256 + ylo
        self.__microsecond = (((us1 << 8) | us2) << 8) | us3
        self._TzInfo = TzInfo

    def __reduce__(self):
        return (self.__class__, self.__getstate())


DateTime.min = DateTime(1, 1, 1)
DateTime.max = DateTime(9999, 12, 31, 23, 59, 59)
DateTime.resolution = TimeDelta(seconds=10**-9)


def _isoweek1monday(year):
    # Helper to calculate the day number of the Monday starting week 1
    # XXX This could be done more efficiently
    THURSDAY = 3
    firstday = _ymd2ord(year, 1, 1)
    firstweekday = (firstday + 6) % 7 # See weekday() above
    week1monday = firstday - firstweekday
    if firstweekday > THURSDAY:
        week1monday += 7
    return week1monday

"""
Some Time zone algebra.  For a DateTime x, let
    x.n = x stripped of its Timezone -- its naive Time.
    x.o = x.utcoffset(), and assuming that doesn't raise an exception or
          return None
    x.d = x.dst(), and assuming that doesn't raise an exception or
          return None
    x.s = x's standard offset, x.o - x.d

Now some derived rules, where k is a duration (TimeDelta).

1. x.o = x.s + x.d
   This follows from the definition of x.s.

2. If x and y have the same TzInfo member, x.s = y.s.
   This is actually a requirement, an assumption we need to make about
   sane TzInfo classes.

3. The naive UTC Time corresponding to x is x.n - x.o.
   This is again a requirement for a sane TzInfo class.

4. (x+k).s = x.s
   This follows from #2, and that daTimeTimetz+TimeDelta preserves TzInfo.

5. (x+k).n = x.n + k
   Again follows from how arithmetic is defined.

Now we can explain tz.fromutc(x).  Let's assume it's an interesting case
(meaning that the various TzInfo methods exist, and don't blow up or return
None when called).

The function wants to return a DateTime y with Timezone tz, equivalent to x.
x is already in UTC.

By #3, we want

    y.n - y.o = x.n                             [1]

The algorithm starts by attaching tz to x.n, and calling that y.  So
x.n = y.n at the start.  Then it wants to add a duration k to y, so that [1]
becomes true; in effect, we want to solve [2] for k:

   (y+k).n - (y+k).o = x.n                      [2]

By #1, this is the same as

   (y+k).n - ((y+k).s + (y+k).d) = x.n          [3]

By #5, (y+k).n = y.n + k, which equals x.n + k because x.n=y.n at the start.
Substituting that into [3],

   x.n + k - (y+k).s - (y+k).d = x.n; the x.n terms cancel, leaving
   k - (y+k).s - (y+k).d = 0; rearranging,
   k = (y+k).s - (y+k).d; by #4, (y+k).s == y.s, so
   k = y.s - (y+k).d

On the RHS, (y+k).d can't be computed directly, but y.s can be, and we
approximate k by ignoring the (y+k).d term at first.  Note that k can't be
very large, since all offset-returning methods return a duration of magnitude
less than 24 hours.  For that reason, if y is firmly in std Time, (y+k).d must
be 0, so ignoring it has no consequence then.

In any case, the new value is

    z = y + y.s                                 [4]

It's helpful to step back at look at [4] from a higher level:  it's simply
mapping from UTC to tz's standard Time.

At this point, if

    z.n - z.o = x.n                             [5]

we have an equivalent Time, and are almost done.  The insecurity here is
at the start of daylight Time.  Picture US Eastern for concreteness.  The wall
Time jumps from 1:59 to 3:00, and wall hours of the form 2:MM don't make good
sense then.  The docs ask that an Eastern TzInfo class consider such a Time to
be EDT (because it's "after 2"), which is a redundant spelling of 1:MM EST
on the day DST starts.  We want to return the 1:MM EST spelling because that's
the only spelling that makes sense on the local wall clock.

In fact, if [5] holds at this point, we do have the standard-Time spelling,
but that takes a bit of proof.  We first prove a stronger result.  What's the
difference between the LHS and RHS of [5]?  Let

    diff = x.n - (z.n - z.o)                    [6]

Now
    z.n =                       by [4]
    (y + y.s).n =               by #5
    y.n + y.s =                 since y.n = x.n
    x.n + y.s =                 since z and y are have the same TzInfo member,
                                    y.s = z.s by #2
    x.n + z.s

Plugging that back into [6] gives

    diff =
    x.n - ((x.n + z.s) - z.o) =     expanding
    x.n - x.n - z.s + z.o =         cancelling
    - z.s + z.o =                   by #2
    z.d

So diff = z.d.

If [5] is true now, diff = 0, so z.d = 0 too, and we have the standard-Time
spelling we wanted in the endcase described above.  We're done.  Contrarily,
if z.d = 0, then we have a UTC equivalent, and are also done.

If [5] is not true now, diff = z.d != 0, and z.d is the offset we need to
add to z (in effect, z is in tz's standard Time, and we need to shift the
local clock into tz's daylight Time).

Let

    z' = z + z.d = z + diff                     [7]

and we can again ask whether

    z'.n - z'.o = x.n                           [8]

If so, we're done.  If not, the TzInfo class is insane, according to the
assumptions we've made.  This also requires a bit of proof.  As before, let's
compute the difference between the LHS and RHS of [8] (and skipping some of
the justifications for the kinds of substitutions we've done several Times
already):

    diff' = x.n - (z'.n - z'.o) =           replacing z'.n via [7]
            x.n  - (z.n + diff - z'.o) =    replacing diff via [6]
            x.n - (z.n + x.n - (z.n - z.o) - z'.o) =
            x.n - z.n - x.n + z.n - z.o + z'.o =    cancel x.n
            - z.n + z.n - z.o + z'.o =              cancel z.n
            - z.o + z'.o =                      #1 twice
            -z.s - z.d + z'.s + z'.d =          z and z' have same TzInfo
            z'.d - z.d

So z' is UTC-equivalent to x iff z'.d = z.d at this point.  If they are equal,
we've found the UTC-equivalent so are done.  In fact, we stop with [7] and
return z', not bothering to compute z'.d.

How could z.d and z'd differ?  z' = z + z.d [7], so merely moving z' by
a dst() offset, and starting *from* a Time already in DST (we know z.d != 0),
would have to change the result dst() returns:  we start in DST, and moving
a little further into it takes us out of DST.

There isn't a sane case where this can happen.  The closest it gets is at
the end of DST, where there's an hour in UTC with no spelling in a hybrid
TzInfo class.  In US Eastern, that's 5:MM UTC = 0:MM EST = 1:MM EDT.  During
that hour, on an Eastern clock 1:MM is taken as being in standard Time (6:MM
UTC) because the docs insist on that, but 0:MM is taken as being in daylight
Time (4:MM UTC).  There is no local Time mapping to 5:MM UTC.  The local
clock jumps from 1:59 back to 1:00 again, and repeats the 1:MM hour in
standard Time.  Since that's what the local clock *does*, we want to map both
UTC hours 5:MM and 6:MM to 1:MM Eastern.  The result is ambiguous
in local Time, but so it goes -- it's the way the local clock works.

When x = 5:MM UTC is the input to this algorithm, x.o=0, y.o=-5 and y.d=0,
so z=0:MM.  z.d=60 (minutes) then, so [5] doesn't hold and we keep going.
z' = z + z.d = 1:MM then, and z'.d=0, and z'.d - z.d = -60 != 0 so [8]
(correctly) concludes that z' is not UTC-equivalent to x.

Because we know z.d said z was in daylight Time (else [5] would have held and
we would have stopped then), and we know z.d != z'.d (else [8] would have held
and we we have stopped then), and there are only 2 possible values dst() can
return in Eastern, it follows that z'.d must be 0 (which it is in the example,
but the reasoning doesn't depend on the example -- it depends on there being
two possible dst() outcomes, one zero and the other non-zero).  Therefore
z' must be in standard Time, and is the spelling we want in this case.

Note again that z' is not UTC-equivalent as far as the hybrid TzInfo class is
concerned (because it takes z' as being in standard Time rather than the
daylight Time we intend here), but returning it gives the real-life "local
clock repeats an hour" behavior when mapping the "unspellable" UTC hour into
tz.

When the input is 6:MM, z=1:MM and z.d=0, and we stop at once, again with
the 1:MM standard Time spelling we want.

So how can this break?  One of the assumptions must be violated.  Two
possibilities:

1) [2] effectively says that y.s is invariant across all y belong to a given
   Time zone.  This isn't true if, for political reasons or continental drift,
   a region decides to change its base offset from UTC.

2) There may be versions of "double daylight" Time where the tail end of
   the analysis gives up a step too early.  I haven't thought about that
   enough to say.

In any case, it's clear that the default fromutc() is strong enough to handle
"almost all" Time zones:  so long as the standard offset is invariant, it
doesn't matter if daylight Time transition points change from year to year, or
if daylight Time is skipped in some years; it doesn't matter how large or
small dst() may get within its bounds; and it doesn't even matter if some
perverse Time zone returns a negative dst()).  So a breaking case must be
pretty bizarre, and a TzInfo subclass can override fromutc() if it is.
"""

