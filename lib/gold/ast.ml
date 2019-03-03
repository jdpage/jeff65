(* jeff65 gold-syntax AST
   Copyright (C) 2019  jeff65 maintainers
   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>. *)

open Sexplib.Std

type position = Lexing.position

let position_of_sexp exp =
  let (pos_fname, pos_lnum, pos_bol, pos_cnum) =
    [%of_sexp: string * int * int * int] exp
  in
  { Lexing.pos_fname; pos_lnum; pos_bol; pos_cnum }

let sexp_of_position pos =
  let { Lexing.pos_fname; pos_lnum; pos_bol; pos_cnum } = pos in
  [%sexp_of: string * int * int * int] (pos_fname, pos_lnum, pos_bol, pos_cnum)

type span = position * position
[@@deriving sexp]

module Spanning = struct
  type 'a t = { node : 'a; span : span }
  [@@deriving fields, sexp]

  let loc (span : span) (node : 'a) : 'a =
    `Spanning { node; span }
end

type storage = Auto | Mut | Stash [@@deriving sexp]

module RefType = struct
  type 'a t = { ty : 'a; storage : storage }
  [@@deriving fields, sexp]
end

module SliceType = struct
  type 'a t = { ty : 'a; storage : storage }
  [@@deriving fields, sexp]
end

module ArrayType = struct
  type ('a, 'b) t = { ty : 'a; storage : storage; range : 'b * 'b }
  [@@deriving fields, sexp]
end

module Typename = struct
  type 'a t =
    | Void
    | Primitive of string
    | Ref of ('a t) RefType.t
    | Slice of ('a t) SliceType.t
    | Array of ('a t, 'a) ArrayType.t
  [@@deriving sexp]
end

module Decl = struct
  type 'a t = { name : string; ty : 'a Typename.t }
  [@@deriving fields, sexp]
end

module ValCall = struct
  type 'a t = { target : 'a; args : 'a list }
  [@@deriving fields, sexp]
end

module StmtUse = struct
  type t = { name : string }
  [@@deriving fields, sexp]
end

module StmtConstant = struct
  type 'a t = { decl : 'a Decl.t; value : 'a }
  [@@deriving fields, sexp]
end

module StmtLet = struct
  type 'a t = { decl : 'a Decl.t; storage : storage; value : 'a }
  [@@deriving fields, sexp]
end

module StmtWhile = struct
  type 'a t = { cond : 'a; body : 'a list }
  [@@deriving fields, sexp]
end

module StmtFor = struct
  type 'a range =
    | Range of 'a * 'a
    | Iter of 'a
  [@@deriving sexp]

  type 'a t = { var : 'a Decl.t; range : 'a range; body : 'a list }
  [@@deriving fields, sexp]
end

module StmtIf = struct
  type 'a branch = { cond : 'a; body : 'a list }
  [@@deriving fields, sexp]

  type 'a t = 'a branch list
  [@@deriving sexp]
end

module StmtIsr = struct
  type 'a t = { name : string; body : 'a list }
  [@@deriving fields, sexp]
end

module StmtAssign = struct
  type 'a t = { lvalue : 'a; rvalue : 'a }
  [@@deriving fields, sexp]
end

module StmtFun = struct
  type 'a t = { name : string
              ; return : 'a Typename.t
              ; params : 'a Decl.t list
              ; body : 'a list
              }
  [@@deriving fields, sexp]
end

module Node = struct
  type t = [
    | `Identifier of string
    | `Boolean of bool
    | `Numeric of string
    | `String of string
    | `Negate of t
    | `Ref of t
    | `Deref of t
    | `Log_not of t
    | `Log_and of t * t
    | `Log_or of t * t
    | `Bit_not of t
    | `Bit_and of t * t
    | `Bit_or of t * t
    | `Bit_xor of t * t
    | `Shl of t * t
    | `Shr of t * t
    | `Add of t * t
    | `Sub of t * t
    | `Mul of t * t
    | `Div of t * t
    | `Cmp_eq of t * t
    | `Cmp_ne of t * t
    | `Cmp_le of t * t
    | `Cmp_ge of t * t
    | `Cmp_lt of t * t
    | `Cmp_gt of t * t
    | `Member_access of t * string
    | `Subscript of t * t
    | `Call of t ValCall.t
    | `Array of t list
    | `Stmt_use of StmtUse.t
    | `Stmt_constant of t StmtConstant.t
    | `Stmt_let of t StmtLet.t
    | `Stmt_while of t StmtWhile.t
    | `Stmt_for of t StmtFor.t
    | `Stmt_if of t StmtIf.t
    | `Stmt_isr of t StmtIsr.t
    | `Stmt_assign of t StmtAssign.t
    | `Stmt_fun of t StmtFun.t
    | `Stmt_expr of t
    | `Stmt_return of t option
    | `Unit of t list
    | `Spanning of t Spanning.t
  ]
  [@@deriving variants, sexp]
end