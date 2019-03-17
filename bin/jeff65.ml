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
  Fpath.of_string path
  |> Result.map_err (fun (`Msg e) -> [Error.of_string e])

let compile copts in_path out_path =
  let open Gold in
  match
    let open Result in
    Sys.getcwd () |> convert_path >>=
    (fun cwd ->
       Debug_opts.t_of_string_list copts.Common_opts.debug_opts
       |> Result.map_err (fun e -> [e]) >>=
       (fun debug_opts -> convert_path in_path >>=
         (fun in_path -> (match out_path with
              | Some p -> convert_path p
              | None -> Ok Fpath.(in_path + ".gold")) >>=
            (fun out_path -> compile
                { in_path = Fpath.(cwd // in_path |> normalize)
                ; out_path = Fpath.(cwd // out_path |> normalize)
                ; debug_opts
                }))))
  with
  | Error errs -> List.iter (fun e ->
      Printf.fprintf stderr "%s\n" (Error.to_string e)) errs
  | Ok () -> ()

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

