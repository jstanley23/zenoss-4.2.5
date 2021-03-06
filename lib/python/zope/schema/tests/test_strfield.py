##############################################################################
#
# Copyright (c) 2001, 2002 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""String field tests
"""
from unittest import TestSuite, main, makeSuite
from six import b, u
from zope.schema import Bytes, BytesLine, Text, TextLine, Password
from zope.schema.interfaces import ValidationError, WrongType
from zope.schema.interfaces import RequiredMissing, InvalidValue
from zope.schema.interfaces import TooShort, TooLong, ConstraintNotSatisfied
from zope.schema.tests.test_field import FieldTestBase

class StrTest(FieldTestBase):
    """Test the Str Field."""

    def testValidate(self):
        field = self._Field_Factory(title=u('Str field'), description=u(''),
                                    readonly=False, required=False)
        field.validate(None)
        field.validate(self._convert('foo'))
        field.validate(self._convert(''))

    def testValidateRequired(self):

        # Note that if we want to require non-empty strings,
        # we need to set the min-length to 1.

        field = self._Field_Factory(
            title=u('Str field'), description=u(''),
            readonly=False, required=True, min_length=1)
        field.validate(self._convert('foo'))

        self.assertRaises(RequiredMissing, field.validate, None)
        self.assertRaises(TooShort, field.validate, self._convert(''))

    def testValidateMinLength(self):
        field = self._Field_Factory(
            title=u('Str field'), description=u(''),
            readonly=False, required=False, min_length=3)
        field.validate(None)
        field.validate(self._convert('333'))
        field.validate(self._convert('55555'))

        self.assertRaises(TooShort, field.validate, self._convert(''))
        self.assertRaises(TooShort, field.validate, self._convert('22'))
        self.assertRaises(TooShort, field.validate, self._convert('1'))

    def testValidateMaxLength(self):
        field = self._Field_Factory(
            title=u('Str field'), description=u(''),
            readonly=False, required=False, max_length=5)
        field.validate(None)
        field.validate(self._convert(''))
        field.validate(self._convert('333'))
        field.validate(self._convert('55555'))

        self.assertRaises(TooLong, field.validate, self._convert('666666'))
        self.assertRaises(TooLong, field.validate, self._convert('999999999'))

    def testValidateMinLengthAndMaxLength(self):
        field = self._Field_Factory(
            title=u('Str field'), description=u(''),
            readonly=False, required=False,
            min_length=3, max_length=5)

        field.validate(None)
        field.validate(self._convert('333'))
        field.validate(self._convert('4444'))
        field.validate(self._convert('55555'))

        self.assertRaises(TooShort, field.validate, self._convert('22'))
        self.assertRaises(TooShort, field.validate, self._convert('22'))
        self.assertRaises(TooLong, field.validate, self._convert('666666'))
        self.assertRaises(TooLong, field.validate, self._convert('999999999'))


class MultiLine(object):

    def test_newlines(self):
        field = self._Field_Factory(title=u('Str field'))
        field.validate(self._convert('hello\nworld'))


class BytesTest(StrTest, MultiLine):
    _Field_Factory = Bytes

    def _convert(self, v):
        return b(v)

    def testBadStringType(self):
        field = self._Field_Factory()
        self.assertRaises(ValidationError, field.validate, u('hello'))


class TextTest(StrTest, MultiLine):
    _Field_Factory = Text
    def _convert(self, v):
        return u(v)

    def testBadStringType(self):
        field = self._Field_Factory()
        self.assertRaises(ValidationError, field.validate, b('hello'))

class SingleLine(object):

    def test_newlines(self):
        field = self._Field_Factory(title=u('Str field'))
        self.assertRaises(ConstraintNotSatisfied,
                                    field.validate,
                                    self._convert('hello\nworld'))

class PasswordTest(SingleLine, TextTest):
    _Field_Factory = Password

    def test_existingValue(self):
        class Dummy(object):
            password = None
        dummy = Dummy()

        field = self._Field_Factory(title=u('Str field'), description=u(''),
                                    readonly=False, required=True, __name__='password')
        field = field.bind(dummy)

        # Using UNCHANGED_PASSWORD is not allowed if no password was set yet
        self.assertRaises(WrongType, field.validate, field.UNCHANGED_PASSWORD)

        dummy.password = 'asdf'
        field.validate(field.UNCHANGED_PASSWORD)

        # Using a normal value, the field gets updated
        field.set(dummy, u('test'))
        self.assertEqual(u('test'), dummy.password)

        # Using UNCHANGED_PASSWORD the field is not updated.
        field.set(dummy, field.UNCHANGED_PASSWORD)
        self.assertEqual(u('test'), dummy.password)


class LineTest(SingleLine, BytesTest):
    _Field_Factory = BytesLine

class TextLineTest(SingleLine, TextTest):
    _Field_Factory = TextLine


def test_suite():
    return TestSuite((
        makeSuite(BytesTest),
        makeSuite(TextTest),
        makeSuite(LineTest),
        makeSuite(TextLineTest),
        makeSuite(PasswordTest),
        ))

if __name__ == '__main__':
    main(defaultTest='test_suite')
