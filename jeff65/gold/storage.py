# jeff65 gold-syntax storage classes
# Copyright (C) 2018  jeff65 maintainers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


class AbsoluteStorage:
    def __init__(self, address, width):
        self.address = address
        self.width = width

    def __repr__(self):
        return "<{} bytes at ${:x}>".format(self.width, self.address)


class ImmediateStorage:
    def __init__(self, value, width):
        self.value = value
        self.width = width

    def __repr__(self):
        return "<immediate {} bytes = ${:x}>".format(self.width, self.value)
