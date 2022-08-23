# region-diagram-generator (pl.py)
A script to convert storm-pars region results to TikZ region diagrams
<div style="overflow: hidden; margin: 2em 10%;">
  <img width=400 height=328 alt="reward_result_diagram" src="https://user-images.githubusercontent.com/23585349/186162429-a066dcfe-044a-40f4-bd59-cf4b69a66f07.png" style="min-width: 200px, max-width: 400px; max-height: 328px; float: left">
  <img width=400 height=328 alt="reward_result_diagram" style="min-width: 200px, max-width: 400px; max-height: 328px; float: left" src="https://user-images.githubusercontent.com/23585349/186168893-6dcb2248-6a3b-47f6-9d3b-77108b0670c1.png">
</div>

## General information
The script expects the output of [`storm-pars`](https://www.stormchecker.org) using the `--resultfile`​ argument.

## Usage
- Running only `pl.py` without passign arguments, will scan the input directory for files with a `.regionresult` extension and output these files in the output directory
- You can recursively search the input directory for said files and mimmick the folder structure within the output directory automatically by supplying `-r`
- Specifying a `--file` will only convert this file. You can specify where to write the results using `--output-file`. If nothing is supplied, the result is written to `STDOUT` instead. This means
  - `./pl.py --file ./input/example.tex --output-file ./output/example.tex`, and
  - `./pl.py --file ./input/example.tex > ./output/example.tex`
   
  behave identically, except that no help information is printed to `STDOUT` in the latter case.
- Many more settings are available. See the `--help` page for more information.

## Disclaimer
This script is an extension of [Linus](https://github.com/glatteis)' [`pl.py`](https://gist.github.com/glatteis/5625f597601cbf38ef8a2664101a56af) implementation
