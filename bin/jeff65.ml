(* jeff65 command-line driver
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

open! Containers
open! Astring
open Jeff65_kernel
open Cmdliner

module Common_opts = struct
  type t = { debug_opts : string list }
end

let help_secs = [
  `S Manpage.s_common_options;
  `P "These options are common to all commands.";
  `S "MORE HELP";
  `P "Use `$(mname) $(i,COMMAND) --help' for help on a single command.";
]

let copts debug_opts = { Common_opts.debug_opts }
let copts_t =
  let docs = Manpage.s_common_options in
  let debugopts =
    let doc = "Enable compiler debugging options." in
    Arg.(value & opt_all string [] & info ["Z"] ~docs ~doc)
  in
  Term.(const copts $ debugopts)

let convert_path path =
  match Fpath.of_string path with
  | Error (`Msg e) -> Or_error.of_string e
  | Ok _ as ok -> ok

let out_path_of in_path out_path =
  Option.map convert_path out_path
  |> Option.get_lazy (fun () -> Ok Fpath.(in_path + ".gold"))

let shorten_path root path =
  let open Result.Infix in
  convert_path path >>= (fun path ->
      Fpath.relativize ~root path
      |> Option.get_or ~default:path
      |> Fpath.to_string
      |> Result.return)

let shorten_loc root = function
  | None -> Ok None
  | Some (start, finish) ->
    let bind = Result.(>>=) in
    let%m start_fname = shorten_path root start.Lexing.pos_fname in
    let%m finish_fname = shorten_path root finish.Lexing.pos_fname in
    Result.return (Some ( { start with pos_fname = start_fname }
                        , { finish with pos_fname = finish_fname }
                        ))

let shorten_locs errs =
  let bind = Result.(>>=) in
  let%m root = Sys.getcwd () |> convert_path in
  match errs with
  | Ok _ as ok -> ok
  | Error errs ->
    Or_error.get errs
    |> List.map (fun (loc, msg) ->
        let%m loc = shorten_loc root loc in
        Ok (loc, msg))
    |> Or_error.all_ok
    |> function
    | Ok e -> Or_error.of_lit e
    | Error _ as e -> e

let compile copts in_path out_path =
  let bind = (Result.(>>=)) in
  begin
    let%m cwd = Sys.getcwd () |> convert_path in
    let%m debug_opts = Gold.Debug_opts.t_of_string_list copts.Common_opts.debug_opts in
    let%m in_path = convert_path in_path in
    let%m out_path = out_path_of in_path out_path in
    Gold.compile { in_path = Fpath.(cwd // in_path |> normalize)
                 ; out_path = Fpath.(cwd // out_path |> normalize)
                 ; debug_opts
                 }
  end
  |> shorten_locs
  |> Or_error.pp Ast.span_pp Format.stderr

let compile_cmd =
  let in_path_t =
    let doc = "The file to compile." in
    Arg.(required & pos 0 (some file) None & info [] ~doc ~docv:"FILE")
  in
  let out_path_t =
    let doc = "Place the output into OUTPUT" in
    Arg.(value & opt (some file) None & info ["o"; "output"] ~docv:"OUTPUT" ~doc)
  in
  let doc = "Compile a source file" in
  Term.(const compile $ copts_t $ in_path_t $ out_path_t),
  Term.info "compile" ~doc

let default_cmd =
  let sdocs = Manpage.s_common_options in
  let man = help_secs in
  Term.(ret (const (fun _ -> `Help (`Pager, None)) $ copts_t)),
  Term.info "jeff65" ~sdocs ~man

let () = Term.exit @@ Term.eval_choice default_cmd [compile_cmd]

