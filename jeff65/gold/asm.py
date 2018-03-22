# jeff65 gold-syntax assembler passes
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

import struct
from . import ast, storage


class AssemblyError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AsmRun:
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return "<asm {}>".format(self.data)


class AssembleWithRelocations(ast.TranslationPass):
    def enter_lda(self, node):
        s = node.attrs['storage']
        if type(s) is storage.ImmediateStorage:
            if s.width != 1:
                raise AssemblyError(
                    "LDA loads one byte ({} given)".format(s.width))
            return AsmRun(struct.pack("<BB", 0xa9, s.value))
        raise NotImplementedError()

    def enter_sta(self, node):
        s = node.attrs['storage']
        if type(s) is storage.AbsoluteStorage:
            if s.width != 1:
                raise AssemblyError(
                    "STA stores one byte ({} given)".format(s.width))
            return AsmRun(struct.pack("<BH", 0x8d, s.address))
        raise NotImplementedError()

    def enter_jmp(self, node):
        s = node.attrs['storage']
        if type(s) is storage.AbsoluteStorage:
            return AsmRun(struct.pack("<BH", 0x4c, s.address))
        raise NotImplementedError()

    def enter_rts(self, node):
        return AsmRun(bytes([0x60]))


class FlattenSymbol(ast.TranslationPass):
    def exit_fun(self, node):
        data = []
        for c in node.children:
            data.append(c.data)

        sym = ast.AstNode('fun_symbol', node.position, {
            'name': node.attrs['name'],
            'type': node.attrs['type'],
            'text': b"".join(data),
        })

        if 'return_addr' in node.attrs:
            sym.attrs['return_addr'] = node.attrs['return_addr']

        return sym

    def exit_unit(self, node):
        node = node.clone()
        del node.attrs['known_names']
        return node


def lda(position, arg):
    assert type(arg) is storage.ImmediateStorage
    return ast.AstNode('lda', position, attrs={
        'storage': arg,
        'size': 2,
    })


def sta(position, arg):
    assert type(arg) is storage.AbsoluteStorage
    return ast.AstNode('sta', position, attrs={
        'storage': arg,
        'size': 3,
    })


def jmp(position, arg):
    assert type(arg) is storage.AbsoluteStorage
    return ast.AstNode('jmp', position, attrs={
        'storage': arg,
        'size': 3,
    })


def rts(position):
    return ast.AstNode('rts', position, attrs={
        'size': 1,
    })
