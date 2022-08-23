#!/usr/bin/python3

from argparse import ArgumentParser, ArgumentTypeError
from colorama import Fore, Style
from datetime import timedelta
from fractions import Fraction
from halo import Halo
from humanize.time import precisedelta
from json import load
from os import mkdir, path, walk, listdir
from pathlib import Path
from re import search
from time import perf_counter

def positive_int(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue

def positive_float(value):
    fvalue = float(value)
    if fvalue <= 0:
        raise ArgumentTypeError(f"{fvalue} is not a positive decimal")
    return fvalue

parser = ArgumentParser(description="Generate tikz graphs from Parameter Lifting input files (coming out of storm, with two variables).")

io_group = parser.add_argument_group("io", description="Arguments to specify inputs and outputs")
io_group.add_argument("--file", "-i", type=str, metavar="file", help="the (singular) input file")
io_group.add_argument("--output-file", "-o", type=str, metavar="file", help="the (singular) output file. If no value is specified and a singular input file is provided, the standard pipe is used for output.")
io_group.add_argument("--input-dir", "-I", type=str, metavar="path", default="./input/", help="the input directory to scan for .regionresult files. No scan is performed, if a singular input file is provided.")
io_group.add_argument("--output-dir", "-O", type=str, metavar="path", default="./output/", help="the output directory to write the output files to")
io_group.add_argument("--output-extension", "-e", type=str, metavar="extension", default="tex", help="the output extension to add to written files")
io_group.add_argument("--no-folder-creation", "-S", action="store_true", help="do not create the output folder structure matching the input structure")

file_group = parser.add_argument_group("file", description="Flags on how to handle files")
file_group.add_argument("--recursive", "-r", action="store_true", help="search the input directory recursively")
file_group.add_argument("--all", "-a", action="store_true", help="convert all region results within the limit, even if an output file already exists")
file_group.add_argument("--no-overwrite", "-nO", action="store_true", help="do not convert files, which already have an output file in the given format")

style_group = parser.add_argument_group("style", "Changing the looks of the diagram")
style_group.add_argument("--styles", "-s", type=str, metavar="file", default="./styles/default.json", help="path to the style file, which specifies styles for each region type")
style_group.add_argument("--title", "-t", type=str, metavar="name", default="", help="TikZ figure title")
style_group.add_argument("--no-title", "-nT", action="store_true", help="do not generate TikZ figure titles")
style_group.add_argument("--x-split", type=positive_int, metavar="amount", default=5, help="mark a tick on the x-axis every 1/<amount> units")
style_group.add_argument("--y-split", type=positive_int, metavar="amount", default=5, help="mark a tick on the y-axis every 1/<amount> units")
style_group.add_argument("--x-split-rounding", type=positive_int, metavar="decimals", default=1, help="round tick amount on the x-axis to <decimals> digits after the decimal point")
style_group.add_argument("--y-split-rounding", type=positive_int, metavar="decimals", default=1, help="round tick amount on the y-axis to <decimals> digits after the decimal point")
style_group.add_argument("--line-width", type=positive_float, metavar="width", default=0, help="line width of regions in mm")

misc_group = parser.add_argument_group("misc", "Miscellaneous arguments")
misc_group.add_argument("--line-limit", "-L", metavar="linecount", type=positive_int, default=100000, help="do not parse files from the input directory having more than <linecount> regions")
misc_group.add_argument("--hide-skipped", "-Hs", action="store_true", help="Hide which files are skipped")

args = parser.parse_args()

class UnexpectedFormatException(BaseException):
    pass

class UnknownStateException(BaseException):
    pass

def get_output_dir_for_input_subdir(curr_walk_dir):
    return path.join(args.output_dir, curr_walk_dir[len(args.input_dir):])

def get_output_file_for_input_file(input_file):
    path_of_file_relative_to_input_dir_starting_index = len(str(Path(args.input_dir))) if args.recursive and not args.file else len(args.input_dir)
    output_file_path_wrong_ext = f"{args.output_dir}{input_file[path_of_file_relative_to_input_dir_starting_index:]}"
    return f"{path.splitext(output_file_path_wrong_ext)[0]}.{args.output_extension.lower()}"

def create_spinner(msg : str, start : bool = True):
    spinner = Halo(text=msg, spinner="dots")
    if start:
        spinner.start()
    return spinner

def create_done_spinner(msg : str, spinner_method, cond : bool = True):
    if cond:
        spinner = create_spinner(msg, False)
        (getattr(spinner, spinner_method))()

def non_recursive_file_condition(input_dir : str, file_name : str):
    return path.isfile(path.join(input_dir, file_name)) and file_name[-len(input_file_mask):] == input_file_mask

paths_of_files_to_convert = None
output_file_paths = {}
output_to_std = False
input_file_mask = ".regionresult"

skipped_too_large_file = False

graph_styles = None
load_default_styles = not args.styles

if args.file:
    paths_of_files_to_convert = [args.file]
    output_file_paths[args.file] = args.output_file
    output_to_std = not args.output_file

if not load_default_styles:
    if not output_to_std:
        spinner = create_spinner("Loading styles")
    try:
        with open(args.styles, "r") as styles_file_handle:
            graph_styles = load(styles_file_handle)
        if not output_to_std:
            spinner.stop()
    except OSError:
        error_msg = f"{Fore.RED}Could not read style file {args.styles}{Style.RESET_ALL}{Style.DIM} - Continuing with default style"
        if output_to_std:
            print(error_msg)
        else:
            spinner.fail(error_msg)
        

if load_default_styles:
    # Default style
    graph_styles = {
        "ExistsSat": "", #"pattern=dots,pattern color=green,preaction={fill,green!30},"
        "AllSat": "pattern=crosshatch dots,pattern color=green,preaction={fill,green!30},",
        "ExistsViolated": "", #"pattern=north west lines,pattern color=red,preaction={fill,red!30},"
        "AllViolated": "pattern=crosshatch,pattern color=red,preaction={fill,red!30},",
        "Unknown": "",
    }
    graph_styles["CenterSat"] = graph_styles["ExistsSat"]
    graph_styles["CenterViolated"] = graph_styles["ExistsViolated"]

if args.input_dir and not args.file:
    paths_of_files_to_convert = \
        list(Path(args.input_dir).rglob("*.regionresult")) \
            if args.recursive \
            else \
        [path.join(args.input_dir, f) for f in listdir(args.input_dir) if non_recursive_file_condition(args.input_dir, f)]
    paths_of_files_to_convert = [str(p) for p in paths_of_files_to_convert]

    filtered_paths = []
    for path_of_file_to_convert in paths_of_files_to_convert:
        with open(path_of_file_to_convert, 'r') as file_handle:
            # Obtain the output file path
            output_file_path = get_output_file_for_input_file(path_of_file_to_convert)

            # Check if file is to be skipped
            if not args.all:
                # Check if a output file already exists
                if path.isfile(output_file_path):
                    if args.no_overwrite:
                        create_done_spinner(f"{Style.DIM}{output_file_path} skipped (Output exists){Style.RESET_ALL}", "info", not args.hide_skipped)
                        continue
                    if path.getmtime(path_of_file_to_convert) < path.getmtime(output_file_path):
                        create_done_spinner(f"{Style.DIM}{path_of_file_to_convert} skipped (File unchanged){Style.RESET_ALL}", "info", not args.hide_skipped)
                        continue
            
            # Check if file exceeds line limit
            num_lines = sum(1 for l in file_handle)
            if num_lines > args.line_limit:
                create_done_spinner(f"{Style.DIM}{path_of_file_to_convert} ({num_lines} lines) exceeds the maximum line number limit of {args.line_limit}.{Style.RESET_ALL}", "info")
                skipped_too_large_file = True
                continue
        
            # Add file to task list
            filtered_paths.append(path_of_file_to_convert)
            output_file_paths[path_of_file_to_convert] = output_file_path

    paths_of_files_to_convert = filtered_paths

if skipped_too_large_file:
    print(f"{Style.DIM}You can specify a different limit using --line-limit{Style.RESET_ALL}")

if not args.output_dir and not args.file:
    print(f"{Fore.RED}Converting multiple files requires the specification of an output directory{Style.RESET_ALL}")
    exit(50)

if not paths_of_files_to_convert:
    print(f"{Style.DIM}No files have been converted.{Style.RESET_ALL}")
    exit(50)

if args.input_dir and not args.no_folder_creation and not args.file:
    spinner = create_spinner("Creating output directories")
    try:
        if not path.isdir(args.output_dir):
            mkdir(args.output_dir)
    except OSError as ex:
        spinner.fail(f"{Fore.RED}The output folder does not exist and could not be created {Style.RESET_ALL}{Style.DIM}\n{(args.output_dir)}")
        exit(100)
    try:
        for dir_path, dir_names, file_names in walk(args.input_dir):
            current_rec_folder = get_output_dir_for_input_subdir(dir_path)
            if not path.isdir(current_rec_folder):
                mkdir(current_rec_folder)
        spinner.stop()
    except OSError as ex:
        spinner.fail(f"{Fore.RED}Could not mimick input folder structure:{Style.RESET_ALL}{Style.DIM}\n{ex}")
        exit(101)

# Structure of the file:
# AllViolated: 1/10000<=prob1<=5001/20000,1/10000<=perr<=5001/20000;

# Function to precisely convert strings to floats
def s2f(float_string : str):
    return float(Fraction(float_string))

def get_output_header_for_vars(x_min, x_max, y_min, y_max, x_tick_distance, y_tick_distance, x_axis, y_axis, title : str = ""):
    return f"""
\\begin{{tikzpicture}}
\\begin{{axis}}[
axis lines=middle,
axis equal,
every axis x label/.style=
    {{at={{(ticklabel cs: 0.5,0)}}, anchor=north}},
every axis y label/.style=
    {{at={{(ticklabel cs: 0.5,0)}}, anchor=east}},
xmin={x_min},xmax={x_max},ymin={y_min},ymax={y_max},
xtick distance={x_tick_distance:.2f},
ytick distance={y_tick_distance:.2f},
xlabel={x_axis},
ylabel={y_axis},
title={{{title}}}
]
"""

def get_output_footer():
    return f"""
\\end{{axis}}[
\\end{{tikzpicture}}
"""

def get_span(min : float, max : float):
    return max - min

def latex_safe_text(text : str):
    return text.replace("_", "\\_")

def generate_output_for_input_file(input_file_handle, input_file_name):
    lines = input_file_handle.readlines()

    x_min = None
    x_max = None
    y_min = None
    y_max = None

    rectangles_output_part = ""
    for line_no, line in enumerate(lines):
        title_search = search('([\\w]*): ([0-9/]*)<=([\\w]*)<=([0-9/]*),([0-9/]*)<=([\\w]*)<=([0-9/]*);', line)
        if title_search == None:
            if line == "":
                continue
            else:
                raise UnexpectedFormatException(f"File line {line_no} is not in expected format")

        state, x0, x_axis, x1, y0, y_axis, y1 = title_search.groups()
        x0 = s2f(x0)
        x1 = s2f(x1)
        y0 = s2f(y0)
        y1 = s2f(y1)

        if x_min is None or x0 < x_min:
            x_min = x0
        if x_max is None or x1 > x_max:
            x_max = x1
        if y_min is None or y0 < y_min:
            y_min = y0
        if y_max is None or y1 > y_max:
            y_max = y1

        try:
            rectangle_style = graph_styles[state]
        except KeyError:
            raise UnknownStateException(f"Unknown state: {state}")

        rectangle_style += f"line width = {args.line_width}mm"

        rectangles_output_part += f"\draw [{rectangle_style}] ({x0},{y0}) rectangle ({x1},{y1});\n"

    x_span = get_span(x_min, x_max)
    y_span = get_span(y_min, y_max)

    x_tick_distance = round(x_span / args.x_split, args.x_split_rounding)
    y_tick_distance = round(y_span / args.y_split, args.y_split_rounding)

    title = "" if args.no_title else latex_safe_text(Path(input_file_name).stem)

    return f"{get_output_header_for_vars(x_min, x_max, y_min, y_max, x_tick_distance, y_tick_distance, x_axis, y_axis, title)}{rectangles_output_part}{get_output_footer()}"

for path_of_file_to_convert in paths_of_files_to_convert:
    if not output_to_std:
        spinner.stop()
        spinner = create_spinner(f"{path_of_file_to_convert}...")
    try:
        with open(path_of_file_to_convert, "r") as file_handle:
            conv_start_time = perf_counter()

            output = generate_output_for_input_file(file_handle, path_of_file_to_convert)

            if output_to_std:
                print(output)
            else:
                output_file_path = output_file_paths[path_of_file_to_convert]
                try:
                    with open(output_file_path, "w") as wf:
                        wf.write(output)
                    conv_end_time = perf_counter()

                    humanized_duration = precisedelta(timedelta(seconds=(conv_end_time - conv_start_time)))

                    spinner.succeed(f"{path_of_file_to_convert} ({humanized_duration})")
                except OSError as ex:
                    spinner.fail(f"{Fore.RED}Could not write output file {output_file_path}:{Style.RESET_ALL}{Style.DIM}\n{ex}")

    except OSError as ex:
        spinner.fail(f"{Fore.RED}Could not read input file {path_of_file_to_convert}:{Style.RESET_ALL}{Style.DIM}\n{ex}")